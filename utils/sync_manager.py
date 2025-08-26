import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from PyQt5.QtWidgets import QMessageBox
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

from ..maphub.exceptions import APIException
from .utils import get_maphub_client, apply_style_to_layer, get_layer_styles_as_json, get_default_download_location


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
        except APIException as e:
            print(f"Error checking remote status: {e}")
            if e.status_code == 404 and "is not processed yet" in e.message:
                return "processing"
            else:
                return "remote_error"
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
            elif status == "processing":
                self.show_error("This map is still being processed by MapHub. Please try again later.")
                return
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
                    get_maphub_client().maps.set_visuals(map_id, style_dict)
                
                # Update metadata
                layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())

                self.iface.messageBar().pushSuccess("MapHub", f"Layer '{layer.name()}' successfully uploaded to MapHub.")
                
            elif direction == "pull":
                # Get the local path or use default download location if missing
                local_path = layer.customProperty("maphub/local_path")
                
                # Check if local path exists or needs to be updated
                if not local_path or not os.path.exists(local_path) or status == "file_missing":
                    # Get default download location
                    default_dir = get_default_download_location()
                    
                    # Create safe filename from layer name
                    layer_name = layer.name()
                    safe_name = ''.join(c for c in layer_name if c.isalnum() or c in ' _-')
                    safe_name = safe_name.replace(' ', '_')
                    
                    # Determine file extension based on layer type
                    if isinstance(layer, QgsVectorLayer):
                        file_extension = '.gpkg'  # Default to GeoPackage for vector
                    elif isinstance(layer, QgsRasterLayer):
                        file_extension = '.tif'  # Default to GeoTIFF for raster
                    else:
                        file_extension = '.gpkg'  # Default fallback
                    
                    # If original path exists, try to use its extension
                    if local_path and os.path.exists(os.path.dirname(local_path)):
                        orig_ext = os.path.splitext(local_path)[1]
                        if orig_ext:
                            file_extension = orig_ext
                    
                    # Create full file path
                    local_path = os.path.join(str(default_dir), f"{safe_name}{file_extension}")
                    
                    # Ensure filename is unique
                    counter = 1
                    base_name = os.path.splitext(local_path)[0]
                    while os.path.exists(local_path):
                        local_path = f"{base_name}_{counter}{file_extension}"
                        counter += 1
                    
                    # Update the layer property with the new path
                    layer.setCustomProperty("maphub/local_path", local_path)
                
                # Download remote changes
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
                for key in ["maphub/map_id", "maphub/folder_id", "maphub/local_path"]:
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


    def add_layer(self, layer, map_name, folder_id, public=False):
        # Create a temporary directory to store the files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Get the layer file path
            layer_path = layer.source()
            if '|' in layer_path:  # Handle layers with query parameters
                layer_path = layer_path.split('|')[0]

            # Determine the file extension based on layer type
            if isinstance(layer, QgsVectorLayer):
                file_extension = os.path.splitext(layer_path)[1]
                if not file_extension:
                    file_extension = '.gpkg'  # Default to GeoPackage
            elif isinstance(layer, QgsRasterLayer):
                file_extension = os.path.splitext(layer_path)[1]
                if not file_extension:
                    file_extension = '.tif'  # Default to GeoTIFF
            else:
                raise Exception("Unsupported layer type.")

            # Create a temporary file path
            temp_file = os.path.join(temp_dir, f"{map_name}{file_extension}")

            # Copy the layer file to the temporary directory
            if os.path.exists(layer_path):
                # For file-based layers, copy the file
                with open(layer_path, 'rb') as src_file:
                    with open(temp_file, 'wb') as dst_file:
                        dst_file.write(src_file.read())

                # For shapefiles, copy all related files
                if file_extension.lower() == '.shp':
                    base_name = os.path.splitext(layer_path)[0]
                    for ext in ['.dbf', '.shx', '.prj', '.qpj', '.cpg']:
                        related_file = f"{base_name}{ext}"
                        if os.path.exists(related_file):
                            with open(related_file, 'rb') as src_file:
                                with open(os.path.join(temp_dir, f"{map_name}{ext}"), 'wb') as dst_file:
                                    dst_file.write(src_file.read())
            else:
                # For memory layers or other non-file layers, save to a new file
                raise Exception("Layer is not file-based. Please save it to a file first.")

            # Get the layer style
            style_json = get_layer_styles_as_json(layer, {})

            # Upload the map to MapHub
            client = get_maphub_client()
            result = client.maps.upload_map(
                map_name,
                folder_id,
                public=public,
                path=temp_file
            )

            # Get the map ID from the result
            map_id = result.get('map_id')

            # Update the layer visuals with the uploaded map style
            client.maps.set_visuals(map_id, style_json)

            # Connect the layer to the uploaded map
            if map_id:
                # Get the layer's source path
                source_path = layer.source()
                if '|' in source_path:  # Handle layers with query parameters
                    source_path = source_path.split('|')[0]

                # Connect the layer to MapHub
                self.connect_layer(
                    layer,
                    map_id,
                    folder_id,
                    source_path
                )

    def connect_layer(self, layer, map_id, folder_id, local_path):
        """
        Connect a layer to a MapHub map.
        
        This method stores connection information in the layer's custom properties,
        establishing a link between the local QGIS layer and a remote MapHub map.
        
        Args:
            layer: The QGIS layer to connect
            map_id: The MapHub map ID
            folder_id: The MapHub folder ID
            workspace_id: The MapHub workspace ID
            local_path: The local file path
            
        Returns:
            None
            
        Raises:
            ValueError: If any of the required parameters are invalid
        """
        # Store MapHub connection information in layer properties
        layer.setCustomProperty("maphub/map_id", str(map_id))
        layer.setCustomProperty("maphub/folder_id", str(folder_id))
        layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
        layer.setCustomProperty("maphub/local_path", local_path)
        
        self.iface.messageBar().pushInfo("MapHub", f"Layer '{layer.name()}' connected to MapHub.")
    
    def disconnect_layer(self, layer):
        """
        Disconnect a layer from MapHub.
        
        This method removes all MapHub connection information from the layer's
        custom properties, effectively breaking the link between the local QGIS
        layer and the remote MapHub map.
        
        Args:
            layer: The QGIS layer to disconnect
            
        Returns:
            None
            
        Raises:
            None
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
        from .error_manager import ErrorManager
        ErrorManager.show_error(message, exception)