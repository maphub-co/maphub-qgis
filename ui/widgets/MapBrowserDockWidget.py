import os
import logging

from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer, QMimeData, QByteArray, QDataStream, QIODevice
from PyQt5.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                            QTreeWidgetItem, QMenu, QAction, QMessageBox, QPushButton, QToolButton)
from PyQt5.QtGui import QIcon, QDrag

from ...utils.utils import get_maphub_client
from ...utils.map_operations import download_map, add_map_as_tiling_service, add_folder_maps_as_tiling_services, download_folder_maps
from ...utils.sync_manager import MapHubSyncManager
from .MapItemDelegate import MapItemDelegate, STATUS_INDICATOR_ROLE
from ...utils.error_manager import handled_exceptions


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


class MapBrowserTreeWidget(QTreeWidget):
    """Custom QTreeWidget with drag and drop support for maps and folders."""
    
    # Custom MIME type for our data
    MIME_TYPE = "application/x-maphub-item"
    
    def __init__(self, parent=None, icon_dir=None):
        super(MapBrowserTreeWidget, self).__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeWidget.DragOnly)
        self.icon_dir = icon_dir
    
    def startDrag(self, supportedActions):
        """Override startDrag to customize drag behavior."""
        # Get the selected items
        items = self.selectedItems()
        if not items:
            return
            
        # Get the first selected item's data
        item = items[0]
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return
            
        # Create mime data
        mime_data = QMimeData()
        
        # Encode the item data
        encoded_data = QByteArray()
        stream = QDataStream(encoded_data, QIODevice.WriteOnly)
        
        # Write the item type and ID
        stream.writeQString(item_data.get('type', ''))
        stream.writeQString(item_data.get('id', ''))
        
        # If it's a map, also write the map data
        if item_data.get('type') == 'map' and 'data' in item_data:
            map_data = item_data['data']
            stream.writeQString(str(map_data.get('id', '')))
            stream.writeQString(map_data.get('name', ''))
            stream.writeQString(map_data.get('type', ''))
            if 'folder_id' in map_data:
                stream.writeQString(str(map_data.get('folder_id', '')))
            else:
                stream.writeQString('')
        
        # Set the mime data
        mime_data.setData(self.MIME_TYPE, encoded_data)
        
        # Create and execute the drag
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        # Set a custom icon for the drag (optional)
        if item_data.get('type') == 'map' and self.icon_dir:
            map_type = item_data.get('data', {}).get('type', '')
            icon_name = 'vector_map.svg' if map_type == 'vector' else 'raster_map.svg'
            drag.setPixmap(QIcon(os.path.join(self.icon_dir, icon_name)).pixmap(32, 32))
        elif item_data.get('type') == 'folder' and self.icon_dir:
            drag.setPixmap(QIcon(os.path.join(self.icon_dir, 'folder.svg')).pixmap(32, 32))
        
        # Execute the drag
        drag.exec_(supportedActions)


