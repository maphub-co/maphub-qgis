import os

from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QTreeWidget, 
                            QTreeWidgetItem, QMenu, QAction, QMessageBox)
from PyQt5.QtGui import QIcon

from qgis.core import QgsProject, QgsVectorTileLayer, QgsRasterLayer
from qgis.utils import iface

from ...utils.utils import get_maphub_client, handled_exceptions
from ...utils.map_operations import download_map, add_map_as_tiling_service, add_folder_maps_as_tiling_services, download_folder_maps
from ...utils.sync_manager import MapHubSyncManager


class WorkspacesLoader(QThread):
    """Thread for loading all workspaces."""
    workspaces_loaded = pyqtSignal(list)  # workspaces
    error_occurred = pyqtSignal(str)  # error message

    def run(self):
        try:
            client = get_maphub_client()
            workspaces = client.workspace.get_workspaces()
            self.workspaces_loaded.emit(workspaces)
        except Exception as e:
            self.error_occurred.emit(str(e))


class WorkspaceContentLoader(QThread):
    """Thread for loading workspace contents."""
    content_loaded = pyqtSignal(object, str, object)  # parent_item, workspace_id, folder_data
    error_occurred = pyqtSignal(str)  # error message

    def __init__(self, parent_item, workspace_id):
        super().__init__()
        self.parent_item = parent_item
        self.workspace_id = workspace_id

    def run(self):
        try:
            client = get_maphub_client()
            root_folder = client.folder.get_root_folder(self.workspace_id)
            folder_id = root_folder["folder"]["id"]
            self.content_loaded.emit(self.parent_item, folder_id, None)
        except Exception as e:
            self.error_occurred.emit(str(e))


class FolderContentLoader(QThread):
    """Thread for loading folder contents."""
    content_loaded = pyqtSignal(object, object)  # parent_item, folder_details
    error_occurred = pyqtSignal(str)  # error message

    def __init__(self, parent_item, folder_id):
        super().__init__()
        self.parent_item = parent_item
        self.folder_id = folder_id

    def run(self):
        try:
            client = get_maphub_client()
            folder_details = client.folder.get_folder(self.folder_id)
            self.content_loaded.emit(self.parent_item, folder_details)
        except Exception as e:
            self.error_occurred.emit(str(e))


