import hashlib
import os
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

from ..maphub.exceptions import APIException
from .utils import get_maphub_client, apply_style_to_layer, get_layer_styles_as_json, get_default_download_location, normalize_style_xml_and_hash


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
            - "style_changed_local": Local style has changed since last sync
            - "style_changed_remote": Remote style has changed since last sync
            - "style_changed_both": Both local and remote styles have changed since last sync
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
            map_info = get_maphub_client().maps.get_map(map_id)['map']
            
            # Get the latest version ID from the map info
            latest_version_id = map_info.get('latest_version_id')
            
            # Get the last synced version ID from layer properties
            last_synced_version_id = layer.customProperty("maphub/last_version_id")
            
            # If we have both IDs and they're different, a new version exists
            if latest_version_id and last_synced_version_id and latest_version_id != last_synced_version_id:
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
        local_style_dict = get_layer_styles_as_json(layer, {})
        
        # Only use the QGIS field for style comparison
        if 'qgis' in local_style_dict:
            # Use normalized XML for hash calculation to handle QGIS reordering elements
            local_style_hash = normalize_style_xml_and_hash(local_style_dict['qgis'])
            
            if 'visuals' in map_info and map_info['visuals'] and 'qgis' in map_info['visuals']:
                # Use normalized XML for remote hash calculation as well
                remote_style_hash = normalize_style_xml_and_hash(map_info['visuals']['qgis'])
                
                if local_style_hash != remote_style_hash:
                    # Get the last synced style hash (stored during last sync)
                    last_synced_hash = layer.customProperty("maphub/last_style_hash")
                    
                    if not last_synced_hash:
                        # First sync or no stored hash, can't determine which side changed
                        return "style_changed_remote"
                    elif local_style_hash != last_synced_hash and remote_style_hash != last_synced_hash:
                        return "style_changed_both"
                    elif local_style_hash != last_synced_hash:
                        return "style_changed_local"
                    elif remote_style_hash != last_synced_hash:
                        return "style_changed_remote"
        
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
        
    def _push_layer_style(self, layer, map_id):
        """
        Push layer style to MapHub.
        
        Args:
            layer: The QGIS layer
            map_id: The MapHub map ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        style_dict = self.get_layer_style_as_dict(layer)
        if not style_dict:
            return False
            
        get_maphub_client().maps.set_visuals(map_id, style_dict)
        
        # Store the current style hash for future comparison
        if 'qgis' in style_dict:
            # Use normalized XML for hash calculation to handle QGIS reordering elements
            style_hash = normalize_style_xml_and_hash(style_dict['qgis'])
            layer.setCustomProperty("maphub/last_style_hash", style_hash)
        
        return True

    def _pull_and_apply_style(self, layer, map_id):
        """
        Pull style from MapHub and apply it to the layer.
        
        Args:
            layer: The QGIS layer
            map_id: The MapHub map ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        map_info = get_maphub_client().maps.get_map(map_id)['map']
        if 'visuals' not in map_info or not map_info['visuals']:
            return False
            
        apply_style_to_layer(layer, map_info['visuals'])
        
        # Store the remote style hash for future comparison
        if 'qgis' in map_info['visuals']:
            # Use normalized XML for hash calculation to handle QGIS reordering elements
            style_hash = normalize_style_xml_and_hash(map_info['visuals']['qgis'])
            layer.setCustomProperty("maphub/last_style_hash", style_hash)
        
        return True
    
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
            elif status == "style_changed_local":
                direction = "push"  # Local changes take precedence
            elif status == "style_changed_remote":
                direction = "pull"  # Remote changes take precedence
            elif status == "style_changed_both":
                # For conflicts, show a resolution dialog
                self.show_style_conflict_resolution_dialog(layer)
                return
            elif status == "in_sync":
                self.iface.messageBar().pushInfo("MapHub", f"Layer '{layer.name()}' is already in sync with MapHub.")
                return
            else:
                self.show_error(f"Cannot synchronize layer with status: {status}")
                return
        
        try:
            if direction == "push":
                # Check if only style has changed
                if status == "style_changed_local":
                    # Only upload the style, not the entire file
                    if self._push_layer_style(layer, map_id):
                        # Update metadata
                        layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                        
                        self.iface.messageBar().pushSuccess("MapHub", f"Style for layer '{layer.name()}' successfully uploaded to MapHub.")
                else:
                    # Upload local changes to MapHub (full file upload)
                    local_path = layer.customProperty("maphub/local_path")
                    new_version = get_maphub_client().versions.upload_version(map_id, "QGIS upload", local_path)
                    
                    # Update style if needed
                    self._push_layer_style(layer, map_id)
                    
                    # Update metadata
                    layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                    
                    # Update the stored version ID
                    if 'task_id' in new_version:
                        layer.setCustomProperty("maphub/last_version_id", str(new_version.get('task_id')))

                    self.iface.messageBar().pushSuccess("MapHub", f"Layer '{layer.name()}' successfully uploaded to MapHub.")
                
            elif direction == "pull":
                # Check if only style has changed
                if status == "style_changed_remote":
                    # Only download and apply the style, not the entire file
                    if self._pull_and_apply_style(layer, map_id):
                        # Update sync timestamp
                        layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                        
                        self.iface.messageBar().pushSuccess("MapHub", f"Style for layer '{layer.name()}' successfully updated from MapHub.")
                else:
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
                    
                    # Store all needed properties from the layer before removing it
                    layer_properties = {key: layer.customProperty(key) for key in layer.customProperties().keys()}

                    try:
                        # Remove current layer
                        QgsProject.instance().removeMapLayer(layer.id())
                        
                        # Add new layer
                        if layer_type == "raster":
                            new_layer = self.iface.addRasterLayer(local_path, layer_name)
                        else:
                            new_layer = self.iface.addVectorLayer(local_path, layer_name, "ogr")
                            
                        if not new_layer or not new_layer.isValid():
                            raise Exception(f"Failed to create new layer from {local_path}")
                    except Exception as e:
                        self.show_error(f"Error reloading layer: {str(e)}", e)
                        return

                    # Get and apply remote style
                    self._pull_and_apply_style(new_layer, map_id)

                    # Update sync timestamp
                    new_layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                    
                    # Update the stored version ID
                    # Get map info to retrieve the latest version ID
                    map_info = get_maphub_client().maps.get_map(map_id)['map']
                    if 'latest_version_id' in map_info:
                        new_layer.setCustomProperty("maphub/last_version_id", str(map_info.get('latest_version_id')))

                    # Transfer MapHub properties using the stored values
                    for key, value in layer_properties.items():
                        if key not in ["maphub/last_version_id", "maphub/last_sync", "maphub/last_style_hash"]:
                            new_layer.setCustomProperty(key, value)


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
        
        # Store initial version ID for future comparison
        try:
            # Get the map info to retrieve the latest version ID
            map_info = get_maphub_client().maps.get_map(map_id)['map']
            if 'latest_version_id' in map_info:
                layer.setCustomProperty("maphub/last_version_id", str(map_info.get('latest_version_id')))
        except Exception as e:
            print(f"Error storing initial version ID: {e}")
        
        # Store initial style hash for future comparison
        try:
            # Get the current style hash
            style_dict = self.get_layer_style_as_dict(layer)
            if 'qgis' in style_dict:
                style_hash = hashlib.md5(style_dict['qgis'].encode()).hexdigest()
                layer.setCustomProperty("maphub/last_style_hash", style_hash)
        except Exception as e:
            print(f"Error storing initial style hash: {e}")
        
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
        layer.removeCustomProperty("maphub/last_style_hash")
        layer.removeCustomProperty("maphub/last_version_id")
        
        self.iface.messageBar().pushInfo("MapHub", f"Layer '{layer.name()}' disconnected from MapHub.")
    
    def show_style_conflict_resolution_dialog(self, layer):
        """
        Show a dialog for resolving style conflicts when both local and remote styles have changed.
        
        Args:
            layer: The QGIS layer with style conflicts
        """
        from PyQt5.QtWidgets import QMessageBox
        
        response = QMessageBox.question(
            self.iface.mainWindow(),
            "Style Conflict",
            f"The layer '{layer.name()}' has style changes on both local and remote versions.\n\n"
            "How would you like to resolve this conflict?",
            QMessageBox.Save | QMessageBox.Open | QMessageBox.Cancel,
            QMessageBox.Cancel
        )
        
        if response == QMessageBox.Save:
            # Upload local style to MapHub
            self.synchronize_layer(layer, "push")
        elif response == QMessageBox.Open:
            # Download remote style from MapHub
            self.synchronize_layer(layer, "pull")
    
    def show_error(self, message, exception=None):
        """
        Show error message with option to see details.
        
        Args:
            message: The error message
            exception: The exception that caused the error (optional)
        """
        from .error_manager import ErrorManager
        ErrorManager.show_error(message, exception)