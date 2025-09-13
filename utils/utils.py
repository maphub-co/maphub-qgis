import hashlib
from pathlib import Path
from typing import Dict, Any
from xml.etree import ElementTree as ET

from qgis.core import QgsMapLayer
from qgis.PyQt.QtCore import QSettings, QStandardPaths
from PyQt5.QtXml import QDomDocument

from ..maphub import MapHubClient


def get_maphub_client() -> MapHubClient:
    settings = QSettings()
    api_key = settings.value("MapHubPlugin/api_key", "")
    
    # Get custom base URL from settings, or use None as default
    base_url = settings.value("MapHubPlugin/base_url", None)

    if not api_key:
        raise Exception("Could not create MapHub client. API key is required.")

    params = {
        "api_key": api_key,
        "x_api_source": "qgis-plugin",
    }

    if base_url:
        params["base_url"] = base_url

    return MapHubClient(**params)


def get_default_download_location():
    """
    Get the default location for downloaded layers.
    
    Returns:
        Path: Path object pointing to the default download location
    """
    # First check if there's a user-defined location in settings
    settings = QSettings()
    default_location = settings.value("MapHubPlugin/default_download_location", "", type=str)
    
    if not default_location:
        # If no user setting, use Documents/MapHub as default
        documents_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        default_location = str(Path(documents_path) / "MapHub")
    
    # Ensure the directory exists
    Path(default_location).mkdir(parents=True, exist_ok=True)
    
    return Path(default_location)


