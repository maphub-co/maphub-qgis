import hashlib
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QProgressBar, QLabel, QVBoxLayout, QDialog, QApplication
from qgis._core import QgsVectorLayer
from qgis.core import QgsProject, QgsVectorTileLayer, QgsRasterLayer
from qgis.utils import iface

# from .. import utils
from .utils import get_maphub_client, apply_style_to_layer, place_layer_at_position, get_default_download_location, layer_position
from .sync_manager import MapHubSyncManager
from .project_utils import load_maphub_project


def download_map(map_data: Dict[str, Any], parent=None, selected_format: str = None) -> Optional[str]:
    """
    Download a map to the default download location and add it to the QGIS project.
    
    Args:
        map_data (Dict[str, Any]): The map data
        parent: The parent widget for dialogs
        selected_format (str, optional): The format to download the map in. If None, a default format will be selected based on the map type.
    
    Returns:
        Optional[str]: The path to the downloaded file
    """
    print(f"Downloading map: {map_data.get('name')}")

    # Use the centralized download function from MapHubSyncManager
    from .sync_manager import MapHubSyncManager
    sync_manager = MapHubSyncManager(iface)
    
    layer = sync_manager.download_map(
        map_id=map_data['id'],
        file_format=selected_format,
        layer_name=map_data.get('name'),
        connect_layer=False  # Ensure the layer is connected
    )
    
    # Return the path to the downloaded file
    return layer.source() if layer else None


def add_map_as_tiling_service(map_data: Dict[str, Any], parent=None) -> bool:
    """
    Add a map as a tiling service to the QGIS project.

    Args:
        map_data (Dict[str, Any]): The map data
        parent: The parent widget for dialogs

    Returns:
        bool: True if the map was successfully added as a tiling service, False otherwise
    """
    print(f"Adding tiling service for map: {map_data.get('name')}")

    layer_info = get_maphub_client().maps.get_layer_info(map_data['id'])
    tiler_url = layer_info['tiling_url']
    layer_name = map_data.get('name', f"Tiled Map {map_data['id']}")

    # Add layer based on map type
    if map_data.get('type') == 'vector':
        # Add as vector tile layer
        vector_tile_layer_string = f"type=xyz&url={tiler_url}&zmin={layer_info.get('min_zoom', 0)}&zmax={layer_info.get('max_zoom', 15)}"
        vector_layer = QgsVectorTileLayer(vector_tile_layer_string, layer_name)
        if vector_layer.isValid():
            QgsProject.instance().addMapLayer(vector_layer)
            if 'visuals' in map_data and map_data['visuals']:
                apply_style_to_layer(vector_layer, map_data['visuals'], tiling=True)
            iface.messageBar().pushSuccess("Success", f"Vector tile layer '{layer_name}' added.")
            return True
        else:
            iface.messageBar().pushWarning("Warning", f"Could not add vector tile layer from URL: {tiler_url}")
            return False
    elif map_data.get('type') == 'raster':
        # Add as raster tile layer
        uri = f"type=xyz&url={tiler_url.replace('&', '%26')}"
        raster_layer = QgsRasterLayer(uri, layer_name, "wms")
        if raster_layer.isValid():
            QgsProject.instance().addMapLayer(raster_layer)
            if 'visuals' in map_data and map_data['visuals']:
                apply_style_to_layer(raster_layer, map_data['visuals'])
            iface.messageBar().pushSuccess("Success", f"XYZ tile layer '{layer_name}' added.")
            return True
        else:
            iface.messageBar().pushWarning("Warning", f"Could not add XYZ tile layer from URL: {tiler_url}")
            return False
    else:
        raise Exception(f"Unknown layer type: {map_data['type']}")


