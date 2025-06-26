from typing import List, Dict, Any, Optional, Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QComboBox, QFrame, QSizePolicy)

from ...utils import get_maphub_client
from .ProjectNavigationWidget import ProjectNavigationWidget


class WorkspaceNavigationWidget(QWidget):
    """
    A reusable widget that combines workspace selection with project navigation.

    This widget provides a UI for selecting a workspace and browsing folders in MapHub, including:
    - Workspace selection dropdown
    - Navigation controls (back button, current folder display)
    - Folder items display
    - Navigation actions (back, click on folder)

    Signals:
        workspace_changed(str): Emitted when a workspace is selected
        folder_clicked(str): Emitted when a folder is clicked for navigation
        folder_selected(str): Emitted when a folder is selected (e.g., for an operation)
    """

    workspace_changed = pyqtSignal(str)
    folder_clicked = pyqtSignal(str)
    folder_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super(WorkspaceNavigationWidget, self).__init__(parent)

        # Initialize state
        self.selected_workspace_id: Optional[str] = None
        self.custom_button_config: Optional[Dict[str, Any]] = None

        # Set up UI
        self.setup_ui()

        # Populate workspaces
        self._populate_workspaces_combobox()

        # Connect signals
        self.comboBox_workspace.currentIndexChanged.connect(self.on_workspace_selected)
        self.project_nav_widget.folder_clicked.connect(self.on_folder_clicked)
        self.project_nav_widget.folder_selected.connect(self.on_folder_selected)

        self.on_workspace_selected(0)

    def setup_ui(self):
        """Set up the widget UI"""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(5)

        # Workspace selection layout
        self.workspace_layout = QHBoxLayout()
        self.workspace_layout.setContentsMargins(0, 0, 0, 0)
        self.workspace_layout.setSpacing(5)

        # Workspace label
        self.label_workspace = QLabel("Select Workspace:")
        self.workspace_layout.addWidget(self.label_workspace)

        # Workspace combobox
        self.comboBox_workspace = QComboBox()
        self.workspace_layout.addWidget(self.comboBox_workspace)

        # Add workspace selection to main layout
        self.main_layout.addLayout(self.workspace_layout)

        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        self.main_layout.addWidget(separator)

        # Create project navigation widget
        self.project_nav_widget = ProjectNavigationWidget(self)
        self.main_layout.addWidget(self.project_nav_widget)

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

        # Automatically select the first workspace if available
        if self.comboBox_workspace.count() > 0:
            self.comboBox_workspace.setCurrentIndex(0)

    def on_workspace_selected(self, index):
        """Handle workspace selection change"""
        if index < 0:
            return

        workspace_id = self.comboBox_workspace.itemData(index)
        self.selected_workspace_id = workspace_id

        # Use the navigation widget to set the workspace and load its contents
        self.project_nav_widget.set_workspace(workspace_id, self.custom_button_config)

        # Emit the workspace_changed signal
        self.workspace_changed.emit(workspace_id)

    def on_folder_clicked(self, folder_id):
        """Forward the folder_clicked signal"""
        self.folder_clicked.emit(folder_id)

    def on_folder_selected(self, folder_id):
        """Forward the folder_selected signal"""
        self.folder_selected.emit(folder_id)

    def set_custom_button(self, custom_button_config: Optional[Dict[str, Any]]):
        """
        Set a custom button configuration for folder items

        Args:
            custom_button_config (Dict[str, Any], optional): Custom button configuration for folder items
                {
                    'text': str,
                    'tooltip': str,
                    'callback': Callable[[str], None]
                }
        """
        self.custom_button_config = custom_button_config

        # If a workspace is already selected, update the navigation widget
        if self.selected_workspace_id:
            self.project_nav_widget.set_workspace(self.selected_workspace_id, custom_button_config)

    def set_add_select_button(self, add_select_button: bool):
        """
        Set whether to add a select button to folder items

        Args:
            add_select_button (bool): Whether to add a select button
        """
        self.project_nav_widget.add_select_button = add_select_button

        # If a workspace is already selected, update the navigation widget
        if self.selected_workspace_id:
            self.project_nav_widget.set_workspace(self.selected_workspace_id, self.custom_button_config)

    def get_selected_folder_id(self) -> Optional[str]:
        """
        Get the ID of the currently selected folder

        Returns:
            Optional[str]: The ID of the selected folder, or None if no folder is selected
        """
        return self.project_nav_widget.get_selected_folder_id()

    def get_current_folder_id(self) -> Optional[str]:
        """
        Get the ID of the current folder (the one being displayed)

        Returns:
            Optional[str]: The ID of the current folder, or None if no folder is being displayed
        """
        return self.project_nav_widget.get_current_folder_id()

    def get_selected_workspace_id(self) -> Optional[str]:
        """
        Get the ID of the currently selected workspace

        Returns:
            Optional[str]: The ID of the selected workspace, or None if no workspace is selected
        """
        return self.selected_workspace_id

    def load_folder_contents(self, folder_id: str):
        """
        Load and display the contents of a folder

        Args:
            folder_id (str): The ID of the folder to load
        """
        self.project_nav_widget.load_folder_contents(folder_id)
