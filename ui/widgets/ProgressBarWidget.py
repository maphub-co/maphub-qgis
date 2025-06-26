import os
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, 
                            QLabel, QDialog, QApplication)
from ..dialogs.MapHubBaseDialog import style

class ProgressBarWidget(QWidget):
    """
    A reusable progress bar widget that can be used to show progress of operations.
    """

    def __init__(self, parent=None, title="Progress", message="Processing..."):
        """
        Initialize the progress bar widget.

        Args:
            parent (QWidget): The parent widget
            title (str): The title of the progress dialog
            message (str): The initial message to display
        """
        super(ProgressBarWidget, self).__init__(parent)

        # Create the progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

        # Create the message label
        self.message_label = QLabel(message)

        # Set up the layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.message_label)
        layout.addWidget(self.progress_bar)

        # Create the dialog that will contain this widget
        self.dialog = QDialog(parent)
        self.dialog.setWindowTitle(title)
        self.dialog.setMinimumWidth(300)

        # Apply the style sheet
        if style:
            self.dialog.setStyleSheet(style)

        # Set the layout for the dialog
        dialog_layout = QVBoxLayout(self.dialog)
        dialog_layout.addWidget(self)

    def show_dialog(self):
        """Show the progress dialog"""
        self.dialog.show()

    def close_dialog(self):
        """Close the progress dialog"""
        self.dialog.close()

    def set_value(self, value):
        """
        Set the progress bar value

        Args:
            value (int): The progress value (0-100)
        """
        self.progress_bar.setValue(value)
        QApplication.processEvents()

    def set_message(self, message):
        """
        Set the progress message

        Args:
            message (str): The message to display
        """
        self.message_label.setText(message)
        QApplication.processEvents()

    def update_progress(self, value, message=None):
        """
        Update both the progress value and optionally the message

        Args:
            value (int): The progress value (0-100)
            message (str, optional): The message to display
        """
        self.progress_bar.setValue(value)
        if message:
            self.message_label.setText(message)
        QApplication.processEvents()