def get_layer_styles_as_json(layer, visuals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieves layer styling information in both QGIS native style format and SLD
    format, storing the results in a given visuals dictionary. If the export of
    either style format fails, relevant error messages or null values are added to
    the visuals dictionary.

    :param layer: The QGIS layer object whose styling information is to be exported.
    :type layer: QgsMapLayer
    :param visuals: Dictionary storing the exported styling information and any
        associated errors.
    :type visuals: Dict[str, Any]
    :return: The updated visuals dictionary containing QGIS native style and SLD
        style (if export is successful) or their respective error details.
    :rtype: Dict[str, Any]
    :raises Exception: If exporting the QGIS native style fails.
    """
    # Get QGIS native style format
    qgis_doc = QDomDocument()
    error_message = []  # Use a list instead of a string for output parameter
    layer.exportNamedStyle(qgis_doc)
    
    # Filter out MapHub-specific properties before storing
    root = qgis_doc.documentElement()
    custom_props = root.elementsByTagName("customproperties").item(0)
    if not custom_props.isNull():
        options = custom_props.firstChildElement("Option")
        if not options.isNull():
            option_list = options.childNodes()
            for i in range(option_list.count() - 1, -1, -1):
                option = option_list.item(i).toElement()
                if option.attribute("name").startswith("maphub/"):
                    options.removeChild(option_list.item(i))
    
    # Store filtered QGIS style XML
    visuals["qgis"] = qgis_doc.toString()

    # Get SLD style format
    sld_doc = QDomDocument()
    layer.exportSldStyle(sld_doc, "")

    visuals["sld"] = sld_doc.toString()

    return visuals


def vector_style_to_tiling_style(style: str) -> str:
    """
    Convert a QGIS .qml style file from a local vector layer format to one compatible with vector tile layers.
    Removes unsupported sections and keeps only essential symbology.
    """
    # Parse the XML content
    root = ET.fromstring(style)

    # Create a new <qgis> root element for the vector tile format
    new_root = ET.Element('qgis', {
        'styleCategories': 'AllStyleCategories',
        'version': root.attrib.get('version', '3.34.4-Prizren'),
        'hasScaleBasedVisibilityFlag': '0',
        'maxScale': '0',
        'minScale': '100000000'
    })

    # Copy over the <renderer-v2> section (symbology) and convert it to a renderer section that is applyed to any geometry
    symbols = root.find('renderer-v2').find('symbols')
    if symbols is not None:
        renderer = ET.Element('renderer', {
            "type": "basic"
        })

        poly_style = ET.Element('style', {
            'min-zoom': '-1',
            'max-zoom': '-1',
            'name': 'Polygons',
            'enabled': '1',
            'expression': "geometry_type(@geometry)='Polygon'",
            'layer': '',
            'geometry': '2'
        })
        poly_style.append(symbols)

        line_style = ET.Element('style', {
            'min-zoom': '-1',
            'max-zoom': '-1',
            'name': 'Lines',
            'enabled': '1',
            'expression': "geometry_type(@geometry)='Line'",
            'layer': '',
            'geometry': '1'
        })
        line_style.append(symbols)

        point_style = ET.Element('style', {
            'min-zoom': '-1',
            'max-zoom': '-1',
            'name': 'Points',
            'enabled': '1',
            'expression': "geometry_type(@geometry)='Point'",
            'layer': '',
            'geometry': '0'
        })
        point_style.append(symbols)

        styles = ET.Element('styles')
        styles.extend([poly_style, line_style, point_style])
        renderer.append(styles)
        new_root.append(renderer)

    # Add <customproperties> if they exist
    custom_props = root.find('customproperties')
    if custom_props is not None:
        new_root.append(custom_props)

    # Add <blendMode> if it exists
    blend_mode = root.find('blendMode')
    if blend_mode is not None:
        new_root.append(blend_mode)

    # Return the result as a string
    return ET.tostring(new_root, encoding='unicode')


def apply_style_to_layer(layer, visuals: Dict[str, Any], tiling: bool = False):
    """
    Apply a specific style to a given map layer using a provided set of visuals.

    This function attempts to apply styling to a layer using the provided visual
    definitions. It gives priority to the QGIS native styling (if available and
    valid) for its greater compatibility and features. If applying the QGIS style
    fails or is unavailable, it falls back to the SLD (Styled Layer Descriptor)
    format for styling. The method also includes error handling to catch and
    report issues when applying styles.

    :param layer: The map layer to which the style should be applied. It must
                  be a valid `QgsMapLayer`.
    :param visuals: A dictionary containing visual styles with keys such as "qgis"
                    for QGIS native style (expected as XML string) and "sld" for
                    SLD styling (path/location or XML definition). Both keys are
                    optional, but at least one must be valid for the function to
                    succeed.
    :param tiling: Whether to convert the style to a format compatible with vector tile layers.

    :return: True if the style was successfully applied, False otherwise.
    :rtype: bool
    """
    # Check if we have a valid layer
    if not layer or not isinstance(layer, QgsMapLayer):
        print("Invalid layer provided to apply_style_to_layer")
        return False

    # Check if visuals dictionary is valid
    if not visuals or not isinstance(visuals, dict):
        print(f"Invalid visuals provided to apply_style_to_layer: {visuals}")
        return False

    # Try to apply QGIS native style first (most complete)
    if "qgis" in visuals and visuals["qgis"]:
        try:
            qgis_doc = QDomDocument()

            if tiling:
                qgis_style = vector_style_to_tiling_style(visuals["qgis"])
            else:
                qgis_style = visuals["qgis"]

            if not qgis_doc.setContent(qgis_style):
                print(f"Failed to parse QGIS style XML: Invalid XML format")
            else:
                success = layer.importNamedStyle(qgis_doc)

                if success:
                    layer.triggerRepaint()
                    return True
        except Exception as e:
            print(f"Error applying QGIS style: {str(e)}")

    # Fall back to SLD if QGIS style failed or isn't available
    if "sld" in visuals and visuals["sld"]:
        try:
            success = layer.loadSldStyle(visuals["sld"])

            if success:
                layer.triggerRepaint()
                return True
            else:
                print("Failed to apply SLD style: The SLD format may be incompatible with this layer type")
        except Exception as e:
            print(f"Error applying SLD style: {str(e)}")

    # If both methods failed, return False
    print(f"Failed to apply any style to layer '{layer.name()}'. Available style keys: {list(visuals.keys())}")
    return False


def layer_position(project, layer):
    """
    Extract the exact position of a layer within the project's layer tree.

    Args:
        project (QgsProject): The QGIS project instance
        layer (QgsMapLayer): The layer to find the position for

    Returns:
        list: A list of indices representing the path to the layer in the tree,
              where each index is the position within its parent group
    """
    # Get the layer tree root
    root = project.layerTreeRoot()

    # Find the layer node in the tree
    layer_node = root.findLayer(layer.id())

    if not layer_node:
        # Layer not found in the tree
        return []

    # Initialize the position list
    position = []

    # Start with the layer node
    current_node = layer_node

    # Traverse up the tree to build the position path
    while current_node and current_node.parent():
        # Get the parent node
        parent = current_node.parent()

        # Get the index of the current node within its parent's children
        index = parent.children().index(current_node)

        # Add the index to the beginning of our position list
        position.insert(0, index)

        # Move up to the parent
        current_node = parent

        # Stop if we've reached the root
        if current_node == root:
            break

    return position


def normalize_style_xml_and_hash(style_xml: str) -> str:
    """
    Normalize XML by extracting and sorting the renderer section,
    then generate an MD5 hash of the normalized XML.
    
    This function addresses the issue where QGIS may rearrange the order of keywords
    in tags when exporting styles, causing hash comparison failures even when styles
    are functionally equivalent.
    
    Args:
        style_xml (str): The XML string to normalize and hash
        
    Returns:
        str: MD5 hash of the normalized XML
    """
    if not style_xml:
        return ""
        
    try:
        # Remove the DOCTYPE declaration as it's not part of the functional style
        if '<!DOCTYPE' in style_xml:
            style_xml = style_xml[style_xml.find('<qgis'):]
        
        # Parse the XML
        root = ET.fromstring(style_xml)
        
        # Extract only the renderer section which contains the actual styling
        renderer = root.find('.//renderer-v2')
        if renderer is None:
            # If no renderer found, fall back to the original method
            return hashlib.md5(style_xml.encode()).hexdigest()
        
        def sort_element(elem):
            # Sort attributes
            attrib = dict(sorted(elem.attrib.items()))
            elem.attrib.clear()
            for key, value in sorted(attrib.items()):
                elem.set(key, value)
            
            # Sort children by tag and then recursively sort their content
            children = sorted(list(elem), key=lambda child: child.tag)
            for child in list(elem):
                elem.remove(child)
            for child in children:
                sort_element(child)
                elem.append(child)
        
        # Sort the renderer tree
        sort_element(renderer)
        
        # Convert back to string
        normalized_xml = ET.tostring(renderer, encoding='unicode')
        
        # Calculate and return the hash
        return hashlib.md5(normalized_xml.encode()).hexdigest()
    except Exception as e:
        print(f"Error normalizing XML: {str(e)}")
        # If normalization fails, fall back to direct hashing
        return hashlib.md5(style_xml.encode()).hexdigest()


def place_layer_at_position(project, layer, position):
    """
    Place a layer at a specific position in the project's layer tree.

    Args:
        project (QgsProject): The QGIS project instance
        layer (QgsMapLayer): The layer to place
        position (list): A list of indices representing the path to the layer in the tree,
                        where each index is the position within its parent group

    Returns:
        bool: True if the layer was successfully placed, False otherwise
    """
    if not position:
        # If no position is specified, add the layer to the root
        project.addMapLayer(layer)
        return True

    # Get the layer tree root
    root = project.layerTreeRoot()

    # Add the layer to the project without adding it to the layer tree
    project.addMapLayer(layer, False)

    # Start with the root node
    current_node = root

    # Traverse the tree to find the correct parent group
    for i, index in enumerate(position[:-1]):  # All but the last index
        # Get the children of the current node
        children = current_node.children()

        # Check if the index is valid
        if index >= len(children):
            # Index is out of range, add the layer to the current node
            current_node.addLayer(layer)
            return True

        # Get the child at the specified index
        child = children[index]

        # Check if the child is a group
        if not child.nodeType() == child.NodeGroup:
            # Child is not a group, add the layer to the current node
            current_node.addLayer(layer)
            return True

        # Move to the next level
        current_node = child

    # At this point, current_node is the parent group where the layer should be added
    # Get the last index from the position list
    last_index = position[-1]

    # Get the children of the current node
    children = current_node.children()

    # Check if the last index is valid
    if last_index >= len(children):
        # Last index is out of range, add the layer to the end of the current node
        current_node.addLayer(layer)
    else:
        # Insert the layer at the specified position
        current_node.insertLayer(last_index, layer)

    return True
