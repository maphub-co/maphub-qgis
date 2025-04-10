# -*- coding: utf-8 -*-

import os
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal, QSettings
from qgis.PyQt.QtWidgets import QLineEdit, QMessageBox

from ..utils import handled_exceptions, get_maphub_client

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'CreateProjectDialog.ui'))


class CreateProjectDialog(QtWidgets.QDialog, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(CreateProjectDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        self.setupUi(self)

        # Get default workspace from settings
        self.settings = QSettings()
        self.workspace = self.settings.value("project_manager/workspace", "")

        # Connect signals to slots
        self.button_box.accepted.connect(self.create_project)
        self.button_box.rejected.connect(self.reject)

        self.project = None

    @handled_exceptions
    def create_project(self):
        """Create the project with the given name"""
        project_name = self.lineEdit_projectName.text().strip()

        if not project_name:
            raise Exception("Project name needs to be set.")

        project = get_maphub_client().create_project(project_name)
        self.project = project

    def closeEvent(self, event):
        """Override closeEvent to emit the closingPlugin signal."""
        self.closingPlugin.emit()
        event.accept()
