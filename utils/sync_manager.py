import hashlib
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from PyQt5.QtWidgets import QMessageBox
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

from .utils import get_maphub_client, apply_style_to_layer


class MapHubSyncManager:
    """
    Manages synchronization between local QGIS layers and MapHub maps.
    
    This class provides functionality to:
    - Track connections between local layers and MapHub maps
    - Check synchronization status of connected layers
    - Synchronize layers with their MapHub counterparts
    """
    
    def __init__(self, iface):
        """
        Initialize the sync manager.
        
        Args:
            iface: The QGIS interface
        """
        self.iface = iface
    
    def get_connected_layers(self) -> List[Any]:
        """
        Get all layers connected to MapHub.
        
        Returns:
            List of layers that have MapHub connection information
        """
        connected_layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if layer.customProperty("maphub/map_id"):
                connected_layers.append(layer)
        return connected_layers
    
    def find_layer_by_map_id(self, map_id: str) -> Optional[Any]:
        """
        Find a layer by its MapHub map ID.
        
        Args:
            map_id: The MapHub map ID
            
        Returns:
            The layer if found, None otherwise
        """
        for layer in QgsProject.instance().mapLayers().values():
            if layer.customProperty("maphub/map_id") == str(map_id):
                return layer
        return None
    
    def get_layer_sync_status(self, layer) -> str:
        """
        Get synchronization status for a layer.
        
        Args:
            layer: The QGIS layer
            
        Returns:
            Status string: 
            - "not_connected": Layer is not connected to MapHub
            - "file_missing": Local file is missing
            - "local_modified": Local file has been modified since last sync
            - "remote_newer": Remote map has been updated since last sync
            - "style_changed": Style has changed since last sync
            - "remote_error": Error checking remote status
            - "in_sync": Layer is in sync with MapHub
        """
        if not layer.customProperty("maphub/map_id"):
            return "not_connected"
        
        # Check if local file exists
        local_path = layer.customProperty("maphub/local_path")
        if not local_path or not os.path.exists(local_path):
            return "file_missing"
        
        # Check if local file is modified
        last_sync = layer.customProperty("maphub/last_sync")
        if last_sync:
            last_sync_time = datetime.fromisoformat(last_sync)
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(local_path))
            if file_mod_time > last_sync_time:
                return "local_modified"
        
        # Check if remote has newer version
        try:
            map_id = layer.customProperty("maphub/map_id")
            map_info = get_maphub_client().maps.get_map(map_id)
            if 'updated_at' in map_info:
                remote_update_time = datetime.fromisoformat(map_info.get('updated_at'))
                if last_sync and remote_update_time > datetime.fromisoformat(last_sync):
                    return "remote_newer"
        except Exception as e:
            print(f"Error checking remote status: {e}")
            return "remote_error"
        
        # Check if styles differ
        # Calculate the current style hash on demand from the local layer
        from ..utils.utils import get_layer_styles_as_json
        local_style_dict = get_layer_styles_as_json(layer, {})
        
        # Only use the QGIS field for style comparison
        if 'qgis' in local_style_dict:
            local_style_hash = hashlib.md5(local_style_dict['qgis'].encode()).hexdigest()
            
            if 'visuals' in map_info and map_info['visuals'] and 'qgis' in map_info['visuals']:
                remote_style_hash = hashlib.md5(map_info['visuals']['qgis'].encode()).hexdigest()
                if local_style_hash != remote_style_hash:
                    return "style_changed"
        
        return "in_sync"
    
    def get_layer_style_as_dict(self, layer) -> Dict[str, Any]:
        """
        Get the layer's style as a dictionary.
        
        Args:
            layer: The QGIS layer
            
        Returns:
            Dictionary representation of the layer's style
        """
        # This is a placeholder - actual implementation would depend on
        # how styles are stored and retrieved in the MapHub plugin
        from ..utils.utils import get_layer_styles_as_json
        return get_layer_styles_as_json(layer, {})
    
    def synchronize_layer(self, layer, direction="auto"):
        """
        Synchronize a layer with its MapHub counterpart.
        
        Args:
            layer: The QGIS layer
            direction: The synchronization direction:
                - "auto": Automatically determine direction based on status
                - "push": Upload local changes to MapHub
                - "pull": Download remote changes from MapHub
        
        Raises:
            Exception: If synchronization fails
        """
        if not layer.customProperty("maphub/map_id"):
            self.show_error("Layer is not connected to MapHub")
            return
        
        status = self.get_layer_sync_status(layer)
        map_id = layer.customProperty("maphub/map_id")
        
        if direction == "auto":
            # Determine direction based on status
            if status == "local_modified":
                direction = "push"
            elif status == "remote_newer":
                direction = "pull"
            elif status == "style_changed":
                # For now, just use push direction for style changes
                # In the future, this would show a style conflict resolution dialog
                direction = "push"
            elif status == "in_sync":
                self.iface.messageBar().pushInfo("MapHub", f"Layer '{layer.name()}' is already in sync with MapHub.")
                return
            else:
                self.show_error(f"Cannot synchronize layer with status: {status}")
                return
        
        try:
            if direction == "push":
                # Upload local changes to MapHub
                local_path = layer.customProperty("maphub/local_path")
                get_maphub_client().versions.upload_version(map_id, "QGIS upload", local_path)
                
                # Update style if needed
                style_dict = self.get_layer_style_as_dict(layer)
                if style_dict:
                    get_maphub_client().maps.update_map_style(map_id, style_dict)
                
                # Update metadata
                layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())

                self.iface.messageBar().pushSuccess("MapHub", f"Layer '{layer.name()}' successfully uploaded to MapHub.")
                
            elif direction == "pull":
                # Download remote changes
                local_path = layer.customProperty("maphub/local_path")
                get_maphub_client().maps.download_map(map_id, local_path)
                
                # Reload layer from file
                layer_name = layer.name()
                layer_type = "raster" if isinstance(layer, QgsRasterLayer) else "vector"
                
                # Remove current layer
                QgsProject.instance().removeMapLayer(layer.id())
                
                # Add new layer
                if layer_type == "raster":
                    new_layer = self.iface.addRasterLayer(local_path, layer_name)
                else:
                    new_layer = self.iface.addVectorLayer(local_path, layer_name, "ogr")
                
                # Transfer MapHub properties
                for key in ["maphub/map_id", "maphub/folder_id", "maphub/workspace_id", "maphub/local_path"]:
                    new_layer.setCustomProperty(key, layer.customProperty(key))
                
                # Get and apply remote style
                map_info = get_maphub_client().maps.get_map(map_id)
                if 'visuals' in map_info and map_info['visuals']:
                    apply_style_to_layer(new_layer, map_info['visuals'])

                # Update sync timestamp
                new_layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                
                self.iface.messageBar().pushSuccess("MapHub", f"Layer '{layer_name}' successfully updated from MapHub.")
                
        except Exception as e:
            self.show_error(f"Synchronization failed: {str(e)}", e)
    
    def disconnect_layer(self, layer):
        """
        Disconnect a layer from MapHub.
        
        Args:
            layer: The QGIS layer
        """
        if not layer.customProperty("maphub/map_id"):
            return
        
        # Remove MapHub properties
        layer.removeCustomProperty("maphub/map_id")
        layer.removeCustomProperty("maphub/folder_id")
        layer.removeCustomProperty("maphub/workspace_id")
        layer.removeCustomProperty("maphub/last_sync")
        layer.removeCustomProperty("maphub/local_path")
        
        self.iface.messageBar().pushInfo("MapHub", f"Layer '{layer.name()}' disconnected from MapHub.")
    
    def show_error(self, message, exception=None):
        """
        Show error message with option to see details.
        
        Args:
            message: The error message
            exception: The exception that caused the error (optional)
        """
        error_dialog = QMessageBox(QMessageBox.Critical, "Error", message)
        
        if exception:
            details = str(exception)
            if hasattr(exception, '__traceback__'):
                import traceback
                details = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            
            error_dialog.setDetailedText(details)
        
        error_dialog.exec_()