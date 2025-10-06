import asyncio
import os
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsLayerTreeNode
from qgis.gui import QgsLayerTreeViewIndicator

from .sync_manager import MapHubSyncManager


class MapHubLayerDecorator:
    """
    Adds visual indicators to QGIS layers that are connected to MapHub.
    
    This class provides functionality to:
    - Add icon overlays to layers in the QGIS layer panel
    - Update icons based on synchronization status
    
    This class implements the Singleton pattern to ensure only one instance
    exists throughout the plugin's lifecycle, preventing duplicate indicators.
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls, iface):
        """
        Get the singleton instance of the decorator.
        
        Args:
            iface: The QGIS interface
            
        Returns:
            MapHubLayerDecorator: The singleton instance
        """
        if cls._instance is None:
            cls._instance = MapHubLayerDecorator(iface)
        return cls._instance

    def __init__(self, iface):
        """
        Initialize the layer decorator.
        
        Note: This should not be called directly. Use get_instance() instead.

        Args:
            iface: The QGIS interface
        """
        # If an instance already exists, don't reinitialize
        if MapHubLayerDecorator._instance is not None:
            return
            
        self.iface = iface
        self.sync_manager = MapHubSyncManager(iface)
        self.icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icons')

        # Cache for status icons
        self._status_icons = {}

        # Dictionary to track registered indicators
        self._indicators = {}

        self.sync_manager = MapHubSyncManager(self.iface)

    async def update_layer_icons(self):
        """Update layer icons with MapHub status indicators"""
        layers = self.sync_manager.get_connected_layers()

        tasks = []
        for layer in layers:
            task = self.update_layer_icon(layer)
            tasks.append(task)

        if tasks:
            return await asyncio.gather(*tasks)

        return None

    async def update_layer_icon(self, layer):
        """Update a layer icon with MapHub status indicators"""
        # Get the layer tree view from the interface
        layer_tree_view = self.iface.layerTreeView()
        if not layer_tree_view:
            return

        # Find the layer node in the layer tree
        root = QgsProject.instance().layerTreeRoot()
        node = root.findLayer(layer.id())

        if not node:
            return  # Layer not found in tree

        # Remove existing indicator for this layer if it exists
        self.cleanup_layer(layer)

        # Get synchronization status (on demand)
        status = await asyncio.to_thread(self.sync_manager.get_layer_sync_status, layer)

        # Store the status in the layer's custom properties for potential use elsewhere
        layer.setCustomProperty("maphub/sync_status", status)

        # Get icon for status
        icon = self._get_status_icon(status)
        tooltip = self._get_status_tooltip(status)

        # Create indicator
        indicator = QgsLayerTreeViewIndicator(layer_tree_view)
        if icon:
            # Use status-specific icon and tooltip
            indicator.setIcon(icon)
            if tooltip:
                indicator.setToolTip(tooltip)
        else:
            # Use chain icon for connected layers with no specific status
            chain_icon_path = os.path.join(self.icon_dir, 'chain.svg')
            chain_icon = QIcon(chain_icon_path)
            indicator.setIcon(chain_icon)
            indicator.setToolTip("Layer is connected to MapHub")

        # Add the indicator to the layer
        layer_tree_view.addIndicator(node, indicator)

        # Create a unique ID for this layer's indicator (consistent regardless of status)
        indicator_id = f"maphub_{layer.id()}"

        # Store the indicator for later removal
        self._indicators[indicator_id] = (node, indicator)

    def cleanup(self):
        """
        Clean up all indicators.
        This should be called when the plugin is unloaded to ensure all indicators are removed.
        """
        layer_tree_view = self.iface.layerTreeView()
        if not layer_tree_view:
            return

        # Remove all indicators
        for indicator_id, (node, indicator) in list(self._indicators.items()):
            try:
                layer_tree_view.removeIndicator(node, indicator)
            except RuntimeError:
                # Node has been deleted, skip it
                pass
            except Exception:
                # Handle any other exceptions
                pass

        # Clear the indicators dictionary
        self._indicators.clear()

    def cleanup_layer(self, layer):
        layer_tree_view = self.iface.layerTreeView()
        if not layer_tree_view:
            return

        indicator_id = f"maphub_{layer.id()}"

        if indicator_id not in self._indicators:
            return

        node, indicator = self._indicators[indicator_id]

        try:
            layer_tree_view.removeIndicator(node, indicator)
        except RuntimeError:
            # Node has been deleted, skip it
            pass
        except Exception:
            # Handle any other exceptions
            pass

        del self._indicators[indicator_id]

    def _get_status_icon(self, status):
        """
        Get an icon for a synchronization status.
        
        Args:
            status: The synchronization status
            
        Returns:
            QIcon: The status icon, or None if no icon is available for the status
        """
        # Check if icon is already cached
        if status in self._status_icons:
            return self._status_icons[status]
            
        # Create icon based on status
        icon_path = None
        if status == "local_modified":
            icon_path = os.path.join(self.icon_dir, 'upload.svg')
        elif status == "remote_newer":
            icon_path = os.path.join(self.icon_dir, 'download.svg')
        elif status == "style_changed_local":
            icon_path = os.path.join(self.icon_dir, 'style.svg')
        elif status == "style_changed_remote":
            icon_path = os.path.join(self.icon_dir, 'style.svg')  # Could use a different icon if available
        elif status == "style_changed_both":
            icon_path = os.path.join(self.icon_dir, 'style.svg')  # Could use a different icon if available
        elif status == "file_missing":
            icon_path = os.path.join(self.icon_dir, 'error.svg')
        elif status == "remote_error":
            icon_path = os.path.join(self.icon_dir, 'warning.svg')
        elif status == "processing":
            icon_path = os.path.join(self.icon_dir, 'refresh.svg')
            
        # Create and cache icon if path exists
        if icon_path and os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self._status_icons[status] = icon
            return icon
            
        return None

    def _get_status_tooltip(self, status) -> str:
        if status == "local_modified":
            return "Local changes need to be uploaded to MapHub"
        elif status == "remote_newer":
            return "Remote changes need to be downloaded from MapHub"
        elif status == "style_changed_local":
            return "Local style changes need to be uploaded to MapHub"
        elif status == "style_changed_remote":
            return "Remote style changes need to be downloaded from MapHub"
        elif status == "style_changed_both":
            return "Style conflict - both local and remote styles have changed"
        elif status == "file_missing":
            return "Local file is missing"
        elif status == "remote_error":
            return "Error checking remote status"
        elif status == "processing":
            return "Map is being processed on MapHub"
        else:
            return None
