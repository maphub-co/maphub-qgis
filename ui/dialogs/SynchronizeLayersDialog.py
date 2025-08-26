import os
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QTreeWidgetItem, QCheckBox, QHeaderView, QMessageBox, QComboBox, QDialog, QPushButton
from PyQt5.QtGui import QBrush, QColor
from qgis.PyQt import uic
from qgis.core import QgsProject

from .MapHubBaseDialog import MapHubBaseDialog
from .UploadMapDialog import UploadMapDialog
from .BatchConnectLayersDialog import BatchConnectLayersDialog
from ...utils.sync_manager import MapHubSyncManager
from ...utils.layer_decorator import MapHubLayerDecorator
from ...utils.status_icon_manager import StatusIconManager

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
        
        # Populate the tree with all layers
        self.populate_layers()
    
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
        download_layers = []  # remote_newer
        upload_layers = []    # local_modified, style_changed
        not_connected_layers = []
        in_sync_layers = []   # in_sync, file_missing, remote_error, processing
        
        # Categorize layers by status
        for layer in all_layers:
            is_connected = layer.customProperty("maphub/map_id") is not None
            
            if not is_connected:
                not_connected_layers.append(layer)
                continue
            
            status = self.sync_manager.get_layer_sync_status(layer)
            
            if status == "remote_newer":
                download_layers.append((layer, status))
            elif status in ["local_modified", "style_changed"]:
                upload_layers.append((layer, status))
            else:
                in_sync_layers.append((layer, status))
        
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
                "title": "LAYERS NOT CONNECTED",
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
                spacing_item.setText(1, "")  # Empty text
                spacing_item.setSizeHint(0, QSize(0, 10))  # Set height to 10 pixels
            
            # Create group header item
            group_item = QTreeWidgetItem(self.layersTree)
            group_item.setText(1, group["title"])
            group_item.setFlags(Qt.ItemIsEnabled)
            
            # Set background color for all columns
            for col in range(3):
                group_item.setBackground(col, QBrush(group["color"]))
            
            # Make font bold for header
            font = group_item.font(1)
            font.setBold(True)
            for col in range(3):
                group_item.setFont(col, font)
            
            # Expand by default
            group_item.setExpanded(group["expanded"])
            
            # Add child items
            if group["title"] == "LAYERS NOT CONNECTED":
                # Add Connect Layers button to the header (smaller size)
                connect_button = QPushButton("Connect")
                connect_button.setMaximumWidth(80)
                connect_button.setMaximumHeight(20)
                connect_button.setStyleSheet("QPushButton { padding: 2px; }")
                connect_button.clicked.connect(self.on_batch_connect_clicked)
                self.layersTree.setItemWidget(group_item, 2, connect_button)
                
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
        item.setText(1, layer.name())
        
        # Set action based on status
        if status == "local_modified":
            item.setText(0, "Upload to MapHub")
        elif status == "remote_newer":
            item.setText(0, "Download from MapHub")
        elif status == "processing":
            item.setText(0, "Processing on MapHub")
        elif status == "style_changed":
            # Add style resolution combo box
            style_combo = QComboBox()
            style_combo.addItems(["Keep Local Style", "Use Remote Style"])
            self.layersTree.setItemWidget(item, 0, style_combo)
        elif status == "in_sync":
            item.setText(0, "In Sync")
        elif status == "file_missing":
            item.setText(0, "File Missing")
        elif status == "remote_error":
            item.setText(0, "Remote Error")
        
        # Add checkbox for selection (except for in-sync layers)
        if status not in ["in_sync", "file_missing", "remote_error", "processing"]:
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            # Ensure the item is visible in the tree before adding the widget
            self.layersTree.setItemWidget(item, 2, checkbox)
            # Force update to make checkbox visible
            item.setSelected(False)
        
        # Store layer reference
        item.setData(1, Qt.UserRole, layer)
    
    def _add_not_connected_layer(self, parent_item, layer):
        """Add a non-connected layer to the tree under the specified parent item."""
        item = QTreeWidgetItem(parent_item)
        item.setText(1, layer.name())
        
        # Gray out the text
        for col in range(3):
            item.setForeground(col, QBrush(QColor(128, 128, 128)))
        
        # Add "Not Connected" text in the action column
        item.setText(0, "Not Connected")
        
        # Add disabled checkbox
        checkbox = QCheckBox()
        checkbox.setEnabled(False)
        self.layersTree.setItemWidget(item, 2, checkbox)
        # Force update to make checkbox visible
        item.setSelected(False)
        
        # Store layer reference
        item.setData(1, Qt.UserRole, layer)
    
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
    
    def on_batch_connect_clicked(self, default_folder_id=None):
        """
        Handle click on the Batch Connect Layers button.
        
        Args:
            default_folder_id: Optional default folder ID to select
        """
        # Get all not connected layers
        not_connected_layers = []
        
        # Find the "LAYERS NOT CONNECTED" group
        for i in range(self.layersTree.topLevelItemCount()):
            group_item = self.layersTree.topLevelItem(i)
            if group_item.text(1) == "LAYERS NOT CONNECTED":
                for j in range(group_item.childCount()):
                    child_item = group_item.child(j)
                    layer = child_item.data(1, Qt.UserRole)
                    not_connected_layers.append(layer)
                break
        
        if not not_connected_layers:
            QMessageBox.information(
                self,
                "No Layers to Connect",
                "All layers are already connected to MapHub."
            )
            return
        
        # Open the batch connect dialog
        batch_dialog = BatchConnectLayersDialog(self.iface, not_connected_layers, self, default_folder_id)
        result = batch_dialog.exec_()
        
        # Refresh the dialog if layers were connected
        if result == QDialog.Accepted:
            self.populate_layers()
            # Additional refresh to ensure checkboxes are visible
            self.refresh_tree()
    
    def on_connect_clicked(self, layer):
        """
        Handle click on the Connect button for a non-connected layer.
        
        Args:
            layer: The layer to connect
        """
        # Create a dialog to choose between uploading a new map or connecting to an existing one
        choice_dialog = QMessageBox(self)
        choice_dialog.setWindowTitle("Connect Layer")
        choice_dialog.setText(f"How would you like to connect layer '{layer.name()}' to MapHub?")
        upload_button = choice_dialog.addButton("Upload as New Map", QMessageBox.ActionRole)
        connect_button = choice_dialog.addButton("Connect to Existing Map", QMessageBox.ActionRole)
        cancel_button = choice_dialog.addButton(QMessageBox.Cancel)
        
        choice_dialog.exec_()
        
        if choice_dialog.clickedButton() == upload_button:
            # Open the UploadMapDialog with pre-selected layer
            upload_dialog = UploadMapDialog(self.iface, self)
            upload_dialog.layerComboBox.setCurrentText(layer.name())
            upload_dialog.exec_()
            
            # Refresh the dialog after upload
            self.populate_layers()
        elif choice_dialog.clickedButton() == connect_button:
            # Open a dialog to select an existing map
            # This would need to be implemented as a new dialog
            QMessageBox.information(
                self,
                "Feature Coming Soon",
                "The 'Connect to Existing Map' feature will be implemented in a future version."
            )
    
    def on_sync_clicked(self):
        """Handle click on the Synchronize Selected button."""
        # Get selected layers with their synchronization directions
        selected_items = []
        
        for i in range(self.layersTree.topLevelItemCount()):
            group_item = self.layersTree.topLevelItem(i)
            for j in range(group_item.childCount()):
                child_item = group_item.child(j)
                checkbox = self.layersTree.itemWidget(child_item, 2)
                if checkbox and checkbox.isChecked():
                    layer = child_item.data(1, Qt.UserRole)
                    
                    # Get synchronization direction
                    direction = "auto"
                    
                    # Check if this is a style conflict
                    widget = self.layersTree.itemWidget(child_item, 0)
                    if isinstance(widget, QComboBox):
                        # This is a style conflict, get the selected option
                        if widget.currentText() == "Keep Local Style":
                            direction = "push"
                        else:  # "Use Remote Style"
                            direction = "pull"
                    
                    selected_items.append((layer, direction))
        
        # If no layers selected, show a message
        if not selected_items:
            QMessageBox.information(
                self,
                "No Layers Selected",
                "Please select at least one layer to synchronize."
            )
            return
        
        # Create and show progress dialog
        from ..widgets.ProgressDialog import ProgressDialog
        progress = ProgressDialog("Synchronizing Layers", "Preparing to synchronize...", self)
        progress.set_progress(0, len(selected_items))
        progress.show()
        
        # Synchronize selected layers
        success_count = 0
        for i, (layer, direction) in enumerate(selected_items):
            progress.set_message(f"Synchronizing layer '{layer.name()}'...")
            progress.set_progress(i)
            
            try:
                self.sync_manager.synchronize_layer(layer, direction)
                success_count += 1
            except Exception as e:
                from ...utils.error_manager import ErrorManager
                ErrorManager.show_error(f"Failed to synchronize layer '{layer.name()}'", e, self)
            
            # Check if user canceled
            if progress.result() == QDialog.Rejected:
                break
        
        # Close progress dialog
        progress.accept()
        
        # Update layer icons
        layer_decorator = MapHubLayerDecorator(self.iface)
        layer_decorator.update_layer_icons()
        
        # Show success message
        QMessageBox.information(
            self,
            "Synchronization Complete",
            f"Successfully synchronized {success_count} of {len(selected_items)} layer(s)."
        )
        
        # Close dialog
        self.accept()