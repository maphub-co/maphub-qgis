import os
import json
import uuid
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QProgressBar, QMessageBox
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QDialog, QFileDialog
from qgis.core import (QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer, 
                      QgsRasterLayer)

from ..utils import get_maphub_client, apply_style_to_layer, handled_exceptions

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'CloneFolderDialog.ui'))

class CloneFolderDialog(QDialog, FORM_CLASS):
    # Define signals
    cloneCompleted = pyqtSignal(str)  # Signal emitted when cloning is complete, passes project path

    def __init__(self, parent=None):
        """Constructor."""
        super(CloneFolderDialog, self).__init__(parent)
        self.setupUi(self)
        self.parent = parent

        # Connect signals
        self.pushButton_browse.clicked.connect(self.browse_destination)

        # Set default CRS to EPSG:4326
        default_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.projectionSelector.setCrs(default_crs)

        # Store folder_id
        self.folder_id = None

    def browse_destination(self):
        """Open file dialog to select destination directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Destination Directory",
            ""
        )
        if directory:
            self.lineEdit_path.setText(directory)

    def get_destination_path(self):
        """Return the selected destination path"""
        return Path(self.lineEdit_path.text())

    def get_crs(self):
        """Return the selected CRS"""
        return self.projectionSelector.crs()

    def set_folder_id(self, folder_id):
        """Set the folder ID to clone"""
        self.folder_id = folder_id

    def accept(self):
        """Override accept to perform cloning when OK is clicked"""
        # Validate inputs
        destination_path = self.get_destination_path()
        if not destination_path or not str(destination_path).strip():
            QMessageBox.warning(self, "Invalid Path", "Please select a destination directory.")
            return

        if not self.folder_id:
            QMessageBox.warning(self, "Invalid Folder", "No folder selected for cloning.")
            return

        # Get the CRS
        crs = self.get_crs()

        # Hide the dialog but don't close it yet
        self.hide()

        # Start the cloning process
        self.clone_folder(self.folder_id, destination_path, crs)

        # Now close the dialog
        super().accept()

    @handled_exceptions
    def clone_folder(self, folder_id, destination_path, crs):
        """Clone a folder from MapHub"""
        print(f"Cloning folder: {folder_id}")

        # Create progress dialog
        progress = QProgressBar()
        progress.setMinimum(0)
        progress.setMaximum(100)
        progress.setValue(0)

        progress_dialog = QDialog(self.parent)
        progress_dialog.setWindowTitle("Cloning Folder")
        progress_dialog.setMinimumWidth(300)

        layout = QVBoxLayout(progress_dialog)
        layout.addWidget(QLabel("Cloning folder from MapHub..."))
        layout.addWidget(progress)

        progress_dialog.show()

        try:
            # Get the MapHub client
            client = get_maphub_client()

            # Clone the folder
            progress.setValue(10)
            QtWidgets.QApplication.processEvents()

            # Use the new clone functionality
            cloned_folder_path = client.clone(folder_id, destination_path)

            if cloned_folder_path is None:
                raise Exception("Folder clone failed.")

            progress.setValue(50)
            QtWidgets.QApplication.processEvents()

            # Load styling information for all maps in the cloned folder
            layout.itemAt(0).widget().setText("Loading styling information...")
            QtWidgets.QApplication.processEvents()
            self.load_and_save_styles(cloned_folder_path)

            progress.setValue(70)
            QtWidgets.QApplication.processEvents()

            # Create a QGIS project in the cloned folder
            layout.itemAt(0).widget().setText("Creating QGIS project...")
            QtWidgets.QApplication.processEvents()
            project_path = self.create_qgis_project(cloned_folder_path, crs)

            progress.setValue(90)
            QtWidgets.QApplication.processEvents()

            progress.setValue(100)
            QtWidgets.QApplication.processEvents()

            # Close progress dialog
            progress_dialog.close()

            # Show completion message
            QMessageBox.information(
                self.parent,
                "Clone Complete",
                f"Successfully cloned folder to {destination_path}."
            )

            # Emit signal with project path
            self.cloneCompleted.emit(str(project_path))

        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(
                self.parent,
                "Clone Failed",
                f"Error cloning folder: {str(e)}"
            )

    def load_and_save_styles(self, folder_path):
        """Load styling information from MapHub and save it as .qml files"""
        print(f"Loading styling information for maps in {folder_path}")

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

                                # Create a temporary layer to apply the style
                                if file.endswith(('.shp', '.gpkg', '.geojson', '.kml', '.fgb')):
                                    temp_layer = QgsVectorLayer(str(file_path), file_path.stem, "ogr")
                                else:
                                    temp_layer = QgsRasterLayer(str(file_path), file_path.stem)

                                if temp_layer.isValid():
                                    # Apply the style to the layer
                                    apply_style_to_layer(temp_layer, map_data['map']['visuals'])

                                    # Save the style to a .qml file
                                    style_path = file_path.with_suffix('.qml')
                                    temp_layer.saveNamedStyle(str(style_path))
                                    print(f"Saved style to {style_path}")
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
                        # Check if there's a QGIS style file
                        style_path = file_path.with_suffix('.qml')
                        if style_path.exists():
                            layer.loadNamedStyle(str(style_path))

                        project.addMapLayer(layer)

                # Add raster layers
                elif file.endswith(('.tif', '.tiff', '.jpg', '.png')):
                    layer = QgsRasterLayer(str(file_path), file_path.stem)
                    if layer.isValid():
                        # Check if there's a QGIS style file
                        style_path = file_path.with_suffix('.qml')
                        if style_path.exists():
                            layer.loadNamedStyle(str(style_path))

                        project.addMapLayer(layer)

        # Save the project
        project_path = folder_path / f"{folder_name}.qgz"
        project.write(str(project_path))

        return project_path
