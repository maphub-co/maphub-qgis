import os
import json
import uuid
import shutil
import platform
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, Qt, QStandardPaths
from PyQt5.QtWidgets import (QLabel, QVBoxLayout, QHBoxLayout, QProgressBar, 
                            QMessageBox, QPushButton, QSpacerItem, QSizePolicy, QFrame)
from PyQt5.QtGui import QIcon, QCursor
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.core import (QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer, 
                      QgsRasterLayer, QgsMapLayer)

from ...utils import get_maphub_client, apply_style_to_layer, handled_exceptions, get_layer_styles_as_json, place_layer_at_position
from .MapHubBaseDialog import MapHubBaseDialog
from .CreateFolderDialog import CreateFolderDialog
from ..widgets.WorkspaceNavigationWidget import WorkspaceNavigationWidget
from ..widgets.ProgressBarWidget import ProgressBarWidget

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'CloneFolderDialog.ui'))

class CloneFolderDialog(MapHubBaseDialog, FORM_CLASS):
    # Define signals
    cloneCompleted = pyqtSignal(str)  # Signal emitted when cloning is complete, passes project path

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(CloneFolderDialog, self).__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.iface = iface

        # Get the list layout for folders
        self.list_layout = self.findChild(QtWidgets.QVBoxLayout, 'listLayout')

        # Set default destination to documents folder
        documents_path = self.get_documents_folder()
        self.lineEdit_path.setText(str(documents_path))

        # Create and set up the workspace navigation widget
        self.workspace_nav_widget = WorkspaceNavigationWidget(self)
        self.list_layout.addWidget(self.workspace_nav_widget)

        # Connect navigation widget signals
        self.workspace_nav_widget.folder_selected.connect(self.on_folder_selected)

        # Add "Create New Folder" button after the navigation widget
        self.add_create_folder_button()

        # Connect signals
        self.pushButton_browse.clicked.connect(self.browse_destination)

        # Set default CRS to EPSG:4326
        default_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.projectionSelector.setCrs(default_crs)


    # Navigation functionality is now handled by WorkspaceNavigationWidget

    def add_create_folder_button(self):
        """Add a button to create a new folder"""
        create_folder_frame = QtWidgets.QFrame()
        create_folder_frame.setStyleSheet("background-color: #e6f7e6; border-radius: 4px;")
        create_folder_layout = QtWidgets.QHBoxLayout(create_folder_frame)
        create_folder_layout.setContentsMargins(5, 5, 5, 5)
        create_folder_layout.setSpacing(5)

        # Add folder icon
        folder_icon = QIcon.fromTheme("folder-new", QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_FileDialogNewFolder))
        folder_icon_label = QtWidgets.QLabel()
        folder_icon_label.setPixmap(folder_icon.pixmap(24, 24))
        create_folder_layout.addWidget(folder_icon_label)

        # Add label
        create_folder_label = QtWidgets.QLabel("Create New Folder")
        create_folder_label.setStyleSheet("font-weight: bold;")
        create_folder_layout.addWidget(create_folder_label)

        # Add spacer
        create_folder_layout.addItem(QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))

        # Make the frame clickable
        create_folder_frame.setCursor(QCursor(Qt.PointingHandCursor))
        create_folder_frame.mousePressEvent = lambda event: self.on_create_folder_clicked()

        # Add to layout
        self.list_layout.addWidget(create_folder_frame)

    # Folder item display and navigation is now handled by ProjectNavigationWidget

    def on_folder_selected(self, folder_id):
        """Handle selection of a folder for cloning"""
        # The folder_id is already set in the navigation widget
        # We just need to store it for use in the accept method
        self.selected_folder_id = folder_id

    def on_create_folder_clicked(self):
        """Handle click on the create folder button"""
        # Get the current workspace ID
        workspace_id = self.workspace_nav_widget.get_selected_workspace_id()

        # Get the current folder ID as the parent
        parent_folder_id = self.workspace_nav_widget.get_current_folder_id()

        # Open the create folder dialog
        create_folder_dialog = CreateFolderDialog(self, workspace_id, parent_folder_id)
        result = create_folder_dialog.exec_()

        if result == QtWidgets.QDialog.Accepted and create_folder_dialog.folder:
            # Refresh the current folder to show the new folder
            current_folder_id = self.workspace_nav_widget.get_current_folder_id()
            if current_folder_id:
                self.workspace_nav_widget.load_folder_contents(current_folder_id)

    def get_documents_folder(self):
        """Return the path to the system's documents folder"""
        # Use QStandardPaths to get the documents location (cross-platform)
        documents_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        return Path(documents_path)

    def browse_destination(self):
        """Open file dialog to select destination directory"""
        # Use current path as starting directory if it exists, otherwise use documents folder
        current_path = self.lineEdit_path.text()
        start_dir = current_path if current_path and os.path.exists(current_path) else str(self.get_documents_folder())

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Destination Directory",
            start_dir
        )
        if directory:
            self.lineEdit_path.setText(directory)

    def get_destination_path(self):
        """Return the selected destination path"""
        return Path(self.lineEdit_path.text())

    def get_crs(self):
        """Return the selected CRS"""
        return self.projectionSelector.crs()

    def get_file_format(self):
        """Get the selected file format or None if default is selected"""
        index = self.comboBox_file_format.currentIndex()
        if index == 0:  # Default option
            return None
        elif index == 1:
            return "gpkg"
        elif index == 2:
            return "tif"
        elif index == 3:
            return "fgb"
        elif index == 4:
            return "geojson"
        elif index == 5:
            return "shp"
        elif index == 6:
            return "xlsx"
        return None

    def accept(self):
        """Override accept to perform cloning when OK is clicked"""
        # Validate inputs
        destination_path = self.get_destination_path()
        if not destination_path or not str(destination_path).strip():
            QMessageBox.warning(self, "Invalid Path", "Please select a destination directory.")
            return

        # Get the selected folder ID from the navigation widget
        selected_folder_id = self.workspace_nav_widget.get_selected_folder_id()
        if not selected_folder_id:
            QMessageBox.warning(self, "Invalid Folder", "No folder selected for cloning.")
            return

        # Get the CRS
        crs = self.get_crs()

        # Get the file format
        file_format = self.get_file_format()

        # Hide the dialog but don't close it yet
        self.hide()

        # Start the cloning process
        self.clone_folder(selected_folder_id, destination_path, crs, file_format)

        # Now close the dialog
        super().accept()


    @handled_exceptions
    def clone_folder(self, folder_id, destination_path, crs, file_format=None):
        """Clone a folder from MapHub"""
        print(f"Cloning folder: {folder_id}")

        # Create progress bar widget
        progress_widget = ProgressBarWidget(
            parent=self.parent,
            title="Cloning Folder",
            message="Cloning folder from MapHub..."
        )
        progress_widget.show_dialog()

        try:
            # Get the MapHub client
            client = get_maphub_client()

            # Clone the folder
            progress_widget.set_value(10)

            # Use the new clone functionality
            cloned_folder_path = client.clone(folder_id, destination_path, file_format)

            if cloned_folder_path is None:
                raise Exception("Folder clone failed.")

            progress_widget.set_value(50)

            # Load styling information for all maps in the cloned folder
            progress_widget.update_progress(50, "Loading styling information...")
            self.load_and_save_styles(cloned_folder_path)

            progress_widget.set_value(70)

            # Create a QGIS project in the cloned folder
            progress_widget.update_progress(70, "Creating QGIS project...")
            project_path = self.create_qgis_project(cloned_folder_path, crs)

            progress_widget.set_value(90)
            progress_widget.set_value(100)

            # Close progress dialog
            progress_widget.close_dialog()

            # Show completion message
            QMessageBox.information(
                self.parent,
                "Clone Complete",
                f"Successfully cloned folder to {destination_path}."
            )

            # Emit signal with project path
            self.cloneCompleted.emit(str(project_path))

        except Exception as e:
            progress_widget.close_dialog()
            QMessageBox.critical(
                self.parent,
                "Clone Failed",
                f"Error cloning folder: {str(e)}"
            )

    def load_and_save_styles(self, folder_path):
        """Load styling information from MapHub and store it in memory"""
        print(f"Loading styling information for maps in {folder_path}")

        # Dictionary to store styles for each file path
        self.file_styles = {}

        # Find all GIS files in the folder
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = Path(root) / file

                # Skip .maphub directory
                if ".maphub" in str(file_path):
                    continue

                # Process only GIS files
                if file.endswith(('.shp', '.gpkg', '.geojson', '.kml', '.fgb', '.tif', '.tiff', '.jpg', '.png')):
                    try:
                        # Extract map ID from the .maphub directory if possible
                        maphub_dir = folder_path / ".maphub" / "maps"
                        map_id = None

                        if maphub_dir.exists():
                            # Look through metadata files to find the one matching this file
                            for metadata_file in maphub_dir.glob("*.json"):
                                with open(metadata_file, "r") as f:
                                    metadata = json.load(f)
                                    if metadata.get("path") == str(file_path.relative_to(folder_path)):
                                        map_id = metadata.get("id")
                                        break

                        if map_id:
                            # Get map data from MapHub
                            map_data = get_maphub_client().maps.get_map(uuid.UUID(map_id))

                            # Check if visuals/styling exists
                            if 'map' in map_data and 'visuals' in map_data['map'] and map_data['map']['visuals']:
                                print(f"Found styling for {file_path.name}")

                                # Store the style in memory
                                self.file_styles[str(file_path)] = map_data['map']['visuals']
                                print(f"Stored style for {file_path.name} in memory")
                    except Exception as e:
                        print(f"Error processing style for {file_path}: {e}")

    def create_qgis_project(self, folder_path, crs):
        """Create a QGIS project in the cloned folder"""
        # Get the folder name from the path
        folder_name = folder_path.name

        # Create a new QGIS project
        project = QgsProject.instance()
        project.clear()

        # Set the project CRS
        project.setCrs(crs)

        # Find all GIS files in the folder and add them as layers
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = Path(root) / file

                # Skip .maphub directory
                if ".maphub" in str(file_path):
                    continue

                # Add vector layers
                if file.endswith(('.shp', '.gpkg', '.geojson', '.kml', '.fgb')):
                    layer = QgsVectorLayer(str(file_path), file_path.stem, "ogr")
                    if layer.isValid():
                        # Get the visuals data for this layer
                        layer_visuals = None
                        if hasattr(self, 'file_styles') and str(file_path) in self.file_styles:
                            layer_visuals = self.file_styles[str(file_path)]
                            apply_style_to_layer(layer, layer_visuals)
                            print(f"Applied style to layer {layer.name()} directly from memory")

                        # Check if layer_order is available in the visuals data
                        if layer_visuals and "layer_order" in layer_visuals:
                            # Place the layer at the specified position
                            place_layer_at_position(project, layer, layer_visuals["layer_order"])
                            print(f"Placed layer {layer.name()} at position {layer_visuals['layer_order']}")
                        else:
                            # Fall back to adding the layer to the root
                            project.addMapLayer(layer)

                # Add raster layers
                elif file.endswith(('.tif', '.tiff', '.jpg', '.png')):
                    layer = QgsRasterLayer(str(file_path), file_path.stem)
                    if layer.isValid():
                        # Get the visuals data for this layer
                        layer_visuals = None
                        if hasattr(self, 'file_styles') and str(file_path) in self.file_styles:
                            layer_visuals = self.file_styles[str(file_path)]
                            apply_style_to_layer(layer, layer_visuals)
                            print(f"Applied style to layer {layer.name()} directly from memory")

                        # Check if layer_order is available in the visuals data
                        if layer_visuals and "layer_order" in layer_visuals:
                            # Place the layer at the specified position
                            place_layer_at_position(project, layer, layer_visuals["layer_order"])
                            print(f"Placed layer {layer.name()} at position {layer_visuals['layer_order']}")
                        else:
                            # Fall back to adding the layer to the root
                            project.addMapLayer(layer)

        # Save the project
        project_path = folder_path / f"{folder_name}.qgz"
        project.write(str(project_path))

        return project_path
