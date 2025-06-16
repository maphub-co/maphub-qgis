import os
import json
import uuid
import shutil
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (QDialog, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar, 
                            QMessageBox, QPushButton, QSpacerItem, QSizePolicy, QFrame)
from PyQt5.QtGui import QIcon, QCursor
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QDialog, QFileDialog
from qgis.core import (QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer, 
                      QgsRasterLayer, QgsMapLayer)

from ..utils import get_maphub_client, apply_style_to_layer, handled_exceptions, get_layer_styles_as_json
from .CreateFolderDialog import CreateFolderDialog

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'CloneFolderDialog.ui'))

class CloneFolderDialog(QDialog, FORM_CLASS):
    # Define signals
    cloneCompleted = pyqtSignal(str)  # Signal emitted when cloning is complete, passes project path

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(CloneFolderDialog, self).__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.iface = iface

        # Initialize folder navigation history
        self.folder_history = []
        self.current_folder = None
        self.selected_folder_id = None

        # Get the list layout for folders
        self.list_layout = self.findChild(QtWidgets.QVBoxLayout, 'listLayout')

        # Connect signals
        self.pushButton_browse.clicked.connect(self.browse_destination)
        self.comboBox_workspace.currentIndexChanged.connect(self.on_workspace_selected)

        # Set default CRS to EPSG:4326
        default_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.projectionSelector.setCrs(default_crs)

        # Initialize UI components
        self._populate_workspaces_combobox()

    def _populate_workspaces_combobox(self):
        """Populate the workspace combobox with available workspaces."""
        self.comboBox_workspace.clear()

        # Get the workspaces from MapHub
        client = get_maphub_client()
        workspaces = client.workspace.get_workspaces()

        for workspace in workspaces:
            workspace_id = workspace.get('id')
            workspace_name = workspace.get('name', 'Unknown Workspace')
            self.comboBox_workspace.addItem(workspace_name, workspace_id)

    def on_workspace_selected(self, index):
        """Handle workspace selection change"""
        if index < 0:
            return

        workspace_id = self.comboBox_workspace.itemData(index)
        root_folder = get_maphub_client().folder.get_root_folder(workspace_id)
        folder_id = root_folder["folder"]["id"]

        # Reset workspace history
        self.folder_history = [folder_id]
        self.current_folder = folder_id

        # Load folder contents
        self.load_folder_contents(folder_id)

    def load_folder_contents(self, folder_id):
        """Load subfolders for a folder"""
        # Clear any existing items
        self.clear_list_layout()

        # Get folder details including child folders
        folder_details = get_maphub_client().folder.get_folder(folder_id)
        child_folders = folder_details.get("child_folders", [])

        # Add navigation controls if we have folder history
        if self.folder_history:
            self.add_navigation_controls()

        # Add "Create New Folder" button
        self.add_create_folder_button()

        # Display child folders
        for folder in child_folders:
            self.add_folder_item(folder)

        # Update the selected folder ID
        self.selected_folder_id = folder_id

    def clear_list_layout(self):
        """Clear all widgets from the list layout"""
        for i in reversed(range(self.list_layout.count())):
            widget = self.list_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

    def add_navigation_controls(self):
        """Add navigation controls for folder browsing"""
        nav_frame = QtWidgets.QFrame()
        nav_frame.setStyleSheet("background-color: #f0f0f0; border-radius: 4px;")
        nav_layout = QtWidgets.QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(5, 5, 5, 5)
        nav_layout.setSpacing(5)

        # Add "Back" button if we have history
        if len(self.folder_history) > 1:
            btn_back = QtWidgets.QPushButton("← Back")
            btn_back.setToolTip("Go back to previous folder")
            btn_back.clicked.connect(self.on_back_clicked)
            nav_layout.addWidget(btn_back)

        # Add current path display
        if self.folder_history:
            current_folder_id = self.folder_history[-1]
            folder_details = get_maphub_client().folder.get_folder(current_folder_id)
            folder_name = folder_details.get("folder", {}).get("name", "Unknown Folder")

            path_label = QtWidgets.QLabel(f"Current folder: {folder_name}")
            path_label.setStyleSheet("font-weight: bold;")
            nav_layout.addWidget(path_label)

        # Add spacer
        nav_layout.addItem(QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))

        # Add to layout
        self.list_layout.addWidget(nav_frame)

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

    def add_folder_item(self, folder_data):
        """Create a frame for each folder item."""
        item_frame = QtWidgets.QFrame()
        item_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        item_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        item_frame.setMinimumHeight(40)

        # Set margin and spacing for a more compact look
        item_layout = QtWidgets.QHBoxLayout(item_frame)
        item_layout.setContentsMargins(5, 5, 5, 5)
        item_layout.setSpacing(5)

        # Add folder icon
        folder_icon = QIcon.fromTheme("folder", QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))
        folder_icon_label = QtWidgets.QLabel()
        folder_icon_label.setPixmap(folder_icon.pixmap(24, 24))
        item_layout.addWidget(folder_icon_label)

        # Folder name
        name_label = QtWidgets.QLabel(folder_data.get('name', 'Unnamed Folder'))
        font = name_label.font()
        font.setBold(True)
        name_label.setFont(font)
        item_layout.addWidget(name_label)

        # Add spacer
        item_layout.addItem(QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))

        # Add "Select" button
        btn_select = QtWidgets.QPushButton("Select")
        btn_select.setToolTip("Select this folder for cloning")
        btn_select.clicked.connect(lambda: self.on_folder_selected(folder_data['id']))
        item_layout.addWidget(btn_select)

        # Store folder_id in the frame for later reference
        item_frame.setProperty("folder_id", folder_data['id'])

        # Check if this is the selected folder
        if self.selected_folder_id and folder_data['id'] == self.selected_folder_id:
            # Highlight the selected folder
            item_frame.setStyleSheet("background-color: #e0f0ff;")

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

    def on_folder_clicked(self, folder_id):
        """Handle click on a folder item to navigate into it"""
        # Add the folder to the navigation history
        self.folder_history.append(folder_id)

        # Load the contents of the clicked folder
        self.load_folder_contents(folder_id)

    def on_folder_selected(self, folder_id):
        """Handle selection of a folder for cloning"""
        # Refresh the display to show the selected folder
        self.selected_folder_id = folder_id
        self.load_folder_contents(self.folder_history[-1])
        self.selected_folder_id = folder_id

    def on_create_folder_clicked(self):
        """Handle click on the create folder button"""
        # Get the current workspace ID
        workspace_id = self.comboBox_workspace.currentData()

        # Get the current folder ID as the parent
        parent_folder_id = self.folder_history[-1] if self.folder_history else None

        # Open the create folder dialog
        create_folder_dialog = CreateFolderDialog(self, workspace_id, parent_folder_id)
        result = create_folder_dialog.exec_()

        if result == QDialog.Accepted and create_folder_dialog.folder:
            # Refresh the current folder to show the new folder
            self.load_folder_contents(self.folder_history[-1])

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

        if not self.selected_folder_id:
            QMessageBox.warning(self, "Invalid Folder", "No folder selected for cloning.")
            return

        # Get the CRS
        crs = self.get_crs()

        # Get the file format
        file_format = self.get_file_format()

        # Hide the dialog but don't close it yet
        self.hide()

        # Start the cloning process
        self.clone_folder(self.selected_folder_id, destination_path, crs, file_format)

        # Now close the dialog
        super().accept()


    @handled_exceptions
    def clone_folder(self, folder_id, destination_path, crs, file_format=None):
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
            cloned_folder_path = client.clone(folder_id, destination_path, file_format)

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
                        # Apply style directly from memory if available
                        if hasattr(self, 'file_styles') and str(file_path) in self.file_styles:
                            apply_style_to_layer(layer, self.file_styles[str(file_path)])
                            print(f"Applied style to layer {layer.name()} directly from memory")

                        project.addMapLayer(layer)

                # Add raster layers
                elif file.endswith(('.tif', '.tiff', '.jpg', '.png')):
                    layer = QgsRasterLayer(str(file_path), file_path.stem)
                    if layer.isValid():
                        # Apply style directly from memory if available
                        if hasattr(self, 'file_styles') and str(file_path) in self.file_styles:
                            apply_style_to_layer(layer, self.file_styles[str(file_path)])
                            print(f"Applied style to layer {layer.name()} directly from memory")

                        project.addMapLayer(layer)

        # Save the project
        project_path = folder_path / f"{folder_name}.qgz"
        project.write(str(project_path))

        return project_path
