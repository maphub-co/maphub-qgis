import hashlib
import os
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsApplication

from ..maphub.exceptions import APIException
from .maphub_plugin_layer import MapHubPluginLayer
from .utils import get_maphub_client, apply_style_to_layer, get_layer_styles_as_json, get_default_download_location, normalize_style_xml_and_hash, layer_position, place_layer_at_position


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
            if isinstance(layer, MapHubPluginLayer):
                connected_layers.append(layer)
            elif layer.customProperty("maphub/map_id"):
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
            if isinstance(layer, MapHubPluginLayer) and layer.map_id() == str(map_id):
                return layer
            elif layer.customProperty("maphub/map_id") == str(map_id):
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
        # Handle MapHubPluginLayer
        if isinstance(layer, MapHubPluginLayer):
            if not layer.map_id():
                return "not_connected"
            
            # Get properties from the MapHubPluginLayer
            map_id = layer.map_id()
            local_path = layer.local_path()
            last_sync = layer.last_sync()
            last_synced_version_id = layer.version_id()
            last_synced_hash = layer.last_style_hash()
        else:
            # Handle standard layers with custom properties
            if not layer.customProperty("maphub/map_id"):
                return "not_connected"
                
            # Get properties from layer custom properties
            map_id = layer.customProperty("maphub/map_id")
            local_path = layer.customProperty("maphub/local_path")
            last_sync = layer.customProperty("maphub/last_sync")
            last_synced_version_id = layer.customProperty("maphub/last_version_id")
            last_synced_hash = layer.customProperty("maphub/last_style_hash")
        
        # Check if local file exists
        if not local_path or not os.path.exists(local_path):
            return "file_missing"
        
        # Check if local file is modified
        if last_sync:
            last_sync_time = datetime.fromisoformat(last_sync)
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(local_path))
            if file_mod_time > last_sync_time:
                return "local_modified"
        
        # Check if remote has newer version
        try:
            map_info = get_maphub_client().maps.get_map(map_id)['map']
            
            # Get the latest version ID from the map info
            latest_version_id = map_info.get('latest_version_id')
            
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
        
        # Get the current layer position and add it to the style
        project = QgsProject.instance()
        position = layer_position(project, layer)
        style_dict['layer_order'] = position
            
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
            layer: The QGIS layer (MapHubPluginLayer or standard layer with custom properties)
            map_id: The MapHub map ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        map_info = get_maphub_client().maps.get_map(map_id)['map']
        if 'visuals' not in map_info or not map_info['visuals']:
            return False

        # Handle MapHubPluginLayer
        if isinstance(layer, MapHubPluginLayer):
            # Apply the style
            apply_style_to_layer(layer, map_info['visuals'])
            
            # Store the remote style hash for future comparison
            if 'qgis' in map_info['visuals']:
                # Use normalized XML for hash calculation to handle QGIS reordering elements
                style_hash = normalize_style_xml_and_hash(map_info['visuals']['qgis'])
                layer.set_last_style_hash(style_hash)
                
            return True
        
        # Legacy support for standard layers with custom properties
        layer_properties = {key: layer.customProperty(key) for key in layer.customProperties().keys()}
            
        apply_style_to_layer(layer, map_info['visuals'])

        # Transfer MapHub properties using the stored values
        for key, value in layer_properties.items():
            if key not in ["maphub/last_version_id", "maphub/last_sync", "maphub/last_style_hash"]:
                layer.setCustomProperty(key, value)

        # Store the remote style hash for future comparison
        if 'qgis' in map_info['visuals']:
            # Use normalized XML for hash calculation to handle QGIS reordering elements
            style_hash = normalize_style_xml_and_hash(map_info['visuals']['qgis'])
            layer.setCustomProperty("maphub/last_style_hash", style_hash)

        return True
    
    def synchronize_layer(self, layer, direction="auto", style_only=False):
        """
        Synchronize a layer with its MapHub counterpart.
        
        Args:
            layer: The QGIS layer (MapHubPluginLayer or standard layer with custom properties)
            direction: The synchronization direction:
                - "auto": Automatically determine direction based on status
                - "push": Upload local changes to MapHub
                - "pull": Download remote changes from MapHub
            style_only: If True, only synchronize the style, not the entire file
        
        Raises:
            Exception: If synchronization fails
        """
        # Handle MapHubPluginLayer
        if isinstance(layer, MapHubPluginLayer):
            if not layer.map_id():
                self.show_error("Layer is not connected to MapHub")
                return
            map_id = layer.map_id()
        # Legacy support for standard layers with custom properties
        elif not layer.customProperty("maphub/map_id"):
            # Convert to MapHubPluginLayer
            self.show_error("Layer is not connected to MapHub")
            return
        else:
            # Get the map_id from custom properties
            map_id = layer.customProperty("maphub/map_id")
            
            # Convert to MapHubPluginLayer
            folder_id = layer.customProperty("maphub/folder_id")
            local_path = layer.customProperty("maphub/local_path")
            version_id = layer.customProperty("maphub/last_version_id")
            
            # Use connect_layer to convert to MapHubPluginLayer
            self.connect_layer(layer, map_id, folder_id, local_path, version_id)
            
            # Find the newly created MapHubPluginLayer
            new_layer = self.find_layer_by_map_id(map_id)
            if new_layer:
                # Recursively call synchronize_layer with the new MapHubPluginLayer
                return self.synchronize_layer(new_layer, direction, style_only)
            else:
                self.show_error("Failed to convert layer to MapHubPluginLayer")
                return
        
        if direction == "auto":
            status = self.get_layer_sync_status(layer)

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
                if style_only:
                    # Only upload the style, not the entire file
                    # Get the current layer position and add it to the style
                    project = QgsProject.instance()
                    position = layer_position(project, layer)
                    
                    # Update style with layer position
                    style_json = self.get_layer_style_as_dict(layer)
                    style_json['layer_order'] = position
                    
                    # Upload the style with layer position
                    get_maphub_client().maps.set_visuals(map_id, style_json)
                    
                    # Store the current style hash for future comparison
                    if 'qgis' in style_json:
                        style_hash = normalize_style_xml_and_hash(style_json['qgis'])
                        if isinstance(layer, MapHubPluginLayer):
                            layer.set_last_style_hash(style_hash)
                        else:
                            layer.setCustomProperty("maphub/last_style_hash", style_hash)
                    
                    # Update metadata
                    if isinstance(layer, MapHubPluginLayer):
                        layer.set_last_sync(datetime.now().isoformat())
                    else:
                        layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                    
                    self.iface.messageBar().pushSuccess("MapHub", f"Style for layer '{layer.name()}' successfully uploaded to MapHub.")
                else:
                    # Upload local changes to MapHub (full file upload)
                    if isinstance(layer, MapHubPluginLayer):
                        local_path = layer.local_path()
                    else:
                        local_path = layer.customProperty("maphub/local_path")
                    
                    # Get the current layer position and add it to the style
                    project = QgsProject.instance()
                    position = layer_position(project, layer)
                    
                    # Update style with layer position
                    style_json = self.get_layer_style_as_dict(layer)
                    style_json['layer_order'] = position
                    
                    # Upload the file
                    new_version = get_maphub_client().versions.upload_version(map_id, "QGIS upload", local_path)
                    
                    # Update the map visuals with the style including layer position
                    get_maphub_client().maps.set_visuals(map_id, style_json)
                    
                    # Get the new version ID
                    new_version_id = None
                    if 'task_id' in new_version:
                        new_version_id = str(new_version.get('task_id'))
                        if isinstance(layer, MapHubPluginLayer):
                            layer.set_version_id(new_version_id)
                        else:
                            layer.setCustomProperty("maphub/last_version_id", new_version_id)
                    
                    # Rename/move the file to reflect the new version
                    if new_version_id:
                        # Get default download location
                        default_dir = get_default_download_location()
                        
                        # Determine file extension
                        file_extension = os.path.splitext(local_path)[1]
                        if not file_extension:
                            # Determine default extension based on layer type
                            if isinstance(layer, QgsVectorLayer) or (isinstance(layer, MapHubPluginLayer) and layer.delegate_layer and isinstance(layer.delegate_layer, QgsVectorLayer)):
                                file_extension = '.fgb'  # Default to FlatGeobuf
                            elif isinstance(layer, QgsRasterLayer) or (isinstance(layer, MapHubPluginLayer) and layer.delegate_layer and isinstance(layer.delegate_layer, QgsRasterLayer)):
                                file_extension = '.tif'  # Default to GeoTIFF
                            else:
                                file_extension = '.fgb'  # Default fallback
                        
                        # Create new file path with map_id and version_id
                        new_path = os.path.join(str(default_dir), f"{map_id}_{new_version_id}{file_extension}")
                        
                        # Store the old path for deletion later
                        old_path = local_path
                        
                        # Copy the file to the new location
                        if os.path.exists(local_path):
                            # Create directory if it doesn't exist
                            os.makedirs(os.path.dirname(new_path), exist_ok=True)
                            
                            # Copy the file
                            with open(local_path, 'rb') as src_file:
                                with open(new_path, 'wb') as dst_file:
                                    dst_file.write(src_file.read())
                            
                            # Update the layer's source path
                            if isinstance(layer, MapHubPluginLayer):
                                layer.set_local_path(new_path)
                                # Recreate the delegate layer with the new path
                                layer._create_delegate_layer()
                            else:
                                layer.setCustomProperty("maphub/local_path", new_path)
                            
                            # For shapefiles, copy all related files and delete old ones
                            if file_extension.lower() == '.shp':
                                base_name = os.path.splitext(local_path)[0]
                                new_base_name = os.path.splitext(new_path)[0]
                                for ext in ['.dbf', '.shx', '.prj', '.qpj', '.cpg']:
                                    related_file = f"{base_name}{ext}"
                                    if os.path.exists(related_file):
                                        # Copy the related file
                                        with open(related_file, 'rb') as src_file:
                                            with open(f"{new_base_name}{ext}", 'wb') as dst_file:
                                                dst_file.write(src_file.read())
                                        # Delete the old related file
                                        os.remove(related_file)
                            
                            # Delete the old file after successful copy
                            os.remove(old_path)
                    
                    # Update metadata
                    if isinstance(layer, MapHubPluginLayer):
                        layer.set_last_sync(datetime.now().isoformat())
                    else:
                        layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                    
                    self.iface.messageBar().pushSuccess("MapHub", f"Layer '{layer.name()}' successfully uploaded to MapHub.")
                
            elif direction == "pull":
                # Check if only style has changed
                if style_only:
                    # Only download and apply the style, not the entire file
                    if self._pull_and_apply_style(layer, map_id):
                        # Update sync timestamp
                        if isinstance(layer, MapHubPluginLayer):
                            layer.set_last_sync(datetime.now().isoformat())
                        else:
                            layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                        
                        self.iface.messageBar().pushSuccess("MapHub", f"Style for layer '{layer.name()}' successfully updated from MapHub.")
                else:
                    # Create safe filename from layer name
                    layer_name = layer.name()
                    
                    # Get map info to retrieve layer_order
                    map_info = get_maphub_client().maps.get_map(map_id)['map']
                    layer_order = map_info.get('visuals', {}).get('layer_order')
                    
                    # Download the map using our centralized function
                    new_layer = self.download_map(
                        map_id=map_id,
                        layer_name=layer_name,
                        connect_layer=True
                    )
                    
                    # Place the layer at the correct position if layer_order exists
                    if layer_order and new_layer:
                        place_layer_at_position(QgsProject.instance(), new_layer, layer_order)
                    
                    # Remove current layer
                    QgsProject.instance().removeMapLayer(layer.id())
                    
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

            # Determine if it's a file-based layer or a database layer
            is_file_based = os.path.exists(layer_path)

            # Determine the file extension based on layer type
            if isinstance(layer, QgsVectorLayer):
                if is_file_based:
                    file_extension = os.path.splitext(layer_path)[1]
                    if not file_extension:
                        file_extension = '.fgb'  # Default to FlatGeobuf
                else:
                    # For database layers (like PostGIS), use FlatGeobuf
                    file_extension = '.fgb'
            elif isinstance(layer, QgsRasterLayer):
                file_extension = os.path.splitext(layer_path)[1]
                if not file_extension:
                    file_extension = '.tif'  # Default to GeoTIFF
            else:
                raise Exception("Unsupported layer type.")

            # Create a temporary file path
            temp_file = os.path.join(temp_dir, f"{map_name}{file_extension}")

            # Handle the layer based on its type and source
            if isinstance(layer, QgsVectorLayer) and not is_file_based:
                # For database layers (like PostGIS), export to file format
                from qgis.core import QgsVectorFileWriter
                
                # Export to FlatGeobuf format
                error = QgsVectorFileWriter.writeAsVectorFormat(
                    layer,
                    temp_file,
                    "UTF-8",
                    layer.crs(),
                    "FlatGeobuf"
                )
                
                if error[0] != QgsVectorFileWriter.NoError:
                    raise Exception(f"Error exporting layer: {error[0]}")
            elif is_file_based:
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
                # For memory layers or other non-file layers that aren't handled above
                raise Exception("Layer is not file-based and couldn't be exported. Please save it to a file first.")

            # Get the layer style
            style_json = get_layer_styles_as_json(layer, {})
            
            # Get the current layer position and add it to the style
            project = QgsProject.instance()
            position = layer_position(project, layer)
            style_json['layer_order'] = position

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

            # Update the layer visuals with the uploaded map style including layer position
            client.maps.set_visuals(map_id, style_json)

            # Connect the layer to the uploaded map
            if map_id:
                # For database layers, store the temp file path as the local path
                # This allows future synchronization to work with the exported file
                if isinstance(layer, QgsVectorLayer) and not is_file_based:
                    # Create a permanent copy of the temporary file in the default download location
                    default_dir = get_default_download_location()
                    permanent_path = os.path.join(str(default_dir), f"{map_name}{file_extension}")
                    
                    # Ensure filename is unique
                    counter = 1
                    base_name = os.path.splitext(permanent_path)[0]
                    while os.path.exists(permanent_path):
                        permanent_path = f"{base_name}_{counter}{file_extension}"
                        counter += 1
                    
                    # Copy the temporary file to the permanent location
                    with open(temp_file, 'rb') as src_file:
                        with open(permanent_path, 'wb') as dst_file:
                            dst_file.write(src_file.read())
                    
                    # Use the permanent path for connection
                    local_path = permanent_path
                else:
                    # Get the layer's source path
                    local_path = layer.source()
                    if '|' in local_path:  # Handle layers with query parameters
                        local_path = local_path.split('|')[0]

                # Connect the layer to MapHub
                self.connect_layer(
                    layer,
                    map_id,
                    folder_id,
                    local_path
                )

    def download_map(self, map_id, version_id=None, path=None, file_format=None, layer_name=None, connect_layer=True):
        """
        Downloads a map from MapHub with consistent file naming that includes version information.
        Uses the default download location as a cache to avoid redownloading files.
        
        Args:
            map_id: The ID of the map to download
            version_id: Optional specific version to download
            path: Optional specific path to save the file. If None, a path will be generated
            file_format: Optional format to download the map in
            layer_name: Optional name for the layer. If None, the map name will be used
            connect_layer: Whether to connect the layer to MapHub after downloading
            
        Returns:
            The QGIS layer object that was added to the project
        """
        # Get map information to retrieve name and version
        map_info = get_maphub_client().maps.get_map(map_id)['map']

        if version_id is None:
            version_id = map_info.get('latest_version_id')
        
        # If no specific path is provided, generate one
        if not path:
            # Get default download location (which serves as our cache)
            default_dir = get_default_download_location()
            
            # Use map_id and version_id as the primary identifier in the filename
            safe_name = f"{map_id}_{version_id}"
            
            # Determine file extension based on format
            if file_format:
                file_extension = f".{file_format}"
            elif map_info.get('type') == 'raster':
                file_extension = '.tif'
                file_format = 'tif'
            else:  # Default to FlatGeobuf for vector
                file_extension = '.fgb'
                file_format = 'fgb'
            
            # Create full file path
            path = os.path.join(str(default_dir), f"{safe_name}{file_extension}")

        
        # Check if the file already exists in the cache (default download location)
        if os.path.exists(path):
            print(f"Using cached file: {path}")
        else:
            # Download the map
            get_maphub_client().versions.download_version(version_id, path, file_format)
        
        # Check if download was successful
        if not os.path.exists(path):
            raise Exception(f"Downloaded file not found at {path}")
        
        # Add the layer to QGIS
        if not layer_name:
            layer_name = map_info.get('name', 'map')
            
        # Add layer based on map type
        if map_info.get('type') == 'raster':
            layer = self.iface.addRasterLayer(path, layer_name)
        else:
            layer = self.iface.addVectorLayer(path, layer_name, "ogr")
        
        if not layer or not layer.isValid():
            raise Exception(f"Failed to create layer from {path}")
        
        # Connect the layer to MapHub if requested
        if connect_layer:
            # Get folder_id and workspace_id from map_info if not already available
            folder_id = map_info.get('folder_id', '')
            workspace_id = map_info.get('workspace_id', '')
            
            # Create a MapHubPluginLayer instead of connecting a standard layer
            # First, get the layer position and style
            project = QgsProject.instance()
            position = layer_position(project, layer)
            style_dict = get_layer_styles_as_json(layer, {})
            
            # Remove the standard layer
            QgsProject.instance().removeMapLayer(layer.id())
            
            # Create a MapHubPluginLayer
            layer = self.create_maphub_layer(
                map_id,
                folder_id,
                workspace_id,
                version_id,
                layer_name
            )
            
            # Apply the style
            if style_dict and 'qgis' in style_dict:
                apply_style_to_layer(layer, style_dict)
                
            # Place the layer at the correct position
            if position:
                place_layer_at_position(project, layer, position)
            
        # Apply the style from MapHub
        self._pull_and_apply_style(layer, map_id)

        
        return layer

    def connect_layer(self, layer, map_id, folder_id, local_path, version_id=None):
        """
        Connect a layer to a MapHub map.
        
        This method is deprecated. Use create_maphub_layer instead.
        
        Args:
            layer: The QGIS layer to connect
            map_id: The MapHub map ID
            folder_id: The MapHub folder ID
            local_path: The local file path
            version_id: Optional specific version to connect
            
        Returns:
            None
        """
        # Get the workspace_id from the map info
        try:
            map_info = get_maphub_client().maps.get_map(map_id)['map']
            workspace_id = map_info.get('workspace_id', '')
        except Exception:
            workspace_id = ''
            
        # Get the layer position and style
        project = QgsProject.instance()
        position = layer_position(project, layer)
        style_dict = get_layer_styles_as_json(layer, {})
        
        # Remove the standard layer
        QgsProject.instance().removeMapLayer(layer.id())
        
        # Create a MapHubPluginLayer
        new_layer = self.create_maphub_layer(
            map_id,
            folder_id,
            workspace_id,
            version_id,
            layer.name()
        )
        
        # Apply the style
        if style_dict and 'qgis' in style_dict:
            apply_style_to_layer(new_layer, style_dict)
            
        # Place the layer at the correct position
        if position:
            place_layer_at_position(project, new_layer, position)
            
        self.iface.messageBar().pushInfo("MapHub", f"Layer '{new_layer.name()}' connected to MapHub.")
    
    def disconnect_layer(self, layer):
        """
        Disconnect a layer from MapHub.
        
        This method handles both MapHubPluginLayer instances and standard layers
        with custom properties.
        
        Args:
            layer: The QGIS layer to disconnect
            
        Returns:
            None
        """
        if isinstance(layer, MapHubPluginLayer):
            # Use the layer's disconnect method
            layer.disconnect_from_maphub()
            self.iface.messageBar().pushInfo("MapHub", f"Layer '{layer.name()}' disconnected from MapHub.")
            return
            
        # Legacy support for standard layers with custom properties
        if not layer.customProperty("maphub/map_id"):
            return
            
        # Get the layer position and style
        project = QgsProject.instance()
        position = layer_position(project, layer)
        style_dict = get_layer_styles_as_json(layer, {})
        local_path = layer.customProperty("maphub/local_path")
        
        # Create a new standard layer with the same source
        if layer.type() == 0:  # Vector layer
            new_layer = QgsVectorLayer(local_path, f"{layer.name()} (Disconnected)", "ogr")
        else:  # Raster layer
            new_layer = QgsRasterLayer(local_path, f"{layer.name()} (Disconnected)")
            
        # Apply the style
        if style_dict and 'qgis' in style_dict:
            apply_style_to_layer(new_layer, style_dict)
            
        # Remove the old layer
        QgsProject.instance().removeMapLayer(layer.id())
        
        # Add the new layer
        QgsProject.instance().addMapLayer(new_layer)
        
        # Place the layer at the correct position
        if position:
            place_layer_at_position(project, new_layer, position)
            
        self.iface.messageBar().pushInfo("MapHub", f"Layer '{new_layer.name()}' disconnected from MapHub.")
    
    def show_style_conflict_resolution_dialog(self, layer):
        """
        Show a dialog for resolving style conflicts when both local and remote styles have changed.
        
        Args:
            layer: The QGIS layer with style conflicts (MapHubPluginLayer or standard layer with custom properties)
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
            # Upload local style to MapHub (style only)
            if isinstance(layer, MapHubPluginLayer):
                map_id = layer.map_id()
            else:
                map_id = layer.customProperty("maphub/map_id")
            
            # Get the current layer position and add it to the style
            project = QgsProject.instance()
            position = layer_position(project, layer)
            
            # Update style with layer position
            style_json = self.get_layer_style_as_dict(layer)
            style_json['layer_order'] = position
            
            # Upload the style with layer position
            get_maphub_client().maps.set_visuals(map_id, style_json)
            
            # Store the current style hash for future comparison
            if 'qgis' in style_json:
                style_hash = normalize_style_xml_and_hash(style_json['qgis'])
                if isinstance(layer, MapHubPluginLayer):
                    layer.set_last_style_hash(style_hash)
                else:
                    layer.setCustomProperty("maphub/last_style_hash", style_hash)
            
            # Update metadata
            if isinstance(layer, MapHubPluginLayer):
                layer.set_last_sync(datetime.now().isoformat())
            else:
                layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                
            self.iface.messageBar().pushSuccess("MapHub", f"Style for layer '{layer.name()}' successfully uploaded to MapHub.")
        elif response == QMessageBox.Open:
            # Download remote style from MapHub (style only)
            if isinstance(layer, MapHubPluginLayer):
                map_id = layer.map_id()
            else:
                map_id = layer.customProperty("maphub/map_id")
            
            # Get map info to retrieve layer_order
            map_info = get_maphub_client().maps.get_map(map_id)['map']
            layer_order = map_info.get('visuals', {}).get('layer_order')
            
            if self._pull_and_apply_style(layer, map_id):
                # Place the layer at the correct position if layer_order exists
                if layer_order:
                    place_layer_at_position(QgsProject.instance(), layer, layer_order)
                
                # Update sync timestamp
                if isinstance(layer, MapHubPluginLayer):
                    layer.set_last_sync(datetime.now().isoformat())
                else:
                    layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                    
                self.iface.messageBar().pushSuccess("MapHub", f"Style for layer '{layer.name()}' successfully updated from MapHub.")
    
    def show_error(self, message, exception=None):
        """
        Show error message with option to see details.
        
        Args:
            message: The error message
            exception: The exception that caused the error (optional)
        """
        from .error_manager import ErrorManager
        ErrorManager.show_error(message, exception)
        
    def create_maphub_layer(self, map_id, folder_id, workspace_id, version_id=None, map_name=None):
        """
        Create a new MapHub plugin layer.
        
        Args:
            map_id: The MapHub map ID
            folder_id: The MapHub folder ID
            workspace_id: The MapHub workspace ID
            version_id: The MapHub version ID (optional)
            map_name: The name to give the layer (optional)
            
        Returns:
            The created MapHub plugin layer
        """
        # Create the layer
        layer = MapHubPluginLayer(map_id, folder_id, workspace_id, version_id)
        
        # Set the layer name if provided
        if map_name:
            layer.setName(map_name)
        
        # Add the layer to the project
        QgsProject.instance().addMapLayer(layer)
        
        return layer