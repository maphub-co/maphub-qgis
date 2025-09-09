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
        # Track layers we connected signals for
        self._signal_layers = set()

    def update_layer_icons(self):
        """Update layer icons with MapHub status indicators"""
        # Get the layer tree view from the interface
        layer_tree_view = self.iface.layerTreeView()
        if not layer_tree_view:
            return
            
        # Clear existing indicators - use the cleanup method to ensure thorough removal
        self.cleanup()
        
        # Process all layers
        root = QgsProject.instance().layerTreeRoot()
        self._process_tree_node(root, layer_tree_view)

    def _process_tree_node(self, node, layer_tree_view):
        """
        Process a layer tree node and its children.

        Args:
            node: The layer tree node
            layer_tree_view: The QGIS layer tree view
        """
        if node.nodeType() == QgsLayerTreeNode.NodeLayer:
            layer = node.layer()
            if layer and self._is_maphub_layer(layer):
                self._update_layer_indicator(layer, node, layer_tree_view)
                self._ensure_layer_signal_connections(layer)
        else:
            for child in node.children():
                self._process_tree_node(child, layer_tree_view)
                
    def _is_maphub_layer(self, layer):
        """
        Check if a layer is connected to MapHub.
        
        Args:
            layer: The QGIS layer
            
        Returns:
            bool: True if the layer is connected to MapHub, False otherwise
        """
        return layer.customProperty("maphub/map_id") is not None
        
    def _update_layer_indicator(self, layer, node, layer_tree_view):
        """
        Add an indicator to a layer in the layer tree view.
        
        Args:
            layer: The QGIS layer
            node: The layer tree node
            layer_tree_view: The QGIS layer tree view
        """
        # Before adding, remove any existing indicator for this layer to avoid duplicates
        try:
            self._remove_indicator_for_layer(layer.id(), layer_tree_view)
        except Exception:
            pass

        # Get synchronization status (on demand)
        status = self.sync_manager.get_layer_sync_status(layer)
        
        # Store the status in the layer's custom properties for potential use elsewhere
        layer.setCustomProperty("maphub/sync_status", status)

        # Create a unique ID for this layer's indicator (consistent regardless of status)
        indicator_id = f"maphub_{layer.id()}"
        
        # Create indicator
        indicator = QgsLayerTreeViewIndicator(layer_tree_view)
        
        # Get icon for status
        icon = self._get_status_icon(status)
        
        if icon:
            # Use status-specific icon and tooltip
            indicator.setIcon(icon)
            
            # Set tooltip based on status
            if status == "local_modified":
                indicator.setToolTip("Local changes need to be uploaded to MapHub")
            elif status == "remote_newer":
                indicator.setToolTip("Remote changes need to be downloaded from MapHub")
            elif status == "style_changed_local":
                indicator.setToolTip("Local style changes need to be uploaded to MapHub")
            elif status == "style_changed_remote":
                indicator.setToolTip("Remote style changes need to be downloaded from MapHub")
            elif status == "style_changed_both":
                indicator.setToolTip("Style conflict - both local and remote styles have changed")
            elif status == "file_missing":
                indicator.setToolTip("Local file is missing")
            elif status == "remote_error":
                indicator.setToolTip("Error checking remote status")
            elif status == "processing":
                indicator.setToolTip("Map is being processed on MapHub")
        else:
            # Use chain icon for connected layers with no specific status
            chain_icon_path = os.path.join(self.icon_dir, 'chain.svg')
            chain_icon = QIcon(chain_icon_path)
            indicator.setIcon(chain_icon)
            indicator.setToolTip("Layer is connected to MapHub")
        
        # Add the indicator to the layer
        layer_tree_view.addIndicator(node, indicator)
        
        # Store the indicator for later removal
        self._indicators[indicator_id] = (node, indicator)

    def _ensure_layer_signal_connections(self, layer):
        """
        Ensure we listen to relevant layer signals to auto-refresh indicators on changes.
        """
        try:
            lid = layer.id()
        except Exception:
            return
        if lid in self._signal_layers:
            return
        # Connect generic map layer signals
        try:
            if hasattr(layer, 'styleChanged'):
                layer.styleChanged.connect(lambda: self._on_layer_event(layer))
        except Exception:
            pass
        try:
            if hasattr(layer, 'repaintRequested'):
                layer.repaintRequested.connect(lambda: self._on_layer_event(layer))
        except Exception:
            pass
        # Connect vector-layer specific signals (best-effort)
        for sig in ['editingStarted', 'editingStopped', 'featureAdded', 'featuresDeleted', 'geometryChanged', 'attributeValueChanged']:
            try:
                if hasattr(layer, sig):
                    getattr(layer, sig).connect(lambda *args, lyr=layer: self._on_layer_event(lyr))
            except Exception:
                pass
        self._signal_layers.add(lid)

    def _on_layer_event(self, layer):
        """
        Handle any layer change by recomputing its indicator.
        """
        try:
            root = QgsProject.instance().layerTreeRoot()
            node = root.findLayer(layer.id()) if hasattr(root, 'findLayer') else None
            view = self.iface.layerTreeView()
            if node and view:
                self._update_layer_indicator(layer, node, view)
        except Exception:
            pass

    def _remove_indicator_for_layer(self, layer_id, layer_tree_view=None):
        """Remove existing indicator for a given layer id if present."""
        try:
            indicator_id = f"maphub_{layer_id}"
            if indicator_id in self._indicators:
                node, indicator = self._indicators.pop(indicator_id)
                # Use provided view or obtain from iface
                view = layer_tree_view or self.iface.layerTreeView()
                if view:
                    try:
                        view.removeIndicator(node, indicator)
                    except RuntimeError:
                        pass
        except Exception:
            pass


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
        # Reset signal tracking; reconnect on next update
        self._signal_layers.clear()
    
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
        

