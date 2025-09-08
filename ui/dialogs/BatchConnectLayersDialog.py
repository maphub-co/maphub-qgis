import os
from datetime import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem, QCheckBox, QHeaderView, QMessageBox, QDialog
from PyQt5.QtGui import QIcon
from qgis.PyQt import uic
from qgis.core import QgsProject

from ...maphub.exceptions import APIException
from ...utils.sync_manager import MapHubSyncManager
from .MapHubBaseDialog import MapHubBaseDialog
from ..widgets.WorkspaceNavigationWidget import WorkspaceNavigationWidget
from ...utils.utils import get_maphub_client
from ...utils.error_manager import ErrorManager, handled_exceptions

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'BatchConnectLayersDialog.ui'))

class BatchConnectLayersDialog(MapHubBaseDialog, FORM_CLASS):
    """Dialog for batch connecting layers to MapHub."""
    
    def __init__(self, iface, layers, parent=None, default_folder_id=None):
        """
        Initialize the dialog.
        
        Args:
            iface: The QGIS interface
            layers: List of layers to connect
            parent: Parent widget
            default_folder_id: Optional default folder ID to select
        """
        super(BatchConnectLayersDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.layers = layers
        self.default_folder_id = default_folder_id
        
        # Initialize MapHub client
        self.client = get_maphub_client()
        
        # Set up the dialog
        self.populate_layers()
        
        # Create workspace navigation widget with default folder
        self.workspace_nav_widget = WorkspaceNavigationWidget(
            self, 
            folder_select_mode=True,
            default_folder_id=default_folder_id
        )
        
        # Add it to the dialog layout
        self.folderSelectionLayout.addWidget(self.workspace_nav_widget)
        
        # Connect signals
        self.workspace_nav_widget.folder_selected.connect(self.on_folder_selected)
        self.selectAllButton.clicked.connect(self.on_select_all_clicked)
        self.selectNoneButton.clicked.connect(self.on_select_none_clicked)
        self.connectButton.clicked.connect(self.on_connect_clicked)
    
    def populate_layers(self):
        """Populate the tree widget with layers."""
        self.layersTree.clear()
        
        for layer in self.layers:
            item = QTreeWidgetItem(self.layersTree)
            item.setText(0, layer.name())
            
            # Add checkbox for selection
            checkbox = QCheckBox()
            checkbox.setChecked(True)  # Select all by default
            self.layersTree.setItemWidget(item, 1, checkbox)
            
            # Store layer reference
            item.setData(0, Qt.UserRole, layer)
    
    def on_select_all_clicked(self):
        """Handle click on the Select All button."""
        for i in range(self.layersTree.topLevelItemCount()):
            item = self.layersTree.topLevelItem(i)
            checkbox = self.layersTree.itemWidget(item, 1)
            if checkbox:
                checkbox.setChecked(True)
    
    def on_select_none_clicked(self):
        """Handle click on the Select None button."""
        for i in range(self.layersTree.topLevelItemCount()):
            item = self.layersTree.topLevelItem(i)
            checkbox = self.layersTree.itemWidget(item, 1)
            if checkbox:
                checkbox.setChecked(False)
    
    def on_folder_selected(self, folder_id):
        """Handle folder selection."""
        # This is handled by the WorkspaceNavigationWidget
        pass
    
    @handled_exceptions
    def on_connect_clicked(self, checked=False):
        """Handle click on the Connect button."""
        # Get selected layers
        selected_layers = []
        for i in range(self.layersTree.topLevelItemCount()):
            item = self.layersTree.topLevelItem(i)
            checkbox = self.layersTree.itemWidget(item, 1)
            if checkbox and checkbox.isChecked():
                layer = item.data(0, Qt.UserRole)
                selected_layers.append(layer)
        
        if not selected_layers:
            QMessageBox.information(
                self,
                "No Layers Selected",
                "Please select at least one layer to connect."
            )
            return
        
        # Get selected folder
        folder_id = self.workspace_nav_widget.get_selected_folder_id()
        if not folder_id:
            QMessageBox.information(
                self,
                "No Folder Selected",
                "Please select a destination folder."
            )
            return
        
        # Create and show progress dialog
        from ..widgets.ProgressDialog import ProgressDialog
        progress = ProgressDialog("Connecting Layers", "Preparing to connect...", self)
        progress.set_progress(0, len(selected_layers))
        progress.show()
        
        # Connect selected layers
        success_count = 0
        for i, layer in enumerate(selected_layers):
            progress.set_message(f"Connecting layer '{layer.name()}'...")
            progress.set_progress(i)
            
            try:
                # Upload the layer as a new map
                sync_manager = MapHubSyncManager(self.iface)
                sync_manager.add_layer(
                    layer=layer,
                    map_name=layer.name(),
                    folder_id=folder_id,
                    public=False
                )

                success_count += 1
            except APIException:
                # Re-raise APIException to be handled by the decorator
                raise
            except Exception as e:
                ErrorManager.show_error(f"Failed to connect layer '{layer.name()}'", e, self)

        
        # Close progress dialog
        progress.accept()
        
        # Show success message
        QMessageBox.information(
            self,
            "Connection Complete",
            f"Successfully connected {success_count} of {len(selected_layers)} layer(s) to MapHub."
        )
        
        # Close dialog
        self.accept()