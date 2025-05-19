# -*- coding: utf-8 -*-

import os
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal, QSettings
from qgis.PyQt.QtWidgets import QLineEdit, QMessageBox

from ..utils import handled_exceptions, get_maphub_client

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'CreateFolderDialog.ui'))


class CreateFolderDialog(QtWidgets.QDialog, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(CreateFolderDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        self.setupUi(self)

        # Get default workspace from settings
        self.settings = QSettings()
        self.workspace = self.settings.value("project_manager/workspace", "")

        # Connect signals to slots
        self.button_box.accepted.connect(self.create_folder)
        self.button_box.rejected.connect(self.reject)

        self.folder = None

    @handled_exceptions
    def create_folder(self):
        """Create the folder with the given name"""
        folder_name = self.lineEdit_folderName.text().strip()

        if not folder_name:
            raise Exception("Folder name needs to be set.")

        # Get the root folder to use as parent
        client = get_maphub_client()
        personal_workspace = client.workspace.get_personal_workspace()
        root_folder = client.folder.get_root_folder(personal_workspace["id"])
        parent_folder_id = root_folder["folder"]["id"]
        
        # Create the folder
        folder = client.folder.create_folder(folder_name, parent_folder_id)
        self.folder = folder

    def closeEvent(self, event):
        """Override closeEvent to emit the closingPlugin signal."""
        self.closingPlugin.emit()
        event.accept()