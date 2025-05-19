# -*- coding: utf-8 -*-
import glob
import os
import tempfile
import zipfile

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsMapLayer, QgsVectorLayer, QgsRasterLayer

from .CreateFolderDialog import CreateFolderDialog
from ..utils import get_maphub_client, handled_exceptions, show_error_dialog

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'UploadMapDialog.ui'))


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

        # Connect signals
        self.button_box.accepted.connect(self.upload_map)
        self.button_box.rejected.connect(self.reject)
        self.btn_create_folder.clicked.connect(self.open_create_folder_dialog)

        self._populate_layers_combobox()
        self._populate_folders_combobox()

    def open_create_folder_dialog(self):
        """Open the Create Folder dialog and update folders if a new one is created."""
        dialog = CreateFolderDialog(self.iface.mainWindow())
        result = dialog.exec_()

        new_folder = dialog.folder

        # Update selectable folder list.
        self._populate_folders_combobox()

        # Select the newly created folder
        if result and new_folder is not None:
            for i in range(self.comboBox_folder.count()):
                folder = self.comboBox_folder.itemData(i)
                if folder.get("id") == new_folder.get("id"):
                    self.comboBox_folder.setCurrentIndex(i)
                    break

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

    def _populate_folders_combobox(self):
        """Populate the options combobox with items returned from a function."""
        self.comboBox_folder.clear()

        # Get the root folder to find child folders
        client = get_maphub_client()
        personal_workspace = client.workspace.get_personal_workspace()
        root_folder = client.folder.get_root_folder(personal_workspace["id"])
        folders = root_folder.get("child_folders", [])

        if len(folders) == 0:
            raise Exception("You do not yet have any folders. Please create one using the 'Create New Folder' button and try again.")

        for folder in folders:
            self.comboBox_folder.addItem(folder["name"], folder)

    def closeEvent(self, event):
        """Override closeEvent to emit the closingPlugin signal."""
        self.closingPlugin.emit()
        event.accept()

    @handled_exceptions
    def upload_map(self):
        client = get_maphub_client()

        # Get selected values
        selected_name = self.lineEdit_map_name.text()
        if selected_name is None:
            return show_error_dialog("No name selected")

        selected_layer = self.comboBox_layer.currentData()
        if selected_layer is None:
            return show_error_dialog("No layer selected")
        file_path = selected_layer.dataProvider().dataSourceUri().split('|')[0]

        selected_folder = self.comboBox_folder.currentData()
        if selected_folder is None:
            return show_error_dialog("No folder selected")

        selected_public = self.checkBox_public.isChecked()

        if file_path.lower().endswith('.shp'):  # Shapefiles
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
                folder_id=selected_folder["id"],
                public=selected_public,
                path=temp_zip,
            )

        else:
            # Upload layer to MapHub
            client.maps.upload_map(
                map_name=selected_name,
                folder_id=selected_folder["id"],
                public=selected_public,
                path=file_path,
            )

        return None
