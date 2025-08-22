from typing import Optional
import logging

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QComboBox, QFrame)

from ...utils.utils import get_maphub_client
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

    def __init__(self, parent=None, folder_select_mode=True, default_folder_id=None):
        super(WorkspaceNavigationWidget, self).__init__(parent)

        # Initialize state
        self.selected_workspace_id: Optional[str] = None
        self.folder_select_mode: bool = folder_select_mode
        self.default_folder_id: Optional[str] = default_folder_id

        # Set up UI
        self.setup_ui()

        # Connect signals
        self.comboBox_workspace.currentIndexChanged.connect(self.on_workspace_selected)
        self.project_nav_widget.folder_clicked.connect(self.on_folder_clicked)
        self.project_nav_widget.folder_selected.connect(self.on_folder_selected)

        # Populate workspaces
        self._populate_workspaces_combobox()
        
        # If a default folder ID is provided, try to navigate to it
        if self.default_folder_id:
            self.set_default_folder(self.default_folder_id)

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

        # Create project navigation widget with default folder
        self.project_nav_widget = ProjectNavigationWidget(
            self, 
            self.folder_select_mode,
            self.default_folder_id
        )
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
            # Setting the current index will trigger on_workspace_selected via the signal
            self.comboBox_workspace.setCurrentIndex(0)

    def on_workspace_selected(self, index):
        """Handle workspace selection change"""
        if index < 0:
            return

        workspace_id = self.comboBox_workspace.itemData(index)
        self.selected_workspace_id = workspace_id

        # Use the navigation widget to set the workspace and load its contents
        self.project_nav_widget.set_workspace(workspace_id)

        # Emit the workspace_changed signal
        self.workspace_changed.emit(workspace_id)

    def on_folder_clicked(self, folder_id):
        """Forward the folder_clicked signal"""
        self.folder_clicked.emit(folder_id)

    def on_folder_selected(self, folder_id):
        """Forward the folder_selected signal"""
        self.folder_selected.emit(folder_id)

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
        
    def set_default_folder(self, folder_id: str):
        """
        Set a default folder and navigate to it, adjusting the workspace if needed.
        
        This method will:
        1. Try to get the folder details to find its workspace
        2. Select the appropriate workspace in the dropdown
        3. Navigate to the folder
        
        If the folder cannot be found, it will log an error and continue as if no default folder was provided.
        
        Args:
            folder_id (str): The ID of the folder to set as default
        """
        try:
            # Get folder details to find its workspace
            client = get_maphub_client()
            folder_details = client.folder.get_folder(folder_id)
            
            # Check if folder details contain workspace_id
            if folder_details and 'folder' in folder_details and 'workspace_id' in folder_details['folder']:
                workspace_id = folder_details['folder']['workspace_id']
                
                # Find the index of this workspace in the combobox
                for i in range(self.comboBox_workspace.count()):
                    if self.comboBox_workspace.itemData(i) == workspace_id:
                        # Select this workspace (this will trigger on_workspace_selected)
                        self.comboBox_workspace.setCurrentIndex(i)
                        
                        # After workspace is loaded, navigate to the folder
                        self.load_folder_contents(folder_id)
                        
                        # Also set it as the selected folder
                        self.project_nav_widget.selected_folder_id = folder_id
                        
                        return
                
                # If we get here, the workspace was not found in the combobox
                logging.warning(f"Workspace {workspace_id} for folder {folder_id} not found in available workspaces")
            else:
                logging.warning(f"Could not determine workspace for folder {folder_id}")
                
        except Exception as e:
            # Log the error and continue as if no default folder was provided
            logging.error(f"Error setting default folder {folder_id}: {str(e)}")
            
            # Select the first workspace if available
            if self.comboBox_workspace.count() > 0:
                self.comboBox_workspace.setCurrentIndex(0)