class MapBrowserDockWidget(QDockWidget):
    """
    A dock widget that displays workspaces, folders, and maps in a tree structure.

    This widget provides a UI for browsing MapHub content, including:
    - Workspaces as top-level items
    - Folders and maps as child items
    - Folder contents loaded on demand when expanded
    """

    def __init__(self, iface, parent=None, refresh_callback=None):
        """Initialize the dock widget."""
        super(MapBrowserDockWidget, self).__init__("MapHub Browser", parent)
        self.iface = iface
        self.refresh_callback = refresh_callback
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Set up logging
        self.logger = logging.getLogger('MapHubPlugin.BrowserDock')
        self.logger.setLevel(logging.DEBUG)
        
        # Track items that are currently being expanded to prevent multiple expansion attempts
        self.expanding_items = set()
        
        # Flag to track if a refresh is already in progress
        self.refresh_in_progress = False

        # Create main widget and layout
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_dir = os.path.join(os.path.dirname(__file__), '../../icons')

        # Create top bar with refresh button
        self.top_bar = QWidget()
        self.top_layout = QHBoxLayout(self.top_bar)
        self.top_layout.setContentsMargins(5, 5, 5, 5)
        
        # Add spacer to push the refresh button to the right
        self.top_layout.addStretch()
        
        # Create refresh button
        self.refresh_button = QToolButton()
        self.refresh_button.setIcon(QIcon(os.path.join(self.icon_dir, 'refresh.svg')))
        self.refresh_button.setToolTip("Refresh browser and sync status")
        self.refresh_button.clicked.connect(self.on_refresh_clicked)
        self.top_layout.addWidget(self.refresh_button)
        
        # Add top bar to main layout
        self.main_layout.addWidget(self.top_bar)

        # Create custom tree widget with drag and drop support
        self.tree_widget = MapBrowserTreeWidget(self, self.icon_dir)
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.tree_widget.itemExpanded.connect(self.on_item_expanded)
        
        # Set custom delegate for rendering status indicators
        self.item_delegate = MapItemDelegate(self.tree_widget)
        self.tree_widget.setItemDelegate(self.item_delegate)

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
                loader.error_occurred.connect(self.on_folder_content_error)
                self.content_loaders.append(loader)
                loader.start()

    def on_workspace_content_loaded(self, parent_item, folder_id, folder_data):
        """Handle workspace content loaded signal."""
        # Remove the loader thread from the list
        for loader in self.content_loaders[:]:
            if not loader.isRunning():
                self.content_loaders.remove(loader)

        # Get workspace info for logging
        workspace_data = parent_item.data(0, Qt.UserRole)
        workspace_id = workspace_data.get('id') if workspace_data else 'unknown'
        workspace_name = parent_item.text(0)
        
        self.logger.debug(f"Workspace content loaded for '{workspace_name}' (ID: {workspace_id})")

        # Remove the placeholder item
        if parent_item.childCount() > 0:
            parent_item.removeChild(parent_item.child(0))

        # Get the stored expanded states if available
        expanded_child_folders = parent_item.data(0, Qt.UserRole + 1) or {}
        self.logger.debug(f"  - Retrieved {len(expanded_child_folders)} expanded child folder states")
        
        # Store the expanded state of the parent item itself for later restoration
        was_expanded = parent_item.isExpanded()
        self.logger.debug(f"  - Current expanded state: {was_expanded}")
        
        # Store this information in the parent item using a special role
        parent_item.setData(0, Qt.UserRole + 3, was_expanded)
        
        # Store expanded states in the parent item for later use
        parent_item.setData(0, Qt.UserRole + 2, expanded_child_folders)
        
        self.logger.debug(f"  - Starting content loader for root folder (ID: {folder_id})")
        loader = FolderContentLoader(parent_item, folder_id)
        loader.content_loaded.connect(self.on_folder_content_loaded)
        loader.error_occurred.connect(self.on_folder_content_error)
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

        # Remove the placeholder item if it exists
        if parent_item.childCount() > 0 and parent_item.child(0).data(0, Qt.UserRole) and parent_item.child(0).data(0, Qt.UserRole).get('type') == 'placeholder':
            parent_item.removeChild(parent_item.child(0))
            
        # Get lists of existing folder and map IDs to track what's been removed
        existing_folder_ids = []
        existing_map_ids = []
        
        # Track expanded state of existing folders
        expanded_folder_ids = {}
        
        # Get previously stored expanded states from parent (for workspace root folders)
        previously_expanded = parent_item.data(0, Qt.UserRole + 2) or {}
        
        # Create sets of new folder and map IDs from the server response
        new_folder_ids = {folder.get('id') for folder in folder_details.get("child_folders", [])}
        new_map_ids = {map_data.get('id') for map_data in folder_details.get("map_infos", [])}
        
        # Get item data for logging
        item_data = parent_item.data(0, Qt.UserRole)
        item_type = item_data.get('type') if item_data else 'unknown'
        item_id = item_data.get('id') if item_data else 'unknown'
        item_text = parent_item.text(0)
        
        self.logger.debug(f"Folder content loaded for {item_type} '{item_text}' (ID: {item_id})")
        
        # First pass: identify existing items and remove those that no longer exist on the server
        i = 0
        while i < parent_item.childCount():
            child = parent_item.child(i)
            item_data = child.data(0, Qt.UserRole)
            
            if not item_data:
                i += 1
                continue
                
            item_type = item_data.get('type')
            item_id = item_data.get('id')
            
            if item_type == 'folder':
                if item_id in new_folder_ids:
                    # Folder still exists, keep it
                    existing_folder_ids.append(item_id)
                    # Store expanded state
                    expanded_folder_ids[item_id] = child.isExpanded()
                    i += 1
                else:
                    # Folder no longer exists, remove it
                    parent_item.removeChild(child)
                    # Don't increment i since we removed an item
            elif item_type == 'map':
                if item_id in new_map_ids:
                    # Map still exists, keep it
                    existing_map_ids.append(item_id)
                    i += 1
                else:
                    # Map no longer exists, remove it
                    parent_item.removeChild(child)
                    # Don't increment i since we removed an item
            else:
                # Unknown item type, keep it
                i += 1
        
        # Store folders that need to be expanded after loading
        folders_to_expand = []
        
        # Add new folders that don't already exist
        child_folders = folder_details.get("child_folders", [])
        for folder in child_folders:
            folder_id = folder.get('id')
            folder_name = folder.get('name', 'Unnamed Folder')
            
            if folder_id not in existing_folder_ids:
                folder_item = QTreeWidgetItem(parent_item)
                folder_item.setText(0, folder_name)
                folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'id': folder_id, 'data': folder})
                folder_item.setIcon(0, QIcon(os.path.join(self.icon_dir, 'folder.svg')))

                # Add placeholder for expandable folders
                placeholder = QTreeWidgetItem(folder_item)
                placeholder.setText(0, "Loading...")
                placeholder.setData(0, Qt.UserRole, {'type': 'placeholder'})
                
                # Check if this folder was previously expanded
                was_expanded = False
                child_expanded_states = {}
                
                # Check in the previously expanded dictionary
                if folder_id in previously_expanded:
                    folder_info = previously_expanded[folder_id]
                    if isinstance(folder_info, dict):
                        was_expanded = folder_info.get('expanded', False)
                        child_expanded_states = folder_info.get('children', {})
                    else:
                        # For backward compatibility with older format
                        was_expanded = bool(folder_info)
                
                # Also check in the expanded_folder_ids from current session
                if not was_expanded and folder_id in expanded_folder_ids:
                    was_expanded = expanded_folder_ids[folder_id]
                
                # If the folder was expanded, add it to the list of folders to expand
                if was_expanded:
                    self.logger.debug(f"  - Folder '{folder_name}' was previously expanded, will restore state")
                    # Store the expanded state and child states for later use
                    folder_item.setData(0, Qt.UserRole + 2, child_expanded_states)
                    folder_item.setData(0, Qt.UserRole + 3, True)
                    # Add to list of folders to expand with a delay
                    folders_to_expand.append((folder_item, folder_name))

        # Add new maps that don't already exist
        maps = folder_details.get("map_infos", [])
        for map_data in maps:
            map_id = map_data.get('id')
            if map_id not in existing_map_ids:
                map_item = QTreeWidgetItem(parent_item)
                map_item.setText(0, map_data.get('name', 'Unnamed Map'))
                map_item.setData(0, Qt.UserRole, {'type': 'map', 'id': map_id, 'data': map_data})

                # Check if this map is connected to a local layer
                connected_layer = self.find_connected_layer(map_id)
                
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
        
        # After all content is loaded, restore the expanded state of the parent item
        # This is crucial for fixing the timing issue with asynchronous loading
        was_expanded = parent_item.data(0, Qt.UserRole + 3)
        
        self.logger.debug(f"  - Was expanded: {was_expanded}")
        self.logger.debug(f"  - Child count: {parent_item.childCount()}")
        self.logger.debug(f"  - Folders to expand: {len(folders_to_expand)}")
        
        # First expand the parent item
        if was_expanded:
            self.logger.debug(f"  - Scheduling delayed expansion for {item_type} '{item_text}'")
            # Use QTimer to delay expansion until after Qt has processed all pending events
            # This ensures the tree widget has time to properly render the items before expanding
            # Increased delay to 250ms to give Qt more time to process events
            QTimer.singleShot(250, lambda p=parent_item, t=item_text: self._delayed_expand(p, t))
            
            # Then expand child folders with additional delay to ensure proper nesting
            delay = 350  # Additional 100ms after parent expansion
            for folder_item, folder_name in folders_to_expand:
                self.logger.debug(f"  - Scheduling delayed expansion for child folder '{folder_name}'")
                QTimer.singleShot(delay, lambda p=folder_item, t=folder_name: self._delayed_expand(p, t))
                delay += 50  # Stagger child expansions to avoid conflicts

    def on_content_error(self, error_message):
        """Handle content loading error."""
        # Remove the loader thread from the list
        for loader in self.content_loaders[:]:
            if not loader.isRunning():
                self.content_loaders.remove(loader)

        # Show error message
        QMessageBox.critical(self, "Error Loading Content", f"An error occurred while loading content: {error_message}")
        
    def on_folder_content_error(self, error_message):
        """
        Handle folder content loading error.
        
        If a folder no longer exists, remove it from the tree.
        For other errors, show an error message.
        """
        # Remove the loader thread from the list
        sender = self.sender()
        if sender in self.content_loaders:
            self.content_loaders.remove(sender)
            
        # Check if this is a "not found" error (folder no longer exists)
        if "404" in error_message or "not found" in error_message.lower():
            # Get the parent item from the sender (FolderContentLoader)
            parent_item = sender.parent_item
            if parent_item:
                # Get the parent of the parent_item (the container that holds this folder)
                container = parent_item.parent()
                if container:
                    # Remove the folder item from its container
                    container.removeChild(parent_item)
        else:
            # For other errors, show the error message
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
            
            # Add separator
            context_menu.addSeparator()

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
            
        # Check if this is a style-only operation
        style_only = status in ["style_changed_local", "style_changed_remote", "style_changed_both"]
        
        # Synchronize the layer
        self.sync_manager.synchronize_layer(layer, "auto", style_only=style_only)
        
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
                
                # Remove any status indicator data
                map_item.setData(0, STATUS_INDICATOR_ROLE, None)
                
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
        elif status == "style_changed_local":
            icon_path = os.path.join(self.icon_dir, 'style.svg')
            tooltip = "Local style changes need to be uploaded to MapHub"
        elif status == "style_changed_remote":
            icon_path = os.path.join(self.icon_dir, 'style.svg')
            tooltip = "Remote style changes need to be downloaded from MapHub"
        elif status == "style_changed_both":
            icon_path = os.path.join(self.icon_dir, 'style.svg')
            tooltip = "Style conflict - both local and remote styles have changed"
        elif status == "file_missing":
            icon_path = os.path.join(self.icon_dir, 'error.svg')
            tooltip = "Local file is missing"
        elif status == "remote_error":
            icon_path = os.path.join(self.icon_dir, 'warning.svg')
            tooltip = "Error checking remote status"
        elif status == "in_sync":
            tooltip = "Layer is in sync with MapHub"
        
        # Set the status indicator data on the item
        if icon_path and os.path.exists(icon_path):
            # Store the status data in the item using the custom role
            status_data = {
                'icon_path': icon_path,
                'tooltip': tooltip,
                'status': status
            }
            map_item.setData(0, STATUS_INDICATOR_ROLE, status_data)
            
            # Set tooltip on the item
            if tooltip:
                map_item.setToolTip(0, tooltip)
                
            # Force a repaint of the item
            self.tree_widget.update()
        elif tooltip:
            # Just set tooltip on the map item if no icon
            map_item.setToolTip(0, tooltip)
            
            # Clear any existing status indicator data
            map_item.setData(0, STATUS_INDICATOR_ROLE, None)
    
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
        
    def refresh_browser(self):
        """
        Refresh the browser dock, including:
        - Update status indicators for connected maps
        - Reload contents of expanded folders to check for changes
        - Refresh workspaces and their root folders
        """
        # Check if a refresh is already in progress
        if self.refresh_in_progress:
            self.logger.debug("Refresh already in progress, skipping this request")
            return
            
        # Set the flag to indicate a refresh is in progress
        self.refresh_in_progress = True
        self.logger.debug("Starting browser refresh")
        
        try:
            # Clear the expanding_items set to ensure a clean state
            if self.expanding_items:
                self.logger.debug(f"Clearing {len(self.expanding_items)} items from expanding_items set")
                self.expanding_items.clear()
            
            # First, update all connected maps (current functionality)
            connected_maps = 0
            for layer in self.iface.mapCanvas().layers():
                map_id = layer.customProperty("maphub/map_id")
                if map_id:
                    self.logger.debug(f"Refreshing map item for layer '{layer.name()}' (Map ID: {map_id})")
                    self.refresh_map_item(map_id)
                    connected_maps += 1
            
            self.logger.debug(f"Updated {connected_maps} connected map items")
            
            # Then, reload contents of expanded folders
            self.logger.debug("Refreshing expanded folders")
            root = self.tree_widget.invisibleRootItem()
            self._refresh_expanded_folders(root)
            
            # Finally, refresh workspaces and their root folders
            self.logger.debug("Refreshing workspaces and root folders")
            self._refresh_workspaces()
            
            self.logger.debug("Browser refresh completed")
        finally:
            # Schedule clearing the flag after all pending events are processed
            # This ensures all delayed expansions have a chance to complete
            QTimer.singleShot(500, self._clear_refresh_flag)

    def _capture_expanded_state_recursive(self, parent_item):
        """
        Recursively capture the expanded state of all folders in the hierarchy.
        
        Args:
            parent_item: The parent item to check
            
        Returns:
            A dictionary mapping folder IDs to their expanded state and nested expanded states
        """
        # Get parent item info for logging
        parent_data = parent_item.data(0, Qt.UserRole)
        parent_type = parent_data.get('type') if parent_data else 'root'
        parent_text = parent_item.text(0) if parent_type != 'root' else 'Root'
        
        self.logger.debug(f"Capturing expanded state for {parent_type} '{parent_text}'")
        
        expanded_states = {}
        folder_count = 0
        expanded_count = 0
        
        # Process all children
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            item_data = child.data(0, Qt.UserRole)
            
            # Skip placeholder items
            if not item_data or item_data.get('type') == 'placeholder':
                continue
                
            # If this is a folder, store its expanded state and recursively process its children
            if item_data.get('type') == 'folder':
                folder_id = item_data.get('id')
                folder_name = child.text(0)
                is_expanded = child.isExpanded()
                folder_count += 1
                
                if is_expanded:
                    expanded_count += 1
                    self.logger.debug(f"  - Folder '{folder_name}' (ID: {folder_id}) is expanded")
                
                # Store this folder's expanded state
                expanded_states[folder_id] = {
                    'expanded': is_expanded,
                    'children': {}
                }
                
                # If the folder is expanded, recursively process its children
                if is_expanded and child.childCount() > 0:
                    child_states = self._capture_expanded_state_recursive(child)
                    expanded_states[folder_id]['children'] = child_states
                    self.logger.debug(f"  - Captured {len(child_states)} child states for folder '{folder_name}'")
        
        self.logger.debug(f"Captured {folder_count} folders ({expanded_count} expanded) under {parent_type} '{parent_text}'")
        return expanded_states
        
    def _refresh_expanded_folders(self, parent_item):
        """
        Recursively refresh the contents of expanded folders.
        
        Args:
            parent_item: The parent item to check
        """
        # Get parent item info for logging
        parent_data = parent_item.data(0, Qt.UserRole)
        parent_type = parent_data.get('type') if parent_data else 'root'
        parent_text = parent_item.text(0) if parent_type != 'root' else 'Root'
        
        self.logger.debug(f"Refreshing children of {parent_type} '{parent_text}'")
        
        # Process all children
        i = 0
        expanded_folders = 0
        while i < parent_item.childCount():
            child = parent_item.child(i)
            item_data = child.data(0, Qt.UserRole)
            
            # Skip placeholder items
            if not item_data or item_data.get('type') == 'placeholder':
                i += 1
                continue
                
            # If this is an expanded folder, reload its contents
            if item_data.get('type') == 'folder':
                folder_id = item_data.get('id')
                folder_name = child.text(0)
                
                # Check if folder still exists on server (only for expanded folders)
                if child.isExpanded():
                    self.logger.debug(f"  - Refreshing expanded folder '{folder_name}' (ID: {folder_id})")
                    expanded_folders += 1
                    
                    # Capture expanded state of all nested folders
                    expanded_child_folders = self._capture_expanded_state_recursive(child)
                    self.logger.debug(f"    - Captured expanded state for {len(expanded_child_folders)} child folders")
                    
                    # Store expanded state in the folder item for later use
                    child.setData(0, Qt.UserRole + 2, expanded_child_folders)
                    
                    # Store the expanded state of the folder itself for delayed restoration
                    was_expanded = child.isExpanded()
                    child.setData(0, Qt.UserRole + 3, was_expanded)
                    self.logger.debug(f"    - Stored expanded state: {was_expanded}")
                    
                    # Remove all children except the first one if it's a placeholder
                    child_count_before = child.childCount()
                    while child.childCount() > 0:
                        # Keep the placeholder if it exists and is the only child
                        if (child.childCount() == 1 and 
                            child.child(0).data(0, Qt.UserRole) and
                            child.child(0).data(0, Qt.UserRole).get('type') == 'placeholder'):
                            break
                        child.removeChild(child.child(0))
                    
                    # Add a placeholder if there isn't one
                    if child.childCount() == 0:
                        placeholder = QTreeWidgetItem(child)
                        placeholder.setText(0, "Loading...")
                        placeholder.setData(0, Qt.UserRole, {'type': 'placeholder'})
                    
                    self.logger.debug(f"    - Removed {child_count_before - child.childCount()} children")
                    
                    # Load folder contents
                    self.logger.debug(f"    - Starting content loader for folder '{folder_name}'")
                    loader = FolderContentLoader(child, folder_id)
                    loader.content_loaded.connect(self.on_folder_content_loaded)
                    loader.error_occurred.connect(self.on_folder_content_error)
                    self.content_loaders.append(loader)
                    loader.start()
                    
                    # Increment counter since we're keeping this item
                    i += 1
                else:
                    # For non-expanded folders, we'll check if they exist in a separate method
                    # to avoid too many API calls at once
                    i += 1
            elif item_data.get('type') == 'map':
                # Maps are refreshed when their parent folder is refreshed
                i += 1
            else:
                # For other item types, just increment the counter
                i += 1
            
            # Recursively process expanded children
            if child.childCount() > 0:
                self._refresh_expanded_folders(child)
        
        self.logger.debug(f"Refreshed {expanded_folders} expanded folders under {parent_type} '{parent_text}'")
                
    def _refresh_workspaces(self):
        """
        Refresh the list of workspaces and their root folders.
        This ensures that organization root folders are also refreshed.
        """
        self.logger.debug("Refreshing workspaces")
        
        # Get all workspace items
        root = self.tree_widget.invisibleRootItem()
        workspace_items = []
        
        # Collect all workspace items
        for i in range(root.childCount()):
            child = root.child(i)
            item_data = child.data(0, Qt.UserRole)
            if item_data and item_data.get('type') == 'workspace':
                workspace_items.append(child)
        
        self.logger.debug(f"Found {len(workspace_items)} workspace items")
        
        # If there are no workspace items, reload all workspaces
        if not workspace_items:
            self.logger.debug("No workspace items found, reloading all workspaces")
            self.load_workspaces()
            return
            
        # For each workspace item that is expanded, refresh its root folder
        expanded_workspaces = 0
        for workspace_item in workspace_items:
            workspace_name = workspace_item.text(0)
            
            if workspace_item.isExpanded():
                expanded_workspaces += 1
                workspace_id = workspace_item.data(0, Qt.UserRole).get('id')
                self.logger.debug(f"Refreshing expanded workspace '{workspace_name}' (ID: {workspace_id})")
                
                # Store expanded state of child folders and their nested folders
                expanded_child_folders = self._capture_expanded_state_recursive(workspace_item)
                self.logger.debug(f"  - Captured expanded state for {len(expanded_child_folders)} child folders")
                
                # Store the expanded state of the workspace item itself
                was_expanded = workspace_item.isExpanded()
                self.logger.debug(f"  - Current expanded state: {was_expanded}")
                
                # Remove all children except the first one if it's a placeholder
                child_count_before = workspace_item.childCount()
                while workspace_item.childCount() > 0:
                    # Keep the placeholder if it exists and is the only child
                    if (workspace_item.childCount() == 1 and 
                        workspace_item.child(0).data(0, Qt.UserRole) and
                        workspace_item.child(0).data(0, Qt.UserRole).get('type') == 'placeholder'):
                        break
                    workspace_item.removeChild(workspace_item.child(0))
                
                # Add a placeholder if there isn't one
                if workspace_item.childCount() == 0:
                    placeholder = QTreeWidgetItem(workspace_item)
                    placeholder.setText(0, "Loading...")
                    placeholder.setData(0, Qt.UserRole, {'type': 'placeholder'})
                
                self.logger.debug(f"  - Removed {child_count_before - workspace_item.childCount()} children")
                
                # Store expanded states for later use
                workspace_item.setData(0, Qt.UserRole + 1, expanded_child_folders)
                
                # Store the expanded state in a special role for delayed restoration
                workspace_item.setData(0, Qt.UserRole + 3, was_expanded)
                
                # Load workspace contents
                self.logger.debug(f"  - Starting content loader for workspace '{workspace_name}'")
                loader = WorkspaceContentLoader(workspace_item, workspace_id)
                loader.content_loaded.connect(self.on_workspace_content_loaded)
                loader.error_occurred.connect(self.on_content_error)
                self.content_loaders.append(loader)
                loader.start()
                
                # Restore the expanded state of the workspace item with a delay
                # This ensures Qt has time to process all events before expanding
                if was_expanded:
                    workspace_text = workspace_item.text(0)
                    self.logger.debug(f"  - Scheduling delayed expansion for workspace '{workspace_text}'")
                    # Increased delay to 250ms to give Qt more time to process events
                    QTimer.singleShot(250, lambda p=workspace_item, t=workspace_text: self._delayed_expand(p, t))
            else:
                self.logger.debug(f"Skipping collapsed workspace '{workspace_name}'")
        
        self.logger.debug(f"Refreshed {expanded_workspaces} expanded workspaces")
    
    def _clear_refresh_flag(self):
        """
        Clear the refresh_in_progress flag after all pending events are processed.
        This allows new refresh operations to start.
        """
        self.logger.debug("Clearing refresh_in_progress flag")
        self.refresh_in_progress = False
    
    def _delayed_expand(self, item, item_text):
        """
        Helper method to expand an item after a delay and log the result.
        Also recursively expands child folders that were previously expanded.
        
        Args:
            item: The tree item to expand
            item_text: The text of the item (for logging)
        """
        # Generate a unique identifier for this item
        item_id = id(item)
        
        # Check if this item is already being expanded
        if item_id in self.expanding_items:
            self.logger.debug(f"Skipping expansion for '{item_text}' - already in progress")
            return
            
        # Add this item to the set of items being expanded
        self.expanding_items.add(item_id)
        
        try:
            # Safely check if the item is still valid and not deleted
            # We need to use a try-except block because accessing a deleted C++ object
            # will raise a RuntimeError
            try:
                # First check if the item exists
                if not item:
                    self.logger.debug(f"Item '{item_text}' is None")
                    return
                
                # Log item details for debugging
                self.logger.debug(f"Checking item '{item_text}' (id: {item_id})")
                
                # Try to access a property to see if the item is still valid
                # This will raise RuntimeError if the C++ object has been deleted
                tree_widget = item.treeWidget()
                if not tree_widget:
                    self.logger.debug(f"Item '{item_text}' has no tree widget")
                    return
                
                # Additional safety check - verify the item is still in the tree
                parent = item.parent()
                if parent:
                    self.logger.debug(f"Item '{item_text}' has parent: {parent.text(0)}")
                else:
                    # Root level items have no parent
                    self.logger.debug(f"Item '{item_text}' is a root level item")
                
                # If we get here, the item is valid
                if not item.isExpanded():
                    self.logger.debug(f"Executing delayed expansion for '{item_text}'")
                    item.setExpanded(True)
                    self.logger.debug(f"  - Is now expanded: {item.isExpanded()}")
                    self.logger.debug(f"  - Child count: {item.childCount()}")
                    
                    # After expanding this item, check if we need to expand any of its children
                    # Get the stored expanded states for child folders
                    item_data = item.data(0, Qt.UserRole)
                    if item_data and item_data.get('type') in ['folder', 'workspace']:
                        # Get the stored child expanded states
                        child_expanded_states = item.data(0, Qt.UserRole + 2) or {}
                        if child_expanded_states:
                            self.logger.debug(f"  - Found {len(child_expanded_states)} child folders to expand")
                            self._expand_child_folders(item, child_expanded_states)
                else:
                    self.logger.debug(f"Item '{item_text}' is already expanded")
                    
                    # Even if already expanded, we should check for child folders to expand
                    # This handles the case where a refresh happens and we need to re-expand nested folders
                    item_data = item.data(0, Qt.UserRole)
                    if item_data and item_data.get('type') in ['folder', 'workspace']:
                        # Get the stored child expanded states
                        child_expanded_states = item.data(0, Qt.UserRole + 2) or {}
                        if child_expanded_states:
                            self.logger.debug(f"  - Found {len(child_expanded_states)} child folders to expand (already expanded parent)")
                            self._expand_child_folders(item, child_expanded_states)
            except RuntimeError as e:
                # The C++ object has been deleted
                self.logger.debug(f"Item '{item_text}' has been deleted: {str(e)}")
                # Log stack trace for debugging
                import traceback
                self.logger.debug(f"Stack trace: {traceback.format_exc()}")
        finally:
            # Remove this item from the set of items being expanded
            if item_id in self.expanding_items:
                self.expanding_items.remove(item_id)
                self.logger.debug(f"Removed '{item_text}' from expanding items set")
                
    def _expand_child_folders(self, parent_item, child_expanded_states):
        """
        Recursively expand child folders based on their stored expanded states.
        
        Args:
            parent_item: The parent item whose children should be expanded
            child_expanded_states: Dictionary mapping folder IDs to their expanded state
        """
        self.logger.debug(f"Expanding child folders of '{parent_item.text(0)}'")
        
        # Process all children of the parent item
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            item_data = child.data(0, Qt.UserRole)
            
            # Skip non-folder items or placeholder items
            if not item_data or item_data.get('type') != 'folder':
                continue
                
            folder_id = item_data.get('id')
            folder_name = child.text(0)
            
            # Check if this folder should be expanded
            if folder_id in child_expanded_states:
                folder_info = child_expanded_states[folder_id]
                
                # Handle both dictionary format and boolean format
                if isinstance(folder_info, dict):
                    should_expand = folder_info.get('expanded', False)
                    nested_expanded_states = folder_info.get('children', {})
                else:
                    # For backward compatibility with older format
                    should_expand = bool(folder_info)
                    nested_expanded_states = {}
                
                if should_expand:
                    self.logger.debug(f"  - Scheduling expansion for child folder '{folder_name}'")
                    
                    # Store the nested expanded states for use when this folder is expanded
                    if nested_expanded_states:
                        child.setData(0, Qt.UserRole + 2, nested_expanded_states)
                        
                    # Store that this folder should be expanded
                    child.setData(0, Qt.UserRole + 3, True)
                    
                    # Schedule expansion with a small delay to ensure parent is fully expanded first
                    QTimer.singleShot(100, lambda p=child, t=folder_name: self._delayed_expand(p, t))
    
    @handled_exceptions
    def on_refresh_clicked(self, checked=False):
        """Handle refresh button click."""
        self.logger.debug("Refresh button clicked")
        
        # Refresh the browser dock
        self.refresh_browser()

        # Call the refresh callback if provided
        if self.refresh_callback:
            self.refresh_callback()
