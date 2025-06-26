# -*- coding: utf-8 -*-

import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, QSettings
from qgis.PyQt.QtWidgets import QLineEdit, QMessageBox

from ...utils import handled_exceptions, get_maphub_client
from .MapHubBaseDialog import MapHubBaseDialog

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'CreateFolderDialog.ui'))


class CreateFolderDialog(MapHubBaseDialog, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None, workspace_id=None, parent_folder_id=None):
        """Constructor."""
        super(CreateFolderDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        self.setupUi(self)

        # Store workspace and parent folder IDs
        self.workspace_id = workspace_id
        self.parent_folder_id = parent_folder_id

        # Get default workspace from settings if not provided
        if self.workspace_id is None:
            self.settings = QSettings()
            self.workspace_id = self.settings.value("project_manager/workspace", "")

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

        client = get_maphub_client()

        # Use provided parent folder ID if available
        if self.parent_folder_id is None:
            # If no parent folder ID is provided, use the root folder of the workspace
            if self.workspace_id is None:
                # If no workspace ID is provided, use the personal workspace
                personal_workspace = client.workspace.get_personal_workspace()
                self.workspace_id = personal_workspace["id"]

            # Get the root folder of the workspace
            root_folder = client.folder.get_root_folder(self.workspace_id)
            self.parent_folder_id = root_folder["folder"]["id"]

        # Create the folder
        folder = client.folder.create_folder(folder_name, self.parent_folder_id)
        self.folder = folder

    def closeEvent(self, event):
        """Override closeEvent to emit the closingPlugin signal."""
        self.closingPlugin.emit()
        event.accept()