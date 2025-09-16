from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt5.QtCore import Qt

from ..dialogs.MapHubBaseDialog import MapHubBaseDialog
from ..widgets.WorkspaceNavigationWidget import WorkspaceNavigationWidget
from ...utils.error_manager import handled_exceptions


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