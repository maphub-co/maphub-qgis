from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt5.QtCore import Qt

from ..dialogs.MapHubBaseDialog import MapHubBaseDialog
from ..widgets.WorkspaceNavigationWidget import WorkspaceNavigationWidget
from ...utils.project_utils import folder_has_project, load_maphub_project


class ProjectFolderNavigationWidget(WorkspaceNavigationWidget):
    """
    A specialized version of WorkspaceNavigationWidget that only shows folders with projects.
    """
    
    def __init__(self, parent=None, folder_select_mode=True, default_folder_id=None):
        """
        Initialize the ProjectFolderNavigationWidget.
        
        Args:
            parent: The parent widget
            folder_select_mode: Whether to enable folder selection mode
            default_folder_id: Optional folder ID to select by default
        """
        super(ProjectFolderNavigationWidget, self).__init__(
            parent, 
            folder_select_mode,
            default_folder_id
        )
    
    def on_folder_clicked(self, folder_id):
        """
        Handle folder click event.
        
        Args:
            folder_id: The ID of the clicked folder
        """
        # Check if the folder has a project before navigating
        if folder_has_project(folder_id):
            # Call the parent method to handle navigation
            super().on_folder_clicked(folder_id)
        else:
            # Show a message that this folder doesn't have a project
            QMessageBox.information(
                self,
                "No Project Found",
                "This folder does not contain a QGIS project. Please select a different folder."
            )


class LoadProjectDialog(MapHubBaseDialog):
    """
    Dialog for selecting an existing project folder to load.
    
    This dialog allows users to navigate through workspaces and folders to select
    a project folder to load.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the LoadProjectDialog.
        
        Args:
            parent: The parent widget
        """
        super(LoadProjectDialog, self).__init__(parent)
        
        self.selected_folder_id = None
        
        self.setWindowTitle("Load Project from MapHub")
        self.resize(500, 600)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Instructions label
        instructions = QLabel("Select a project folder to load:")
        instructions.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(instructions)
        
        # Workspace navigation widget
        self.workspace_nav_widget = ProjectFolderNavigationWidget(
            self, 
            folder_select_mode=True
        )
        main_layout.addWidget(self.workspace_nav_widget)
        
        # Connect signals
        self.workspace_nav_widget.folder_selected.connect(self.on_folder_selected)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Load button
        self.load_button = QPushButton("Load")
        self.load_button.setEnabled(False)  # Disabled until a folder is selected
        self.load_button.clicked.connect(self.accept)
        buttons_layout.addWidget(self.load_button)
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        main_layout.addLayout(buttons_layout)
        
    def on_folder_selected(self, folder_id):
        """
        Handle folder selection.
        
        Args:
            folder_id: The ID of the selected folder
        """
        # Check if the folder has a project
        if folder_has_project(folder_id):
            self.selected_folder_id = folder_id
            self.load_button.setEnabled(True)
        else:
            self.selected_folder_id = None
            self.load_button.setEnabled(False)
            
            # Show a message that this folder doesn't have a project
            QMessageBox.information(
                self,
                "No Project Found",
                "This folder does not contain a QGIS project. Please select a different folder."
            )
        
    def get_selected_folder_id(self):
        """
        Get the ID of the selected folder.
        
        Returns:
            str: The ID of the selected folder, or None if no folder was selected
        """
        return self.selected_folder_id