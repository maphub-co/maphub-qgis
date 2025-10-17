import hashlib
import os
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.core import QgsVectorFileWriter, QgsCoordinateTransformContext

from ..maphub.exceptions import APIException
from .utils import get_maphub_client, apply_style_to_layer, get_layer_styles_as_json, get_default_download_location, \
    normalize_style_xml_and_hash, layer_position, place_layer_at_position, get_maphub_download_location


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
        local_path = get_maphub_download_location(layer)
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
            layer: The QGIS layer
            map_id: The MapHub map ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        map_info = get_maphub_client().maps.get_map(map_id)['map']
        if 'visuals' not in map_info or not map_info['visuals']:
            return False

        layer_properties = {key: layer.customProperty(key) for key in layer.customProperties().keys()}
        print(layer_properties)
            
        apply_style_to_layer(layer, map_info['visuals'])

        # Transfer MapHub properties using the stored values
        for key, value in layer_properties.items():
            if key not in ["maphub/last_sync", "maphub/last_style_hash"]:
                layer.setCustomProperty(key, value)

        # Store the remote style hash for future comparison
        if 'qgis' in map_info['visuals']:
            # Use normalized XML for hash calculation to handle QGIS reordering elements
            style_hash = normalize_style_xml_and_hash(map_info['visuals']['qgis'])
            layer.setCustomProperty("maphub/last_style_hash", style_hash)

        print({key: layer.customProperty(key) for key in layer.customProperties().keys()})

        return True
    
    def synchronize_layer(self, layer, direction="auto", style_only=False):
        """
        Synchronize a layer with its MapHub counterpart.
        
        Args:
            layer: The QGIS layer
            direction: The synchronization direction:
                - "auto": Automatically determine direction based on status
                - "push": Upload local changes to MapHub
                - "pull": Download remote changes from MapHub
            style_only: If True, only synchronize the style, not the entire file
        
        Raises:
            Exception: If synchronization fails
        """
        if not layer.customProperty("maphub/map_id"):
            self.show_error("Layer is not connected to MapHub")
            return

        map_id = layer.customProperty("maphub/map_id")
        
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
            elif status == "file_missing":
                direction = "pull"
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
                        layer.setCustomProperty("maphub/last_style_hash", style_hash)
                    
                    # Update metadata
                    layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                    
                    self.iface.messageBar().pushSuccess("MapHub", f"Style for layer '{layer.name()}' successfully uploaded to MapHub.")
                else:
                    local_path = layer.source()
                    if '|' in local_path:  # Handle layers with query parameters
                        local_path = local_path.split('|')[0]
                    
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
                        layer.setCustomProperty("maphub/last_version_id", new_version_id)
                    
                    # Rename/move the file to reflect the new version
                    if new_version_id:
                        # Get default download location
                        default_dir = get_default_download_location()
                        
                        # Determine file extension
                        file_extension = os.path.splitext(local_path)[1]
                        if not file_extension:
                            # Determine default extension based on layer type
                            if isinstance(layer, QgsVectorLayer):
                                file_extension = '.fgb'  # Default to FlatGeobuf
                            elif isinstance(layer, QgsRasterLayer):
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
                    layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
                    
                    self.iface.messageBar().pushSuccess("MapHub", f"Layer '{layer.name()}' successfully uploaded to MapHub.")
                
            elif direction == "pull":
                # Check if only style has changed
                if style_only:
                    # Only download and apply the style, not the entire file
                    if self._pull_and_apply_style(layer, map_id):
                        # Update sync timestamp
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

            # Handle the layer based on its type and source
            if isinstance(layer, QgsVectorLayer):
                # For database layers (like PostGIS), export to file format

                # Always use FlatGeobuf as requested
                file_extension = '.fgb'
                temp_file = os.path.join(temp_dir, f"{map_name}{file_extension}")

                # Create a list of field indices to include (excluding problematic ones)
                fields = layer.fields()
                valid_indices = []
                skipped_fields = []

                for i in range(fields.count()):
                    field = fields.at(i)
                    # Check if the field is a QVariantList type or other problematic type
                    if "JSON" not in field.typeName():
                        valid_indices.append(i)
                        print(f"Including field {field.name()} with type {field.typeName()}")
                    else:
                        skipped_fields.append(field.name())
                        print(f"Skipping field {field.name()} with type {field.typeName()}")

                # Step 1: Export to GeoPackage first (with field filtering)
                options = QgsVectorFileWriter.SaveVectorOptions()
                options.driverName = "FlatGeobuf"
                options.layerName = layer.name()
                options.fileEncoding = "UTF-8"
                options.attributes = valid_indices  # Only include valid fields

                transform_context = QgsCoordinateTransformContext()

                error = QgsVectorFileWriter.writeAsVectorFormatV3(
                    layer,
                    temp_file,
                    transform_context,
                    options
                )

                if error[0] != QgsVectorFileWriter.NoError:
                    raise Exception(f"Error exporting filtered layer to FlatGeobuf: {error}")

                # Log which fields were skipped
                if skipped_fields:
                    skipped_fields_str = ', '.join(skipped_fields)
                    print(f"Skipped problematic fields: {skipped_fields_str}")
                    # Add a message to the QGIS message bar if interface is available
                    if self.iface:
                        self.iface.messageBar().pushWarning(
                            "MapHub",
                            f"Some fields were excluded during export due to compatibility issues: {skipped_fields_str}"
                        )

            elif  isinstance(layer, QgsRasterLayer):
                temp_file = os.path.join(temp_dir, f"{map_name}{file_extension}")

                # For file-based layers, copy the file
                with open(layer_path, 'rb') as src_file:
                    with open(temp_file, 'wb') as dst_file:
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
            version_id = result.get('id')

            # Update the layer visuals with the uploaded map style including layer position
            client.maps.set_visuals(map_id, style_json)

            # Connect the layer to the uploaded map
            if map_id:
                # Get default download location
                default_dir = get_default_download_location()

                # Create a permanent copy of the file in the default download location
                permanent_path = os.path.join(str(default_dir), f"{map_id}_{version_id}{file_extension}")

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

                # Create a new layer with the permanent path
                if isinstance(layer, QgsVectorLayer):
                    new_layer = QgsVectorLayer(permanent_path, layer.name(), "ogr")
                elif isinstance(layer, QgsRasterLayer):
                    new_layer = QgsRasterLayer(permanent_path, layer.name())

                style_dict = self.get_layer_style_as_dict(layer)
                apply_style_to_layer(new_layer, style_dict)

                if not new_layer or not new_layer.isValid():
                    raise Exception(f"Failed to create layer from {permanent_path}")

                # Transfer custom properties from the old layer to the new layer
                for key in layer.customProperties().keys():
                    new_layer.setCustomProperty(key, layer.customProperty(key))

                # Connect the new layer to MapHub
                self.connect_layer(
                    new_layer,
                    map_id,
                    folder_id,
                    permanent_path,
                    version_id
                )

                # Remove the old layer and add the new one
                QgsProject.instance().removeMapLayer(layer.id())

                # Place the new layer at the same position as the old one
                place_layer_at_position(project, new_layer, position)


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
            # Get folder_id from map_info if not already available
            folder_id = map_info.get('folder_id', '')
            
            self.connect_layer(
                layer,
                map_id,
                folder_id,
                path
            )
            
        # Apply the style from MapHub
        self._pull_and_apply_style(layer, map_id)

        
        return layer

    def connect_layer(self, layer, map_id, folder_id, local_path, version_id=None):
        """
        Connect a layer to a MapHub map.
        
        This method stores connection information in the layer's custom properties,
        establishing a link between the local QGIS layer and a remote MapHub map.
        
        Args:
            layer: The QGIS layer to connect
            map_id: The MapHub map ID
            folder_id: The MapHub folder ID
            local_path: The local file path
            version_id: Optional specific version to connect
            
        Returns:
            None
            
        Raises:
            ValueError: If any of the required parameters are invalid
        """
        # Store MapHub connection information in layer properties
        layer.setCustomProperty("maphub/map_id", str(map_id))
        layer.setCustomProperty("maphub/folder_id", str(folder_id))
        layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())

        if version_id:
            layer.setCustomProperty("maphub/last_version_id", str(version_id))
            print("Version set", layer.customProperty("maphub/last_version_id"))
        else:
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
            # Upload local style to MapHub (style only)
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
                layer.setCustomProperty("maphub/last_style_hash", style_hash)
            
            # Update metadata
            layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())
            self.iface.messageBar().pushSuccess("MapHub", f"Style for layer '{layer.name()}' successfully uploaded to MapHub.")
        elif response == QMessageBox.Open:
            # Download remote style from MapHub (style only)
            map_id = layer.customProperty("maphub/map_id")
            
            # Get map info to retrieve layer_order
            map_info = get_maphub_client().maps.get_map(map_id)['map']
            layer_order = map_info.get('visuals', {}).get('layer_order')
            
            if self._pull_and_apply_style(layer, map_id):
                # Place the layer at the correct position if layer_order exists
                if layer_order:
                    place_layer_at_position(QgsProject.instance(), layer, layer_order)
                
                # Update sync timestamp
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