def add_folder_maps_as_tiling_services(folder_id: str, parent=None) -> Tuple[int, int]:
    """
    Add all maps in a folder as tiling services to the QGIS project.

    Args:
        folder_id (str): The ID of the folder
        parent: The parent widget for dialogs

    Returns:
        Tuple[int, int]: A tuple of (success_count, total_count)
    """
    print(f"Adding all maps in folder {folder_id} as tiling services")

    # Get all maps in the folder
    client = get_maphub_client()
    maps = client.folder.get_folder_maps(folder_id)

    if not maps:
        QMessageBox.information(
            parent,
            "No Maps Found",
            "There are no maps in this folder to add as tiling services."
        )
        return 0, 0

    # Create progress dialog
    progress_dialog = QDialog(parent)
    progress_dialog.setWindowTitle("Adding Tiling Services")
    progress_dialog.setMinimumWidth(300)

    layout = QVBoxLayout(progress_dialog)
    layout.addWidget(QLabel("Adding maps as tiling services..."))

    progress = QProgressBar()
    progress.setMinimum(0)
    progress.setMaximum(len(maps))
    progress.setValue(0)
    layout.addWidget(progress)

    progress_dialog.show()

    # Sort maps based on order in visuals if available
    def get_order(map_data: dict):
        return map_data.get('visuals', {}).get('layer_order', (float('inf'),))
    maps.sort(key=get_order)

    # Add each map as a tiling service
    success_count = 0
    errors = []
    project = QgsProject.instance()
    for i, map_data in enumerate(maps):
        try:
            # Get layer info
            layer_info = client.maps.get_layer_info(map_data['id'])
            tiler_url = layer_info['tiling_url']
            layer_name = map_data.get('name', f"Tiled Map {map_data['id']}")

            # Add layer based on map type
            if map_data.get('type') == 'vector':
                # Add as vector tile layer
                vector_tile_layer_string = f"type=xyz&url={tiler_url}&zmin={layer_info.get('min_zoom', 0)}&zmax={layer_info.get('max_zoom', 15)}"
                vector_layer = QgsVectorTileLayer(vector_tile_layer_string, layer_name)
                if vector_layer.isValid():
                    place_layer_at_position(project, vector_layer, map_data.get('visuals', {}).get('layer_order'))
                    if 'visuals' in map_data and map_data['visuals']:
                        apply_style_to_layer(vector_layer, map_data['visuals'], tiling=True)
                    success_count += 1
            elif map_data.get('type') == 'raster':
                uri = f"type=xyz&url={tiler_url.replace('&', '%26')}"
                raster_layer = QgsRasterLayer(uri, layer_name, "wms")
                if raster_layer.isValid():
                    place_layer_at_position(project, raster_layer, map_data.get('visuals', {}).get('layer_order'))
                    if 'visuals' in map_data and map_data['visuals']:
                        apply_style_to_layer(raster_layer, map_data['visuals'])
                    success_count += 1

            # Update progress
            progress.setValue(i + 1)
            QApplication.processEvents()

        except Exception as e:
            errors.append(f"Error for map {map_data.get('name')} ({map_data.get('id')}): {e}")

    # Close progress dialog
    progress_dialog.close()

    # Show completion message
    message = f"Successfully added {success_count} out of {len(maps)} maps as tiling services."
    if errors:
        message += "\n\nErrors:\n" + "\n".join(errors)
    QMessageBox.information(
        parent,
        "Tiling Services Added",
        message
    )

    return success_count, len(maps)


