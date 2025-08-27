from PyQt5.QtWidgets import QMenu, QAction, QMessageBox
from PyQt5.QtCore import Qt

from .sync_manager import MapHubSyncManager
from ..ui.dialogs.ConfirmSyncDialog import ConfirmSyncDialog


class MapHubLayerMenuProvider:
    """
    Provides MapHub-specific context menu actions for QGIS layers.
    
    This class adds synchronization actions to the context menu of layers
    that are connected to MapHub. It extends the existing QGIS layer context menu
    rather than replacing it, ensuring that all default QGIS actions remain available
    alongside the MapHub-specific actions.
    """
    
    def __init__(self, iface, sync_manager=None):
        """
        Initialize the menu provider.
        
        Args:
            iface: The QGIS interface
            sync_manager: The MapHub synchronization manager (optional)
        """
        self.iface = iface
        self.sync_manager = sync_manager or MapHubSyncManager(iface)
        self.setup()
        
    def setup(self):
        """
        Set up the context menu integration.
        
        This method connects to the appropriate signal for context menu integration
        based on the QGIS version:
        - For newer QGIS versions (3.34+): Uses contextMenuAboutToShow signal
        - For older QGIS versions (3.28 and earlier): Uses customContextMenuRequested signal
        
        This ensures compatibility across different QGIS versions.
        """
        # Check if layerTreeView exists
        if hasattr(self.iface, 'layerTreeView'):
            layer_tree_view = self.iface.layerTreeView()
            
            # Check if contextMenuAboutToShow signal exists (QGIS 3.34+)
            if hasattr(layer_tree_view, 'contextMenuAboutToShow'):
                # For newer QGIS versions (3.34+)
                layer_tree_view.contextMenuAboutToShow.connect(self.extend_context_menu)
            else:
                # For older QGIS versions (3.28 and earlier)
                layer_tree_view.customContextMenuRequested.connect(self.show_context_menu)
            
    def extend_context_menu(self, menu):
        """
        Extend the existing context menu with MapHub-specific actions.
        
        Args:
            menu: The existing context menu to extend
        """
        # Get selected layers
        selected = self.iface.layerTreeView().selectedLayers()
        if not selected:
            return
            
        # Check if any selected layers are MapHub layers
        maphub_layers = [layer for layer in selected if layer.customProperty("maphub/map_id")]
        if not maphub_layers:
            return
            
        # Add a separator before MapHub actions
        menu.addSeparator()
        
        # Add MapHub actions to the menu
        self.add_maphub_actions_to_menu(menu, maphub_layers)
            
    # Keep the show_context_menu method for backward compatibility
    def show_context_menu(self, position):
        """
        Legacy method for showing the context menu. This is kept for backward compatibility.
        The preferred approach is to use the extend_context_menu method.
        
        This method creates a new menu and replaces the default QGIS context menu,
        which means that default QGIS actions are not available. It is maintained
        for backward compatibility but should not be used in new code.
        
        Args:
            position: The position where the context menu was requested
        """
        # Get selected layers
        selected = self.iface.layerTreeView().selectedLayers()
        if not selected:
            return
            
        # Check if any selected layers are MapHub layers
        maphub_layers = [layer for layer in selected if layer.customProperty("maphub/map_id")]
        if not maphub_layers:
            return
            
        # Create menu
        menu = QMenu()
        
        # Add MapHub actions to the menu
        self.add_maphub_actions_to_menu(menu, maphub_layers)
            
        # Show menu
        menu.exec_(self.iface.layerTreeView().viewport().mapToGlobal(position))
        
    def add_maphub_actions_to_menu(self, menu, maphub_layers):
        """
        Add MapHub-specific actions to a menu.
        
        Args:
            menu: The menu to add actions to
            maphub_layers: List of MapHub layers
        """
        if len(maphub_layers) == 1:
            # Single layer options
            layer = maphub_layers[0]
            
            # Check status on demand
            status = self.sync_manager.get_layer_sync_status(layer)
            
            # Add appropriate actions based on status
            if status == "local_modified":
                update_remote_action = QAction("Upload to MapHub", menu)
                update_remote_action.triggered.connect(lambda: self.confirm_sync_action(layer, "Upload local changes to MapHub", "push"))
                menu.addAction(update_remote_action)
            elif status == "remote_newer":
                update_local_action = QAction("Update from MapHub", menu)
                update_local_action.triggered.connect(lambda: self.confirm_sync_action(layer, "Download remote changes from MapHub", "pull"))
                menu.addAction(update_local_action)
            elif status == "style_changed":
                resolve_style_action = QAction("Resolve Style Differences", menu)
                resolve_style_action.triggered.connect(lambda: self.show_style_resolution_dialog(layer))
                menu.addAction(resolve_style_action)
                
            # Always add these options
            sync_action = QAction("Synchronize with MapHub", menu)
            sync_action.triggered.connect(lambda: self.confirm_sync_action(layer, "Synchronize with MapHub", "auto"))
            menu.addAction(sync_action)
            
            disconnect_action = QAction("Disconnect from MapHub", menu)
            disconnect_action.triggered.connect(lambda: self.disconnect_layer(layer))
            menu.addAction(disconnect_action)
        else:
            # Multiple layer options
            sync_all_action = QAction(f"Synchronize {len(maphub_layers)} Layers with MapHub", menu)
            sync_all_action.triggered.connect(lambda: self.sync_multiple_layers(maphub_layers))
            menu.addAction(sync_all_action)
            
            disconnect_all_action = QAction(f"Disconnect {len(maphub_layers)} Layers from MapHub", menu)
            disconnect_all_action.triggered.connect(lambda: self.disconnect_multiple_layers(maphub_layers))
            menu.addAction(disconnect_all_action)
        
    def show_style_resolution_dialog(self, layer):
        """
        Show a dialog for resolving style conflicts.
        
        Args:
            layer: The QGIS layer
        """
        # For now, just use push direction for style changes
        # In the future, this would show a style conflict resolution dialog
        response = QMessageBox.question(
            self.iface.mainWindow(),
            "Style Conflict",
            f"The layer '{layer.name()}' has style differences between local and remote versions.\n\n"
            "How would you like to resolve this conflict?",
            QMessageBox.Save | QMessageBox.Open | QMessageBox.Cancel,
            QMessageBox.Cancel
        )
        
        if response == QMessageBox.Save:
            # Upload local style to MapHub
            self.sync_manager.synchronize_layer(layer, "push")
        elif response == QMessageBox.Open:
            # Download remote style from MapHub
            self.sync_manager.synchronize_layer(layer, "pull")
            
    def disconnect_layer(self, layer):
        """
        Disconnect a layer from MapHub.
        
        Args:
            layer: The QGIS layer
        """
        # Confirm disconnection
        response = QMessageBox.question(
            self.iface.mainWindow(),
            "Disconnect Layer",
            f"Are you sure you want to disconnect layer '{layer.name()}' from MapHub?\n\n"
            "This will not delete the layer or the file, but will remove the connection information.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if response == QMessageBox.Yes:
            # Disconnect the layer
            self.sync_manager.disconnect_layer(layer)
            
    def sync_multiple_layers(self, layers):
        """
        Synchronize multiple layers with MapHub.
        
        Args:
            layers: List of QGIS layers
        """
        for layer in layers:
            self.sync_manager.synchronize_layer(layer)
            
    def disconnect_multiple_layers(self, layers):
        """
        Disconnect multiple layers from MapHub.
        
        Args:
            layers: List of QGIS layers
        """
        # Confirm disconnection
        response = QMessageBox.question(
            self.iface.mainWindow(),
            "Disconnect Layers",
            f"Are you sure you want to disconnect {len(layers)} layers from MapHub?\n\n"
            "This will not delete the layers or files, but will remove the connection information.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if response == QMessageBox.Yes:
            # Disconnect the layers
            for layer in layers:
                self.sync_manager.disconnect_layer(layer)
                
    def confirm_sync_action(self, layer, action_description, direction):
        """
        Show confirmation dialog and perform synchronization if confirmed.
        
        Args:
            layer: The QGIS layer to synchronize
            action_description: Description of the action to perform
            direction: The synchronization direction ("push", "pull", or "auto")
        """
        # Show confirmation dialog
        dialog = ConfirmSyncDialog(layer.name(), action_description, self.iface.mainWindow())
        result = dialog.exec_()
        
        if result == dialog.Accepted:
            # Perform synchronization
            self.sync_manager.synchronize_layer(layer, direction)
            
            # Update layer icons
            from .layer_decorator import MapHubLayerDecorator
            layer_decorator = MapHubLayerDecorator(self.iface)
            layer_decorator.update_layer_icons()