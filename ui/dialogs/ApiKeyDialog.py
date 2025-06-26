# -*- coding: utf-8 -*-

import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, QSettings
from qgis.PyQt.QtWidgets import QLineEdit

from .MapHubBaseDialog import MapHubBaseDialog

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ApiKeyDialog.ui'))


class ApiKeyDialog(MapHubBaseDialog, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(ApiKeyDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        self.setupUi(self)

        # Load API key if it exists
        settings = QSettings()
        api_key = settings.value("MapHubPlugin/api_key", "")
        self.lineEdit_apikey.setText(api_key)

        # Connect show/hide password button
        self.toolButton_showHide.toggled.connect(self.toggle_password_visibility)

        # Connect signals
        self.button_box.accepted.connect(self.save_api_key)
        self.button_box.rejected.connect(self.reject)

    def toggle_password_visibility(self, checked):
        """Toggle the visibility of the API key text."""
        if checked:
            self.lineEdit_apikey.setEchoMode(QLineEdit.Normal)
        else:
            self.lineEdit_apikey.setEchoMode(QLineEdit.Password)

    def save_api_key(self):
        """Save the API key to QSettings."""
        api_key = self.lineEdit_apikey.text().strip()
        if api_key:
            settings = QSettings()
            settings.setValue("MapHubPlugin/api_key", api_key)
            self.accept()
        else:
            # Show an error message if API key is empty
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "API Key Required",
                "Please enter a valid API key to continue."
            )

    def get_api_key(self):
        """Return the entered API key."""
        return self.lineEdit_apikey.text().strip()

    def closeEvent(self, event):
        """Override closeEvent to emit the closingPlugin signal."""
        self.closingPlugin.emit()
        event.accept()