def download_folder_maps(folder_id: str, parent=None, format_type: str = None) -> Tuple[int, int]:
    """
    Download all maps in a folder to the default download location and add them to the QGIS project.
    Shows a progress dialog during download and only displays a message if errors occur.

    Args:
        folder_id (str): The ID of the folder
        parent: The parent widget for dialogs
        format_type (str, optional): The format to download the maps in. If None, the default format will be used based on map type.

    Returns:
        Tuple[int, int]: A tuple of (success_count, total_count)
    """
    print(f"Downloading all maps in folder {folder_id}")

    # Get all maps in the folder
    client = get_maphub_client()
    maps = client.folder.get_folder_maps(folder_id)

    if not maps:
        QMessageBox.information(
            parent,
            "No Maps Found",
            "There are no maps in this folder to download."
        )
        return 0, 0

    # Use default download location
    directory = str(get_default_download_location())

    # Create progress dialog
    progress_dialog = QDialog(parent)
    progress_dialog.setWindowTitle("Downloading Maps")
    progress_dialog.setMinimumWidth(300)

    layout = QVBoxLayout(progress_dialog)
    layout.addWidget(QLabel("Downloading maps..."))

    progress = QProgressBar()
    progress.setMinimum(0)
    progress.setMaximum(len(maps))
    progress.setValue(0)
    layout.addWidget(progress)

    progress_dialog.show()

    # Sort maps based on order in visuals if available
    def get_order(map_data: dict):
        return map_data.get('visuals', {}).get('layer_order', (float('inf'),))
    maps.sort(key=get_order)

    # Download each map
    success_count = 0
    errors = []
    project = QgsProject.instance()
    for i, map_data in enumerate(maps):
        try:
            # Determine format based on map type if not specified
            selected_format = format_type
            if not selected_format:
                if map_data.get('type') == 'raster':
                    selected_format = "tif"
                elif map_data.get('type') == 'vector':
                    selected_format = "fgb"  # Default to FlatGeobuf for vector

            # Create file path
            map_id = map_data.get('id')
            file_name = f"{map_data.get('name', f'map_{map_id}')}.{selected_format}"
            file_path = os.path.join(directory, file_name)
            
            # Fetch complete map data including visuals if not already present
            if 'visuals' not in map_data:
                try:
                    complete_map_info = client.maps.get_map(map_id)
                    if 'map' in complete_map_info and 'visuals' in complete_map_info['map']:
                        map_data['visuals'] = complete_map_info['map']['visuals']
                except Exception as e:
                    print(f"Error fetching map visuals: {str(e)}")

            # Use the centralized download function from MapHubSyncManager
            sync_manager = MapHubSyncManager(iface)
            
            # Download the map
            layer = sync_manager.download_map(
                map_id=map_data['id'],
                file_format=selected_format,
                layer_name=map_data.get('name'),
                connect_layer=False  # Ensure the layer is connected
            )

            if layer and layer.isValid():
                place_layer_at_position(project, layer, map_data.get('visuals', {}).get('layer_order'))
                success_count += 1

            # Update progress
            progress.setValue(i + 1)
            QApplication.processEvents()

        except Exception as e:
            errors.append(f"Error for map {map_data.get('name')} ({map_data.get('id')}): {e}")

    # Close progress dialog
    progress_dialog.close()

    # Log errors to console if any occurred
    if errors:
        error_message = f"Errors occurred while downloading maps:\n" + "\n".join(errors)
        print(error_message)
        # Show only error messages in a dialog
        QMessageBox.warning(
            parent,
            "Download Errors",
            error_message
        )

    return success_count, len(maps)


