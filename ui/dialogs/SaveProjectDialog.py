from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import Qt

from ...utils.project_utils import folder_has_project
from ..dialogs.MapHubBaseDialog import MapHubBaseDialog
from ..widgets.WorkspaceNavigationWidget import WorkspaceNavigationWidget


class SaveProjectDialog(MapHubBaseDialog):
    """
    Dialog for selecting a folder to save the current QGIS project to MapHub.
    
    This dialog allows users to navigate through workspaces and folders to select
    a destination folder for saving the current project.
    """
    
    def __init__(self, parent=None, default_folder_id=None):
        """
        Initialize the SaveProjectDialog.
        
        Args:
            parent: The parent widget
            default_folder_id: Optional folder ID to select by default
        """
        super(SaveProjectDialog, self).__init__(parent)
        
        self.selected_folder_id = None
        self.default_folder_id = default_folder_id
        
        self.setWindowTitle("Save Project to MapHub")
        self.resize(500, 600)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Instructions label
        instructions = QLabel("Select a folder to save your project to:")
        instructions.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(instructions)
        
        # Workspace navigation widget
        self.workspace_nav_widget = WorkspaceNavigationWidget(
            self, 
            folder_select_mode=True,
            default_folder_id=self.default_folder_id
        )
        main_layout.addWidget(self.workspace_nav_widget)
        
        # Connect signals
        self.workspace_nav_widget.folder_selected.connect(self.on_folder_selected)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.setEnabled(False)  # Disabled until a folder is selected
        self.save_button.clicked.connect(self.accept)
        buttons_layout.addWidget(self.save_button)
        
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
        self.selected_folder_id = folder_id
        self.save_button.setEnabled(True)
        
    def get_selected_folder_id(self):
        """
        Get the ID of the selected folder.
        
        Returns:
            str: The ID of the selected folder, or None if no folder was selected
        """
        return self.selected_folder_id

    def accept(self):
        """Override accept to check for existing project before accepting the dialog"""
        # Get the selected folder ID
        folder_id = self.selected_folder_id

        if not folder_id:
            # No folder selected, show an error
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Folder Selected", "Please select a folder to save the project to.")
            return

        # Check if the folder already has a project
        if folder_has_project(folder_id):
            # Show confirmation dialog
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "Project Already Exists",
                "This folder already has a QGIS project. Do you want to overwrite it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.No:
                # User chose not to overwrite, cancel the save
                # Don't call super().accept() to ensure the dialog stays open
                return

        # If we get here, either there's no existing project or the user confirmed overwrite
        # Call the parent class's accept method to close the dialog
        super(SaveProjectDialog, self).accept()