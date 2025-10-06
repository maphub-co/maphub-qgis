# -*- coding: utf-8 -*-
import asyncio
import os
import sys
import site
from qgis.PyQt.QtWidgets import QApplication

# Add the lib directory to the Python path
lib_path = os.path.join(os.path.dirname(__file__), 'lib')
if os.path.exists(lib_path) and lib_path not in sys.path:
    site.addsitedir(lib_path)

# Extract qasync wheel if needed and add to path
wheel_path = os.path.join(lib_path, 'qasync-0.28.0-py3-none-any.whl')
if os.path.exists(wheel_path) and wheel_path not in sys.path:
    sys.path.insert(0, wheel_path)


import qasync
# Set up qasync as early as possible
def setup_qasync():
    app = QApplication.instance()
    if app:
        # Create event loop with already_running=True since QGIS is already running
        loop = qasync.QEventLoop(app, already_running=True)
        asyncio.set_event_loop(loop)
        return loop
    return None

# Initialize the event loop
loop = setup_qasync()

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load MapHubPlugin class from file MapHubPlugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .MapHubPlugin import MapHubPlugin
    return MapHubPlugin(iface)
