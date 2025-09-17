import os
from typing import Optional, Dict, Any

from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import (
    QgsPluginLayer, QgsPluginLayerType, QgsMapLayerRenderer, 
    QgsRasterLayer, QgsVectorLayer, QgsProject, QgsApplication,
    QgsDataProvider, QgsCoordinateReferenceSystem
)

from ..maphub.exceptions import APIException
from .utils import get_maphub_client, apply_style_to_layer, get_layer_styles_as_json
from .error_manager import ErrorManager


class MapHubLayerRenderer(QgsMapLayerRenderer):
    """Renderer for MapHub plugin layer"""
    
    def __init__(self, layer_id, render_context, maphub_layer):
        super().__init__(layer_id, render_context)
        self.maphub_layer = maphub_layer
        self.delegate_layer = maphub_layer.delegate_layer
        
    def render(self):
        """Render the layer by delegating to the underlying layer"""
        if not self.delegate_layer or not self.delegate_layer.isValid():
            # Layer is not ready for rendering
            return True
            
        # Delegate rendering to the underlying layer's renderer
        return self.delegate_layer.renderer().render(self.renderContext())


class MapHubPluginLayer(QgsPluginLayer):
    """
    Custom QGIS layer type for MapHub maps.
    
    This layer type handles synchronization with MapHub and manages
    downloading/uploading data as needed.
    """
    
    LAYER_TYPE = "MapHubLayer"
    
    def __init__(self, map_id=None, folder_id=None, workspace_id=None, version_id=None):
        """
        Initialize a new MapHub layer.
        
        Args:
            map_id: The MapHub map ID
            folder_id: The MapHub folder ID
            workspace_id: The MapHub workspace ID
            version_id: The MapHub version ID (optional)
        """
        super().__init__(MapHubPluginLayer.LAYER_TYPE, "MapHub Layer")
        
        # MapHub connection properties
        self._map_id = map_id
        self._folder_id = folder_id
        self._workspace_id = workspace_id
        self._version_id = version_id
        self._last_sync = None
        self._local_path = None
        self._last_style_hash = None
        
        # The actual layer that handles data and rendering
        self.delegate_layer = None
        
        # Set layer as valid
        self.setValid(True)
        
        # Initialize the layer if map_id is provided
        if map_id:
            self._initialize_layer()
    
    def _initialize_layer(self):
        """Initialize the layer by downloading data if needed"""
        if not self._map_id:
            return
            
        try:
            # Get the sync manager
            from .sync_manager import MapHubSyncManager
            sync_manager = MapHubSyncManager(None)
            
            # Check if we have a local path and if the file exists
            if self._local_path and os.path.exists(self._local_path):
                # File exists, create the delegate layer
                self._create_delegate_layer()
            else:
                # File doesn't exist, download it
                self._download_map_data()
        except Exception as e:
            ErrorManager.show_error(f"Error initializing MapHub layer: {str(e)}", e)
    
    def _download_map_data(self):
        """Download map data from MapHub"""
        try:
            # Show a message in the message bar
            if hasattr(QgsApplication, 'messageBar') and QgsApplication.messageBar():
                QgsApplication.messageBar().pushInfo(
                    "MapHub", f"Downloading map data for {self.name()}"
                )
            
            # Get the sync manager
            from .sync_manager import MapHubSyncManager
            sync_manager = MapHubSyncManager(None)
            
            # Download the map
            layer = sync_manager.download_map(
                self._map_id, 
                version_id=self._version_id,
                connect_layer=False  # Don't connect as we're handling this ourselves
            )
            
            if layer and layer.isValid():
                # Store the local path
                self._local_path = layer.source()
                
                # Create our delegate layer
                self._create_delegate_layer()
                
                # Update properties
                self._last_sync = layer.customProperty("maphub/last_sync")
                self._version_id = layer.customProperty("maphub/version_id")
                self._last_style_hash = layer.customProperty("maphub/last_style_hash")
                
                # Remove the temporary layer
                QgsProject.instance().removeMapLayer(layer.id())
            else:
                ErrorManager.show_error(f"Failed to download map data for {self.name()}")
        except Exception as e:
            ErrorManager.show_error(f"Error downloading map data: {str(e)}", e)
    
    def _create_delegate_layer(self):
        """Create the delegate layer from the local file"""
        if not self._local_path or not os.path.exists(self._local_path):
            return
            
        # Determine layer type based on file extension
        file_ext = os.path.splitext(self._local_path)[1].lower()
        
        if file_ext in ['.tif', '.tiff', '.jpg', '.jpeg', '.png']:
            # Create a raster layer
            self.delegate_layer = QgsRasterLayer(self._local_path, self.name())
        else:
            # Create a vector layer
            self.delegate_layer = QgsVectorLayer(self._local_path, self.name(), "ogr")
        
        # Check if the layer is valid
        if not self.delegate_layer.isValid():
            ErrorManager.show_error(f"Failed to create valid layer from {self._local_path}")
            self.delegate_layer = None
            return
            
        # Copy CRS and extent from delegate layer
        self.setCrs(self.delegate_layer.crs())
        
        # Emit dataChanged signal to refresh the layer
        self.emitDataChanged()
    
    def createMapRenderer(self, rendererContext):
        """Create a renderer for this layer"""
        if not self.delegate_layer:
            return None
        return MapHubLayerRenderer(self.id(), rendererContext, self)
    
    def extent(self):
        """Return the layer extent"""
        if self.delegate_layer:
            return self.delegate_layer.extent()
        return None
    
    def dataProvider(self):
        """Return the data provider of the delegate layer"""
        if self.delegate_layer:
            return self.delegate_layer.dataProvider()
        return None
    
    def crs(self):
        """Return the CRS of the delegate layer"""
        if self.delegate_layer:
            return self.delegate_layer.crs()
        return QgsCoordinateReferenceSystem()
    
    # MapHub specific methods
    
    def map_id(self):
        """Get the MapHub map ID"""
        return self._map_id
        
    def folder_id(self):
        """Get the MapHub folder ID"""
        return self._folder_id
        
    def workspace_id(self):
        """Get the MapHub workspace ID"""
        return self._workspace_id
        
    def version_id(self):
        """Get the MapHub version ID"""
        return self._version_id
        
    def last_sync(self):
        """Get the last sync timestamp"""
        return self._last_sync
        
    def local_path(self):
        """Get the local file path"""
        return self._local_path
        
    def last_style_hash(self):
        """Get the last style hash"""
        return self._last_style_hash
    
    def set_map_id(self, map_id):
        """Set the MapHub map ID"""
        self._map_id = map_id
        
    def set_folder_id(self, folder_id):
        """Set the MapHub folder ID"""
        self._folder_id = folder_id
        
    def set_workspace_id(self, workspace_id):
        """Set the MapHub workspace ID"""
        self._workspace_id = workspace_id
        
    def set_version_id(self, version_id):
        """Set the MapHub version ID"""
        self._version_id = version_id
        
    def set_last_sync(self, last_sync):
        """Set the last sync timestamp"""
        self._last_sync = last_sync
        
    def set_local_path(self, local_path):
        """Set the local file path"""
        self._local_path = local_path
        
    def set_last_style_hash(self, last_style_hash):
        """Set the last style hash"""
        self._last_style_hash = last_style_hash
    
    def get_sync_status(self):
        """Get the synchronization status of this layer"""
        from .sync_manager import MapHubSyncManager
        sync_manager = MapHubSyncManager(None)
        
        # Create a temporary layer with the same properties as this one
        # to reuse the existing sync status logic
        temp_layer = self.delegate_layer.clone() if self.delegate_layer else None
        
        if not temp_layer:
            return "not_connected"
            
        # Set custom properties on the temp layer
        temp_layer.setCustomProperty("maphub/map_id", self._map_id)
        temp_layer.setCustomProperty("maphub/folder_id", self._folder_id)
        temp_layer.setCustomProperty("maphub/workspace_id", self._workspace_id)
        temp_layer.setCustomProperty("maphub/version_id", self._version_id)
        temp_layer.setCustomProperty("maphub/last_sync", self._last_sync)
        temp_layer.setCustomProperty("maphub/local_path", self._local_path)
        temp_layer.setCustomProperty("maphub/last_style_hash", self._last_style_hash)
        
        # Get the sync status
        status = sync_manager.get_layer_sync_status(temp_layer)
        
        # Clean up
        del temp_layer
        
        return status
    
    def synchronize(self, direction="auto", style_only=False):
        """Synchronize this layer with MapHub"""
        from .sync_manager import MapHubSyncManager
        sync_manager = MapHubSyncManager(None)
        
        # Create a temporary layer with the same properties as this one
        # to reuse the existing synchronization logic
        temp_layer = self.delegate_layer.clone() if self.delegate_layer else None
        
        if not temp_layer:
            ErrorManager.show_error("Cannot synchronize: delegate layer is not valid")
            return False
            
        # Set custom properties on the temp layer
        temp_layer.setCustomProperty("maphub/map_id", self._map_id)
        temp_layer.setCustomProperty("maphub/folder_id", self._folder_id)
        temp_layer.setCustomProperty("maphub/workspace_id", self._workspace_id)
        temp_layer.setCustomProperty("maphub/version_id", self._version_id)
        temp_layer.setCustomProperty("maphub/last_sync", self._last_sync)
        temp_layer.setCustomProperty("maphub/local_path", self._local_path)
        temp_layer.setCustomProperty("maphub/last_style_hash", self._last_style_hash)
        
        # Synchronize the temp layer
        result = sync_manager.synchronize_layer(temp_layer, direction, style_only)
        
        if result:
            # Update our properties from the synchronized temp layer
            self._map_id = temp_layer.customProperty("maphub/map_id")
            self._folder_id = temp_layer.customProperty("maphub/folder_id")
            self._workspace_id = temp_layer.customProperty("maphub/workspace_id")
            self._version_id = temp_layer.customProperty("maphub/version_id")
            self._last_sync = temp_layer.customProperty("maphub/last_sync")
            self._local_path = temp_layer.customProperty("maphub/local_path")
            self._last_style_hash = temp_layer.customProperty("maphub/last_style_hash")
            
            # If the local path changed, recreate the delegate layer
            if self._local_path != self.delegate_layer.source():
                self._create_delegate_layer()
        
        # Clean up
        del temp_layer
        
        return result
    
    def disconnect_from_maphub(self):
        """Disconnect this layer from MapHub"""
        # Clear MapHub properties
        self._map_id = None
        self._folder_id = None
        self._workspace_id = None
        self._version_id = None
        self._last_sync = None
        self._last_style_hash = None
        
        # Keep the local path and delegate layer
        
        # Change the layer name to indicate it's disconnected
        self.setName(f"{self.name()} (Disconnected)")
        
        # Emit dataChanged signal to refresh the layer
        self.emitDataChanged()
        
        return True
    
    # XML serialization methods for project save/load
    
    def writeXml(self, node, doc, context):
        """Write layer properties to XML for project save"""
        element = super().writeXml(node, doc, context)
        
        # Write MapHub properties
        element.setAttribute("map_id", self._map_id or "")
        element.setAttribute("folder_id", self._folder_id or "")
        element.setAttribute("workspace_id", self._workspace_id or "")
        element.setAttribute("version_id", self._version_id or "")
        element.setAttribute("last_sync", self._last_sync or "")
        element.setAttribute("local_path", self._local_path or "")
        element.setAttribute("last_style_hash", self._last_style_hash or "")
        
        return element
    
    def readXml(self, node, context):
        """Read layer properties from XML for project load"""
        if not super().readXml(node, context):
            return False
        
        # Read MapHub properties
        self._map_id = node.attribute("map_id", "")
        self._folder_id = node.attribute("folder_id", "")
        self._workspace_id = node.attribute("workspace_id", "")
        self._version_id = node.attribute("version_id", "")
        self._last_sync = node.attribute("last_sync", "")
        self._local_path = node.attribute("local_path", "")
        self._last_style_hash = node.attribute("last_style_hash", "")
        
        # Initialize the layer
        QTimer.singleShot(0, self._initialize_layer)
        
        return True


class MapHubPluginLayerType(QgsPluginLayerType):
    """Factory for creating MapHub plugin layers"""
    
    def __init__(self):
        super().__init__(MapHubPluginLayer.LAYER_TYPE)
    
    def createLayer(self):
        """Create a new MapHub plugin layer"""
        return MapHubPluginLayer()
    
    def showLayerProperties(self, layer):
        """Show layer properties dialog"""
        # For now, delegate to the standard layer properties dialog
        # of the delegate layer if it exists
        if layer.delegate_layer:
            from qgis.utils import iface
            if iface:
                iface.showLayerProperties(layer.delegate_layer)
                return True
        return False