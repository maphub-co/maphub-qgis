# -*- coding: utf-8 -*-

import os
import json
import requests
import tempfile

from PyQt5 import QtGui, QtCore, QtWidgets, uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtWidgets import (QDialog, QLabel, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QSizePolicy, QSpacerItem,
                             QMessageBox, QGroupBox, QProgressBar)
from PyQt5.QtGui import QPixmap, QIcon, QCursor, QFont
from qgis.core import Qgis, QgsProject
from qgis.utils import iface

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal, QSettings, Qt, QByteArray
from qgis.PyQt.QtGui import QColor, QPixmap
from qgis.PyQt.QtWidgets import QLineEdit, QFileDialog, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, QByteArray
from PyQt5.QtGui import QPixmap
from qgis.core import QgsVectorTileLayer, QgsRasterLayer, QgsProject, QgsDataSourceUri

from ..utils import get_maphub_client, handled_exceptions


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

        # Clear layout
        self.clear_list_layout()

        # Initialize UI components
        self._populate_projects_combobox()

        # Connect signals
        self.comboBox_project.currentIndexChanged.connect(self.on_project_selected)
        self.tabWidget_map_type.currentChanged.connect(self.on_tab_changed)
        self.pushButton_search.clicked.connect(self.on_search_clicked)
        self.lineEdit_search.returnPressed.connect(self.on_search_clicked)
        self.comboBox_sort.currentIndexChanged.connect(self.on_sort_changed)

        # Initialize with the first tab
        self.on_tab_changed(0)

    def closeEvent(self, event):
        """Handle close event, clean up resources"""
        # Clear the list
        self.clear_list_layout()

        # Emit closing signal
        self.closingPlugin.emit()
        event.accept()

    def clear_list_layout(self):
        """Clear all widgets from the list layout"""
        # while self.list_layout.count():
        #     item = self.list_layout.takeAt(0)
        #     if item.widget():
        #         item.widget().deleteLater()
        #
        # Cancel any running threads
        for loader in self.thumb_loaders:
            if loader.isRunning():
                loader.terminate()
                loader.wait()
        self.thumb_loaders = []

        for i in reversed(range(self.list_layout.count())):
            widget = self.list_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

    def on_tab_changed(self, index):
        """Handle tab change event"""
        self.clear_list_layout()

        if index == 0:  # Project Maps tab
            # If a project is already selected, load its maps
            if self.comboBox_project.count() > 0:
                self.on_project_selected(self.comboBox_project.currentIndex())
            else:
                no_maps_label = QLabel(f"You dont have any projects yet. Check out the public maps instead.")
                no_maps_label.setAlignment(Qt.AlignCenter)
                self.list_layout.addWidget(no_maps_label)

        else:  # Public Maps tab
            # Load public maps with default sorting (Recent)
            self.load_public_maps()

    def on_project_selected(self, index):
        """Handle project selection change"""
        if index < 0:
            return

        # Only respond if we're on the project maps tab
        if self.tabWidget_map_type.currentIndex() == 0:
            project_id = self.comboBox_project.itemData(index)
            self.load_project_maps(project_id)

    def on_search_clicked(self):
        """Handle search button click"""
        # Only in public maps tab
        if self.tabWidget_map_type.currentIndex() == 1:
            search_term = self.lineEdit_search.text().strip()
            sort_option = self.get_sort_option()
            self.search_public_maps(search_term, sort_option)

    def on_sort_changed(self, index):
        """Handle sort option change"""
        # Only in public maps tab
        if self.tabWidget_map_type.currentIndex() == 1:
            search_term = self.lineEdit_search.text().strip()
            sort_option = self.get_sort_option()

            if search_term:
                self.search_public_maps(search_term, sort_option)
            else:
                self.load_public_maps(sort_option)

    def get_sort_option(self):
        """Get the current sort option"""
        index = self.comboBox_sort.currentIndex()
        if index == 0:
            return "recent"
        elif index == 1:
            return "views"
        elif index == 2:
            return "stars"
        return "recent"  # Default

    def load_project_maps(self, project_id):
        """Load maps for a project"""
        # Clear any existing items
        self.clear_list_layout()

        # Get maps
        maps = get_maphub_client().get_project_maps(project_id)

        self.load_maps(maps)

    def load_public_maps(self, sort_by="recent", page=1, append=False):
        """Load public maps with optional sorting and pagination"""
        # Clear any existing items if not appending
        if not append:
            self.clear_list_layout()

        # Get maps
        public_maps_response = get_maphub_client().get_public_maps(sort_by=sort_by, page=page)
        maps = public_maps_response.get('maps', [])
        pagination = public_maps_response.get('pagination', {})

        self.load_maps(maps)

        # Add "Load more" button if there are more pages
        if pagination.get('has_next', False):
            load_more_button = QPushButton("Load more")
            load_more_button.setObjectName("load_more_button")
            load_more_button.clicked.connect(lambda: self.on_load_more_clicked(
                next_page=page+1,
                sort_by=sort_by
            ))

            # Add button to layout
            self.list_layout.addWidget(load_more_button)

    def on_load_more_clicked(self, next_page: int, sort_by: str):
        """Handle click on the 'Load more' button"""
        # Remove the current load more button first
        for i in reversed(range(self.list_layout.count())):
            widget = self.list_layout.itemAt(i).widget()
            if widget is not None and widget.objectName() == "load_more_button":
                widget.deleteLater()
                break

        # Increment page and load more maps
        self.load_public_maps(sort_by=sort_by, page=next_page, append=True)

    def search_public_maps(self, search_term, sort_by="recent"):
        """Search for public maps"""
        self.clear_list_layout()

        if not search_term:
            self.load_public_maps(sort_by)
            return

        maps = get_maphub_client().search_maps(search_term)

        self.load_maps(maps)

    def load_maps(self, maps):
        if len(maps) == 0:
            # No maps found
            no_maps_label = QLabel(f"No maps found.")
            no_maps_label.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(no_maps_label)
        else:
            # Add map items to the list
            for map_data in maps:
                self.add_map_item(map_data)

    def _populate_projects_combobox(self):
        """Populate the options combobox with items returned from a function."""
        self.comboBox_project.clear()

        projects = get_maphub_client().get_projects()

        for project in projects:
            project_id = project.get('id')
            project_name = project.get('name', 'Unnamed Project')

            self.comboBox_project.addItem(project_name, project_id)

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
