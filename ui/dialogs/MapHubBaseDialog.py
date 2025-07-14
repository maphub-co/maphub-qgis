import os

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QFile, QTextStream, QSettings


def is_dark_mode():
    """
    Check if QGIS is in dark mode.

    Returns:
        bool: True if QGIS is in dark mode, False otherwise.
    """
    settings = QSettings()
    theme = settings.value('UI/UITheme', '')
    return theme.lower() in ['night mapping', 'blend of gray']


def load_style():
    """
    Load a style from a QSS file.
    If QGIS is in dark mode, loads the dark mode variant of the style.

    Returns:
        str: The content of the style file.
    """
    # Choose the appropriate style file based on QGIS theme
    style_filename = "style_dark.qss" if is_dark_mode() else "style.qss"
    style_file = os.path.join(os.path.dirname(__file__), f"../{style_filename}")

    # Fall back to default style if dark style doesn't exist
    if not os.path.exists(style_file) and is_dark_mode():
        style_file = os.path.join(os.path.dirname(__file__), f"../style.qss")
        print(f"Dark style file not found, falling back to default style.")

    if not os.path.exists(style_file):
        print(f"Style file {style_file} not found.")
        return ""

    with open(style_file, 'r') as f:
        return f.read()


class MapHubBaseDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(MapHubBaseDialog, self).__init__(parent)

        # Load the style each time a dialog is created to ensure it matches the current QGIS theme
        style = load_style()
        if style:
            self.setStyleSheet(style)
