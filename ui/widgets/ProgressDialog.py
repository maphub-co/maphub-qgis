from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton

class ProgressDialog(QDialog):
    """Reusable progress dialog for long-running operations."""
    
    def __init__(self, title, message, parent=None):
        """
        Initialize the progress dialog.
        
        Args:
            title (str): The dialog title
            message (str): The initial message
            parent (QWidget, optional): Parent widget
        """
        super(ProgressDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.resize(400, 150)
        
        # Set up UI
        self.layout = QVBoxLayout(self)
        
        # Add message label
        self.message_label = QLabel(message)
        self.layout.addWidget(self.message_label)
        
        # Add progress bar
        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.progress_bar)
        
        # Add cancel button
        self.button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_layout)
        
    def set_progress(self, value, maximum=100):
        """
        Set the progress bar value.
        
        Args:
            value (int): The current progress value
            maximum (int, optional): The maximum progress value
        """
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)
        
    def set_message(self, message):
        """
        Update the message text.
        
        Args:
            message (str): The new message
        """
        self.message_label.setText(message)