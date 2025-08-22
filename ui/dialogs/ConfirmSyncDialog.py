import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy
from PyQt5.QtCore import Qt

from .MapHubBaseDialog import MapHubBaseDialog


class ConfirmSyncDialog(MapHubBaseDialog):
    """
    Dialog for confirming synchronization of a single layer.
    
    This dialog shows information about the layer to be synchronized and
    asks the user to confirm the synchronization action.
    """
    
    def __init__(self, layer_name, action, parent=None):
        """
        Initialize the dialog.
        
        Args:
            layer_name: The name of the layer to synchronize
            action: The synchronization action to perform
            parent: The parent widget
        """
        super(ConfirmSyncDialog, self).__init__(parent)
        self.setWindowTitle("Confirm Synchronization")
        self.resize(400, 200)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Add message
        message_label = QLabel("Are you sure you want to synchronize this layer?")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        
        # Add layer info
        layer_label = QLabel(f"<b>Layer:</b> {layer_name}")
        layer_label.setWordWrap(True)
        layout.addWidget(layer_label)
        
        # Add action info
        action_label = QLabel(f"<b>Action:</b> {action}")
        action_label.setWordWrap(True)
        layout.addWidget(action_label)
        
        # Add spacer
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Add buttons
        button_layout = QHBoxLayout()
        
        # Add spacer to push buttons to the right
        button_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # Add Synchronize button
        sync_button = QPushButton("Synchronize")
        sync_button.clicked.connect(self.accept)
        button_layout.addWidget(sync_button)
        
        # Add Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)