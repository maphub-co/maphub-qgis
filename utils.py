from qgis.core import QgsMapLayer, QgsVectorLayer, QgsRasterLayer
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from .maphub import MapHubClient
from .ui.ApiKeyDialog import ApiKeyDialog
from .maphub.exceptions import APIException


def show_error_dialog(message, title="Error"):
    """Display a modal error dialog.

    Args:
        message (str): The error message
        title (str): Dialog title
    """
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setText(message)
    msg_box.setWindowTitle(title)
    msg_box.setStandardButtons(QMessageBox.Ok)
    msg_box.exec_()


def handled_exceptions(func):
    """Decorator to handle exceptions."""
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except APIException as e:
            if e.status_code == 500:
                show_error_dialog(
                    "Error from the MapHub server. A Bug report is sent and the issue will be investigated asap.",
                    "MapHub API Error"
                )
            elif e.status_code == 402:
                show_error_dialog(
                    f"{e.message}\nUpgrade to premium here: https://maphub.co/dashboard/subscription",
                    "Premium account required."
                )
            elif e.status_code == 401:
                show_error_dialog(
                    f"{e.message}\nPlease check your API key and try again.",
                    "Invalid API key."
                )
            elif e.status_code == 403:
                show_error_dialog(
                    f"{e.message}\nMake sure the currently used API key has the correct permissions.",
                    "Permission denied."
                )
            else:
                show_error_dialog(f"Code {e.status_code}: {e.message}", "Error uploading map to MapHub")
        except Exception as e:
            show_error_dialog(f"{e}", "Error")

    return wrapper

def get_maphub_client():
    settings = QSettings()
    api_key = settings.value("MapHubPlugin/api_key", "")

    if not api_key:
        # No API key found, ask user to input it
        dlg = ApiKeyDialog()
        result = dlg.exec_()

        if result:
            # User provided an API key
            api_key = dlg.get_api_key()
            return api_key
        else:
            # User canceled the dialog
            return None

    if api_key is None:
        return show_error_dialog(
            "API key is required. Please enter it in the plugin settings or click the 'Set API Key' button to set it.")

    return MapHubClient(
        api_key=api_key,
    )