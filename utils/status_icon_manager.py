import os
from PyQt5.QtGui import QIcon

class StatusIconManager:
    """Manages status icons and text for MapHub synchronization status."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StatusIconManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the icon manager."""
        # Get the path to the icons directory
        self.icon_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'icons')
        
        # Define status mappings
        self._status_icons = {
            "local_modified": "upload.svg",
            "remote_newer": "download.svg",
            "style_changed": "style.svg",
            "file_missing": "error.svg",
            "remote_error": "warning.svg",
            "in_sync": "check.svg",
            "not_connected": "link.svg",
            "processing": "sync.svg"  # Using sync icon for processing status
        }
        
        self._status_tooltips = {
            "local_modified": "Local changes need to be uploaded to MapHub",
            "remote_newer": "Remote changes need to be downloaded from MapHub",
            "style_changed": "Style changes detected",
            "file_missing": "Local file is missing",
            "remote_error": "Error checking remote status",
            "in_sync": "Layer is in sync with MapHub",
            "not_connected": "Layer is not connected to MapHub",
            "processing": "Map is still being processed by MapHub"
        }
    
    def get_icon_path(self, status):
        """
        Get the path to the icon for a status.
        
        Args:
            status (str): The synchronization status
            
        Returns:
            str: The path to the icon, or None if not found
        """
        if status in self._status_icons:
            icon_path = os.path.join(self.icon_dir, self._status_icons[status])
            if os.path.exists(icon_path):
                return icon_path
        return None
    
    def get_icon(self, status):
        """
        Get the QIcon for a status.
        
        Args:
            status (str): The synchronization status
            
        Returns:
            QIcon: The icon, or an empty icon if not found
        """
        icon_path = self.get_icon_path(status)
        if icon_path:
            return QIcon(icon_path)
        return QIcon()
    
    def get_tooltip(self, status):
        """
        Get the tooltip text for a status.
        
        Args:
            status (str): The synchronization status
            
        Returns:
            str: The tooltip text, or None if not found
        """
        return self._status_tooltips.get(status)