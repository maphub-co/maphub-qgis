import json
from typing import Dict, Any

from qgis.core import QgsMapLayer, QgsVectorLayer, QgsRasterLayer
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from PyQt5.QtXml import QDomDocument

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


def get_layer_styles_as_json(layer, visuals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieves layer styling information in both QGIS native style format and SLD
    format, storing the results in a given visuals dictionary. If the export of
    either style format fails, relevant error messages or null values are added to
    the visuals dictionary.

    :param layer: The QGIS layer object whose styling information is to be exported.
    :type layer: QgsMapLayer
    :param visuals: Dictionary storing the exported styling information and any
        associated errors.
    :type visuals: Dict[str, Any]
    :return: The updated visuals dictionary containing QGIS native style and SLD
        style (if export is successful) or their respective error details.
    :rtype: Dict[str, Any]
    :raises Exception: If exporting the QGIS native style fails.
    """
    # Get QGIS native style format
    qgis_doc = QDomDocument()
    error_message = []  # Use a list instead of a string for output parameter
    layer.exportNamedStyle(qgis_doc)

    # Store QGIS style XML
    visuals["qgis"] = qgis_doc.toString()

    # Get SLD style format
    sld_doc = QDomDocument()
    sld_document = layer.exportSldStyle(sld_doc, "")

    if not sld_document:
        visuals["sld"] = None
    else:
        visuals["sld"] = sld_document

    return visuals


def apply_style_to_layer(layer, visuals: Dict[str, Any]):
    """
    Apply a specific style to a given map layer using a provided set of visuals.

    This function attempts to apply styling to a layer using the provided visual
    definitions. It gives priority to the QGIS native styling (if available and
    valid) for its greater compatibility and features. If applying the QGIS style
    fails or is unavailable, it falls back to the SLD (Styled Layer Descriptor)
    format for styling. The method also includes error handling to catch and
    report issues when applying styles.

    :param layer: The map layer to which the style should be applied. It must
                  be a valid `QgsMapLayer`.
    :param visuals: A dictionary containing visual styles with keys such as "qgis"
                    for QGIS native style (expected as XML string) and "sld" for
                    SLD styling (path/location or XML definition). Both keys are
                    optional, but at least one must be valid for the function to
                    succeed.

    :return: True if the style was successfully applied, False otherwise.
    :rtype: bool
    """
    # Check if we have a valid layer
    if not layer or not isinstance(layer, QgsMapLayer):
        print("Invalid layer provided to apply_style_to_layer")
        return False

    # Check if visuals dictionary is valid
    if not visuals or not isinstance(visuals, dict):
        print(f"Invalid visuals provided to apply_style_to_layer: {visuals}")
        return False

    # Try to apply QGIS native style first (most complete)
    if "qgis" in visuals and visuals["qgis"]:
        try:
            qgis_doc = QDomDocument()
            if not qgis_doc.setContent(visuals["qgis"]):
                print(f"Failed to parse QGIS style XML: Invalid XML format")
            else:
                success = layer.importNamedStyle(qgis_doc)

                if success:
                    layer.triggerRepaint()
                    return True
        except Exception as e:
            print(f"Error applying QGIS style: {str(e)}")

    # Fall back to SLD if QGIS style failed or isn't available
    if "sld" in visuals and visuals["sld"]:
        try:
            success = layer.loadSldStyle(visuals["sld"])

            if success:
                layer.triggerRepaint()
                return True
            else:
                print("Failed to apply SLD style: The SLD format may be incompatible with this layer type")
        except Exception as e:
            print(f"Error applying SLD style: {str(e)}")

    # If both methods failed, return False
    print(f"Failed to apply any style to layer '{layer.name()}'. Available style keys: {list(visuals.keys())}")
    return False
