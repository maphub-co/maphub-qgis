# -*- coding: utf-8 -*-

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal, QSettings, Qt, QByteArray
from qgis.PyQt.QtGui import QColor, QPixmap
from qgis.PyQt.QtWidgets import QLineEdit, QFileDialog, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, QByteArray
from PyQt5.QtGui import QPixmap
from qgis.core import QgsVectorTileLayer, QgsRasterLayer, QgsProject, QgsDataSourceUri


from ..utils import handled_exceptions
from ..utils import get_maphub_client


class ThumbnailLoader(QThread):
    thumbnail_loaded = pyqtSignal(str, QByteArray)  # map_id, thumbnail data

    def __init__(self, map_id):
        super().__init__()
        self.map_id = map_id

    def run(self):
        try:
            thumb_data = get_maphub_client().get_thumbnail(self.map_id)
            self.thumbnail_loaded.emit(self.map_id, QByteArray(thumb_data))
        except Exception as e:
            print(f"Error loading thumbnail for map {self.map_id}: {e}")


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'GetMapDialog.ui'))


class GetMapDialog(QtWidgets.QDialog, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(GetMapDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        self.setupUi(self)

        self.iface = iface
        self.thumb_loaders = []

        self.list_layout = self.findChild(QtWidgets.QVBoxLayout, 'listLayout')

        self._populate_projects_combobox()

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def closeEvent(self, event):
        """Override closeEvent to emit the closingPlugin signal."""
        self.closingPlugin.emit()
        event.accept()

    def load_map_items(self, project_id):
        # Clear any existing items
        self.thumb_loaders = []
        for i in reversed(range(self.list_layout.count())):
            widget = self.list_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        # Get maps
        maps = get_maphub_client().get_maps(project_id)

        # Add the map items to the list
        for map_data in maps:
            self.add_map_item(map_data)

    def _populate_projects_combobox(self):
        """Populate the options combobox with items returned from a function."""
        self.comboBox_project.clear()

        projects = get_maphub_client().get_projects()
        if len(projects) == 0:
            raise Exception(
                "You do not yet have any projects. Please create one on https://maphub.co/dashboard/projects and try again.")

        for project in projects:
            self.comboBox_project.addItem(project["name"], project)

        # Connect layer combobox to map name field
        def update_project(index):
            if index >= 0:
                selected_project = self.comboBox_project.currentData()
                if selected_project:
                    self.load_map_items(selected_project["id"])

        # Connect the signal
        self.comboBox_project.currentIndexChanged.connect(update_project)

        update_project(0)

    def add_map_item(self, map_data):
        """Create a frame for each list item."""
        item_frame = QtWidgets.QFrame()
        item_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        item_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        item_frame.setMinimumHeight(128)

        # Create layout for the item
        item_layout = QtWidgets.QHBoxLayout(item_frame)

        # Add image
        image_label = QtWidgets.QLabel()
        image_label.setFixedSize(128, 128)
        image_label.setScaledContents(True)

        # Set a placeholder image while loading
        placeholder_pixmap = QPixmap(128, 128)
        placeholder_pixmap.fill(QColor(200, 200, 200))  # Light gray
        image_label.setPixmap(placeholder_pixmap)

        # Store map_id in the label for later reference
        image_label.setProperty("map_id", map_data['id'])

        item_layout.addWidget(image_label)

        # Start loading the thumbnail in a separate thread
        thumb_loader = ThumbnailLoader(map_data['id'])
        thumb_loader.thumbnail_loaded.connect(self.update_thumbnail)
        thumb_loader.start()

        self.thumb_loaders.append(thumb_loader)

        # Add description section
        desc_layout = QtWidgets.QVBoxLayout()

        # Map name
        name_label = QtWidgets.QLabel(map_data.get('name', 'Unnamed Map'))
        font = name_label.font()
        font.setBold(True)
        name_label.setFont(font)
        desc_layout.addWidget(name_label)

        # Map description
        desc_label = QtWidgets.QLabel(map_data.get('description', 'No description available'))
        desc_label.setWordWrap(True)
        desc_layout.addWidget(desc_label)

        # Map tags
        tags_container = QtWidgets.QWidget()
        tags_layout = QtWidgets.QHBoxLayout(tags_container)
        tags_layout.setContentsMargins(0, 5, 0, 0)  # Add some top margin

        for tag in map_data.get('tags'):
            tag_label = QtWidgets.QLabel(tag)
            tag_label.setStyleSheet("""
                background-color: #e0e0e0; 
                border-radius: 4px; 
                padding: 2px 6px;
                color: #444444;
                margin-right: 4px;
            """)
            tags_layout.addWidget(tag_label)

        # Add stretch at the end to left-align tags
        tags_layout.addStretch()
        desc_layout.addWidget(tags_container)

        item_layout.addLayout(desc_layout, 1)  # Give description area more weight

        # Add buttons
        button_layout = QtWidgets.QVBoxLayout()

        # Button 1 - Download
        btn_download = QtWidgets.QPushButton("Download")
        btn_download.clicked.connect(lambda: self.on_download_clicked(map_data))
        button_layout.addWidget(btn_download)

        # Button 2 - View Details
        btn_tiling = QtWidgets.QPushButton("Tiling Service")
        btn_tiling.clicked.connect(lambda: self.on_tiling_clicked(map_data))
        button_layout.addWidget(btn_tiling)

        # Add some spacing between buttons and borders
        button_layout.addStretch()

        item_layout.addLayout(button_layout)

        # Add the item to the list layout
        self.list_layout.addWidget(item_frame)

    def update_thumbnail(self, map_id, thumb_data):
        """Update the thumbnail image when loaded."""
        # Find the image label for this map_id
        for i in range(self.list_layout.count()):
            item_frame = self.list_layout.itemAt(i).widget()
            if item_frame:
                # Find the image label in the frame
                for child in item_frame.children():
                    if isinstance(child, QtWidgets.QLabel) and child.property("map_id") == map_id:
                        pixmap = QPixmap()
                        pixmap.loadFromData(thumb_data)
                        child.setPixmap(pixmap)
                        break

    @handled_exceptions
    def on_download_clicked(self, map_data):
        print(f"Downloading map: {map_data.get('name')}\n{map_data}")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Map",
            f"{map_data.get('name', 'map')}.tif" if map_data.get('type') == 'raster' else f"{map_data.get('name', 'map')}.fgb",
            "GeoTIFF (*.tif);;All Files (*)" if map_data.get('type') == 'raster' else "FlatGeobuf (*.fgb);;All Files (*)"
        )

        # If user cancels the dialog, return early
        if not file_path:
            return

        get_maphub_client().download_map(map_data['id'], file_path)

        # Adding downloaded file to layers
        if not os.path.exists(file_path):
            raise Exception(f"Downloaded file not found at {file_path}")


        if map_data.get('type') == 'raster':
            layer = self.iface.addRasterLayer(file_path, map_data.get('name', os.path.basename(file_path)))
        elif map_data.get('type') == 'vector':
            layer = self.iface.addVectorLayer(file_path, map_data.get('name', os.path.basename(file_path)), "ogr")
        else:
            raise Exception(f"Unknown layer type: {map_data['type']}")

        if not layer.isValid():
            raise Exception(f"The downloaded map could not be added as a layer. Please check the file: {file_path}")
        else:
            QMessageBox.information(
                self,
                "Download Complete",
                f"Map '{map_data.get('name')}' has been downloaded and added to your layers."
            )

    @handled_exceptions
    def on_tiling_clicked(self, map_data):
        print(f"Viewing details for map: {map_data.get('name')}\n{map_data}")

        layer_info = get_maphub_client().get_layer_info(map_data['id'])
        tiler_url = layer_info['tiling_url']
        layer_name = map_data.get('name', f"Tiled Map {map_data['id']}")

        # Add layer based on map type
        if map_data.get('type') == 'vector':
            # Add as vector tile layer
            vector_tile_layer_string = f"type=xyz&url={tiler_url}&zmin={layer_info.get('min_zoom', 0)}&zmax={layer_info.get('max_zoom', 15)}"
            vector_layer = QgsVectorTileLayer(vector_tile_layer_string, layer_name)
            if vector_layer.isValid():
                QgsProject.instance().addMapLayer(vector_layer)
                self.iface.messageBar().pushSuccess("Success", f"Vector tile layer '{layer_name}' added.")
            else:
                self.iface.messageBar().pushWarning("Warning", f"Could not add vector tile layer from URL: {tiler_url}")
        elif map_data.get('type') == 'raster':
            uri = f"type=xyz&url={tiler_url.replace('&', '%26')}"

            raster_layer = QgsRasterLayer(uri, layer_name, "wms")

            if raster_layer.isValid():
                QgsProject.instance().addMapLayer(raster_layer)
                self.iface.messageBar().pushSuccess("Success", f"XYZ tile layer '{layer_name}' added.")
            else:
                self.iface.messageBar().pushWarning("Warning", f"Could not add XYZ tile layer from URL: {tiler_url}")
        else:
            raise Exception(f"Unknown layer type: {map_data['type']}")

