# -*- coding: utf-8 -*-
import glob
import os
import tempfile
import zipfile

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal, Qt, QSize
from qgis.PyQt.QtGui import QIcon, QCursor
from qgis.core import QgsMapLayer, QgsVectorLayer, QgsRasterLayer

from .CreateFolderDialog import CreateFolderDialog
from ..utils import get_maphub_client, handled_exceptions, show_error_dialog

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'UploadMapDialog.ui'))


class UploadMapDialog(QtWidgets.QDialog, FORM_CLASS):
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

        # Set initial value if there's a layer selected
        update_map_name(0)

    def _populate_workspaces_combobox(self):
        """Populate the workspace combobox with available workspaces."""
        self.comboBox_workspace.clear()

        # Get workspaces
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

        # Reset folder history
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
        """Load folders for a folder"""
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

        # Update the selected folder ID
        self.selected_folder_id = folder_id

    def add_navigation_controls(self):
        """Add navigation controls for folder browsing"""
        nav_frame = QtWidgets.QFrame()
        nav_frame.setStyleSheet("background-color: #f0f0f0; border-radius: 4px;")
        nav_layout = QtWidgets.QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(5, 5, 5, 5)
        nav_layout.setSpacing(5)

        # Back button
        back_button = QtWidgets.QPushButton("← Back")
        back_button.setMaximumWidth(80)
        back_button.clicked.connect(self.navigate_back)
        back_button.setEnabled(len(self.folder_history) > 1)
        nav_layout.addWidget(back_button)

        # Current folder path
        if self.folder_history:
            # Get the current folder details
            folder_id = self.folder_history[-1]
            folder_details = get_maphub_client().folder.get_folder(folder_id)
            folder_name = folder_details["folder"].get("name", "Unknown Folder")

            # Create a label for the current folder
            current_folder_label = QtWidgets.QLabel(f"Current folder: {folder_name}")
            current_folder_label.setStyleSheet("font-weight: bold;")
            nav_layout.addWidget(current_folder_label)

        # Add spacer
        nav_layout.addItem(QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))

        # Add to layout before the list items
        self.folder_layout.addWidget(nav_frame)

    def navigate_back(self):
        """Navigate back to the previous folder"""
        if len(self.folder_history) > 1:
            # Remove the current folder from history
            self.folder_history.pop()

            # Get the previous folder
            previous_folder_id = self.folder_history[-1]

            # Load the previous folder without adding to history
            self.load_folder_contents(previous_folder_id)

    def on_folder_clicked(self, folder_id):
        """Handle click on a folder item"""
        # Add the folder to the navigation history
        self.folder_history.append(folder_id)

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
        folder_icon_label = QtWidgets.QLabel()
        folder_icon_label.setFixedSize(24, 24)
        folder_icon_label.setScaledContents(True)

        # Use a standard folder icon from Qt
        folder_icon = QIcon.fromTheme("folder", QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))
        pixmap = folder_icon.pixmap(QSize(24, 24))
        folder_icon_label.setPixmap(pixmap)

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

        # Check if this is the current folder
        if self.folder_history and folder_data['id'] == self.folder_history[-1]:
            # Highlight the current folder
            item_frame.setStyleSheet("background-color: #e0f0ff;")

        # Make the entire frame clickable
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
        client = get_maphub_client()

        # Get selected values
        selected_name = self.lineEdit_map_name.text()
        if not selected_name:
            return show_error_dialog("No name selected")

        selected_layer = self.comboBox_layer.currentData()
        if selected_layer is None:
            return show_error_dialog("No layer selected")
        file_path = selected_layer.dataProvider().dataSourceUri().split('|')[0]

        if self.selected_folder_id is None:
            return show_error_dialog("No destination folder selected. Please select a folder.")

        selected_public = self.checkBox_public.isChecked()

        if file_path.lower().endswith('.shp') or file_path.lower().endswith('.shx') or file_path.lower().endswith('.dbf'):  # Shapefiles
            base_dir = os.path.dirname(file_path)
            file_name = os.path.splitext(os.path.basename(file_path))[0]

            # Create temporary zip file
            temp_zip = tempfile.mktemp(suffix='.zip')

            with zipfile.ZipFile(temp_zip, 'w') as zipf:
                # Find all files with same basename but different extensions
                pattern = os.path.join(base_dir, file_name + '.*')
                shapefile_parts = glob.glob(pattern)

                for part_file in shapefile_parts:
                    # Add file to zip with just the filename (not full path)
                    zipf.write(part_file, os.path.basename(part_file))

            # Upload layer to MapHub
            client.maps.upload_map(
                map_name=selected_name,
                folder_id=self.selected_folder_id,
                public=selected_public,
                path=temp_zip,
            )

        else:
            # Upload layer to MapHub
            client.maps.upload_map(
                map_name=selected_name,
                folder_id=self.selected_folder_id,
                public=selected_public,
                path=file_path,
            )

        return None