def load_and_sync_folder(folder_id: str, iface, parent=None) -> None:
    """
    Load a QGIS project from MapHub and synchronize all connected layers.
    
    This function first loads the QGIS project associated with the folder,
    then synchronizes all layers that are connected to MapHub.
    
    Args:
        folder_id (str): The ID of the folder containing the project
        parent: The parent widget for dialogs
    """
    # Load the QGIS project from MapHub
    try:
        load_maphub_project(folder_id)
    except Exception as e:
        iface.messageBar().pushSuccess("MapHub", f"Folder has no associated project. Downloading maps of folder instead.")

        download_folder_maps(folder_id)
        return
    
    # Create a progress dialog
    progress_dialog = QDialog(parent)
    progress_dialog.setWindowTitle("Synchronizing Layers")
    progress_dialog.setMinimumWidth(300)
    
    layout = QVBoxLayout(progress_dialog)
    layout.addWidget(QLabel("Synchronizing connected layers..."))
    
    # Get all connected layers
    sync_manager = MapHubSyncManager(iface)
    connected_layers = sync_manager.get_connected_layers()
    
    if not connected_layers:
        progress_dialog.close()
        QMessageBox.information(
            parent,
            "Synchronization Complete",
            "Project loaded successfully. No connected layers found to synchronize."
        )
        return
    
    # Set up progress bar
    progress = QProgressBar()
    progress.setMinimum(0)
    progress.setMaximum(len(connected_layers))
    progress.setValue(0)
    layout.addWidget(progress)
    
    progress_dialog.show()
    
    # Synchronize each connected layer
    success_count = 0
    errors = []
    
    for i, layer in enumerate(connected_layers):
        try:
            fix_missing_data_maphub_layer(layer)
            success_count += 1
        except Exception as e:
            errors.append(f"Error synchronizing layer {layer.name()}: {str(e)}")
        
        # Update progress
        progress.setValue(i + 1)
        QApplication.processEvents()
    
    # Close progress dialog
    progress_dialog.close()
    
    # Show results
    if errors:
        error_message = f"Project loaded successfully, but errors occurred while synchronizing layers:\n" + "\n".join(errors)
        QMessageBox.warning(
            parent,
            "Synchronization Errors",
            error_message
        )
    else:
        QMessageBox.information(
            parent,
            "Synchronization Complete",
            f"Project loaded successfully. {success_count} layers synchronized."
        )


def fix_missing_data_maphub_layer(layer):
    sync_manager = MapHubSyncManager(iface)
    status = sync_manager.get_layer_sync_status(layer)

    if status != "file_missing":
        return

    map_id = layer.customProperty("maphub/map_id")

    # Get map info to retrieve the latest version ID
    map_info = get_maphub_client().maps.get_map(map_id)['map']
    version_id = map_info.get('latest_version_id')

    # Get default download location
    default_dir = get_default_download_location()

    # Determine file extension based on layer type
    if isinstance(layer, QgsVectorLayer):
        file_extension = '.fgb'  # Default to FlatGeobuf
    elif isinstance(layer, QgsRasterLayer):
        file_extension = '.tif'  # Default to GeoTIFF
    else:
        file_extension = '.fgb'  # Default fallback

    # Create new file path with map_id and version_id
    new_path = os.path.join(str(default_dir), f"{map_id}_{version_id}{file_extension}")

    # Download the file
    if not os.path.exists(new_path):
        get_maphub_client().versions.download_version(version_id, new_path, file_extension.replace('.', ''))

    # Store the layer name and custom properties
    layer_name = layer.name()
    layer_properties = {key: layer.customProperty(key) for key in layer.customProperties().keys()}

    # Get layer position for later placement
    project = QgsProject.instance()
    layer_pos = layer_position(project, layer)

    # Create a new layer with the downloaded file but don't add it to the project yet
    if isinstance(layer, QgsVectorLayer):
        new_layer = QgsVectorLayer(new_path, layer_name, "ogr")
    elif isinstance(layer, QgsRasterLayer):
        new_layer = QgsRasterLayer(new_path, layer_name)
    else:
        sync_manager.show_error(f"Unsupported layer type for '{layer_name}'")
        return

    if not new_layer or not new_layer.isValid():
        sync_manager.show_error(f"Failed to create layer from {new_path}")
        return

    # Transfer custom properties to the new layer
    for key, value in layer_properties.items():
        if key != "maphub/local_path":  # Update local_path with the new path
            new_layer.setCustomProperty(key, value)

    # Update the new layer's properties
    new_layer.setCustomProperty("maphub/local_path", new_path)
    new_layer.setCustomProperty("maphub/last_version_id", version_id)
    # new_layer.setCustomProperty("maphub/last_sync", datetime.now().isoformat())

    # Apply the style from MapHub
    sync_manager._pull_and_apply_style(new_layer, map_id)

    # Remove the old layer
    QgsProject.instance().removeMapLayer(layer.id())
    
    # Add the new layer to the project at the same position as the old layer
    place_layer_at_position(project, new_layer, layer_pos)

    iface.messageBar().pushSuccess("MapHub", f"Missing file for layer '{layer_name}' successfully downloaded from MapHub.")
    return