import os
from typing import List, Dict, Any, Optional, Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, 
                            QPushButton, QLabel, QSpacerItem, QSizePolicy)
from PyQt5.QtGui import QIcon, QCursor

from ...utils import get_maphub_client
from ..dialogs.MapHubBaseDialog import style


class ProjectNavigationWidget(QWidget):
    """
    A reusable widget for project navigation in MapHub.

    This widget provides a UI for browsing folders in MapHub, including:
    - Navigation controls (back button, current folder display)
    - Folder items display
    - Navigation actions (back, click on folder)

    Signals:
        folder_clicked(str): Emitted when a folder is clicked for navigation
        folder_selected(str): Emitted when a folder is selected (e.g., for an operation)
    """

    folder_clicked = pyqtSignal(str)
    folder_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super(ProjectNavigationWidget, self).__init__(parent)

        # Initialize state
        self.folder_history: List[str] = []
        self.selected_folder_id: Optional[str] = None
        self.custom_button_config: Optional[Dict[str, Any]] = None
        self.add_select_button: bool = True

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

    def clear_list_layout(self):
        """Clear all widgets from the list layout"""
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

    def get_current_folder_id(self) -> Optional[str]:
        """
        Get the ID of the current folder (the one being displayed)

        Returns:
            Optional[str]: The ID of the current folder, or None if no folder is being displayed
        """
        if self.folder_history:
            return self.folder_history[-1]
        return None
