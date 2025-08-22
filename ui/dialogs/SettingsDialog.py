import os
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QIcon
from qgis.PyQt import uic

from .MapHubBaseDialog import MapHubBaseDialog
from ...utils.error_manager import handled_exceptions

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
        
        # Load settings
        self.load_settings()
        
    def on_accepted(self):
        """Handle dialog acceptance."""
        # Save settings
        self.save_settings()
        
        # Call the settings changed callback if provided
        if self.on_settings_changed:
            self.on_settings_changed()
    
    def load_settings(self):
        """Load settings from QSettings."""
        settings = QSettings()
        
        # Load scheduler settings
        enable_periodic = settings.value("MapHubPlugin/enable_periodic_updates", False, type=bool)
        update_interval = settings.value("MapHubPlugin/update_interval", 5, type=int)
        
        self.enablePeriodicUpdatesCheckBox.setChecked(enable_periodic)
        self.updateIntervalSpinBox.setValue(update_interval)
        
        # Future: Load settings for other tabs
        
    def save_settings(self):
        """Save settings to QSettings."""
        settings = QSettings()
        
        # Save scheduler settings
        settings.setValue("MapHubPlugin/enable_periodic_updates", 
                         self.enablePeriodicUpdatesCheckBox.isChecked())
        settings.setValue("MapHubPlugin/update_interval", 
                         self.updateIntervalSpinBox.value())
        
        # Future: Save settings for other tabs

    @handled_exceptions
    def on_refresh_now_clicked(self, checked=False):
        """Handle click on the Refresh Now button."""
        if self.refresh_callback:
            self.refresh_callback()