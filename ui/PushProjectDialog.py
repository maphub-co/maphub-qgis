import os
import json
import uuid
import re
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, Qt, QUrl
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QProgressBar, QMessageBox
from PyQt5.QtGui import QDesktopServices
from qgis.PyQt import uic, QtWidgets
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer, QgsVectorFileWriter,
    QgsRasterFileWriter, QgsRasterPipe
)

from .CloneFolderDialog import CloneFolderDialog
from ..utils import get_maphub_client, apply_style_to_layer, handled_exceptions, get_layer_styles_as_json

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'PushProjectDialog.ui'))

class PushProjectDialog(QDialog, FORM_CLASS):
    # Define signals
    pushCompleted = pyqtSignal(str)  # Signal emitted when push is complete, passes project path

    @staticmethod
    def sanitize_filename(name):
        """
        Sanitize a string to be used as a filename.

        Args:
            name (str): The string to sanitize

        Returns:
            str: A sanitized string that can be used as a filename
        """
        # Replace spaces with underscores
        name = name.replace(' ', '_')

        # Remove any characters that aren't alphanumeric, underscore, or hyphen
        name = re.sub(r'[^\w\-]', '', name)

        # Ensure the name isn't empty
        if not name:
            name = "layer"

        return name

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(PushProjectDialog, self).__init__(parent)
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
            # Save the current project layers before they get cleared
            saved_layers = []
            current_layers = project.mapLayers().values()

            for layer in current_layers:
                # Store layer information
                layer_info = {
                    'source': layer.source(),
                    'name': layer.name(),
                    'type': 'vector' if isinstance(layer, QgsVectorLayer) else 'raster' if isinstance(layer, QgsRasterLayer) else 'unknown'
                }

                # Save style information if available
                if layer.styleManager().currentStyle():
                    layer_info['style'] = layer.styleManager().style(layer.styleManager().currentStyle())
                    layer_info['style_name'] = layer.styleManager().currentStyle()

                saved_layers.append(layer_info)

            # If there is no saved project yet, clone a folder from MapHub, and merge the in memory Project with the one from the clone.
            clone_dialog = CloneFolderDialog(self.iface, self)
            clone_dialog.cloneCompleted.connect(lambda path: self.load_and_append(path, saved_layers))
            result = clone_dialog.exec_()

            if not result:
                raise Exception("Project is not linked to MapHub. You must clone a (empty) folder first.")
        else:
            # Get the project directory
            self.project_path = Path(os.path.dirname(project_filename))

        project_dir = self.project_path

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
                link_text = f'Project is linked to <a href="{folder_url}">MapHub folder {self.folder_id}</a>. Ready to push changes.'
                self.label_status.setText(link_text)
            except Exception as e:
                # If we can't get the workspace ID, fall back to the original text
                print(f"Error getting workspace ID: {str(e)}")
                self.label_status.setText(f"Project is linked to MapHub folder {self.folder_id}. Ready to push changes.")

            self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(True)

        except Exception as e:
            self.label_status.setText(f"Error reading MapHub configuration: {str(e)}")
            self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
            return

    def load_and_append(self, project_path: Path, saved_layers=None):
        # Add the layers saved in the project to the Project that is saved in the project_path
        # Create a temporary project to load the project from project_path
        temp_project = QgsProject()
        temp_project.read(str(project_path))


        # Add each saved layer to the temporary project
        for layer_info in saved_layers:
            # Create a new layer based on the saved information
            if layer_info['type'] == 'vector':
                new_layer = QgsVectorLayer(layer_info['source'], layer_info['name'], "ogr")
            elif layer_info['type'] == 'raster':
                new_layer = QgsRasterLayer(layer_info['source'], layer_info['name'])
            else:
                continue

            if new_layer.isValid():
                # Apply the original style to the new layer if available
                if 'style' in layer_info and 'style_name' in layer_info:
                    new_layer.styleManager().addStyle(
                        layer_info['style_name'],
                        layer_info['style']
                    )
                    new_layer.styleManager().setCurrentStyle(layer_info['style_name'])

                # Add the new layer to the temporary project
                temp_project.addMapLayer(new_layer)

        # Save the temporary project with the added layers
        temp_project.write(str(project_path))

        # Set the project_dir to the directory of our project
        self.project_path = Path(os.path.dirname(project_path))

        if project_path:
            self.iface.addProject(project_path)

    def accept(self):
        """Override accept to perform push when OK is clicked"""
        # Validate inputs
        if not self.project_path or not self.maphub_dir or not self.folder_id:
            QMessageBox.warning(self, "Invalid Project", "This project is not properly linked to MapHub.")
            return

        # Hide the dialog but don't close it yet
        self.hide()

        # Start the push process
        self.push_project()

        # Now close the dialog
        super().accept()

    @handled_exceptions
    def push_project(self):
        """
        Push the project data to MapHub.

        This method first saves all local layers to disk to ensure that all edits
        are committed before pushing to MapHub, then pushes the project data to
        the linked MapHub folder.
        """
        print(f"Pushing project to MapHub folder: {self.folder_id}")

        # Create progress dialog
        progress = QProgressBar()
        progress.setMinimum(0)
        progress.setMaximum(100)
        progress.setValue(0)

        progress_dialog = QDialog(self.parent)
        progress_dialog.setWindowTitle("Pushing Project")
        progress_dialog.setMinimumWidth(300)

        layout = QVBoxLayout(progress_dialog)
        layout.addWidget(QLabel("Pushing changes to MapHub..."))
        layout.addWidget(progress)

        progress_dialog.show()

        try:
            # Get the MapHub client
            client = get_maphub_client()

            # Save all local layers before pushing
            layout.itemAt(0).widget().setText("Saving all local layers...")
            QtWidgets.QApplication.processEvents()
            self.save_all_layers()
            progress.setValue(20)
            QtWidgets.QApplication.processEvents()

            # Push the changes
            layout.itemAt(0).widget().setText("Pushing changes to MapHub...")
            QtWidgets.QApplication.processEvents()

            # Use the push functionality
            client.push(self.project_path)

            progress.setValue(50)
            QtWidgets.QApplication.processEvents()

            # Update QGIS visuals for all layers after pushing
            layout.itemAt(0).widget().setText("Updating QGIS visuals...")
            QtWidgets.QApplication.processEvents()
            self.update_qgis_visuals()

            progress.setValue(90)
            QtWidgets.QApplication.processEvents()

            progress.setValue(100)
            QtWidgets.QApplication.processEvents()

            # Close progress dialog
            progress_dialog.close()

            # Show completion message
            QMessageBox.information(
                self.parent,
                "Push Complete",
                f"Successfully pushed project changes to MapHub."
            )

            # Emit signal with project path
            self.pushCompleted.emit(str(self.project_path))

        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(
                self.parent,
                "Push Failed",
                f"Error pushing project: {str(e)}"
            )

    def save_all_layers(self):
        """
        Save all local layers in the project.

        This ensures that all edits to vector layers are committed to disk
        and all layers are saved in the project folder before pushing to MapHub,
        preventing data loss or inconsistencies between local files and what 
        gets pushed to the server.
        """
        # Get the current project
        project = QgsProject.instance()

        # Get all layers in the project
        layers = project.mapLayers().values()

        # Save each editable vector layer and ensure all layers are saved in the project folder
        for layer in layers:
            # Commit changes for editable vector layers
            if isinstance(layer, QgsVectorLayer) and layer.isEditable():
                print(f"Committing changes to layer: {layer.name()}")
                layer.commitChanges()

            # Check if the layer is already saved in the project folder
            if hasattr(layer, 'source') and layer.source():
                # Handle layers with complex data sources (e.g., with query parameters)
                source = layer.source()
                if '|' in source:
                    source_path = Path(source.split('|')[0])
                else:
                    source_path = Path(source)

                # Skip layers without a valid file path
                if not source_path.exists():
                    print(f"Skipping layer with non-file source: {layer.name()} ({source})")
                    continue

                # If the layer is not in the project folder, save it there
                if not str(source_path).startswith(str(self.project_path)):
                    try:
                        print(f"Saving layer to project folder: {layer.name()}")

                        # Create a new filename in the project folder with sanitized name
                        sanitized_name = self.sanitize_filename(layer.name())
                        new_filename = self.project_path / sanitized_name

                        # Determine the appropriate extension based on layer type
                        if isinstance(layer, QgsVectorLayer):
                            new_filename = new_filename.with_suffix('.fgb')
                            # Save vector layer to FlatGeoBuf
                            error = QgsVectorFileWriter.writeAsVectorFormat(
                                layer,
                                str(new_filename),
                                'UTF-8',
                                layer.crs(),
                                'FlatGeobuf'
                            )
                            if error[0] != QgsVectorFileWriter.NoError:
                                print(f"Error saving vector layer {layer.name()}: {error}")

                        elif isinstance(layer, QgsRasterLayer):
                            new_filename = new_filename.with_suffix('.tif')
                            # Save raster layer to GeoTIFF
                            pipe = QgsRasterPipe()
                            provider = layer.dataProvider()
                            if not pipe.set(provider.clone()):
                                print(f"Cannot set pipe provider for raster layer: {layer.name()}")
                                continue

                            writer = QgsRasterFileWriter(str(new_filename))
                            writer.setOutputFormat('GTiff')

                            # Write the raster
                            error = writer.writeRaster(
                                pipe,
                                provider.xSize(),
                                provider.ySize(),
                                provider.extent(),
                                provider.crs()
                            )

                            if error != QgsRasterFileWriter.NoError:
                                print(f"Error saving raster layer {layer.name()}: {error}")
                                continue

                        # Add the newly saved layer to the project and replace the old one
                        print(f"Layer saved to: {new_filename}")

                        # Get the layer's properties before removing it
                        layer_name = layer.name()
                        layer_id = layer.id()
                        is_visible = project.layerTreeRoot().findLayer(layer_id).isVisible()
                        layer_style = layer.styleManager().style(layer.styleManager().currentStyle())

                        # Create a new layer from the saved file
                        new_layer = None
                        if isinstance(layer, QgsVectorLayer):
                            new_layer = QgsVectorLayer(str(new_filename), layer_name, "ogr")
                        elif isinstance(layer, QgsRasterLayer):
                            new_layer = QgsRasterLayer(str(new_filename), layer_name)

                        if new_layer and new_layer.isValid():
                            # Apply the original style to the new layer
                            if layer_style:
                                new_layer.styleManager().addStyle(
                                    layer.styleManager().currentStyle(), 
                                    layer_style
                                )
                                new_layer.styleManager().setCurrentStyle(layer.styleManager().currentStyle())

                            # Add the new layer to the project
                            project.addMapLayer(new_layer, False)

                            # Get the layer tree and find the old layer's node
                            root = project.layerTreeRoot()
                            old_node = root.findLayer(layer_id)
                            if old_node:
                                # Get the parent group
                                parent = old_node.parent()

                                # Add the new layer to the same group
                                new_node = parent.insertLayer(parent.children().index(old_node), new_layer)

                                # Set visibility to match the old layer
                                new_node.setItemVisibilityChecked(is_visible)

                                # Remove the old layer
                                parent.removeChildNode(old_node)
                                print(f"Replaced layer {layer_name} with saved version")
                            else:
                                # If we can't find the old node, just add the new layer
                                root.addLayer(new_layer)
                                print(f"Added new layer {layer_name} (couldn't find old layer in tree)")
                        else:
                            print(f"Failed to create valid layer from saved file: {new_filename}")
                    except Exception as e:
                        print(f"Error saving layer {layer.name()} to project folder: {str(e)}")

    def update_qgis_visuals(self):
        """Update QGIS visuals for all layers in the project"""
        # Get the current project
        project = QgsProject.instance()

        # Get all layers in the project
        layers = project.mapLayers().values()

        # Update visuals for each layer
        for layer in layers:
            try:
                # Skip layers that don't have a file source
                if not hasattr(layer, 'source') or not layer.source():
                    continue

                # Get the file path
                file_path = Path(layer.source().split('|')[0])

                # Skip layers that aren't in the project directory
                if not str(file_path).startswith(str(self.project_path)):
                    continue

                # Extract map ID from the .maphub directory if possible
                maphub_dir = self.project_path / ".maphub" / "maps"
                map_id = None

                if maphub_dir.exists():
                    # Look through metadata files to find the one matching this file
                    for metadata_file in maphub_dir.glob("*.json"):
                        with open(metadata_file, "r") as f:
                            metadata = json.load(f)
                            if metadata.get("path") == str(file_path.relative_to(self.project_path)):
                                map_id = metadata.get("id")
                                break

                if map_id:
                    # Extract style information
                    try:
                        visuals = get_layer_styles_as_json(layer, {})

                        # Set the visuals for the map
                        client = get_maphub_client()
                        client.maps.set_visuals(uuid.UUID(map_id), visuals)
                        print(f"Updated visuals for map: {layer.name()}")
                    except Exception as e:
                        print(f"Warning: Failed to extract or update layer style: {str(e)}")
            except Exception as e:
                print(f"Error updating visuals for layer {layer.name()}: {e}")
