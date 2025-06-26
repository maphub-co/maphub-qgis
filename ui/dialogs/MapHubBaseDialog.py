import os

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QFile, QTextStream


def load_style():
    """
    Load a style from a QSS file.

    Returns:
        str: The content of the style file.
    """
    style_file = os.path.join(os.path.dirname(__file__), f"../style.qss")

    if not os.path.exists(style_file):
        print(f"Style file {style_file} not found.")
        return ""

    with open(style_file, 'r') as f:
        return f.read()

style = load_style()


class MapHubBaseDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(MapHubBaseDialog, self).__init__(parent)

        if style:
            self.setStyleSheet(style)