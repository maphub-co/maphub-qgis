import os
from typing import Dict, Any, Optional, Tuple

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QProgressBar, QLabel, QVBoxLayout, QDialog, QApplication
from qgis.core import QgsProject, QgsVectorTileLayer, QgsRasterLayer
from qgis.utils import iface

# from .. import utils
from .utils import get_maphub_client, apply_style_to_layer, place_layer_at_position


def download_map(map_data: Dict[str, Any], parent=None, selected_format: str = None) -> Optional[str]:
    """
    Download a map and add it to the QGIS project.

    Args:
        map_data (Dict[str, Any]): The map data
        parent: The parent widget for dialogs
        selected_format (str, optional): The format to download the map in. If None, the user will be prompted.

    Returns:
        Optional[str]: The path to the downloaded file, or None if the download was cancelled
    """
    print(f"Downloading map: {map_data.get('name')}")

    # If format not specified, determine based on map type
    if not selected_format:
        if map_data.get('type') == 'raster':
            selected_format = "tif"
        elif map_data.get('type') == 'vector':
            selected_format = "gpkg"  # Default to GeoPackage for vector

    # Determine file extension and filter based on selected format
    file_extension = f".{selected_format}"

    # Create filter string based on selected format
    if selected_format == "tif":
        filter_string = "GeoTIFF (*.tif);;All Files (*)"
    elif selected_format == "fgb":
        filter_string = "FlatGeobuf (*.fgb);;All Files (*)"
    elif selected_format == "shp":
        filter_string = "Shapefile (*.shp);;All Files (*)"
    elif selected_format == "gpkg":
        filter_string = "GeoPackage (*.gpkg);;All Files (*)"
    else:
        filter_string = "All Files (*)"

    file_path, _ = QFileDialog.getSaveFileName(
        parent,
        "Save Map",
        f"{map_data.get('name', 'map')}{file_extension}",
        filter_string
    )

    # If user cancels the dialog, return early
    if not file_path:
        return None

    # Download the map with the selected format
    get_maphub_client().maps.download_map(map_data['id'], file_path, selected_format)

    # Adding downloaded file to layers
    if not os.path.exists(file_path):
        raise Exception(f"Downloaded file not found at {file_path}")

    if map_data.get('type') == 'raster':
        layer = iface.addRasterLayer(file_path, map_data.get('name', os.path.basename(file_path)))
    elif map_data.get('type') == 'vector':
        layer = iface.addVectorLayer(file_path, map_data.get('name', os.path.basename(file_path)), "ogr")
    else:
        raise Exception(f"Unknown layer type: {map_data['type']}")

    if not layer.isValid():
        raise Exception(f"The downloaded map could not be added as a layer. Please check the file: {file_path}")
    else:
        # Apply style if available
        if 'visuals' in map_data and map_data['visuals']:
            visuals = map_data['visuals']
            apply_style_to_layer(layer, visuals)

        QMessageBox.information(
            parent,
            "Download Complete",
            f"Map '{map_data.get('name')}' has been downloaded and added to your layers."
        )

    return file_path


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
        return (0, 0)

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

    return (success_count, len(maps))


def download_folder_maps(folder_id: str, parent=None, format_type: str = None) -> Tuple[int, int]:
    """
    Download all maps in a folder and add them to the QGIS project.

    Args:
        folder_id (str): The ID of the folder
        parent: The parent widget for dialogs
        format_type (str, optional): The format to download the maps in. If None, the default format will be used.

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
        return (0, 0)

    # Ask for directory to save maps
    directory = QFileDialog.getExistingDirectory(
        parent,
        "Select Directory to Save Maps",
        "",
        QFileDialog.ShowDirsOnly
    )

    if not directory:
        return (0, 0)  # User cancelled

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
                    selected_format = "gpkg"  # Default to GeoPackage for vector

            # Create file path
            file_name = f"{map_data.get('name', f'map_{map_data.get('id')}')}.{selected_format}"
            file_path = os.path.join(directory, file_name)

            # Download the map
            client.maps.download_map(map_data['id'], file_path, selected_format)

            # Add to QGIS project
            if os.path.exists(file_path):
                if map_data.get('type') == 'raster':
                    layer = iface.addRasterLayer(file_path, map_data.get('name', os.path.basename(file_path)))
                elif map_data.get('type') == 'vector':
                    layer = iface.addVectorLayer(file_path, map_data.get('name', os.path.basename(file_path)), "ogr")

                if layer and layer.isValid():
                    place_layer_at_position(project, layer, map_data.get('visuals', {}).get('layer_order'))
                    if 'visuals' in map_data and map_data['visuals']:
                        apply_style_to_layer(layer, map_data['visuals'])
                    success_count += 1

            # Update progress
            progress.setValue(i + 1)
            QApplication.processEvents()

        except Exception as e:
            errors.append(f"Error for map {map_data.get('name')} ({map_data.get('id')}): {e}")

    # Close progress dialog
    progress_dialog.close()

    # Show completion message
    message = f"Successfully downloaded {success_count} out of {len(maps)} maps."
    if errors:
        message += "\n\nErrors:\n" + "\n".join(errors)
    QMessageBox.information(
        parent,
        "Maps Downloaded",
        message
    )

    return (success_count, len(maps))
