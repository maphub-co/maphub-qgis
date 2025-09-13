import logging
import sys
import traceback
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QSettings

from ..maphub.exceptions import APIException
from ..ui.dialogs.ApiKeyDialog import ApiKeyDialog


def ensure_api_key(func):
    """Decorator to ensure API key is set before executing a function."""
    def wrapper(self, *args, **kwargs):
        # Check if API key exists
        settings = QSettings()
        api_key = settings.value("MapHubPlugin/api_key", "")
        
        if not api_key:
            # No API key found, ask user to input it
            dlg = ApiKeyDialog(self.iface.mainWindow() if hasattr(self, 'iface') else None)
            result = dlg.exec_()
            
            if result:
                # User provided an API key
                api_key = dlg.get_api_key()
            else:
                # User canceled the dialog
                return None
        
        # Execute the function if API key is set
        if api_key:
            return func(self, *args, **kwargs)
        else:
            # Show error message if API key is still not set
            ErrorManager.show_error(
                "API key is required. Please enter it in the plugin settings"
            )
            return None
    
    return wrapper


def handled_exceptions(func):
    """Decorator to handle exceptions."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)  # Return the function's result
        except APIException as e:
            # Capture the current exception info including traceback
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print(traceback.format_exc())
            ErrorManager.handle_api_exception(e, tb=exc_traceback)
        except Exception as e:
            # Capture the current exception info including traceback
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print(traceback.format_exc())
            ErrorManager.show_error(f"{e}", e, tb=exc_traceback)
    return wrapper


class ErrorManager:
    """Centralized error handling for MapHub QGIS Plugin."""
    
    # Debug mode flag for more detailed error reporting during development
    DEBUG_MODE = False
    
    @staticmethod
    def set_debug_mode(enabled=True):
        """Enable or disable debug mode for more detailed error reporting"""
        ErrorManager.DEBUG_MODE = enabled
    
    @staticmethod
    def show_error(message, exception=None, parent=None, show_details=True, tb=None):
        """
        Display a standardized error dialog with optional details.
        
        Args:
            message (str): The error message to display
            exception (Exception, optional): The exception that caused the error
            parent (QWidget, optional): Parent widget for the dialog
            show_details (bool): Whether to show exception details
            tb (traceback, optional): The exception traceback
        """
        error_dialog = QMessageBox(QMessageBox.Critical, "Error", message, parent=parent)
        
        if exception and show_details:
            if tb:
                # Use the provided traceback for more accurate stack trace
                details = ''.join(traceback.format_tb(tb))
                details += f"\n{type(exception).__name__}: {str(exception)}"
            elif hasattr(exception, '__traceback__'):
                details = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            else:
                details = str(exception)

            error_dialog.setDetailedText(details)
        
        error_dialog.exec_()
        
        # Also log the error
        logging.error(f"{message} - {str(exception) if exception else ''}")
    
    @staticmethod
    def handle_api_exception(exception, parent=None, tb=None):
        """
        Handle API exceptions with appropriate messages based on status code.
        
        Args:
            exception (APIException): The API exception to handle
            parent (QWidget, optional): Parent widget for the dialog
            tb (traceback, optional): The exception traceback
        """
        if exception.status_code == 500:
            ErrorManager.show_error(
                "Error from the MapHub server. A Bug report is sent and the issue will be investigated asap.",
                exception, parent, True, tb
            )
        elif exception.status_code == 402:
            ErrorManager.show_error(
                f"{exception.message}\nUpgrade your organization here: https://www.maphub.co/settings/billing",
                exception, parent, False, tb
            )
        elif exception.status_code == 401:
            ErrorManager.show_error(
                f"{exception.message}\nPlease check your API key and try again.",
                exception, parent, False, tb
            )
        elif exception.status_code == 403:
            ErrorManager.show_error(
                f"{exception.message}\nMake sure the currently used API key has the correct permissions.",
                exception, parent, False, tb
            )
        else:
            ErrorManager.show_error(
                f"Code {exception.status_code}: {exception.message}", 
                exception, parent, True, tb
            )