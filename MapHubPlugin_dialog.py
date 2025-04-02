# -*- coding: utf-8 -*-

import os
from typing import List, Dict, Any

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'MapHubPlugin_dialog_base.ui'))


class MapHubPluginDialog(QtWidgets.QDialog, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(MapHubPluginDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # Connect signals
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def populate_layers_combobox(self, layers):
        """Populate the layer combobox with available layers."""
        self.comboBox_layer.clear()
        for layer in layers:
            self.comboBox_layer.addItem(layer.name(), layer)

    def populate_projects_combobox(self, projects: List[Dict[str, Any]]):
        """Populate the options combobox with items returned from a function."""
        self.comboBox_project.clear()
        for project in projects:
            self.comboBox_project.addItem(project["name"], project)

    def get_selected_layer(self):
        """Return the currently selected layer."""
        return self.comboBox_layer.currentData()

    def get_selected_project(self):
        """Return the currently selected option."""
        return self.comboBox_project.currentData()

    def get_selected_public(self):
        """Return whether the map should be uploaded publicly."""
        return self.checkBox_public.isChecked()

    def set_default_map_name(self, name):
        """Set the default map name based on the selected layer."""
        self.lineEdit_map_name.setText(name)

    def get_map_name(self):
        """Return the user-specified map name."""
        return self.lineEdit_map_name.text()

    def closeEvent(self, event):
        """Override closeEvent to emit the closingPlugin signal."""
        self.closingPlugin.emit()
        event.accept()
