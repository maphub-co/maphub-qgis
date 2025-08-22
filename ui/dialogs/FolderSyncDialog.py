import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem, QCheckBox, QHeaderView, QMessageBox, QComboBox
from qgis.PyQt import uic

from .MapHubBaseDialog import MapHubBaseDialog
from ...utils.sync_manager import MapHubSyncManager
from ...utils.layer_decorator import MapHubLayerDecorator
from ...utils.utils import get_maphub_client
from ...utils.error_manager import handled_exceptions

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'FolderSyncDialog.ui'))


class FolderSyncDialog(MapHubBaseDialog, FORM_CLASS):
    """
    Dialog for synchronizing maps in a folder with MapHub.
    
    This dialog displays a list of maps in a folder and allows
    the user to select which maps to synchronize.
    """
    
    def __init__(self, folder_id, iface, parent=None):
        """
        Initialize the dialog.
        
        Args:
            folder_id: The ID of the folder to synchronize
            iface: The QGIS interface
            parent: The parent widget
        """
        super(FolderSyncDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.folder_id = folder_id
        
        # Initialize sync manager
        self.sync_manager = MapHubSyncManager(iface)
        
        # Configure tree widget
        self.mapsTree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        
        # Connect signals
        self.syncButton.clicked.connect(self.on_sync_clicked)
        self.selectAllButton.clicked.connect(self.on_select_all_clicked)
        self.selectNoneButton.clicked.connect(self.on_select_none_clicked)
        
        # Populate the tree with maps in the folder
        self.populate_maps()
        
    @handled_exceptions
    def populate_maps(self):
        """Populate the tree widget with maps in the folder."""
        # Get folder details
        try:
            folder_details = get_maphub_client().folder.get_folder(self.folder_id)
            
            # Set dialog title to include folder name
            folder_name = folder_details.get('name', 'Unknown Folder')
            self.setWindowTitle(f"Synchronize Folder '{folder_name}' with MapHub")
            
            # Get maps in folder
            maps = folder_details.get("map_infos", [])
            
            # If no maps, show a message and close the dialog
            if not maps:
                QMessageBox.information(
                    self,
                    "No Maps Found",
                    f"No maps found in folder '{folder_name}'."
                )
                self.reject()
                return
            
            # Add maps to tree
            for map_data in maps:
                item = QTreeWidgetItem(self.mapsTree)
                item.setText(0, map_data.get('name', 'Unnamed Map'))
                item.setText(1, map_data.get('type', 'unknown'))
                
                # Find connected layer
                connected_layer = self.sync_manager.find_layer_by_map_id(map_data.get('id'))
                
                if connected_layer:
                    # Get synchronization status
                    status = self.sync_manager.get_layer_sync_status(connected_layer)
                    item.setText(2, status)
                    
                    # Set action based on status
                    if status == "local_modified":
                        item.setText(3, "Upload to MapHub")
                    elif status == "remote_newer":
                        item.setText(3, "Update from MapHub")
                    elif status == "style_changed":
                        # For style conflicts, add a combo box with options
                        style_combo = QComboBox()
                        style_combo.addItems(["Keep Local Style", "Use Remote Style"])
                        self.mapsTree.setItemWidget(item, 3, style_combo)
                    elif status == "in_sync":
                        item.setText(3, "No Action Needed")
                    elif status == "file_missing":
                        item.setText(3, "File Missing")
                    elif status == "remote_error":
                        item.setText(3, "Remote Error")
                else:
                    # Not connected to a local layer
                    item.setText(2, "Not Connected")
                    item.setText(3, "Download")
                
                # Add checkbox for selection
                checkbox = QCheckBox()
                checkbox.setChecked(connected_layer is None or 
                                   (status != "in_sync" and status != "file_missing" and status != "remote_error"))
                self.mapsTree.setItemWidget(item, 4, checkbox)
                
                # Store map data and connected layer
                item.setData(0, Qt.UserRole, {
                    'map_data': map_data,
                    'connected_layer': connected_layer
                })
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Folder",
                f"An error occurred while loading folder data: {str(e)}"
            )
            self.reject()
    
    def on_select_all_clicked(self):
        """Handle click on the Select All button."""
        for i in range(self.mapsTree.topLevelItemCount()):
            item = self.mapsTree.topLevelItem(i)
            checkbox = self.mapsTree.itemWidget(item, 4)
            checkbox.setChecked(True)
    
    def on_select_none_clicked(self):
        """Handle click on the Select None button."""
        for i in range(self.mapsTree.topLevelItemCount()):
            item = self.mapsTree.topLevelItem(i)
            checkbox = self.mapsTree.itemWidget(item, 4)
            checkbox.setChecked(False)
    
    @handled_exceptions
    def on_sync_clicked(self):
        """Handle click on the Synchronize Selected button."""
        # Get selected maps
        selected_maps = []
        for i in range(self.mapsTree.topLevelItemCount()):
            item = self.mapsTree.topLevelItem(i)
            checkbox = self.mapsTree.itemWidget(item, 4)
            if checkbox.isChecked():
                item_data = item.data(0, Qt.UserRole)
                map_data = item_data.get('map_data')
                connected_layer = item_data.get('connected_layer')
                status = item.text(2)
                
                # Determine action based on connection status and synchronization status
                if connected_layer:
                    # Determine synchronization direction
                    direction = "auto"
                    if status == "style_changed":
                        # Get the selected style resolution option
                        style_combo = self.mapsTree.itemWidget(item, 3)
                        if style_combo.currentText() == "Keep Local Style":
                            direction = "push"
                        else:  # "Use Remote Style"
                            direction = "pull"
                    
                    selected_maps.append({
                        'map_data': map_data,
                        'connected_layer': connected_layer,
                        'action': 'sync',
                        'direction': direction
                    })
                else:
                    # Not connected, download the map
                    selected_maps.append({
                        'map_data': map_data,
                        'connected_layer': None,
                        'action': 'download',
                        'direction': None
                    })
        
        # If no maps selected, show a message
        if not selected_maps:
            QMessageBox.information(
                self,
                "No Maps Selected",
                "Please select at least one map to synchronize."
            )
            return
        
        # Process selected maps
        for map_info in selected_maps:
            if map_info['action'] == 'sync':
                # Synchronize connected layer
                self.sync_manager.synchronize_layer(map_info['connected_layer'], map_info['direction'])
            elif map_info['action'] == 'download':
                # Download the map
                from ...utils.map_operations import download_map
                download_map(map_info['map_data'], self)
        
        # Update layer icons
        layer_decorator = MapHubLayerDecorator(self.iface)
        layer_decorator.update_layer_icons()
        
        # Close dialog
        self.accept()