# -*- coding: utf-8 -*-
import os
import tempfile
from datetime import datetime

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal, Qt, QSize
from qgis.PyQt.QtGui import QIcon, QCursor
from qgis.core import QgsMapLayer, QgsVectorLayer, QgsRasterLayer

from .CreateFolderDialog import CreateFolderDialog
from ...utils.utils import get_maphub_client, get_layer_styles_as_json
from .MapHubBaseDialog import MapHubBaseDialog
from ...utils.error_manager import handled_exceptions

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'UploadMapDialog.ui'))


class UploadMapDialog(MapHubBaseDialog, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(UploadMapDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.iface = iface

        # Initialize folder navigation history
        self.folder_history = []
        self.selected_folder_id = None

        # Get the folder layout
        self.folder_layout = self.findChild(QtWidgets.QVBoxLayout, 'folderLayout')

        # Connect signals
        self.button_box.accepted.connect(self.upload_map)
        self.button_box.rejected.connect(self.reject)
        self.btn_create_folder.clicked.connect(self.open_create_folder_dialog)

        # Initialize UI components
        self._populate_layers_combobox()
        self._populate_workspaces_combobox()

        # Connect workspace combobox
        self.comboBox_workspace.currentIndexChanged.connect(self.on_workspace_selected)

        # Select the first workspace if available
        self.on_workspace_selected(0)

    def open_create_folder_dialog(self):
        """Open the Create Folder dialog and update folders if a new one is created."""
        # Get current workspace ID
        workspace_id = None
        if self.comboBox_workspace.currentIndex() >= 0:
            workspace_id = self.comboBox_workspace.itemData(self.comboBox_workspace.currentIndex())

        # Get current folder ID (if any)
        parent_folder_id = None
        if len(self.folder_history) > 0:
            parent_folder_id = self.folder_history[-1]

        # Open dialog with current workspace and folder
        dialog = CreateFolderDialog(
            parent=self.iface.mainWindow(),
            workspace_id=workspace_id,
            parent_folder_id=parent_folder_id
        )
        result = dialog.exec_()

        new_folder = dialog.folder

        # Reload the current folder to show the new folder
        if result and new_folder is not None and len(self.folder_history) > 0:
            current_folder_id = self.folder_history[-1]
            self.load_folder_contents(current_folder_id)

    def _populate_layers_combobox(self):
        """Populate the layer combobox with available layers."""

        # Get all open layers that are either vector or raster layers with a file location.
        layers = [
            layer for layer in self.iface.mapCanvas().layers()
            if (layer.type() in [QgsMapLayer.VectorLayer,
                                 QgsMapLayer.RasterLayer] and layer.dataProvider().dataSourceUri())
        ]
        # TODO filter out stuff like open street map layers
        if len(layers) == 0:
            raise Exception("No layers that have local files detected. Please add a layer and try again.")

        self.comboBox_layer.clear()
        for layer in layers:
            self.comboBox_layer.addItem(layer.name(), layer)

        # Connect layer combobox to map name field
        def update_map_name(index):
            if index >= 0:
                layer = self.comboBox_layer.currentData()
                if layer:
                    self.lineEdit_map_name.setText(layer.name())

        # Connect the signal
        self.comboBox_layer.currentIndexChanged.connect(update_map_name)

        # Initialize map name with first layer
        if self.comboBox_layer.count() > 0:
            update_map_name(0)

    def _populate_workspaces_combobox(self):
        """Populate the workspace combobox with available workspaces."""
        self.comboBox_workspace.clear()

        # Get the workspaces from MapHub
        client = get_maphub_client()
        workspaces = client.workspace.get_workspaces()

        for workspace in workspaces:
            workspace_id = workspace.get('id')
            workspace_name = workspace.get('name', 'Unknown Workspace')
            self.comboBox_workspace.addItem(workspace_name, workspace_id)

    def on_workspace_selected(self, index):
        """Handle workspace selection change"""
        if index < 0:
            return

        workspace_id = self.comboBox_workspace.itemData(index)
        root_folder = get_maphub_client().folder.get_root_folder(workspace_id)
        folder_id = root_folder["folder"]["id"]

        # Reset workspace history
        self.folder_history = [folder_id]
        self.selected_folder_id = folder_id

        # Load folder contents
        self.load_folder_contents(folder_id)

    def clear_folder_layout(self):
        """Clear all widgets from the folder layout"""
        for i in reversed(range(self.folder_layout.count())):
            widget = self.folder_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

    def load_folder_contents(self, folder_id):
        """Load subfolders for a folder"""
        # Clear any existing items
        self.clear_folder_layout()

        # Get folder details including child folders
        folder_details = get_maphub_client().folder.get_folder(folder_id)
        child_folders = folder_details.get("child_folders", [])

        # Add navigation controls if we have folder history
        if self.folder_history:
            self.add_navigation_controls()

        # Display child folders
        for folder in child_folders:
            self.add_folder_item(folder)

    def add_navigation_controls(self):
        """Add navigation controls for folder browsing"""
        nav_frame = QtWidgets.QFrame()
        nav_frame.setStyleSheet("background-color: #f0f0f0; border-radius: 4px;")
        nav_layout = QtWidgets.QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(5, 5, 5, 5)
        nav_layout.setSpacing(5)

        # Add "Back" button if we have history
        if len(self.folder_history) > 1:
            btn_back = QtWidgets.QPushButton("← Back")
            btn_back.setToolTip("Go back to previous folder")
            btn_back.clicked.connect(self.navigate_back)
            nav_layout.addWidget(btn_back)

        # Add current path display
        if self.folder_history:
            current_folder_id = self.folder_history[-1]
            folder_details = get_maphub_client().folder.get_folder(current_folder_id)
            folder_name = folder_details.get("folder", {}).get("name", "Unknown Folder")

            path_label = QtWidgets.QLabel(f"Current folder: {folder_name}")
            path_label.setStyleSheet("font-weight: bold;")
            nav_layout.addWidget(path_label)

        # Add spacer
        nav_layout.addItem(QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))

        # Add to layout
        self.folder_layout.addWidget(nav_frame)

    def navigate_back(self):
        """Handle click on the back button"""
        if len(self.folder_history) > 1:
            # Remove the current folder from history
            self.folder_history.pop()

            # Load the previous folder
            previous_folder_id = self.folder_history[-1]
            self.selected_folder_id = previous_folder_id
            self.load_folder_contents(previous_folder_id)

    def on_folder_clicked(self, folder_id):
        """Handle click on a folder item to navigate into it"""
        # Add the folder to the navigation history
        self.folder_history.append(folder_id)
        self.selected_folder_id = folder_id

        # Load the contents of the clicked folder
        self.load_folder_contents(folder_id)

    def add_folder_item(self, folder_data):
        """Create a frame for each folder item."""
        item_frame = QtWidgets.QFrame()
        item_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        item_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        item_frame.setMinimumHeight(40)

        # Set margin and spacing for a more compact look
        item_layout = QtWidgets.QHBoxLayout(item_frame)
        item_layout.setContentsMargins(5, 5, 5, 5)
        item_layout.setSpacing(5)

        # Add folder icon
        folder_icon = QIcon.fromTheme("folder", QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))
        folder_icon_label = QtWidgets.QLabel()
        folder_icon_label.setPixmap(folder_icon.pixmap(24, 24))
        item_layout.addWidget(folder_icon_label)

        # Folder name
        name_label = QtWidgets.QLabel(folder_data.get('name', 'Unnamed Folder'))
        font = name_label.font()
        font.setBold(True)
        name_label.setFont(font)
        item_layout.addWidget(name_label)

        # Add spacer
        item_layout.addItem(QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))

        # Store folder_id in the frame for later reference
        item_frame.setProperty("folder_id", folder_data['id'])

        # Check if this is the selected folder
        if self.selected_folder_id and folder_data['id'] == self.selected_folder_id:
            # Highlight the selected folder
            item_frame.setStyleSheet("background-color: #e0f0ff;")

        # Make the entire frame clickable to navigate into the folder
        item_frame.setCursor(QCursor(Qt.PointingHandCursor))
        item_frame.mousePressEvent = lambda event: self.on_folder_clicked(folder_data['id'])

        # Add to layout
        self.folder_layout.addWidget(item_frame)

    def closeEvent(self, event):
        """Override closeEvent to emit the closingPlugin signal."""
        self.closingPlugin.emit()
        event.accept()

    @handled_exceptions
    def upload_map(self):
        """Upload the selected layer to MapHub."""
        # Get the selected layer
        layer = self.comboBox_layer.currentData()
        if not layer:
            raise Exception("No layer selected.")

        # Get the map name
        map_name = self.lineEdit_map_name.text().strip()
        if not map_name:
            raise Exception("Map name is required.")

        # Get the selected folder
        if not self.selected_folder_id:
            raise Exception("No folder selected.")

        # Get the map privacy setting
        is_public = self.checkBox_public.isChecked()

        # Create a temporary directory to store the files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Get the layer file path
            layer_path = layer.source()
            if '|' in layer_path:  # Handle layers with query parameters
                layer_path = layer_path.split('|')[0]

            # Determine the file extension based on layer type
            if isinstance(layer, QgsVectorLayer):
                file_extension = os.path.splitext(layer_path)[1]
                if not file_extension:
                    file_extension = '.gpkg'  # Default to GeoPackage
            elif isinstance(layer, QgsRasterLayer):
                file_extension = os.path.splitext(layer_path)[1]
                if not file_extension:
                    file_extension = '.tif'  # Default to GeoTIFF
            else:
                raise Exception("Unsupported layer type.")

            # Create a temporary file path
            temp_file = os.path.join(temp_dir, f"{map_name}{file_extension}")

            # Copy the layer file to the temporary directory
            if os.path.exists(layer_path):
                # For file-based layers, copy the file
                with open(layer_path, 'rb') as src_file:
                    with open(temp_file, 'wb') as dst_file:
                        dst_file.write(src_file.read())

                # For shapefiles, copy all related files
                if file_extension.lower() == '.shp':
                    base_name = os.path.splitext(layer_path)[0]
                    for ext in ['.dbf', '.shx', '.prj', '.qpj', '.cpg']:
                        related_file = f"{base_name}{ext}"
                        if os.path.exists(related_file):
                            with open(related_file, 'rb') as src_file:
                                with open(os.path.join(temp_dir, f"{map_name}{ext}"), 'wb') as dst_file:
                                    dst_file.write(src_file.read())
            else:
                # For memory layers or other non-file layers, save to a new file
                raise Exception("Layer is not file-based. Please save it to a file first.")

            # Get the layer style
            style_json = get_layer_styles_as_json(layer, {})

            # Upload the map to MapHub
            client = get_maphub_client()
            result = client.maps.upload_map(
                map_name,
                self.selected_folder_id,
                public=is_public,
                path=temp_file
            )
            
            # Get the map ID from the result
            map_id = result.get('map_id')

            # Update the layer visuals with the uploaded map style
            client.maps.set_visuals(map_id, style_json)
            
            # Connect the layer to the uploaded map
            if map_id:
                # Get the layer's source path
                source_path = layer.source()
                if '|' in source_path:  # Handle layers with query parameters
                    source_path = source_path.split('|')[0]
                
                # Connect the layer to MapHub
                from ...utils.sync_manager import MapHubSyncManager
                sync_manager = MapHubSyncManager(self.iface)
                sync_manager.connect_layer(
                    layer,
                    map_id,
                    self.selected_folder_id,
                    source_path
                )
                
                # Show success message with connection information
                QtWidgets.QMessageBox.information(
                    self,
                    "Upload Successful",
                    f"Map '{map_name}' has been uploaded to MapHub and connected to the selected layer."
                )
            else:
                # Show success message without connection information
                QtWidgets.QMessageBox.information(
                    self,
                    "Upload Successful",
                    f"Map '{map_name}' has been uploaded to MapHub."
                )

            # Close the dialog
            self.accept()