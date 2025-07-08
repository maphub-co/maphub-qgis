import os
from typing import Dict, Any, Optional, List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QTreeWidget, 
                            QTreeWidgetItem, QMenu, QAction, QMessageBox)
from PyQt5.QtGui import QIcon, QCursor

from qgis.core import QgsProject, QgsVectorTileLayer, QgsRasterLayer
from qgis.utils import iface

from ...utils import get_maphub_client, apply_style_to_layer, handled_exceptions


class MapBrowserDockWidget(QDockWidget):
    """
    A dock widget that displays workspaces, folders, and maps in a tree structure.

    This widget provides a UI for browsing MapHub content, including:
    - Workspaces as top-level items
    - Folders and maps as child items
    - Folder contents loaded on demand when expanded
    """

    def __init__(self, iface, parent=None):
        """Initialize the dock widget."""
        super(MapBrowserDockWidget, self).__init__("MapHub Browser", parent)
        self.iface = iface
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Create main widget and layout
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_dir = os.path.join(os.path.dirname(__file__), '../../icons')

        # Create tree widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("MapHub Content")
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.itemExpanded.connect(self.on_item_expanded)

        # Add tree widget to layout
        self.main_layout.addWidget(self.tree_widget)

        # Set the main widget as the dock widget's content
        self.setWidget(self.main_widget)

        # Load workspaces
        self.load_workspaces()

    @handled_exceptions
    def load_workspaces(self):
        """Load workspaces as top-level items."""
        self.tree_widget.clear()

        # Get workspaces from MapHub
        client = get_maphub_client()
        workspaces = client.workspace.get_workspaces()

        # Add workspaces to tree
        for workspace in workspaces:
            workspace_id = workspace.get('id')
            workspace_name = workspace.get('name', 'Unknown Workspace')

            # Create workspace item
            workspace_item = QTreeWidgetItem(self.tree_widget)
            workspace_item.setText(0, workspace_name)
            workspace_item.setData(0, Qt.UserRole, {'type': 'workspace', 'id': workspace_id})

            # Use custom workspace icon
            workspace_item.setIcon(0, QIcon(os.path.join(self.icon_dir, 'workspace.svg')))

            # Add a placeholder child to show the expand arrow
            placeholder = QTreeWidgetItem(workspace_item)
            placeholder.setText(0, "Loading...")
            placeholder.setData(0, Qt.UserRole, {'type': 'placeholder'})

    def on_item_expanded(self, item):
        """Handle item expansion to load children on demand."""
        # Get item data
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        item_type = item_data.get('type')
        item_id = item_data.get('id')

        # Check if this is a placeholder item's parent
        if item.childCount() == 1 and item.child(0).data(0, Qt.UserRole).get('type') == 'placeholder':
            # Remove placeholder
            item.removeChild(item.child(0))

            # Load children based on item type
            if item_type == 'workspace':
                self.load_workspace_contents(item, item_id)
            elif item_type == 'folder':
                self.load_folder_contents(item, item_id)

    @handled_exceptions
    def load_workspace_contents(self, parent_item, workspace_id):
        """Load the contents of a workspace."""
        # Get the root folder for the workspace
        client = get_maphub_client()
        root_folder = client.folder.get_root_folder(workspace_id)
        folder_id = root_folder["folder"]["id"]

        # Load the root folder contents
        self.load_folder_contents(parent_item, folder_id)

    @handled_exceptions
    def load_folder_contents(self, parent_item, folder_id):
        """Load the contents of a folder."""
        # Get folder details including child folders and maps
        client = get_maphub_client()
        folder_details = client.folder.get_folder(folder_id)

        # Add child folders
        child_folders = folder_details.get("child_folders", [])
        for folder in child_folders:
            folder_item = QTreeWidgetItem(parent_item)
            folder_item.setText(0, folder.get('name', 'Unnamed Folder'))
            folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'id': folder.get('id'), 'data': folder})
            folder_item.setIcon(0, QIcon(os.path.join(self.icon_dir, 'folder.svg')))

            # Add placeholder for expandable folders
            placeholder = QTreeWidgetItem(folder_item)
            placeholder.setText(0, "Loading...")
            placeholder.setData(0, Qt.UserRole, {'type': 'placeholder'})

        # Add maps
        maps = folder_details.get("map_infos", [])
        for map_data in maps:
            map_item = QTreeWidgetItem(parent_item)
            map_item.setText(0, map_data.get('name', 'Unnamed Map'))
            map_item.setData(0, Qt.UserRole, {'type': 'map', 'id': map_data.get('id'), 'data': map_data})

            # Use different custom icons based on map type
            if map_data.get('type') == 'vector':
                map_item.setIcon(0, QIcon(os.path.join(self.icon_dir, 'vector_map.svg')))
            else:
                map_item.setIcon(0, QIcon(os.path.join(self.icon_dir, 'raster_map.svg')))