# -*- coding: utf-8 -*-

import os
from typing import List, Dict, Any

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsMapLayer, QgsVectorLayer, QgsRasterLayer

from .CreateProjectDialog import CreateProjectDialog
from ..utils import get_maphub_client

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
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.btn_create_project.clicked.connect(self.open_create_project_dialog)

        self._populate_layers_combobox()
        self._populate_projects_combobox()

    def open_create_project_dialog(self):
        """Open the Create Project dialog and update projects if a new one is created."""
        dialog = CreateProjectDialog(self.iface.mainWindow())
        result = dialog.exec_()

        new_project = dialog.project

        # Update selectable project list.
        self._populate_projects_combobox()

        # Select the newly created project
        if result and new_project is not None:
            for i in range(self.comboBox_project.count()):
                project = self.comboBox_project.itemData(i)
                if project.get("id") == new_project.get("id"):
                    self.comboBox_project.setCurrentIndex(i)
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

    def _populate_projects_combobox(self):
        """Populate the options combobox with items returned from a function."""
        self.comboBox_project.clear()

        projects = get_maphub_client().get_projects()
        if len(projects) == 0:
            raise Exception("You do not yet have any projects. Please create one on https://maphub.co/dashboard/projects and try again.")

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

    def get_map_name(self):
        """Return the user-specified map name."""
        return self.lineEdit_map_name.text()

    def closeEvent(self, event):
        """Override closeEvent to emit the closingPlugin signal."""
        self.closingPlugin.emit()
        event.accept()
