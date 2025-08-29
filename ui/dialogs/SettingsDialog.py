import os
from PyQt5.QtCore import QSettings, QStandardPaths
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFileDialog, QLineEdit
from qgis.PyQt import uic
from pathlib import Path

from .MapHubBaseDialog import MapHubBaseDialog
from ...utils.error_manager import handled_exceptions
from ...utils.utils import get_default_download_location

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'SettingsDialog.ui'))


class SettingsDialog(MapHubBaseDialog, FORM_CLASS):
    """
    Generic settings dialog for MapHub plugin.
    
    This dialog provides a tabbed interface for different categories of settings.
    It is designed to be extensible, allowing new settings tabs to be added in the future.
    """
    
    def __init__(self, iface, parent=None, refresh_callback=None, on_settings_changed=None):
        """
        Initialize the settings dialog.
        
        Args:
            iface: The QGIS interface
            parent: The parent widget
            refresh_callback: Optional callback function to execute when the "Refresh Now" button is clicked
            on_settings_changed: Optional callback function to execute when settings are changed and saved
        """
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.refresh_callback = refresh_callback
        self.on_settings_changed = on_settings_changed
        
        # Set up icons
        self.icon_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'icons')
        
        # Set refresh icon
        refresh_icon_path = os.path.join(self.icon_dir, 'refresh.svg')
        if os.path.exists(refresh_icon_path):
            self.refreshNowButton.setIcon(QIcon(refresh_icon_path))
        
        # Connect signals
        self.buttonBox.accepted.connect(self.on_accepted)
        self.refreshNowButton.clicked.connect(self.on_refresh_now_clicked)
        self.browseButton.clicked.connect(self.on_browse_clicked)
        self.toolButton_showHide.toggled.connect(self.toggle_password_visibility)
        
        # Load settings
        self.load_settings()
        
    def on_accepted(self):
        """Handle dialog acceptance."""
        # Save settings
        self.save_settings()
        
        # Call the settings changed callback if provided
        if self.on_settings_changed:
            self.on_settings_changed()
    
    def toggle_password_visibility(self, checked):
        """Toggle the visibility of the API key text."""
        if checked:
            self.apiKeyLineEdit.setEchoMode(QLineEdit.Normal)
        else:
            self.apiKeyLineEdit.setEchoMode(QLineEdit.Password)
            
    def load_settings(self):
        """Load settings from QSettings."""
        settings = QSettings()
        
        # Load scheduler settings
        enable_periodic = settings.value("MapHubPlugin/enable_periodic_updates", True, type=bool)
        update_interval = settings.value("MapHubPlugin/update_interval", 5, type=int)
        
        self.enablePeriodicUpdatesCheckBox.setChecked(enable_periodic)
        self.updateIntervalSpinBox.setValue(update_interval)
        
        # Load default download location
        default_location = settings.value("MapHubPlugin/default_download_location", "", type=str)
        if not default_location:
            # If no setting exists, use the default location from the utility function
            default_location = str(get_default_download_location())
        
        self.defaultLocationLineEdit.setText(default_location)
        
        # Load API settings
        api_key = settings.value("MapHubPlugin/api_key", "", type=str)
        self.apiKeyLineEdit.setText(api_key)
        
        base_url = settings.value("MapHubPlugin/base_url", "", type=str)
        self.baseUrlLineEdit.setText(base_url)
        
    def save_settings(self):
        """Save settings to QSettings."""
        settings = QSettings()
        
        # Save scheduler settings
        settings.setValue("MapHubPlugin/enable_periodic_updates", 
                         self.enablePeriodicUpdatesCheckBox.isChecked())
        settings.setValue("MapHubPlugin/update_interval", 
                         self.updateIntervalSpinBox.value())
        
        # Save default download location
        settings.setValue("MapHubPlugin/default_download_location",
                         self.defaultLocationLineEdit.text())
        
        # Save API settings
        api_key = self.apiKeyLineEdit.text().strip()
        if api_key:
            settings.setValue("MapHubPlugin/api_key", api_key)
        
        base_url = self.baseUrlLineEdit.text().strip()
        if base_url and len(base_url) > 0:
            settings.setValue("MapHubPlugin/base_url", base_url)
        else:
            # If the field is empty, remove the setting to use the default
            settings.remove("MapHubPlugin/base_url")

    @handled_exceptions
    def on_refresh_now_clicked(self, checked=False):
        """Handle click on the Refresh Now button."""
        if self.refresh_callback:
            self.refresh_callback()
            
    @handled_exceptions
    def on_browse_clicked(self, checked=False):
        """Handle click on the Browse button for default download location."""
        # Get current path or default to Documents folder
        current_path = self.defaultLocationLineEdit.text()
        if not current_path:
            documents_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            current_path = str(Path(documents_path) / "MapHub")
            
        # Open directory selection dialog
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Default Download Location",
            current_path
        )
        
        # Update text field if a directory was selected
        if directory:
            self.defaultLocationLineEdit.setText(directory)