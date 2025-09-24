import os
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QTreeWidgetItem, QCheckBox, QHeaderView, QMessageBox, QComboBox, QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtGui import QBrush, QColor, QFont
from qgis.PyQt import uic
from qgis.core import QgsProject

from .MapHubBaseDialog import MapHubBaseDialog
from .UploadMapDialog import UploadMapDialog
from ...utils.sync_manager import MapHubSyncManager
from ...utils.status_icon_manager import StatusIconManager
from ...utils.project_utils import get_project_folder_id, save_project_to_maphub
from ...utils.utils import get_maphub_client
from .SaveProjectDialog import SaveProjectDialog
from ..widgets.ProgressDialog import ProgressDialog
from ...utils.error_manager import ErrorManager
from ...utils.layer_decorator import MapHubLayerDecorator

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'SynchronizeLayersDialog.ui'))


class SynchronizeLayersDialog(MapHubBaseDialog, FORM_CLASS):
    """
    Dialog for synchronizing layers with MapHub.
    
    This dialog displays a list of all loaded layers, showing which ones are connected
    to MapHub and allowing the user to select which layers to synchronize.
    """
    
    def __init__(self, iface, parent=None):
        """
        Initialize the dialog.
        
        Args:
            iface: The QGIS interface
            parent: The parent widget
        """
        super(SynchronizeLayersDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.icon_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'icons')

        self.folder_id = self._collect_folder_id()
        
        # Flag to determine if project should be saved on sync
        self.save_project_on_sync = True

        # Initialize sync manager
        self.sync_manager = MapHubSyncManager(iface)
        
        # Configure tree widget
        self.layersTree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        
        # Connect signals
        self.syncButton.clicked.connect(self.on_sync_clicked)
        self.selectAllButton.clicked.connect(self.on_select_all_clicked)
        self.selectNoneButton.clicked.connect(self.on_select_none_clicked)
        
        # Hide the top batch connect button as we'll add it to the header
        self.batchConnectButton.hide()
        
        # Add folder name label at the top of the dialog
        self._add_folder_name_label()
        
        # Populate the tree with all layers
        self.populate_layers()

        self.on_select_all_clicked()

    def _collect_folder_id(self) -> str:
        # Get folder_id from project
        folder_id = get_project_folder_id()

        if folder_id:
            return folder_id

        # Show the folder selection dialog
        save_dialog = SaveProjectDialog(self)
        result = save_dialog.exec_()

        if result:
            folder_id = save_dialog.get_selected_folder_id()
            # Save the folder_id to the project
            QgsProject.instance().writeEntry("maphub", "folder_id", folder_id)
            return folder_id

        else:
            raise Exception("You need to select a folder to synchronize layers with MapHub.")
            
    def _on_save_project_checkbox_changed(self, state):
        """
        Handle changes to the save project checkbox state.
        
        Args:
            state: The new state of the checkbox
        """
        self.save_project_on_sync = state == Qt.Checked
        
    def _on_change_folder_clicked(self):
        """
        Handle click on the Change Folder button.
        
        This method shows the SaveProjectDialog to select a new folder,
        updates the project's folder_id, and disconnects all connected layers.
        """
        # Show confirmation dialog first
        result = QMessageBox.question(
            self,
            "Change Project Folder",
            "Changing the project folder will disconnect all layers from MapHub. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # Show the folder selection dialog
        save_dialog = SaveProjectDialog(self)
        result = save_dialog.exec_()
        
        if not result:
            return
            
        # Get the selected folder_id
        new_folder_id = save_dialog.get_selected_folder_id()
        
        if new_folder_id == self.folder_id:
            QMessageBox.information(
                self,
                "No Change",
                "The same folder was selected. No changes were made."
            )
            return
            
        # Disconnect all connected layers
        connected_layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if layer.customProperty("maphub/map_id") is not None:
                connected_layers.append(layer)

        sync_manager = MapHubSyncManager(self.iface)

        # Disconnect each layer
        for i, layer in enumerate(connected_layers):
            sync_manager.disconnect_layer(layer)

        
        # Update the project's folder_id
        QgsProject.instance().writeEntry("maphub", "folder_id", new_folder_id)
        self.folder_id = new_folder_id
        
        # Update layer icons - use the existing decorator from the plugin instance
        from qgis.utils import plugins
        if 'MapHubPlugin' in plugins:
            plugins['MapHubPlugin'].layer_decorator.update_layer_icons()
        
        # Clear and rebuild the folder name label
        # First, remove the existing layout at index 0
        old_layout = self.verticalLayout.itemAt(0)
        if old_layout:
            # Remove all widgets from the layout
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            # Remove the layout itself
            self.verticalLayout.removeItem(old_layout)
            
        # Add the new folder name label
        self._add_folder_name_label()
        
        # Repopulate the layers tree
        self.populate_layers()
        
        QMessageBox.information(
            self,
            "Folder Changed",
            f"Project folder changed successfully. All layers have been disconnected from MapHub."
        )
    
    def _add_folder_name_label(self):
        """
        Add a label at the top of the dialog showing the folder name and a checkbox
        to specify whether the project should be saved when synchronizing.
        Also adds a "Change Folder" button to allow changing the project's folder.
        """
        try:
            # Get the folder information using the MapHub client
            client = get_maphub_client()
            folder_info = client.folder.get_folder(self.folder_id)
            folder_name = folder_info['folder'].get('name', 'Unknown Folder')
            
            # Create a horizontal layout for the folder name and checkbox
            folder_layout = QHBoxLayout()
            
            # Create a label with the folder name
            folder_label = QLabel(f"Folder: {folder_name}")
            
            # Style the label to make it stand out
            font = QFont()
            font.setBold(True)
            folder_label.setFont(font)
            
            # Add the label to the horizontal layout
            folder_layout.addWidget(folder_label)
            
            # Add a "Change Folder" button
            change_folder_button = QPushButton("Change Folder")
            change_folder_button.setToolTip("Change the project's folder (will disconnect all connected layers)")
            change_folder_button.clicked.connect(self._on_change_folder_clicked)
            folder_layout.addWidget(change_folder_button)
            
            # Add a spacer to push the checkbox to the right
            folder_layout.addStretch()
            
            # Create a checkbox for saving the project
            save_project_checkbox = QCheckBox("Save project on synchronize")
            save_project_checkbox.setChecked(self.save_project_on_sync)
            save_project_checkbox.stateChanged.connect(self._on_save_project_checkbox_changed)
            folder_layout.addWidget(save_project_checkbox)
            
            # Insert the horizontal layout at the top of the dialog
            self.verticalLayout.insertLayout(0, folder_layout)
            
        except Exception as e:
            # If there's an error getting the folder name, just show "Unknown Folder"
            folder_layout = QHBoxLayout()
            folder_label = QLabel("Folder: Unknown")
            folder_layout.addWidget(folder_label)
            
            # Add a "Change Folder" button
            change_folder_button = QPushButton("Change Folder")
            change_folder_button.setToolTip("Change the project's folder (will disconnect all connected layers)")
            change_folder_button.clicked.connect(self._on_change_folder_clicked)
            folder_layout.addWidget(change_folder_button)
            
            # Add a spacer to push the checkbox to the right
            folder_layout.addStretch()
            
            # Create a checkbox for saving the project
            save_project_checkbox = QCheckBox("Save project on synchronize")
            save_project_checkbox.setChecked(self.save_project_on_sync)
            save_project_checkbox.stateChanged.connect(self._on_save_project_checkbox_changed)
            folder_layout.addWidget(save_project_checkbox)
            
            # Insert the horizontal layout at the top of the dialog
            self.verticalLayout.insertLayout(0, folder_layout)

    
    def on_select_all_clicked(self):
        """Handle click on the Select All button."""
        for i in range(self.layersTree.topLevelItemCount()):
            group_item = self.layersTree.topLevelItem(i)
            for j in range(group_item.childCount()):
                child_item = group_item.child(j)
                checkbox = self.layersTree.itemWidget(child_item, 2)
                if checkbox and checkbox.isEnabled():
                    checkbox.setChecked(True)
    
    def on_select_none_clicked(self):
        """Handle click on the Select None button."""
        for i in range(self.layersTree.topLevelItemCount()):
            group_item = self.layersTree.topLevelItem(i)
            for j in range(group_item.childCount()):
                child_item = group_item.child(j)
                checkbox = self.layersTree.itemWidget(child_item, 2)
                if checkbox:
                    checkbox.setChecked(False)
        
    def refresh_tree(self):
        """Force the tree widget to refresh and update all items."""
        # This helps ensure all widgets (like checkboxes) are properly displayed
        self.layersTree.update()
        # Collapse and re-expand items to force redraw
        for i in range(self.layersTree.topLevelItemCount()):
            item = self.layersTree.topLevelItem(i)
            if item.childCount() > 0:  # Only process items with children
                was_expanded = item.isExpanded()
                if was_expanded:
                    item.setExpanded(False)
                    item.setExpanded(True)

    def populate_layers(self):
        """Populate the tree widget with all layers grouped by sync status."""
        # Clear existing items
        self.layersTree.clear()
        
        # Get all layers from the project
        all_layers = QgsProject.instance().mapLayers().values()
        
        if not all_layers:
            QMessageBox.information(
                self,
                "No Layers",
                "There are no layers in the current project."
            )
            self.reject()
            return
        
        # Create dictionaries to store layers by status
        download_layers = []  # remote_newer, style_changed_remote
        upload_layers = []    # local_modified, style_changed_local, style_changed_both
        not_connected_layers = []
        in_sync_layers = []   # in_sync, file_missing, remote_error, processing
        
        # Categorize layers by status
        for layer in all_layers:
            is_connected = layer.customProperty("maphub/map_id") is not None
            
            if not is_connected:
                not_connected_layers.append(layer)
                continue
            
            status = self.sync_manager.get_layer_sync_status(layer)
            
            if status == "remote_newer" or status == "style_changed_remote":
                download_layers.append((layer, status))
            elif status == "local_modified" or status == "style_changed_local":
                upload_layers.append((layer, status))
            elif status == "style_changed_both":
                upload_layers.append((layer, status))  # Default to upload, but will show conflict resolution UI
            else:
                in_sync_layers.append((layer, status))

        # Update layer icons - use the existing decorator from the plugin instance
        # This prevents creating multiple decorators that might add duplicate indicators
        layer_decorator = MapHubLayerDecorator.get_instance(self.iface)
        layer_decorator.update_layer_icons()
        
        # Define group headers with colors
        groups = [
            {
                "title": "LAYERS TO DOWNLOAD (Accept Remote Changes)",
                "layers": download_layers,
                "color": QColor(173, 216, 230),  # Light blue
                "expanded": True
            },
            {
                "title": "LAYERS TO UPLOAD (Push Local Changes)",
                "layers": upload_layers,
                "color": QColor(144, 238, 144),  # Light green
                "expanded": True
            },
            {
                "title": "LAYERS TO CONNECT (Will be uploaded to MapHub)",
                "layers": not_connected_layers,
                "color": QColor(255, 255, 224),  # Light yellow
                "expanded": True
            },
            {
                "title": "LAYERS IN SYNC (No Action Needed)",
                "layers": in_sync_layers,
                "color": QColor(211, 211, 211),  # Light gray
                "expanded": False
            }
        ]
        
        # Add groups to tree
        for group in groups:
            if not group["layers"]:
                continue  # Skip empty groups
            
            # Add spacing item before group (except for the first non-empty group)
            if self.layersTree.topLevelItemCount() > 0:
                spacing_item = QTreeWidgetItem(self.layersTree)
                spacing_item.setFlags(Qt.NoItemFlags)  # Make it non-selectable
                spacing_item.setText(0, "")  # Empty text
                spacing_item.setSizeHint(0, QSize(0, 10))  # Set height to 10 pixels
            
            # Create group header item
            group_item = QTreeWidgetItem(self.layersTree)
            group_item.setText(0, group["title"])
            group_item.setFlags(Qt.ItemIsEnabled)
            
            # Set background color for all columns
            for col in range(3):
                group_item.setBackground(col, QBrush(group["color"]))
            
            # Make font bold for header
            font = group_item.font(0)
            font.setBold(True)
            for col in range(3):
                group_item.setFont(col, font)
            
            # Expand by default
            group_item.setExpanded(group["expanded"])
            
            # Add child items
            if group["title"] == "LAYERS TO CONNECT (Will be uploaded to MapHub)":
                # Handle not connected layers
                for layer in group["layers"]:
                    self._add_not_connected_layer(group_item, layer)
            else:
                # Handle connected layers
                for layer, status in group["layers"]:
                    self._add_connected_layer(group_item, layer, status)
        
        # Resize columns to content
        for i in range(3):
            self.layersTree.resizeColumnToContents(i)
            
        # Force refresh to ensure all widgets are properly displayed
        self.refresh_tree()
    
    def _add_connected_layer(self, parent_item, layer, status):
        """Add a connected layer to the tree under the specified parent item."""
        item = QTreeWidgetItem(parent_item)
        item.setText(0, layer.name())
        
        # Set action based on status
        if status == "local_modified":
            item.setText(1, "Upload to MapHub")
        elif status == "remote_newer":
            item.setText(1, "Download from MapHub")
        elif status == "processing":
            item.setText(1, "Processing on MapHub")
        elif status == "style_changed_local":
            item.setText(1, "Upload Style to MapHub")
        elif status == "style_changed_remote":
            item.setText(1, "Download Style from MapHub")
        elif status == "style_changed_both":
            # Add style resolution combo box
            style_combo = QComboBox()
            style_combo.addItems(["Keep Local Style", "Use Remote Style"])
            style_combo.setMaximumWidth(80)
            style_combo.setMaximumHeight(20)
            self.layersTree.setItemWidget(item, 1, style_combo)
        elif status == "in_sync":
            item.setText(1, "In Sync")
        elif status == "file_missing":
            item.setText(1, "File Missing")
        elif status == "remote_error":
            item.setText(1, "Remote Error")
        
        # Add checkbox for selection (except for in-sync layers)
        if status not in ["in_sync", "file_missing", "remote_error", "processing"]:
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            # Ensure the item is visible in the tree before adding the widget
            self.layersTree.setItemWidget(item, 2, checkbox)
            # Force update to make checkbox visible
            item.setSelected(False)
        
        # Store layer reference
        item.setData(0, Qt.UserRole, layer)
    
    def _add_not_connected_layer(self, parent_item, layer):
        """Add a non-connected layer to the tree under the specified parent item."""
        item = QTreeWidgetItem(parent_item)
        item.setText(0, layer.name())
        
        # Gray out the text but not as much as before
        for col in range(3):
            item.setForeground(col, QBrush(QColor(80, 80, 80)))  # Darker than before to be more readable
        
        # Add "Will Connect" text in the action column
        item.setText(1, "Will Connect")
        
        # Add enabled checkbox
        checkbox = QCheckBox()
        checkbox.setEnabled(True)  # Enable the checkbox
        checkbox.setChecked(False)  # Unchecked by default
        self.layersTree.setItemWidget(item, 2, checkbox)
        
        # Force update to make checkbox visible
        item.setSelected(False)
        
        # Store layer reference
        item.setData(0, Qt.UserRole, layer)
    
    def _add_status_icon(self, item, column, status):
        """
        Add a status icon to the specified column.
        
        Args:
            item: The tree widget item
            column: The column index
            status: The synchronization status
        """
        
        icon_manager = StatusIconManager()
        icon = icon_manager.get_icon(status)
        tooltip = icon_manager.get_tooltip(status)
        
        if not icon.isNull():
            item.setIcon(column, icon)
            if tooltip:
                item.setToolTip(column, tooltip)

    def on_sync_clicked(self):
        """Handle click on the Synchronize Selected button."""
        # Get selected layers with their synchronization directions
        selected_items = []
        selected_not_connected = []
        
        for i in range(self.layersTree.topLevelItemCount()):
            group_item = self.layersTree.topLevelItem(i)
            group_title = group_item.text(0)
            
            for j in range(group_item.childCount()):
                child_item = group_item.child(j)
                checkbox = self.layersTree.itemWidget(child_item, 2)
                if checkbox and checkbox.isChecked():
                    layer = child_item.data(0, Qt.UserRole)
                    
                    # Check if this is a not-connected layer
                    if "TO CONNECT" in group_title:
                        selected_not_connected.append(layer)
                    else:
                        # Get synchronization direction
                        direction = "auto"
                        
                        # Check if this is a style conflict
                        widget = self.layersTree.itemWidget(child_item, 1)
                        if isinstance(widget, QComboBox):
                            # This is a style conflict, get the selected option
                            if widget.currentText() == "Keep Local Style":
                                direction = "push"
                            else:  # "Use Remote Style"
                                direction = "pull"
                            # Set style_only flag to True for style conflicts
                            selected_items.append((layer, direction, True))
                        else:
                            # Get the layer's status to check if it's a style-related status
                            status = self.sync_manager.get_layer_sync_status(layer)
                            style_only = status in ["style_changed_local", "style_changed_remote", "style_changed_both"]
                            selected_items.append((layer, direction, style_only))
        
        # If no layers selected
        if not selected_items and not selected_not_connected:
            # If save_project_on_sync is true, save the project even if no layers are selected
            if self.save_project_on_sync:
                save_project_to_maphub(folder_id=self.folder_id)
                QMessageBox.information(
                    self,
                    "Project Saved",
                    "No layers were selected for synchronization, but the project was saved."
                )
                self.accept()
                return
            else:
                # Otherwise show the standard message
                QMessageBox.information(
                    self,
                    "No Layers Selected",
                    "Please select at least one layer to synchronize."
                )
                return
        
        # Create and show progress dialog
        progress = ProgressDialog("Synchronizing Layers", "Preparing to synchronize...", self)
        total_operations = len(selected_items) + len(selected_not_connected)
        progress.set_progress(0, total_operations)
        progress.show()
        
        # First, connect not-connected layers
        success_count = 0
        connect_count = 0
        
        if selected_not_connected:
            progress.set_message("Connecting layers to MapHub...")
            
            for i, layer in enumerate(selected_not_connected):
                progress.set_message(f"Connecting layer '{layer.name()}'...")
                progress.set_progress(i)
                
                try:
                    # Upload the layer as a new map
                    self.sync_manager.add_layer(
                        layer=layer,
                        map_name=layer.name(),
                        folder_id=self.folder_id,
                        public=False
                    )
                    connect_count += 1
                except Exception as e:
                    ErrorManager.show_error(f"Failed to connect layer '{layer.name()}'", e, self)

        
        # Then, synchronize connected layers
        start_index = len(selected_not_connected)
        for i, (layer, direction, style_only) in enumerate(selected_items):
            progress.set_message(f"Synchronizing layer '{layer.name()}'...")
            progress.set_progress(start_index + i)
            
            try:
                self.sync_manager.synchronize_layer(layer, direction, style_only)
                success_count += 1
            except Exception as e:
                ErrorManager.show_error(f"Failed to synchronize layer '{layer.name()}'", e, self)

        
        # Close progress dialog
        progress.accept()
        
        # Update layer icons - use the existing decorator from the plugin instance
        # This prevents creating multiple decorators that might add duplicate indicators
        layer_decorator = MapHubLayerDecorator.get_instance(self.iface)
        layer_decorator.update_layer_icons()
        
        # Show success message
        if connect_count > 0 and success_count > 0:
            message = f"Successfully connected {connect_count} layer(s) and synchronized {success_count} layer(s)."
        elif connect_count > 0:
            message = f"Successfully connected {connect_count} layer(s) to MapHub."
        else:
            message = f"Successfully synchronized {success_count} of {len(selected_items)} layer(s)."


        # Save the project if the checkbox is checked
        if self.save_project_on_sync:
            save_project_to_maphub(folder_id=self.folder_id)

        QMessageBox.information(
            self,
            "Operation Complete",
            message
        )
        
        # Close dialog
        self.accept()