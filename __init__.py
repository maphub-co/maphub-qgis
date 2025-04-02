# -*- coding: utf-8 -*-

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load MapHubPlugin class from file MapHubPlugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .MapHubPlugin import MapHubPlugin
    return MapHubPlugin(iface)
