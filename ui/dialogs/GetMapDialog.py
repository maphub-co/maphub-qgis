# -*- coding: utf-8 -*-

import os
from pathlib import Path

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QPushButton, QMessageBox

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, QByteArray
from PyQt5.QtGui import QPixmap
from qgis.core import QgsVectorTileLayer, QgsRasterLayer, QgsProject

from ...utils.utils import get_maphub_client, apply_style_to_layer, get_default_download_location
from .MapHubBaseDialog import MapHubBaseDialog
from ..widgets.WorkspaceNavigationWidget import WorkspaceNavigationWidget
from ...utils.error_manager import handled_exceptions


class ThumbnailLoader(QThread):
    thumbnail_loaded = pyqtSignal(str, QByteArray)  # map_id, thumbnail data

    def __init__(self, map_id):
        super().__init__()
        self.map_id = map_id

    def run(self):
        try:
            thumb_data = get_maphub_client().maps.get_thumbnail(self.map_id)
            self.thumbnail_loaded.emit(self.map_id, QByteArray(thumb_data))
        except Exception as e:
            print(f"Error loading thumbnail for map {self.map_id}: {e}")


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'GetMapDialog.ui'))


class GetMapDialog(MapHubBaseDialog, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(GetMapDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        self.setupUi(self)

        self.iface = iface
        self.thumb_loaders = []

        # Initialize both list layouts
        self.list_layout_workspace = self.findChild(QtWidgets.QVBoxLayout, 'listLayout')
        self.list_layout_public = self.findChild(QtWidgets.QVBoxLayout, 'listLayout_public')

        # Current active list layout (will be set in on_tab_changed)
        self.list_layout = self.list_layout_workspace

        # The workspace navigation widget will be created when needed in on_tab_changed
        self.workspace_nav_widget = None

        # Track if content has been loaded for each tab
        self.workspace_content_loaded = False
        self.public_content_loaded = False

        # Find the scroll area widgets to hide/show them
        self.scroll_area_workspace = self.findChild(QtWidgets.QScrollArea, 'scrollArea_workspace')
        self.scroll_area_public = self.findChild(QtWidgets.QScrollArea, 'scrollArea_public')

        # Initially hide the public scroll area since we start with the workspace tab
        self.scroll_area_public.setVisible(False)

        # Connect signals
        self.tabWidget_map_type.currentChanged.connect(self.on_tab_changed)
        self.pushButton_search.clicked.connect(self.on_search_clicked)
        self.lineEdit_search.returnPressed.connect(self.on_search_clicked)
        self.comboBox_sort.currentIndexChanged.connect(self.on_sort_changed)

        # Initialize with the first tab
        self.on_tab_changed(0)

    def closeEvent(self, event):
        """Handle close event, clean up resources"""
        # Cancel any running threads
        for loader in self.thumb_loaders:
            if loader.isRunning():
                loader.terminate()
                loader.wait()
        self.thumb_loaders = []

        # Reset content loaded flags
        self.workspace_content_loaded = False
        self.public_content_loaded = False

        # Emit closing signal
        self.closingPlugin.emit()
        event.accept()

    def clear_list_layout(self):
        """Clear all widgets from the list layout"""
        # Cancel any running threads
        for loader in self.thumb_loaders:
            if loader.isRunning():
                loader.terminate()
                loader.wait()
        self.thumb_loaders = []

        # Clear the current active list layout
        if self.list_layout:
            for i in reversed(range(self.list_layout.count())):
                widget = self.list_layout.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()

    def on_tab_changed(self, index):
        """Handle tab change event"""
        if index == 0:  # workspace Maps tab
            # Set the active list layout to workspace
            self.list_layout = self.list_layout_workspace

            # Show workspace content, hide public content
            self.scroll_area_workspace.setVisible(True)
            self.scroll_area_public.setVisible(False)

            # Initialize workspace content if not already loaded
            if not self.workspace_content_loaded:
                # Create the workspace navigation widget if it doesn't exist
                if not hasattr(self, 'workspace_nav_widget') or self.workspace_nav_widget is None:
                    self.workspace_nav_widget = WorkspaceNavigationWidget(self, folder_select_mode=False)
                    self.workspace_nav_widget.folder_clicked.connect(self.on_folder_navigation)
                    # No need to set_add_select_button(False) as it's now handled by folder_select_mode

                # Add the workspace navigation widget to the layout
                self.list_layout.addWidget(self.workspace_nav_widget)
                self.workspace_content_loaded = True

        else:  # Public Maps tab
            # Set the active list layout to public
            self.list_layout = self.list_layout_public

            # Show public content, hide workspace content
            self.scroll_area_workspace.setVisible(False)
            self.scroll_area_public.setVisible(True)

            # Load public maps if not already loaded
            if not self.public_content_loaded:
                # Load public maps with default sorting (Recent)
                self.load_public_maps()
                self.public_content_loaded = True


    def on_folder_navigation(self, folder_id):
        """Handle folder navigation from the WorkspaceNavigationWidget"""
        # Navigation is now handled by the WorkspaceNavigationWidget
        pass

    # Navigation controls are now handled by ProjectNavigationWidget

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

    # Folder navigation is now handled by ProjectNavigationWidget

    def load_public_maps(self, sort_by="recent", page=1, append=False):
        """Load public maps with optional sorting and pagination"""
        # Clear any existing items if not appending and we're reloading the content
        if not append:
            # Only clear if we're actively in the public tab
            if self.tabWidget_map_type.currentIndex() == 1:
                self.clear_list_layout()

        # Get maps
        public_maps_response = get_maphub_client().maps.get_public_maps(sort_by=sort_by, page=page)
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
        # Only proceed if we're in the public tab
        if self.tabWidget_map_type.currentIndex() == 1:
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
        # Only clear if we're actively in the public tab
        if self.tabWidget_map_type.currentIndex() == 1:
            self.clear_list_layout()

        if not search_term:
            self.load_public_maps(sort_by)
            return

        maps = get_maphub_client().maps.search_maps(search_term)

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
                self.add_public_map_item(map_data)


    # Folder item display and workspace selection are now handled by WorkspaceNavigationWidget

    def add_public_map_item(self, map_data):
        """Create a frame for each list item."""
        item_frame = QtWidgets.QFrame()
        item_frame.setObjectName("map_item_frame")  # Set object name for styling
        item_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        item_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        item_frame.setMinimumHeight(96)

        # Create layout for the item
        item_layout = QtWidgets.QHBoxLayout(item_frame)
        item_layout.setContentsMargins(5, 5, 5, 5)
        item_layout.setSpacing(5)

        # Add image
        image_label = QtWidgets.QLabel()
        image_label.setFixedSize(96, 96)
        image_label.setScaledContents(True)

        # Set a placeholder image while loading
        placeholder_pixmap = QPixmap(96, 96)
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
            # Use class property for styling with QSS
            tag_label.setProperty("class", "tag_label")
            tags_layout.addWidget(tag_label)

        # Add stretch at the end to left-align tags
        tags_layout.addStretch()
        desc_layout.addWidget(tags_container)

        item_layout.addLayout(desc_layout, 1)  # Give description area more weight

        # Add buttons and format selection
        button_layout = QtWidgets.QVBoxLayout()

        # Format selection dropdown
        format_layout = QtWidgets.QHBoxLayout()
        format_label = QtWidgets.QLabel("Format:")
        format_combo = QtWidgets.QComboBox()

        # Set object name for the combo box to find it later
        format_combo.setObjectName(f"format_combo_{map_data['id']}")

        # Add format options based on map type
        if map_data.get('type') == 'raster':
            format_combo.addItem("GeoTIFF (.tif)", "tif")
        elif map_data.get('type') == 'vector':
            format_combo.addItem("FlatGeobuf (.fgb)", "fgb")
            format_combo.addItem("Shapefile (.shp)", "shp")
            format_combo.addItem("GeoPackage (.gpkg)", "gpkg")

        format_layout.addWidget(format_label)
        format_layout.addWidget(format_combo)
        button_layout.addLayout(format_layout)

        # Button 1 - Download
        btn_download = QtWidgets.QPushButton("Download")
        # No need to set style as QPushButton styling is already in style.qss
        btn_download.clicked.connect(lambda: self.on_download_clicked(map_data))
        button_layout.addWidget(btn_download)

        # Button 2 - View Details
        btn_tiling = QtWidgets.QPushButton("Tiling Service")
        # No need to set style as QPushButton styling is already in style.qss
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
        print(f"Downloading map: {map_data.get('name')}")

        # Find the format combo box for this map
        format_combo = self.findChild(QtWidgets.QComboBox, f"format_combo_{map_data['id']}")
        if not format_combo:
            raise Exception("Format selection not found")

        # Get the selected format
        selected_format = format_combo.currentData()
        file_extension = f".{selected_format}"
        
        # Get default download location
        default_dir = get_default_download_location()
        
        # Create safe filename from map name
        safe_name = ''.join(c for c in map_data.get('name', 'map') if c.isalnum() or c in ' _-')
        safe_name = safe_name.replace(' ', '_')
        
        # Create full file path
        file_path = os.path.join(str(default_dir), f"{safe_name}{file_extension}")
        
        # Ensure filename is unique
        counter = 1
        base_name = os.path.splitext(file_path)[0]
        while os.path.exists(file_path):
            file_path = f"{base_name}_{counter}{file_extension}"
            counter += 1
        
        # Fetch complete map data including visuals if not already present
        if 'visuals' not in map_data:
            try:
                complete_map_info = get_maphub_client().maps.get_map(map_data['id'])
                if 'map' in complete_map_info and 'visuals' in complete_map_info['map']:
                    map_data['visuals'] = complete_map_info['map']['visuals']
            except Exception as e:
                print(f"Error fetching map visuals: {str(e)}")
        
        # Download the map with the selected format
        get_maphub_client().maps.download_map(map_data['id'], file_path, selected_format)

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
            # Apply style if available
            if 'visuals' in map_data and map_data['visuals']:
                visuals = map_data['visuals']
                apply_style_to_layer(layer, visuals)

            QMessageBox.information(
                self,
                "Download Complete",
                f"Map '{map_data.get('name')}' has been downloaded to {file_path} and added to your layers."
            )

    @handled_exceptions
    def on_tiling_clicked(self, map_data):
        print(f"Viewing details for map: {map_data.get('name')}")

        layer_info = get_maphub_client().maps.get_layer_info(map_data['id'])
        tiler_url = layer_info['tiling_url']
        layer_name = map_data.get('name', f"Tiled Map {map_data['id']}")

        # Add layer based on map type
        if map_data.get('type') == 'vector':
            # Add as vector tile layer
            vector_tile_layer_string = f"type=xyz&url={tiler_url}&zmin={layer_info.get('min_zoom', 0)}&zmax={layer_info.get('max_zoom', 15)}"
            vector_layer = QgsVectorTileLayer(vector_tile_layer_string, layer_name)
            if vector_layer.isValid():
                QgsProject.instance().addMapLayer(vector_layer)
                if 'visuals' in map_data and map_data['visuals']:
                    apply_style_to_layer(vector_layer, map_data['visuals'], tiling=True)
                self.iface.messageBar().pushSuccess("Success", f"Vector tile layer '{layer_name}' added.")
            else:
                self.iface.messageBar().pushWarning("Warning", f"Could not add vector tile layer from URL: {tiler_url}")
        elif map_data.get('type') == 'raster':
            uri = f"type=xyz&url={tiler_url.replace('&', '%26')}"

            raster_layer = QgsRasterLayer(uri, layer_name, "wms")

            if raster_layer.isValid():
                QgsProject.instance().addMapLayer(raster_layer)
                if 'visuals' in map_data and map_data['visuals']:
                    apply_style_to_layer(raster_layer, map_data['visuals'])
                self.iface.messageBar().pushSuccess("Success", f"XYZ tile layer '{layer_name}' added.")
            else:
                self.iface.messageBar().pushWarning("Warning", f"Could not add XYZ tile layer from URL: {tiler_url}")
        else:
            raise Exception(f"Unknown layer type: {map_data['type']}")

