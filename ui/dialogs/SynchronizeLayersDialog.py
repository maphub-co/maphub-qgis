import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem, QCheckBox, QHeaderView, QMessageBox, QComboBox, QDialog
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
        self.layersTree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        
        # Connect signals
        self.syncButton.clicked.connect(self.on_sync_clicked)
        self.selectAllButton.clicked.connect(self.on_select_all_clicked)
        self.selectNoneButton.clicked.connect(self.on_select_none_clicked)
        self.batchConnectButton.clicked.connect(self.on_batch_connect_clicked)
        
        # Populate the tree with all layers
        self.populate_layers()
    
    def on_select_all_clicked(self):
        """Handle click on the Select All button."""
        for i in range(self.layersTree.topLevelItemCount()):
            item = self.layersTree.topLevelItem(i)
            checkbox = self.layersTree.itemWidget(item, 4)
            if checkbox and not checkbox.isEnabled():
                continue
            if checkbox:
                checkbox.setChecked(True)
    
    def on_select_none_clicked(self):
        """Handle click on the Select None button."""
        for i in range(self.layersTree.topLevelItemCount()):
            item = self.layersTree.topLevelItem(i)
            checkbox = self.layersTree.itemWidget(item, 4)
            if checkbox:
                checkbox.setChecked(False)
        
    def populate_layers(self):
        """Populate the tree widget with all layers."""
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
        
        # Add layers to tree
        for layer in all_layers:
            item = QTreeWidgetItem(self.layersTree)
            item.setText(0, layer.name())
            
            # Check if layer is connected to MapHub
            is_connected = layer.customProperty("maphub/map_id") is not None
            
            if is_connected:
                # Get synchronization status
                status = self.sync_manager.get_layer_sync_status(layer)
                
                # Set local status column
                if status in ["local_modified", "style_changed"]:
                    self._add_status_icon(item, 1, status)
                
                # Set remote status column
                if status in ["remote_newer", "processing"]:
                    self._add_status_icon(item, 2, status)
                
                # Set action based on status
                if status == "local_modified":
                    item.setText(3, "Upload to MapHub")
                elif status == "remote_newer":
                    item.setText(3, "Download from MapHub")
                elif status == "processing":
                    item.setText(3, "Processing on MapHub")
                elif status == "style_changed":
                    # Add style resolution combo box
                    style_combo = QComboBox()
                    style_combo.addItems(["Keep Local Style", "Use Remote Style"])
                    self.layersTree.setItemWidget(item, 3, style_combo)
                elif status == "in_sync":
                    item.setText(3, "In Sync")
                elif status == "file_missing":
                    item.setText(3, "File Missing")
                elif status == "remote_error":
                    item.setText(3, "Remote Error")
                
                # Add checkbox for selection
                checkbox = QCheckBox()
                checkbox.setChecked(False)
                # Disable checkbox for layers that can't be synchronized
                if status in ["in_sync", "file_missing", "remote_error", "processing"]:
                    checkbox.setEnabled(False)
                self.layersTree.setItemWidget(item, 4, checkbox)
            else:
                # Non-connected layer - gray out the text
                for col in range(5):
                    item.setForeground(col, QBrush(QColor(128, 128, 128)))
                
                # Add "Not Connected" text in the action column
                item.setText(3, "Not Connected")
                
                # Add disabled checkbox
                checkbox = QCheckBox()
                checkbox.setEnabled(False)
                self.layersTree.setItemWidget(item, 4, checkbox)
            
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
    
    def on_batch_connect_clicked(self, default_folder_id=None):
        """
        Handle click on the Batch Connect Layers button.
        
        Args:
            default_folder_id: Optional default folder ID to select
        """
        # Get all not connected layers
        not_connected_layers = []
        for i in range(self.layersTree.topLevelItemCount()):
            item = self.layersTree.topLevelItem(i)
            layer = item.data(0, Qt.UserRole)
            if layer.customProperty("maphub/map_id") is None:
                not_connected_layers.append(layer)
        
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
            item = self.layersTree.topLevelItem(i)
            checkbox = self.layersTree.itemWidget(item, 4)
            if checkbox and checkbox.isChecked():
                layer = item.data(0, Qt.UserRole)
                
                # Get synchronization direction
                direction = "auto"
                
                # Check if this is a style conflict
                widget = self.layersTree.itemWidget(item, 3)
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
                from ...utils.error_handling import ErrorManager
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