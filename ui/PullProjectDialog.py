import os
import json
import uuid
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, Qt, QUrl
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QProgressBar, QMessageBox
from PyQt5.QtGui import QDesktopServices
from qgis.PyQt import uic, QtWidgets
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer

from ..utils import get_maphub_client, apply_style_to_layer, handled_exceptions

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'PullProjectDialog.ui'))

class PullProjectDialog(QDialog, FORM_CLASS):
    # Define signals
    pullCompleted = pyqtSignal(str)  # Signal emitted when pull is complete, passes project path

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(PullProjectDialog, self).__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.iface = iface

        # Initialize variables
        self.project_path = None
        self.maphub_dir = None
        self.workspace_id = None

        # Connect signals
        self.label_status.setOpenExternalLinks(True)

        # Check if current project has a .maphub folder
        self.check_project_status()

    def check_project_status(self):
        """Check if the current project has a .maphub folder"""
        # Get the current project path
        project = QgsProject.instance()
        project_filename = project.fileName()

        if not project_filename:
            self.label_status.setText("No project is currently open. Please open a project first.")
            self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
            return

        # Get the project directory
        project_dir = Path(os.path.dirname(project_filename))
        self.project_path = project_dir

        # Check if .maphub folder exists
        maphub_dir = project_dir / ".maphub"
        if not maphub_dir.exists():
            self.label_status.setText("This project is not linked to MapHub. Use 'Clone Folder' to create a linked project.")
            self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
            return

        # Check if config.json exists in .maphub folder
        config_file = maphub_dir / "config.json"
        if not config_file.exists():
            self.label_status.setText("Invalid MapHub configuration. Use 'Clone Folder' to create a properly linked project.")
            self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
            return

        # Read config.json to get folder_id
        try:
            with open(config_file, "r") as f:
                config = json.load(f)

            if "remote_id" not in config:
                self.label_status.setText("Invalid MapHub configuration. Missing remote_id.")
                self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
                return

            self.folder_id = uuid.UUID(config["remote_id"])
            self.maphub_dir = maphub_dir

            # Get the MapHub client and workspace ID
            try:
                client = get_maphub_client()
                folder_data = client.folder.get_folder(self.folder_id)
                self.workspace_id = folder_data["folder"]["workspace_id"]

                # Create a clickable link to the folder on MapHub
                folder_url = f"https://www.maphub.co/dashboard/workspaces/{self.workspace_id}/{self.folder_id}"
                link_text = f'Project is linked to <a href="{folder_url}">MapHub folder {self.folder_id}</a>. Ready to pull.'
                self.label_status.setText(link_text)
            except Exception as e:
                # If we can't get the workspace ID, fall back to the original text
                print(f"Error getting workspace ID: {str(e)}")
                self.label_status.setText(f"Project is linked to MapHub folder {self.folder_id}. Ready to pull.")

            self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(True)

        except Exception as e:
            self.label_status.setText(f"Error reading MapHub configuration: {str(e)}")
            self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
            return

    def accept(self):
        """Override accept to perform pull when OK is clicked"""
        # Validate inputs
        if not self.project_path or not self.maphub_dir or not self.folder_id:
            QMessageBox.warning(self, "Invalid Project", "This project is not properly linked to MapHub.")
            return

        # Hide the dialog but don't close it yet
        self.hide()

        # Start the pull process
        self.pull_project()

        # Now close the dialog
        super().accept()

    @handled_exceptions
    def pull_project(self):
        """Pull the latest data from MapHub to update the project"""
        print(f"Pulling latest data from MapHub folder: {self.folder_id}")

        # Create progress dialog
        progress = QProgressBar()
        progress.setMinimum(0)
        progress.setMaximum(100)
        progress.setValue(0)

        progress_dialog = QDialog(self.parent)
        progress_dialog.setWindowTitle("Pulling Project")
        progress_dialog.setMinimumWidth(300)

        layout = QVBoxLayout(progress_dialog)
        layout.addWidget(QLabel("Pulling latest changes from MapHub..."))
        layout.addWidget(progress)

        progress_dialog.show()

        try:
            # Get the MapHub client
            client = get_maphub_client()

            # Pull the latest changes
            progress.setValue(10)
            QtWidgets.QApplication.processEvents()

            # Use the pull functionality
            client.pull(self.project_path)

            progress.setValue(50)
            QtWidgets.QApplication.processEvents()

            # Load styling information for all maps in the folder
            layout.itemAt(0).widget().setText("Loading styling information...")
            QtWidgets.QApplication.processEvents()
            self.load_and_save_styles(self.project_path)

            progress.setValue(70)
            QtWidgets.QApplication.processEvents()

            # Update the QGIS project with new or updated layers
            layout.itemAt(0).widget().setText("Updating QGIS project...")
            QtWidgets.QApplication.processEvents()
            self.update_qgis_project(self.project_path)

            progress.setValue(90)
            QtWidgets.QApplication.processEvents()

            progress.setValue(100)
            QtWidgets.QApplication.processEvents()

            # Close progress dialog
            progress_dialog.close()

            # Show completion message
            QMessageBox.information(
                self.parent,
                "Pull Complete",
                f"Successfully pulled latest data from MapHub."
            )

            # Emit signal with project path
            self.pullCompleted.emit(str(self.project_path))

        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(
                self.parent,
                "Pull Failed",
                f"Error pulling project: {str(e)}"
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

    def update_qgis_project(self, folder_path):
        """Update the QGIS project with new or updated layers"""
        # Get the current project
        project = QgsProject.instance()

        # Get all existing layers in the project
        existing_layers = {}
        for layer_id, layer in project.mapLayers().items():
            existing_layers[str(Path(layer.source()).resolve())] = layer

        # Find all GIS files in the folder and add them as layers if they don't exist
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = Path(root) / file

                # Skip .maphub directory
                if ".maphub" in str(file_path):
                    continue

                # Process vector layers
                if file.endswith(('.shp', '.gpkg', '.geojson', '.kml', '.fgb')):
                    abs_path = str(file_path.resolve())
                    if abs_path in existing_layers:
                        # Layer already exists, check if we need to update style
                        layer = existing_layers[abs_path]
                        # Apply style directly from memory if available
                        if hasattr(self, 'file_styles') and str(file_path) in self.file_styles:
                            apply_style_to_layer(layer, self.file_styles[str(file_path)])
                            print(f"Applied style to existing layer {layer.name()} directly from memory")
                            layer.triggerRepaint()
                    else:
                        # New layer, add it to the project
                        layer = QgsVectorLayer(str(file_path), file_path.stem, "ogr")
                        if layer.isValid():
                            # Apply style directly from memory if available
                            if hasattr(self, 'file_styles') and str(file_path) in self.file_styles:
                                apply_style_to_layer(layer, self.file_styles[str(file_path)])
                                print(f"Applied style to new layer {layer.name()} directly from memory")

                            project.addMapLayer(layer)

                # Process raster layers
                elif file.endswith(('.tif', '.tiff', '.jpg', '.png')):
                    abs_path = str(file_path.resolve())
                    if abs_path in existing_layers:
                        # Layer already exists, check if we need to update style
                        layer = existing_layers[abs_path]
                        # Apply style directly from memory if available
                        if hasattr(self, 'file_styles') and str(file_path) in self.file_styles:
                            apply_style_to_layer(layer, self.file_styles[str(file_path)])
                            print(f"Applied style to existing layer {layer.name()} directly from memory")
                            layer.triggerRepaint()
                    else:
                        # New layer, add it to the project
                        layer = QgsRasterLayer(str(file_path), file_path.stem)
                        if layer.isValid():
                            # Apply style directly from memory if available
                            if hasattr(self, 'file_styles') and str(file_path) in self.file_styles:
                                apply_style_to_layer(layer, self.file_styles[str(file_path)])
                                print(f"Applied style to new layer {layer.name()} directly from memory")

                            project.addMapLayer(layer)

        # Save the project
        project.write()
