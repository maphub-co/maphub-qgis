import os
from typing import List, Dict, Any, Optional, Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, 
                            QCheckBox, QLabel, QSpacerItem, QSizePolicy)
from qgis.core import QgsProject, QgsMapLayer
from qgis.utils import iface

class LayerSelectionWidget(QWidget):
    """
    A widget that displays the currently open layers with checkboxes and 
    provides a function to access the selected layers.

    Signals:
        layers_selection_changed: Emitted when the selection of layers changes
    """

    layers_selection_changed = pyqtSignal()

    def __init__(self, parent=None, validation_func=None):
        super(LayerSelectionWidget, self).__init__(parent)

        # Initialize state
        self.selected_layers = {}  # Dictionary to store selected layers {layer_id: layer}
        self.validation_func = validation_func  # Function to validate if a layer should be selectable

        # Set widget styling
        self.setObjectName("layerSelectionWidget")

        # Set up UI
        self.setup_ui()

        # Load current layers
        self.refresh_layers()

        # Connect to the layersAdded and layersRemoved signals to update when layers change
        QgsProject.instance().layersAdded.connect(self.refresh_layers)
        QgsProject.instance().layersRemoved.connect(self.refresh_layers)

    def setup_ui(self):
        """Set up the widget UI"""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(5)

        # Header
        header_label = QLabel("Available Layers")
        header_label.setObjectName("headerLabel")
        self.main_layout.addWidget(header_label)

        # Frame for layers
        self.layers_frame = QFrame()
        self.layers_frame.setObjectName("layersFrame")
        self.layers_frame.setFrameShape(QFrame.StyledPanel)
        self.layers_frame.setFrameShadow(QFrame.Raised)

        # Layout for layers
        self.layers_layout = QVBoxLayout(self.layers_frame)
        self.layers_layout.setContentsMargins(5, 5, 5, 5)
        self.layers_layout.setSpacing(5)

        self.main_layout.addWidget(self.layers_frame)

        # Add spacer at the bottom
        self.main_layout.addItem(QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def refresh_layers(self):
        """Refresh the list of layers"""
        # Clear existing layer checkboxes
        for i in reversed(range(self.layers_layout.count())):
            widget = self.layers_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        # Get all layers from the project
        layers = QgsProject.instance().mapLayers().values()

        # Create a checkbox for each layer
        for layer in layers:
            self.add_layer_checkbox(layer)

        # Emit signal that selection might have changed
        self.layers_selection_changed.emit()

    def add_layer_checkbox(self, layer):
        """Add a checkbox for a layer"""
        # Create a frame for the layer item
        item_frame = QFrame()
        item_frame.setObjectName(f"layerItem_{layer.id()}")

        # Create layout for the item
        item_layout = QHBoxLayout(item_frame)
        item_layout.setContentsMargins(5, 5, 5, 5)
        item_layout.setSpacing(5)

        # Create checkbox
        checkbox = QCheckBox(layer.name())
        checkbox.setObjectName(f"layerCheckbox_{layer.id()}")

        # Store layer ID as property
        checkbox.setProperty("layer_id", layer.id())

        # Connect checkbox state change
        checkbox.stateChanged.connect(lambda state, lid=layer.id(): self.on_checkbox_state_changed(state, lid))

        # Add to layout
        item_layout.addWidget(checkbox)

        # Validate the layer if a validation function is provided
        if self.validation_func:
            try:
                # Call the validation function
                is_valid = self.validation_func(layer)
            except Exception as e:
                # If validation raises an exception, disable the checkbox and store the error message
                is_valid = False
                error_message = str(e)

                if error_message:
                    error_label = QLabel(f"{error_message}")
                    error_label.setStyleSheet("color: orange; font-size: 10px;")
                    error_label.setWordWrap(True)
                    item_layout.addWidget(error_label)

            # Enable/disable checkbox based on validation result
            checkbox.setEnabled(is_valid)

            # If not valid, add a disabled style
            if not is_valid:
                checkbox.setStyleSheet("color: gray;")
                # If there's an error message, add a label to display it


        # Add to layers layout
        self.layers_layout.addWidget(item_frame)

    def on_checkbox_state_changed(self, state, layer_id):
        """Handle checkbox state change"""
        layer = QgsProject.instance().mapLayer(layer_id)

        if state == Qt.Checked:
            # Add to selected layers
            self.selected_layers[layer_id] = layer
        else:
            # Remove from selected layers
            if layer_id in self.selected_layers:
                del self.selected_layers[layer_id]

        # Emit signal that selection has changed
        self.layers_selection_changed.emit()

    def get_selected_layers(self) -> List[QgsMapLayer]:
        """
        Get the list of selected layers

        Returns:
            List[QgsMapLayer]: List of selected layers
        """
        return list(self.selected_layers.values())

    def select_all_layers(self):
        """Select all layers that are enabled"""
        for i in range(self.layers_layout.count()):
            widget = self.layers_layout.itemAt(i).widget()
            if widget is not None:
                for child in widget.children():
                    if isinstance(child, QCheckBox) and child.isEnabled():
                        child.setChecked(True)

    def deselect_all_layers(self):
        """Deselect all layers"""
        for i in range(self.layers_layout.count()):
            widget = self.layers_layout.itemAt(i).widget()
            if widget is not None:
                for child in widget.children():
                    if isinstance(child, QCheckBox):
                        child.setChecked(False)