class MapBrowserDockWidget(QDockWidget):
    """
    A dock widget that displays workspaces, folders, and maps in a tree structure.

    This widget provides a UI for browsing MapHub content, including:
    - Workspaces as top-level items
    - Folders and maps as child items
    - Folder contents loaded on demand when expanded
    """

    def __init__(self, iface, parent=None):
        """Initialize the dock widget."""
        super(MapBrowserDockWidget, self).__init__("MapHub Browser", parent)
        self.iface = iface
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Create main widget and layout
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_dir = os.path.join(os.path.dirname(__file__), '../../icons')

        # Create tree widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.tree_widget.itemExpanded.connect(self.on_item_expanded)

        # Add tree widget to layout
        self.main_layout.addWidget(self.tree_widget)

        # Set the main widget as the dock widget's content
        self.setWidget(self.main_widget)

        # Keep track of content loader threads
        self.content_loaders = []

        # Initialize custom context menu actions
        self.custom_context_menu_actions = {
            'workspace': [],
            'folder': [],
            'map': []
        }
        
        # Initialize sync manager
        self.sync_manager = MapHubSyncManager(iface)

        # Load workspaces
        self.load_workspaces()

    def closeEvent(self, event):
        """Handle close event, clean up resources."""
        # Cancel any running threads
        for loader in self.content_loaders:
            if loader.isRunning():
                loader.terminate()
                loader.wait()
        self.content_loaders = []

        super(MapBrowserDockWidget, self).closeEvent(event)

    def load_workspaces(self):
        """Load workspaces as top-level items."""
        self.tree_widget.clear()

        # Create a loading indicator as the only item
        loading_item = QTreeWidgetItem(self.tree_widget)
        loading_item.setText(0, "Loading workspaces... Please wait")

        # Load workspaces in a background thread
        loader = WorkspacesLoader()
        loader.workspaces_loaded.connect(self.on_workspaces_loaded)
        loader.error_occurred.connect(self.on_content_error)
        self.content_loaders.append(loader)
        loader.start()

    def on_workspaces_loaded(self, workspaces):
        """Handle workspaces loaded signal."""
        # Remove the loader thread from the list
        for loader in self.content_loaders[:]:
            if not loader.isRunning():
                self.content_loaders.remove(loader)

        # Clear the tree and add workspaces
        self.tree_widget.clear()

        # Add workspaces to tree
        for workspace in workspaces:
            workspace_id = workspace.get('id')
            workspace_name = workspace.get('name', 'Unknown Workspace')

            # Create workspace item
            workspace_item = QTreeWidgetItem(self.tree_widget)
            workspace_item.setText(0, workspace_name)
            workspace_item.setData(0, Qt.UserRole, {'type': 'workspace', 'id': workspace_id})

            # Use custom workspace icon
            workspace_item.setIcon(0, QIcon(os.path.join(self.icon_dir, 'workspace.svg')))

            # Add a placeholder child to show the expand arrow
            placeholder = QTreeWidgetItem(workspace_item)
            placeholder.setText(0, "Loading...")
            placeholder.setData(0, Qt.UserRole, {'type': 'placeholder'})

    def on_item_expanded(self, item):
        """Handle item expansion to load children on demand."""
        # Get item data
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        item_type = item_data.get('type')
        item_id = item_data.get('id')

        # Check if this is a placeholder item's parent
        if item.childCount() == 1 and item.child(0).data(0, Qt.UserRole).get('type') == 'placeholder':
            # Update placeholder text to indicate loading
            placeholder = item.child(0)
            placeholder.setText(0, "Loading... Please wait")

            # Load children based on item type in a background thread
            if item_type == 'workspace':
                loader = WorkspaceContentLoader(item, item_id)
                loader.content_loaded.connect(self.on_workspace_content_loaded)
                loader.error_occurred.connect(self.on_content_error)
                self.content_loaders.append(loader)
                loader.start()
            elif item_type == 'folder':
                loader = FolderContentLoader(item, item_id)
                loader.content_loaded.connect(self.on_folder_content_loaded)
                loader.error_occurred.connect(self.on_content_error)
                self.content_loaders.append(loader)
                loader.start()

    def on_workspace_content_loaded(self, parent_item, folder_id, folder_data):
        """Handle workspace content loaded signal."""
        # Remove the loader thread from the list
        for loader in self.content_loaders[:]:
            if not loader.isRunning():
                self.content_loaders.remove(loader)

        # Remove the placeholder item
        if parent_item.childCount() > 0:
            parent_item.removeChild(parent_item.child(0))

        # Load the folder contents
        loader = FolderContentLoader(parent_item, folder_id)
        loader.content_loaded.connect(self.on_folder_content_loaded)
        loader.error_occurred.connect(self.on_content_error)
        self.content_loaders.append(loader)
        loader.start()

    def find_connected_layer(self, map_id):
        """
        Find a layer connected to a MapHub map.
        
        Args:
            map_id: The MapHub map ID
            
        Returns:
            The connected layer if found, None otherwise
        """
        return self.sync_manager.find_layer_by_map_id(map_id)
        
    def on_folder_content_loaded(self, parent_item, folder_details):
        """Handle folder content loaded signal."""
        # Remove the loader thread from the list
        for loader in self.content_loaders[:]:
            if not loader.isRunning():
                self.content_loaders.remove(loader)

        # Remove the placeholder item
        if parent_item.childCount() > 0 and parent_item.child(0).data(0, Qt.UserRole).get('type') == 'placeholder':
            parent_item.removeChild(parent_item.child(0))

        # Add child folders
        child_folders = folder_details.get("child_folders", [])
        for folder in child_folders:
            folder_item = QTreeWidgetItem(parent_item)
            folder_item.setText(0, folder.get('name', 'Unnamed Folder'))
            folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'id': folder.get('id'), 'data': folder})
            folder_item.setIcon(0, QIcon(os.path.join(self.icon_dir, 'folder.svg')))

            # Add placeholder for expandable folders
            placeholder = QTreeWidgetItem(folder_item)
            placeholder.setText(0, "Loading...")
            placeholder.setData(0, Qt.UserRole, {'type': 'placeholder'})

        # Add maps
        maps = folder_details.get("map_infos", [])
        for map_data in maps:
            map_item = QTreeWidgetItem(parent_item)
            map_item.setText(0, map_data.get('name', 'Unnamed Map'))
            map_item.setData(0, Qt.UserRole, {'type': 'map', 'id': map_data.get('id'), 'data': map_data})

            # Check if this map is connected to a local layer
            connected_layer = self.find_connected_layer(map_data.get('id'))
            
            # Use different custom icons based on map type
            if map_data.get('type') == 'vector':
                map_item.setIcon(0, QIcon(os.path.join(self.icon_dir, 'vector_map.svg')))
            else:
                map_item.setIcon(0, QIcon(os.path.join(self.icon_dir, 'raster_map.svg')))
                
            # Store connection information
            if connected_layer:
                map_item.setData(1, Qt.UserRole, connected_layer)
                # Add visual indicator that this map is connected (e.g., bold text)
                font = map_item.font(0)
                font.setBold(True)
                map_item.setFont(0, font)
                
                # Check synchronization status and add status indicator
                status = self.sync_manager.get_layer_sync_status(connected_layer)
                self._add_status_indicator(map_item, status)

    def on_content_error(self, error_message):
        """Handle content loading error."""
        # Remove the loader thread from the list
        for loader in self.content_loaders[:]:
            if not loader.isRunning():
                self.content_loaders.remove(loader)

        # Show error message
        QMessageBox.critical(self, "Error Loading Content", f"An error occurred while loading content: {error_message}")

    def show_context_menu(self, position):
        """Show context menu for the selected item."""
        # Get the item at the position
        item = self.tree_widget.itemAt(position)
        if not item:
            return

        # Get item data
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        item_type = item_data.get('type')
        item_id = item_data.get('id')
        map_data = item_data.get('data')

        # Create context menu
        context_menu = QMenu()

        if item_type == 'workspace':
            # Workspace context menu actions
            # No default actions for workspaces
            pass

        elif item_type == 'folder':
            # Folder context menu actions
            action_download_all = QAction("Download All Maps", self)
            action_download_all.triggered.connect(lambda: self.on_download_all_clicked(item_id))
            context_menu.addAction(action_download_all)

            action_tiling_all = QAction("Add All as Tiling Services", self)
            action_tiling_all.triggered.connect(lambda: self.on_tiling_all_clicked(item_id))
            context_menu.addAction(action_tiling_all)

        elif item_type == 'map':
            # Map context menu actions
            # Check if this map is connected to a local layer
            connected_layer = self.find_connected_layer(item_id)
            
            if connected_layer:
                # Connected map options
                action_sync = QAction("Synchronize", self)
                action_sync.triggered.connect(lambda: self.on_sync_clicked(map_data, connected_layer))
                context_menu.addAction(action_sync)
                
                action_disconnect = QAction("Disconnect from Layer", self)
                action_disconnect.triggered.connect(lambda: self.on_disconnect_clicked(map_data, connected_layer))
                context_menu.addAction(action_disconnect)
            else:
                # Standard options for non-connected maps
                action_download = QAction("Download", self)
                action_download.triggered.connect(lambda: self.on_download_clicked(map_data))
                context_menu.addAction(action_download)
                
                action_tiling = QAction("Add as Tiling Service", self)
                action_tiling.triggered.connect(lambda: self.on_tiling_clicked(map_data))
                context_menu.addAction(action_tiling)

        # Add custom context menu actions if available
        if item_type in self.custom_context_menu_actions and self.custom_context_menu_actions[item_type]:
            # Add separator if there are already actions
            if not context_menu.isEmpty():
                context_menu.addSeparator()

            # Add custom actions
            for action_config in self.custom_context_menu_actions[item_type]:
                action = QAction(action_config['name'], self)
                # Use a lambda with default argument to capture the current value
                action.triggered.connect(lambda checked=False, ac=action_config, id=item_id: ac['callback'](id))
                context_menu.addAction(action)

        # Show the context menu
        if not context_menu.isEmpty():
            context_menu.exec_(self.tree_widget.viewport().mapToGlobal(position))

    @handled_exceptions
    def on_download_clicked(self, map_data):
        """Handle click on the download button."""
        download_map(map_data, self)

    @handled_exceptions
    def on_tiling_clicked(self, map_data):
        """Handle click on the tiling button."""
        add_map_as_tiling_service(map_data, self)

    @handled_exceptions
    def on_download_all_clicked(self, folder_id):
        """Handle click on the download all button."""
        download_folder_maps(folder_id, self)

    @handled_exceptions
    def on_tiling_all_clicked(self, folder_id):
        """Handle click on the tiling all button."""
        add_folder_maps_as_tiling_services(folder_id, self)
        
    @handled_exceptions
    def on_sync_clicked(self, map_data, layer):
        """
        Handle click on the synchronize button.
        
        Args:
            map_data: The map data
            layer: The connected layer
        """
        # Get synchronization status
        status = self.sync_manager.get_layer_sync_status(layer)
        
        if status == "in_sync":
            QMessageBox.information(
                self,
                "Synchronization",
                f"Layer '{layer.name()}' is already in sync with MapHub."
            )
            return
            
        # Synchronize the layer
        self.sync_manager.synchronize_layer(layer)
        
        # Refresh the tree item to update visual indicators
        self.refresh_map_item(map_data['id'])
        
    @handled_exceptions
    def on_disconnect_clicked(self, map_data, layer):
        """
        Handle click on the disconnect button.
        
        Args:
            map_data: The map data
            layer: The connected layer
        """
        # Confirm disconnection
        response = QMessageBox.question(
            self,
            "Disconnect Layer",
            f"Are you sure you want to disconnect layer '{layer.name()}' from MapHub?\n\n"
            "This will not delete the layer or the file, but will remove the connection information.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if response == QMessageBox.Yes:
            # Disconnect the layer
            self.sync_manager.disconnect_layer(layer)
            
            # Refresh the tree item to update visual indicators
            self.refresh_map_item(map_data['id'])
            
    def refresh_map_item(self, map_id):
        """
        Refresh a map item in the tree.
        
        Args:
            map_id: The MapHub map ID
        """
        # Find the map item in the tree
        root = self.tree_widget.invisibleRootItem()
        map_item = self._find_map_item(root, map_id)
        
        if map_item:
            # Get the map data
            item_data = map_item.data(0, Qt.UserRole)
            map_data = item_data.get('data')
            
            # Check if this map is connected to a local layer
            connected_layer = self.find_connected_layer(map_id)
            
            # Update the visual indicator
            if connected_layer:
                map_item.setData(1, Qt.UserRole, connected_layer)
                # Add visual indicator that this map is connected (e.g., bold text)
                font = map_item.font(0)
                font.setBold(True)
                map_item.setFont(0, font)
                
                # Check synchronization status and add status indicator
                status = self.sync_manager.get_layer_sync_status(connected_layer)
                self._add_status_indicator(map_item, status)
            else:
                map_item.setData(1, Qt.UserRole, None)
                # Remove visual indicator
                font = map_item.font(0)
                font.setBold(False)
                map_item.setFont(0, font)
                
                # Remove any status indicators
                for i in range(map_item.childCount() - 1, -1, -1):
                    child = map_item.child(i)
                    if child.data(0, Qt.UserRole) and child.data(0, Qt.UserRole).get('type') == 'status_indicator':
                        map_item.removeChild(child)
                
    def _add_status_indicator(self, map_item, status):
        """
        Add a status indicator to a map item.
        
        Args:
            map_item: The map item
            status: The synchronization status
        """
        # Get status icon based on status
        icon_path = None
        tooltip = None
        
        if status == "local_modified":
            icon_path = os.path.join(self.icon_dir, 'upload.svg')
            tooltip = "Local changes need to be uploaded to MapHub"
        elif status == "remote_newer":
            icon_path = os.path.join(self.icon_dir, 'download.svg')
            tooltip = "Remote changes need to be downloaded from MapHub"
        elif status == "style_changed":
            icon_path = os.path.join(self.icon_dir, 'style.svg')
            tooltip = "Style changes detected"
        elif status == "file_missing":
            icon_path = os.path.join(self.icon_dir, 'error.svg')
            tooltip = "Local file is missing"
        elif status == "remote_error":
            icon_path = os.path.join(self.icon_dir, 'warning.svg')
            tooltip = "Error checking remote status"
        elif status == "in_sync":
            tooltip = "Layer is in sync with MapHub"
        
        # Create a child item for the status indicator if needed
        if icon_path and os.path.exists(icon_path):
            # Check if status indicator already exists
            for i in range(map_item.childCount()):
                child = map_item.child(i)
                if child.data(0, Qt.UserRole) and child.data(0, Qt.UserRole).get('type') == 'status_indicator':
                    # Update existing indicator
                    child.setIcon(0, QIcon(icon_path))
                    child.setToolTip(0, tooltip)
                    return
            
            # Create new status indicator
            status_item = QTreeWidgetItem(map_item)
            status_item.setIcon(0, QIcon(icon_path))
            status_item.setText(0, "")  # No text, just icon
            status_item.setToolTip(0, tooltip)
            status_item.setData(0, Qt.UserRole, {'type': 'status_indicator', 'status': status})
            
            # Make the status indicator not selectable
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsSelectable)
        elif tooltip:
            # Just set tooltip on the map item if no icon
            map_item.setToolTip(0, tooltip)
    
    def _find_map_item(self, parent_item, map_id):
        """
        Find a map item in the tree by its ID.
        
        Args:
            parent_item: The parent item to search in
            map_id: The MapHub map ID
            
        Returns:
            The map item if found, None otherwise
        """
        # Check all children of the parent item
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            item_data = child.data(0, Qt.UserRole)
            
            if item_data and item_data.get('type') == 'map' and item_data.get('id') == map_id:
                return child
                
            # Recursively search in child folders
            if child.childCount() > 0:
                result = self._find_map_item(child, map_id)
                if result:
                    return result
                    
        return None

    def register_context_menu_action(self, item_type, name, callback):
        """
        Register a custom context menu action for a specific item type.

        Args:
            item_type (str): The type of item ('workspace', 'folder', or 'map')
            name (str): The name of the action to display in the context menu
            callback (callable): The function to call when the action is triggered
        """
        if item_type not in self.custom_context_menu_actions:
            self.custom_context_menu_actions[item_type] = []

        self.custom_context_menu_actions[item_type].append({
            'name': name,
            'callback': callback
        })
