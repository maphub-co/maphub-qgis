import os
from typing import List, Dict, Any, Optional, Callable

from PyQt5.QtCore import Qt, pyqtSignal, QThread, QByteArray
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, 
                            QPushButton, QLabel, QSpacerItem, QSizePolicy,
                            QComboBox, QApplication, QDialog, QFileDialog, QMessageBox)
from PyQt5.QtGui import QIcon, QCursor, QPixmap, QColor, QFont
from qgis.core import QgsProject
from qgis.utils import iface

from ...utils import get_maphub_client, apply_style_to_layer, handled_exceptions
from ..dialogs.MapHubBaseDialog import style


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


class ProjectNavigationWidget(QWidget):
    """
    A reusable widget for project navigation in MapHub.

    This widget provides a UI for browsing folders in MapHub, including:
    - Navigation controls (back button, current folder display)
    - Folder items display
    - Navigation actions (back, click on folder)
    - Optionally displays maps within folders

    Signals:
        folder_clicked(str): Emitted when a folder is clicked for navigation
        folder_selected(str): Emitted when a folder is selected (e.g., for an operation)
    """

    folder_clicked = pyqtSignal(str)
    folder_selected = pyqtSignal(str)

    def __init__(self, parent=None, folder_select_mode=True):
        super(ProjectNavigationWidget, self).__init__(parent)

        # Initialize state
        self.folder_history: List[str] = []
        self.selected_folder_id: Optional[str] = None
        self.custom_button_config: Optional[Dict[str, Any]] = None
        self.folder_select_mode: bool = folder_select_mode
        self.add_select_button: bool = folder_select_mode
        self.thumb_loaders = []

        # Set widget styling
        self.setObjectName("projectNavigationWidget")

        # Apply the style from style.qss
        if style:
            self.setStyleSheet(style)

        # Set up UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the widget UI"""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(5)

        # List layout for folders
        self.list_layout = QVBoxLayout()
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(5)

        self.main_layout.addLayout(self.list_layout)

    def set_workspace(self, workspace_id: str, add_custom_button: Optional[Dict[str, Any]] = None):
        """
        Set the current workspace and load its root folder

        Args:
            workspace_id (str): The ID of the workspace to load
            add_custom_button (Dict[str, Any], optional): Custom button configuration for folder items
                {
                    'text': str,
                    'tooltip': str,
                    'callback': Callable[[str], None]
                }
        """
        # Store the custom button configuration
        self.custom_button_config = add_custom_button

        # Get the root folder for the workspace
        root_folder = get_maphub_client().folder.get_root_folder(workspace_id)
        folder_id = root_folder["folder"]["id"]

        # Reset folder history
        self.folder_history = [folder_id]

        # Load folder contents
        self.load_folder_contents(folder_id)

    def load_folder_contents(self, folder_id: str):
        """
        Load and display the contents of a folder

        Args:
            folder_id (str): The ID of the folder to load
        """
        # Clear any existing items
        self.clear_list_layout()

        # Get folder details including child folders
        folder_details = get_maphub_client().folder.get_folder(folder_id)
        child_folders = folder_details.get("child_folders", [])

        # Add navigation controls if we have folder history
        if self.folder_history:
            self.add_navigation_controls()

        # Display child folders
        for folder in child_folders:
            self.add_folder_item(folder, self.add_select_button, self.custom_button_config)

        # If not in folder select mode, also display maps
        if not self.folder_select_mode:
            maps = folder_details.get("map_infos", [])
            for map_data in maps:
                self.add_map_item(map_data)

    def clear_list_layout(self):
        """Clear all widgets from the list layout"""
        # Cancel any running thumbnail loader threads
        for loader in self.thumb_loaders:
            if loader.isRunning():
                loader.terminate()
                loader.wait()
        self.thumb_loaders = []

        # Clear widgets
        for i in reversed(range(self.list_layout.count())):
            widget = self.list_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

    def add_navigation_controls(self):
        """Add navigation controls for folder browsing"""
        nav_frame = QFrame()
        nav_frame.setObjectName("navigationFrame")
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(5, 5, 5, 5)
        nav_layout.setSpacing(5)

        # Add "Back" button if we have history
        if len(self.folder_history) > 1:
            btn_back = QPushButton("← Back")
            btn_back.setToolTip("Go back to previous folder")
            btn_back.clicked.connect(self.on_back_clicked)
            btn_back.setMaximumWidth(80)
            nav_layout.addWidget(btn_back)

        # Add current path display
        if self.folder_history:
            current_folder_id = self.folder_history[-1]
            folder_details = get_maphub_client().folder.get_folder(current_folder_id)
            folder_name = folder_details.get("folder", {}).get("name", "Unknown Folder")

            path_label = QLabel(f"Current folder: {folder_name}")
            path_label.setObjectName("currentFolderLabel")
            nav_layout.addWidget(path_label)

        # Add spacer
        nav_layout.addItem(QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Add to layout
        self.list_layout.addWidget(nav_frame)

    def add_folder_item(self, folder_data: Dict[str, Any], 
                        add_select_button: bool = True,
                        add_custom_button: Optional[Dict[str, Any]] = None):
        """
        Create a frame for each folder item

        Args:
            folder_data (Dict[str, Any]): The folder data
            add_select_button (bool): Whether to add a select button
            add_custom_button (Dict[str, Any], optional): Custom button configuration
                {
                    'text': str,
                    'tooltip': str,
                    'callback': Callable[[str], None]
                }
        """
        # Create a unique object name for this folder item
        folder_id = folder_data['id']
        item_frame = QFrame()
        item_frame.setObjectName(f"folderItem_{folder_id}")
        item_frame.setFrameShape(QFrame.StyledPanel)
        item_frame.setFrameShadow(QFrame.Raised)
        item_frame.setMinimumHeight(40)

        # No need to apply base styling as it's in style.qss

        # Set margin and spacing for a more compact look
        item_layout = QHBoxLayout(item_frame)
        item_layout.setContentsMargins(5, 5, 5, 5)
        item_layout.setSpacing(5)

        # Add folder icon
        folder_icon = QIcon.fromTheme("folder", QIcon())
        if folder_icon.isNull():
            # Use a standard folder icon from Qt if theme icon is not available
            from PyQt5.QtWidgets import QApplication, QStyle
            folder_icon = QApplication.style().standardIcon(QStyle.SP_DirIcon)

        folder_icon_label = QLabel()
        folder_icon_label.setPixmap(folder_icon.pixmap(24, 24))
        item_layout.addWidget(folder_icon_label)

        # Folder name
        name_label = QLabel(folder_data.get('name', 'Unnamed Folder'))
        name_label.setObjectName(f"folderName_{folder_id}")
        item_layout.addWidget(name_label)

        # Add spacer
        item_layout.addItem(QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Add custom button if provided
        if add_custom_button:
            btn_custom = QPushButton(add_custom_button.get('text', 'Custom'))
            btn_custom.setObjectName(f"customButton_{folder_id}")
            btn_custom.setToolTip(add_custom_button.get('tooltip', ''))
            callback = add_custom_button.get('callback')
            if callback:
                btn_custom.clicked.connect(lambda: callback(folder_data['id']))
            item_layout.addWidget(btn_custom)

        # Add "Select" button if requested
        if add_select_button:
            btn_select = QPushButton("Select")
            btn_select.setObjectName(f"selectButton_{folder_id}")
            btn_select.setToolTip("Select this folder")
            btn_select.clicked.connect(lambda: self.on_folder_selected(folder_data['id']))
            item_layout.addWidget(btn_select)

        # Store folder_id in the frame for later reference
        item_frame.setProperty("folder_id", folder_data['id'])

        # Check if this is the selected folder
        if self.selected_folder_id and folder_data['id'] == self.selected_folder_id:
            # Highlight the selected folder using the "selected" property
            item_frame.setProperty("selected", "true")
            # Force style update
            item_frame.style().polish(item_frame)

        # Make the entire frame clickable to navigate into the folder
        item_frame.setCursor(QCursor(Qt.PointingHandCursor))
        item_frame.mousePressEvent = lambda event: self.on_folder_clicked(folder_data['id'])

        # Add to layout
        self.list_layout.addWidget(item_frame)

    def on_back_clicked(self):
        """Handle click on the back button"""
        if len(self.folder_history) > 1:
            # Remove the current folder from history
            self.folder_history.pop()

            # Load the previous folder
            previous_folder_id = self.folder_history[-1]
            self.load_folder_contents(previous_folder_id)

    def on_folder_clicked(self, folder_id: str):
        """
        Handle click on a folder item to navigate into it

        Args:
            folder_id (str): The ID of the clicked folder
        """
        # Add the folder to the navigation history
        self.folder_history.append(folder_id)

        # Load the contents of the clicked folder
        self.load_folder_contents(folder_id)

        # Update the selected folder ID
        self.selected_folder_id = folder_id

        # Emit the folder_clicked signal
        self.folder_clicked.emit(folder_id)

    def on_folder_selected(self, folder_id: str):
        """
        Handle selection of a folder

        Args:
            folder_id (str): The ID of the selected folder
        """
        # Update the selected folder ID
        self.selected_folder_id = folder_id

        # Refresh the display to show the selected folder
        self.load_folder_contents(self.folder_history[-1])

        # Emit the folder_selected signal
        self.folder_selected.emit(folder_id)

    def get_selected_folder_id(self) -> Optional[str]:
        """
        Get the ID of the currently selected folder

        Returns:
            Optional[str]: The ID of the selected folder, or None if no folder is selected
        """
        return self.selected_folder_id

    def add_map_item(self, map_data):
        """Create a frame for each map item."""
        item_frame = QFrame()
        item_frame.setObjectName("map_item_frame")  # Set object name for styling
        item_frame.setFrameShape(QFrame.StyledPanel)
        item_frame.setFrameShadow(QFrame.Raised)
        item_frame.setMinimumHeight(96)

        # Create layout for the item
        item_layout = QHBoxLayout(item_frame)
        item_layout.setContentsMargins(5, 5, 5, 5)
        item_layout.setSpacing(5)

        # Add image
        image_label = QLabel()
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
        desc_layout = QVBoxLayout()

        # Map name
        name_label = QLabel(map_data.get('name', 'Unnamed Map'))
        font = name_label.font()
        font.setBold(True)
        name_label.setFont(font)
        desc_layout.addWidget(name_label)

        # Map description
        desc_label = QLabel(map_data.get('description', 'No description available'))
        desc_label.setWordWrap(True)
        desc_layout.addWidget(desc_label)

        # Map tags
        tags_container = QWidget()
        tags_layout = QHBoxLayout(tags_container)
        tags_layout.setContentsMargins(0, 5, 0, 0)  # Add some top margin

        for tag in map_data.get('tags'):
            tag_label = QLabel(tag)
            # Use class property for styling with QSS
            tag_label.setProperty("class", "tag_label")
            tags_layout.addWidget(tag_label)

        # Add stretch at the end to left-align tags
        tags_layout.addStretch()
        desc_layout.addWidget(tags_container)

        item_layout.addLayout(desc_layout, 1)  # Give description area more weight

        # Add buttons
        button_layout = QVBoxLayout()

        # Format selection dropdown
        format_layout = QHBoxLayout()
        format_label = QLabel("Format:")
        format_combo = QComboBox()

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

        # Add download button
        btn_download = QPushButton("Download")
        btn_download.setToolTip("Download this map")
        btn_download.clicked.connect(lambda: self.on_download_clicked(map_data))
        button_layout.addWidget(btn_download)

        # Add tiling button
        btn_tiling = QPushButton("Tiling Service")
        btn_tiling.setToolTip("Add as tiling service")
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
                    if isinstance(child, QLabel) and child.property("map_id") == map_id:
                        pixmap = QPixmap()
                        pixmap.loadFromData(thumb_data)
                        child.setPixmap(pixmap)
                        break

    @handled_exceptions
    def on_tiling_clicked(self, map_data):
        """Handle click on the tiling button"""
        print(f"Adding tiling service for map: {map_data.get('name')}")

        layer_info = get_maphub_client().maps.get_layer_info(map_data['id'])
        tiler_url = layer_info['tiling_url']
        layer_name = map_data.get('name', f"Tiled Map {map_data['id']}")

        # Add layer based on map type
        if map_data.get('type') == 'vector':
            # Add as vector tile layer
            from qgis.core import QgsVectorTileLayer
            vector_tile_layer_string = f"type=xyz&url={tiler_url}&zmin={layer_info.get('min_zoom', 0)}&zmax={layer_info.get('max_zoom', 15)}"
            vector_layer = QgsVectorTileLayer(vector_tile_layer_string, layer_name)
            if vector_layer.isValid():
                QgsProject.instance().addMapLayer(vector_layer)
                if 'visuals' in map_data and map_data['visuals']:
                    apply_style_to_layer(vector_layer, map_data['visuals'], tiling=True)
                iface.messageBar().pushSuccess("Success", f"Vector tile layer '{layer_name}' added.")
            else:
                iface.messageBar().pushWarning("Warning", f"Could not add vector tile layer from URL: {tiler_url}")
        elif map_data.get('type') == 'raster':
            # Add as raster tile layer
            from qgis.core import QgsRasterLayer
            uri = f"type=xyz&url={tiler_url.replace('&', '%26')}"
            raster_layer = QgsRasterLayer(uri, layer_name, "wms")
            if raster_layer.isValid():
                QgsProject.instance().addMapLayer(raster_layer)
                if 'visuals' in map_data and map_data['visuals']:
                    apply_style_to_layer(raster_layer, map_data['visuals'])
                iface.messageBar().pushSuccess("Success", f"XYZ tile layer '{layer_name}' added.")
            else:
                iface.messageBar().pushWarning("Warning", f"Could not add XYZ tile layer from URL: {tiler_url}")
        else:
            raise Exception(f"Unknown layer type: {map_data['type']}")

    @handled_exceptions
    def on_download_clicked(self, map_data):
        """Handle click on the download button"""
        print(f"Downloading map: {map_data.get('name')}")

        # Find the format combo box for this map
        format_combo = self.findChild(QComboBox, f"format_combo_{map_data['id']}")
        if not format_combo:
            raise Exception("Format selection not found")

        # Get the selected format
        selected_format = format_combo.currentData()

        # Determine file extension and filter based on selected format
        file_extension = f".{selected_format}"

        # Create filter string based on selected format
        if selected_format == "tif":
            filter_string = "GeoTIFF (*.tif);;All Files (*)"
        elif selected_format == "fgb":
            filter_string = "FlatGeobuf (*.fgb);;All Files (*)"
        elif selected_format == "shp":
            filter_string = "Shapefile (*.shp);;All Files (*)"
        elif selected_format == "gpkg":
            filter_string = "GeoPackage (*.gpkg);;All Files (*)"
        else:
            filter_string = "All Files (*)"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Map",
            f"{map_data.get('name', 'map')}{file_extension}",
            filter_string
        )

        # If user cancels the dialog, return early
        if not file_path:
            return

        # Download the map with the selected format
        get_maphub_client().maps.download_map(map_data['id'], file_path, selected_format)

        # Adding downloaded file to layers
        if not os.path.exists(file_path):
            raise Exception(f"Downloaded file not found at {file_path}")

        if map_data.get('type') == 'raster':
            layer = iface.addRasterLayer(file_path, map_data.get('name', os.path.basename(file_path)))
        elif map_data.get('type') == 'vector':
            layer = iface.addVectorLayer(file_path, map_data.get('name', os.path.basename(file_path)), "ogr")
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
                f"Map '{map_data.get('name')}' has been downloaded and added to your layers."
            )

    def get_current_folder_id(self) -> Optional[str]:
        """
        Get the ID of the current folder (the one being displayed)

        Returns:
            Optional[str]: The ID of the current folder, or None if no folder is being displayed
        """
        if self.folder_history:
            return self.folder_history[-1]
        return None
