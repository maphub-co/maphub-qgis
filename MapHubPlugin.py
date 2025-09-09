# -*- coding: utf-8 -*-

import os
import os.path

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QEvent, QDataStream, QIODevice, QObject, QUrl
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QTreeView
from qgis.core import QgsProject

from .ui.dialogs.CloneFolderDialog import CloneFolderDialog
from .ui.dialogs.GetMapDialog import GetMapDialog
from .ui.dialogs.CreateFolderDialog import CreateFolderDialog
from .ui.dialogs.ApiKeyDialog import ApiKeyDialog
from .ui.dialogs.SettingsDialog import SettingsDialog
from .ui.dialogs.UploadMapDialog import UploadMapDialog
from .ui.dialogs.PullProjectDialog import PullProjectDialog
from .ui.dialogs.PushProjectDialog import PushProjectDialog
from .ui.widgets.MapBrowserDockWidget import MapBrowserDockWidget, MapBrowserTreeWidget
from .utils.scheduler_manager import SchedulerManager
from .utils.error_manager import handled_exceptions
from .utils.map_operations import download_map, download_folder_maps

from qgis.core import (
    QgsDataItem,
    QgsDataItemProvider,
    QgsDataItemProviderRegistry,
    QgsApplication,
    Qgis,
    QgsMimeDataUtils,
    QgsDataCollectionItem,
    QgsLayerItem
)
from qgis.gui import QgsGui, QgsCustomDropHandler
from . import resources

# Icon for Browser items (loaded from Qt resources)
BROWSER_ICON = QIcon(":/plugins/maphub/icons/icon.png")

class MaphubRootItem(QgsDataItem):
    def __init__(self, parent=None):
        # type Custom, label, path
        super().__init__(QgsDataItem.Custom, parent, "MapHub", "maphub:")
        self.mIcon = BROWSER_ICON
        print("MapHub: MaphubRootItem created (label=MapHub, path=maphub:)")

    def icon(self):
        return BROWSER_ICON

    def hasChildren(self):
        return True

    def createChildren(self):
        print("MapHub: MaphubRootItem.createChildren() called - loading workspaces")
        children = []
        try:
            from .utils.utils import get_maphub_client
            client = get_maphub_client()

            # Try to list all workspaces; if unavailable, fallback to personal workspace only
            workspaces = []
            try:
                workspaces = client.workspace.get_workspaces()
            except Exception:
                pass

            if workspaces:
                for ws in workspaces:
                    ws_id = ws.get("id") or ws.get("workspace", {}).get("id")
                    ws_name = ws.get("name") or ws.get("workspace", {}).get("name") or "Workspace"
                    if ws_id:
                        children.append(MaphubWorkspaceItem(ws_name, f"maphub:/workspace/{ws_id}", ws_id, self))
            else:
                # Fallback to personal workspace only
                try:
                    ws = client.workspace.get_personal_workspace()
                    ws_id = ws.get("id")
                    ws_name = ws.get("name") or "Personal Workspace"
                    if ws_id:
                        children.append(MaphubWorkspaceItem(ws_name, f"maphub:/workspace/{ws_id}", ws_id, self))
                except Exception as e:
                    print(f"MapHub: Failed to load workspaces: {str(e)}")
        except Exception as e:
            print(f"MapHub: Error creating root children: {str(e)}")

        return children


class MaphubWorkspaceItem(QgsDataCollectionItem):
    def __init__(self, label, path, workspace_id, parent=None):
        super().__init__(parent, label, path)
        self.mIcon = QIcon(":/plugins/maphub/icons/workspace.svg")
        self._workspace_id = workspace_id
        self._label = label
        print(f"MapHub: MaphubWorkspaceItem created (label={label}, id={workspace_id})")

    def hasChildren(self):
        return True

    def icon(self):
        return self.mIcon

    def createChildren(self):
        print(f"MapHub: Loading root folder for workspace {self._workspace_id}")
        children = []
        try:
            from .utils.utils import get_maphub_client
            client = get_maphub_client()
            root = client.folder.get_root_folder(self._workspace_id)
            folder = root.get("folder", {})
            folder_id = folder.get("id")
            folder_name = folder.get("name") or "Root"
            if folder_id:
                children.append(MaphubFolderItem(folder_name, f"maphub:/folder/{folder_id}", folder_id, self))
        except Exception as e:
            print(f"MapHub: Error loading workspace root folder: {str(e)}")
        return children

    def mimeUris(self):
        try:
            u = QgsMimeDataUtils.Uri()
            u.uri = f"maphub:/workspace/{self._workspace_id}"
            u.name = self._label
            return [u]
        except Exception:
            return []


class MaphubFolderItem(QgsDataCollectionItem):
    def __init__(self, label, path, folder_id, parent=None):
        super().__init__(parent, label, path)
        self.mIcon = QIcon(":/plugins/maphub/icons/folder.svg")
        self._folder_id = folder_id
        self._label = label
        print(f"MapHub: MaphubFolderItem created (label={label}, id={folder_id})")

    def hasChildren(self):
        return True

    def icon(self):
        return self.mIcon

    def createChildren(self):
        print(f"MapHub: Loading folder contents for {self._folder_id}")
        children = []
        try:
            from .utils.utils import get_maphub_client
            client = get_maphub_client()
            details = client.folder.get_folder(self._folder_id)
            # Subfolders
            for sub in details.get("child_folders", []):
                sub_id = sub.get("id")
                sub_name = sub.get("name") or "Folder"
                if sub_id:
                    children.append(MaphubFolderItem(sub_name, f"maphub:/folder/{sub_id}", sub_id, self))
            # Maps
            for map_info in details.get("map_infos", []):
                map_id = map_info.get("id")
                map_name = map_info.get("name") or "Map"
                map_type = map_info.get("type") or "unknown"
                if map_id:
                    children.append(MaphubMapItem(map_name, f"maphub:/map/{map_id}", map_id, map_type, map_info, self))
        except Exception as e:
            print(f"MapHub: Error loading folder contents: {str(e)}")
        return children

    def actions(self, parent):
        actions = []
        try:
            action_download_all = QAction(QIcon(":/plugins/maphub/icons/download.svg"), "Download all maps", parent)
            action_download_all.triggered.connect(lambda: self._download_all(parent))
            actions.append(action_download_all)

            action_tiling_all = QAction(QIcon(":/plugins/maphub/icons/raster_map.svg"), "Add all as tiling services", parent)
            action_tiling_all.triggered.connect(lambda: self._tiling_all(parent))
            actions.append(action_tiling_all)
        except Exception:
            pass
        return actions

    def _download_all(self, parent=None):
        try:
            from .utils.map_operations import download_folder_maps
            download_folder_maps(str(self._folder_id), parent)
        except Exception as e:
            print(f"MapHub: download all failed: {str(e)}")

    def _tiling_all(self, parent=None):
        try:
            from .utils.map_operations import add_folder_maps_as_tiling_services
            add_folder_maps_as_tiling_services(str(self._folder_id), parent)
        except Exception as e:
            print(f"MapHub: tiling all failed: {str(e)}")

    def mimeUris(self):
        try:
            u = QgsMimeDataUtils.Uri()
            u.uri = f"maphub:/folder/{self._folder_id}"
            u.name = self._label
            return [u]
        except Exception:
            return []


class MaphubMapItem(QgsLayerItem):
    def __init__(self, label, path, map_id, map_type, map_info=None, parent=None):
        layer_type = QgsLayerItem.Vector if map_type == "vector" else QgsLayerItem.Raster
        uri = f"maphub:/map/{map_id}"
        # Signature: (parent, name, path, providerKey, layerType, uri)
        super().__init__(parent, label, path, "maphub", layer_type, uri)
        if map_type == "vector":
            self.mIcon = QIcon(":/plugins/maphub/icons/vector_map.svg")
        elif map_type == "raster":
            self.mIcon = QIcon(":/plugins/maphub/icons/raster_map.svg")
        else:
            self.mIcon = BROWSER_ICON
        self._label = label
        self._map_id = map_id
        self._map_type = map_type
        self._map_info = map_info or {}
        print(f"MapHub: MaphubMapItem created (label={label}, id={map_id})")

    def icon(self):
        return self.mIcon

    def actions(self, parent):
        actions = []
        try:
            action_download = QAction(QIcon(":/plugins/maphub/icons/download.svg"), "Download", parent)
            action_download.triggered.connect(lambda: self._download(parent))
            actions.append(action_download)

            action_tiling = QAction(QIcon(":/plugins/maphub/icons/style.svg"), "Add as tiling", parent)
            action_tiling.triggered.connect(lambda: self._tiling(parent))
            actions.append(action_tiling)
        except Exception:
            pass
        return actions

    def _build_map_data(self):
        data = {
            'id': str(self._map_id),
            'name': self._label,
            'type': self._map_type,
        }
        # If visuals already present, include them to style tiling layer
        if 'visuals' in self._map_info:
            data['visuals'] = self._map_info['visuals']
        else:
            # Try fetch visuals lazily
            try:
                from .utils.utils import get_maphub_client
                info = get_maphub_client().maps.get_map(self._map_id)
                if 'map' in info and 'visuals' in info['map']:
                    data['visuals'] = info['map']['visuals']
            except Exception:
                pass
        return data

    def _download(self, parent=None):
        try:
            from .utils.map_operations import download_map
            download_map(self._build_map_data(), parent)
        except Exception as e:
            print(f"MapHub: map download failed: {str(e)}")

    def _tiling(self, parent=None):
        try:
            from .utils.map_operations import add_map_as_tiling_service
            add_map_as_tiling_service(self._build_map_data(), parent)
        except Exception as e:
            print(f"MapHub: map tiling failed: {str(e)}")

    def mimeUris(self):
        try:
            u = QgsMimeDataUtils.Uri()
            u.uri = f"maphub:/map/{self._map_id}"
            u.name = self._label
            u.providerKey = "maphub"
            u.layerType = self._map_type or "unknown"
            return [u]
        except Exception:
            return []

class MaphubProvider(QgsDataItemProvider):
    def __init__(self):
        super().__init__()
        print("MapHub: MaphubProvider initialized")

    def name(self):
        return "maphub"

    def capabilities(self):
        # QGIS 3.40 expects a Capabilities flags object
        try:
            caps = QgsDataItemProvider.Capabilities()
            print("MapHub: capabilities -> QgsDataItemProvider.Capabilities()")
            return caps
        except Exception:
            try:
                caps = Qgis.DataItemProviderCapabilities(
                    Qgis.DataItemProviderCapability.Directories | Qgis.DataItemProviderCapability.Files
                )
                print("MapHub: capabilities -> Qgis.DataItemProviderCapabilities(Directories|Files)")
                return caps
            except Exception:
                print("MapHub: capabilities -> Qgis.DataItemProviderCapabilities(0)")
                return Qgis.DataItemProviderCapabilities(0)

    # Top-level item(s) in the Browser
    def createRootNodes(self):
        print("MapHub: createRootNodes() called")
        return [MaphubRootItem(None)]

    # Required by abstract base in some QGIS versions
    def createDataItem(self, path, parentItem):
        try:
            if not path:
                print("MapHub: createDataItem(path is empty) -> MaphubRootItem(None)")
                return MaphubRootItem(None)
            if isinstance(path, str) and (path == "maphub:" or path == "maphub:/"):
                print(f"MapHub: createDataItem(path={path}) -> MaphubRootItem(parent)")
                return MaphubRootItem(parentItem)
            if isinstance(path, str) and path.startswith("maphub:/workspace/"):
                ws_id = path.split('/')[-1]
                print(f"MapHub: createDataItem(path={path}) -> MaphubWorkspaceItem(id={ws_id})")
                return MaphubWorkspaceItem(f"Workspace {ws_id}", path, ws_id, parentItem)
            if isinstance(path, str) and path.startswith("maphub:/folder/"):
                folder_id = path.split('/')[-1]
                print(f"MapHub: createDataItem(path={path}) -> MaphubFolderItem(id={folder_id})")
                return MaphubFolderItem(f"Folder {folder_id}", path, folder_id, parentItem)
            if isinstance(path, str) and path.startswith("maphub:/map/"):
                map_id = path.split('/')[-1]
                print(f"MapHub: createDataItem(path={path}) -> MaphubMapItem(id={map_id})")
                return MaphubMapItem(f"Map {map_id}", path, map_id, "unknown", None, parentItem)
        except Exception:
            pass
        print(f"MapHub: createDataItem(path={path}) -> None")
        return None


class MapHubDropHandler(QgsCustomDropHandler):
    def __init__(self, plugin):
        super().__init__()
        self._plugin = plugin

    def canHandleMimeData(self, md):
        try:
            # Check custom dock mime
            if md.hasFormat(MapBrowserTreeWidget.MIME_TYPE):
                return True
            # Check text
            text = md.text() if hasattr(md, 'text') else ''
            if text and ('maphub:/map/' in text or 'maphub:/folder/' in text or 'maphub:/' in text or text.strip() == 'maphub:'):
                return True
            # Check urls
            if hasattr(md, 'hasUrls') and md.hasUrls():
                for url in md.urls():
                    s = url.toString()
                    if s.startswith('maphub:/'):
                        return True
            # Check QGIS URIs
            try:
                uris = QgsMimeDataUtils.decodeUriList(md)
                for u in uris:
                    s = getattr(u, 'uri', None) or getattr(u, 'layerUri', None) or ''
                    if isinstance(s, str) and s.startswith('maphub:/'):
                        return True
            except Exception:
                pass
        except Exception:
            pass
        return False

    def handleMimeDataV2(self, md):
        try:
            # Prefer custom dock format
            if md.hasFormat(MapBrowserTreeWidget.MIME_TYPE):
                self._plugin.processDrop(md)
                return True
            # Aggregate strings to process via existing helper
            lines = []
            text = md.text() if hasattr(md, 'text') else ''
            if text:
                lines.extend([p.strip() for p in text.splitlines() if p.strip()])
            if hasattr(md, 'hasUrls') and md.hasUrls():
                for url in md.urls():
                    try:
                        lines.append(url.toString())
                    except Exception:
                        pass
            try:
                uris = QgsMimeDataUtils.decodeUriList(md)
                for u in uris:
                    try:
                        s = getattr(u, 'uri', None) or getattr(u, 'layerUri', None) or ''
                        if isinstance(s, str):
                            lines.append(s)
                    except Exception:
                        pass
            except Exception:
                pass
            if lines:
                if self._plugin._process_maphub_uri_drop('\n'.join(lines)):
                    return True
        except Exception as e:
            print(f"MapHub: Drop handler failed: {str(e)}")
        return False

    def customUriProviderKey(self):
        try:
            return "maphub"
        except Exception:
            return "maphub"

    def handleCustomUriDrop(self, uri):
        """
        Handle drops for URIs whose providerKey == 'maphub'.
        uri is a QgsMimeDataUtils.Uri with attributes: uri, name, providerKey, layerType, etc.
        """
        try:
            s = getattr(uri, 'uri', None) or ''
            if not isinstance(s, str):
                return False
            if s.startswith('maphub:/map/'):
                map_id = s.split('/')[-1]
                # Build map_data (fetch visuals)
                map_data = {'id': map_id, 'name': getattr(uri, 'name', None) or f'Map {map_id}', 'type': getattr(uri, 'layerType', None) or 'unknown'}
                try:
                    from .utils.utils import get_maphub_client
                    info = get_maphub_client().maps.get_map(map_id)
                    if 'map' in info:
                        m = info['map']
                        map_data['name'] = m.get('name', map_data['name'])
                        map_data['type'] = m.get('type', map_data['type'])
                        if 'visuals' in m:
                            map_data['visuals'] = m['visuals']
                except Exception:
                    pass
                download_map(map_data, self._plugin.iface.mainWindow())
                return True
            if s.startswith('maphub:/folder/'):
                folder_id = s.split('/')[-1]
                download_folder_maps(folder_id, self._plugin.iface.mainWindow())
                return True
            # Root or unknown
            return False
        except Exception as e:
            print(f"MapHub: handleCustomUriDrop failed: {str(e)}")
            return False

class MapHubPlugin(QObject):
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Initialize the QObject base class
        super(MapHubPlugin, self).__init__()

        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'MapHubPlugin_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&MapHub')
        
        # Initialize synchronization components
        self.layer_decorator = None
        self.layer_menu_provider = None
        self.map_browser_dock = None
        self.status_update_scheduler = None
        self.maphub_data_item_provider = None
        self._registry_log_source = None
        self._drop_handler = None

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('MapHubPlugin', message)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = os.path.join(self.plugin_dir, 'icons', 'icon.png')
        self.add_action(
            os.path.join(self.plugin_dir, 'get.png'),
            text=self.tr(u'Get map'),
            callback=self.get_map,
            parent=self.iface.mainWindow(),
            add_to_toolbar=True
        )

        # self.add_action(
        #     icon_path,
        #     text=self.tr(u'Upload to MapHub'),
        #     callback=self.upload_map,
        #     parent=self.iface.mainWindow(),
        #     add_to_toolbar=True
        # )
        #
        # self.add_action(
        #     icon_path,
        #     text=self.tr(u'Create folder'),
        #     callback=self.create_folder,
        #     parent=self.iface.mainWindow(),
        #     add_to_toolbar=False
        # )

        self.add_action(
            icon_path,
            text=self.tr(u'Set API Key'),
            callback=self.show_api_key_settings,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )
        #
        # self.add_action(
        #     os.path.join(self.plugin_dir, 'clone.png'),
        #     text=self.tr(u'Clone Project From MapHub'),
        #     callback=self.clone_project,
        #     parent=self.iface.mainWindow(),
        #     add_to_toolbar=False
        # )
        #
        # self.add_action(
        #     os.path.join(self.plugin_dir, 'pull.png'),
        #     text=self.tr(u'Pull Project from MapHub'),
        #     callback=self.pull_project,
        #     parent=self.iface.mainWindow(),
        #     add_to_toolbar=False
        # )
        #
        # self.add_action(
        #     os.path.join(self.plugin_dir, 'push.png'),
        #     text=self.tr(u'Push Project to MapHub'),
        #     callback=self.push_project,
        #     parent=self.iface.mainWindow(),
        #     add_to_toolbar=False
        # )

        # Add Synchronize button
        self.add_action(
            os.path.join(self.plugin_dir, 'icons', 'sync.svg'),
            text=self.tr(u'Synchronize Layers with MapHub'),
            callback=self.synchronize_layers,
            parent=self.iface.mainWindow(),
            add_to_toolbar=True
        )

        self.add_action(
            os.path.join(self.plugin_dir, 'icons', 'browser.svg'),
            text=self.tr(u'MapHub Browser'),
            callback=self.show_map_browser,
            parent=self.iface.mainWindow(),
            add_to_toolbar=True
        )
        
        # Add settings action
        self.add_action(
            os.path.join(self.plugin_dir, 'icons', 'settings.svg'),
            text=self.tr(u'MapHub Settings'),
            callback=self.show_settings,
            parent=self.iface.mainWindow(),
            add_to_toolbar=True
        )

        # will be set False in run()
        self.first_start = True
        
        # Initialize layer decorator and menu provider
        from .utils.layer_decorator import MapHubLayerDecorator
        from .utils.layer_menu_provider import MapHubLayerMenuProvider
        from .utils.sync_manager import MapHubSyncManager
        
        self.sync_manager = MapHubSyncManager(self.iface)
        self.layer_decorator = MapHubLayerDecorator.get_instance(self.iface)
        self.layer_menu_provider = MapHubLayerMenuProvider(self.iface, self.sync_manager)
        
        # Initialize the status update scheduler
        self.initialize_status_update_scheduler()
        
        # Update layer icons
        self.layer_decorator.update_layer_icons()
        
        # Connect to project events to update layer icons
        QgsProject.instance().layersAdded.connect(self.on_layers_changed)
        QgsProject.instance().layersRemoved.connect(self.on_layers_changed)
        
        # Register drop handlers for drag and drop support
        self.iface.mapCanvas().setAcceptDrops(True)
        self.iface.mapCanvas().installEventFilter(self)
        self.iface.layerTreeView().setAcceptDrops(True)
        self.iface.layerTreeView().installEventFilter(self)

        # Register the MapHub browser provider
        if self.maphub_data_item_provider is None:
            self.maphub_data_item_provider = MaphubProvider()
            try:
                registry = self._get_provider_registry()
                if registry:
                    print("MapHub: Adding provider to registry")
                    registry.addProvider(self.maphub_data_item_provider)
                self._refresh_browser_ui()
                print("MapHub: Provider registered and browser UI refresh requested")
            except Exception as e:
                print(f"MapHub: Failed to register browser provider: {str(e)}")

        # Register a custom drop handler so drops from Browser work on canvas/layer tree
        try:
            if self._drop_handler is None:
                self._drop_handler = MapHubDropHandler(self)
                if hasattr(QgsGui.instance(), 'registerCustomDropHandler'):
                    QgsGui.instance().registerCustomDropHandler(self._drop_handler)
                    print("MapHub: Registered custom drop handler")
        except Exception as e:
            print(f"MapHub: Failed to register custom drop handler: {str(e)}")

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&MapHub'),
                action)
            self.iface.removeToolBarIcon(action)
            
        # Disconnect from project events
        if hasattr(QgsProject.instance(), 'layersAdded'):
            QgsProject.instance().layersAdded.disconnect(self.on_layers_changed)
        if hasattr(QgsProject.instance(), 'layersRemoved'):
            QgsProject.instance().layersRemoved.disconnect(self.on_layers_changed)
            
        # Clean up UI components
        if self.layer_decorator:
            self.layer_decorator.cleanup()
            self.layer_decorator = None
        self.layer_menu_provider = None
        
        # Stop and clean up the scheduler
        if self.status_update_scheduler:
            self.status_update_scheduler.stop_periodic_updates()
            self.status_update_scheduler = None
        
        # Close the map browser dock if it exists
        if self.map_browser_dock:
            self.map_browser_dock.close()
            self.map_browser_dock = None
            
        # Remove event filters for drag and drop
        if self.iface.mapCanvas():
            self.iface.mapCanvas().removeEventFilter(self)
        if self.iface.layerTreeView():
            self.iface.layerTreeView().removeEventFilter(self)

        # Unregister the MapHub browser provider
        if self.maphub_data_item_provider:
            try:
                # removeProvider may not exist in some QGIS versions, so guard it
                registry = self._get_provider_registry()
                if registry and hasattr(registry, 'removeProvider'):
                    print("MapHub: Removing provider from registry")
                    registry.removeProvider(self.maphub_data_item_provider)
                self._refresh_browser_ui()
                print("MapHub: Provider unregistered and browser UI refresh requested")
            except Exception as e:
                print(f"MapHub: Failed to unregister browser provider: {str(e)}")
            finally:
                self.maphub_data_item_provider = None

        # Unregister drop handler
        try:
            if self._drop_handler and hasattr(QgsGui.instance(), 'unregisterCustomDropHandler'):
                QgsGui.instance().unregisterCustomDropHandler(self._drop_handler)
                print("MapHub: Unregistered custom drop handler")
        except Exception as e:
            print(f"MapHub: Failed to unregister custom drop handler: {str(e)}")
        finally:
            self._drop_handler = None

    def _get_provider_registry(self):
        """Return the data item provider registry in a version-tolerant way."""
        try:
            if hasattr(QgsApplication, 'dataItemProviderRegistry'):
                if self._registry_log_source != 'QgsApplication':
                    print("MapHub: Using QgsApplication.dataItemProviderRegistry()")
                    self._registry_log_source = 'QgsApplication'
                return QgsApplication.dataItemProviderRegistry()
        except Exception:
            pass
        try:
            gui = QgsGui.instance() if hasattr(QgsGui, 'instance') else None
            if gui and hasattr(gui, 'dataItemProviderRegistry'):
                if self._registry_log_source != 'QgsGui':
                    print("MapHub: Using QgsGui.instance().dataItemProviderRegistry()")
                    self._registry_log_source = 'QgsGui'
                return gui.dataItemProviderRegistry()
        except Exception:
            pass
        try:
            browser_model = QgsGui.instance().browserModel()
            if browser_model and hasattr(browser_model, 'providerRegistry'):
                if self._registry_log_source != 'BrowserModel':
                    print("MapHub: Using browserModel.providerRegistry()")
                    self._registry_log_source = 'BrowserModel'
                return browser_model.providerRegistry()
        except Exception:
            pass
        return None

    def _refresh_browser_ui(self):
        """Attempt to refresh the QGIS Browser UI in multiple ways."""
        refreshed = False
        try:
            browser_model = QgsGui.instance().browserModel()
            if browser_model:
                browser_model.refresh()
                refreshed = True
                print("MapHub: Browser model refreshed via QgsGui.instance().browserModel()")
        except Exception:
            pass

        if not refreshed:
            try:
                dock = self.iface.mainWindow().findChild(QDockWidget, "Browser")
                if dock:
                    tree = dock.findChild(QTreeView)
                    if tree and tree.model() and hasattr(tree.model(), 'refresh'):
                        tree.model().refresh()
                        refreshed = True
                        print("MapHub: Browser model refreshed via Browser dock tree")
            except Exception:
                pass

    def check_api_key(self):
        """Check if API key exists, prompt for it if not."""
        settings = QSettings()
        api_key = settings.value("MapHubPlugin/api_key", "")

        if not api_key:
            # No API key found, ask user to input it
            dlg = ApiKeyDialog(self.iface.mainWindow())
            result = dlg.exec_()

            if result:
                # User provided an API key
                api_key = dlg.get_api_key()
                return api_key
            else:
                # User canceled the dialog
                return None

        return api_key

    @handled_exceptions
    def create_folder(self, checked=False):
        dlg = CreateFolderDialog(self.iface.mainWindow())
        dlg.exec_()

    @handled_exceptions
    def show_api_key_settings(self, checked=False):
        """Show API key settings dialog to update the key."""
        dlg = ApiKeyDialog(self.iface.mainWindow())
        dlg.exec_()

    @handled_exceptions
    def get_map(self, checked=False):
        """Show API key settings dialog to update the key."""
        dlg = GetMapDialog(self.iface, self.iface.mainWindow())
        result = dlg.exec_()

    @handled_exceptions
    def upload_map(self, checked=False):
        """Show upload map dialog to upload a map."""
        dlg = UploadMapDialog(self.iface, self.iface.mainWindow())
        result = dlg.exec_()

    @handled_exceptions
    def pull_project(self, checked=False):
        """Show pull project dialog to update the current project with latest data from MapHub."""
        dlg = PullProjectDialog(self.iface, self.iface.mainWindow())
        result = dlg.exec_()

    @handled_exceptions
    def push_project(self, checked=False):
        """Show push project dialog to push the current project data to MapHub."""
        dlg = PushProjectDialog(self.iface, self.iface.mainWindow())
        result = dlg.exec_()

    @handled_exceptions
    def show_map_browser(self, checked=False):
        """Show the map browser dock widget."""
        if self.map_browser_dock is None:
            self.map_browser_dock = MapBrowserDockWidget(self.iface, self.iface.mainWindow(), refresh_callback=self.refresh_status)
            self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.map_browser_dock)
            
            # Refresh the browser dock immediately to ensure it's up to date
            if self.status_update_scheduler:
                self.status_update_scheduler.execute_now()
        else:
            # If the dock widget exists but is hidden, show it
            self.map_browser_dock.setVisible(True)

    @handled_exceptions
    def clone_project(self, checked=False):
        """Show the clone project dialog to clone a directory from MapHub."""
        dlg = CloneFolderDialog(self.iface, self.iface.mainWindow())

        def on_clone_completed(project_path):
            if project_path:
                self.iface.addProject(project_path)

        dlg.cloneCompleted.connect(on_clone_completed)

        result = dlg.exec_()
        
    def on_layers_changed(self):
        """Update layer icons when layers are added or removed."""
        if self.layer_decorator:
            self.layer_decorator.update_layer_icons()
    
    @handled_exceptions
    def synchronize_layers(self, checked=False):
        """Synchronize layers with MapHub."""
        from .ui.dialogs.SynchronizeLayersDialog import SynchronizeLayersDialog
        
        # Create and show the synchronization dialog
        dialog = SynchronizeLayersDialog(self.iface, self.iface.mainWindow())
        dialog.exec_()
        
    def initialize_status_update_scheduler(self):
        """Initialize the status update scheduler."""
        # Create the scheduler with the refresh function
        self.status_update_scheduler = SchedulerManager(lambda: self.refresh_status())
        
        # Apply settings from QSettings
        settings = QSettings()
        enable_periodic = settings.value("MapHubPlugin/enable_periodic_updates", True, type=bool)
        if enable_periodic:
            update_interval = settings.value("MapHubPlugin/update_interval", 5, type=int)
            # Convert minutes to milliseconds
            interval_ms = update_interval * 60 * 1000
            self.status_update_scheduler.start_periodic_updates(interval_ms)
    
    @handled_exceptions
    def show_settings(self, checked=False):
        """Show the settings dialog."""
        # Create the settings dialog with callbacks
        dialog = SettingsDialog(
            self.iface, 
            self.iface.mainWindow(),
            refresh_callback=self.refresh_status,
            on_settings_changed=self.apply_scheduler_settings
        )
        
        # Show the dialog
        dialog.exec_()
    
    def apply_scheduler_settings(self):
        """Apply scheduler settings from QSettings."""
        settings = QSettings()
        enable_periodic = settings.value("MapHubPlugin/enable_periodic_updates", True, type=bool)
        update_interval = settings.value("MapHubPlugin/update_interval", 5, type=int)
        
        if enable_periodic and self.status_update_scheduler:
            # Convert minutes to milliseconds
            interval_ms = update_interval * 60 * 1000
            self.status_update_scheduler.start_periodic_updates(interval_ms)
        elif self.status_update_scheduler:
            self.status_update_scheduler.stop_periodic_updates()
    
    def refresh_status(self):
        """Refresh all MapHub status icons and browser items."""
        # Update layer icons in the layers panel
        if self.layer_decorator:
            self.layer_decorator.update_layer_icons()

        # Update browser dock if available
        if self.map_browser_dock:
            self.map_browser_dock.refresh_browser()
            
    def eventFilter(self, obj, event):
        """
        Handle events for objects that have installed this object as an event filter.
        
        This is used to handle drag and drop events from the MapBrowserDockWidget.
        """
        if event.type() == QEvent.DragEnter:
            md = event.mimeData()
            if md.hasFormat(MapBrowserTreeWidget.MIME_TYPE):
                event.acceptProposedAction()
                return True
            # Also accept native QGIS Browser drags that include maphub URIs
            try:
                # Check text
                text = md.text() if hasattr(md, 'text') else ''
                if text and ('maphub:/map/' in text or 'maphub:/folder/' in text or text.strip() == 'maphub:/' or text.strip() == 'maphub:'):
                    event.acceptProposedAction()
                    return True
                # Check url list
                if hasattr(md, 'hasUrls') and md.hasUrls():
                    for url in md.urls():
                        s = url.toString()
                        if s.startswith('maphub:/'):
                            event.acceptProposedAction()
                            return True
                # Check QGIS URI mime
                try:
                    uris = QgsMimeDataUtils.decodeUriList(md)
                    for u in uris:
                        try:
                            s = getattr(u, 'uri', None) or getattr(u, 'layerUri', None) or ''
                            if isinstance(s, str) and s.startswith('maphub:/'):
                                event.acceptProposedAction()
                                return True
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception:
                pass
        elif event.type() == QEvent.Drop:
            md = event.mimeData()
            if md.hasFormat(MapBrowserTreeWidget.MIME_TYPE):
                # Process the drop from custom dock widget
                self.processDrop(md)
                event.acceptProposedAction()
                return True
            # Handle native QGIS Browser drops containing maphub URIs
            try:
                # Handle text/uri-list
                text = md.text() if hasattr(md, 'text') else ''
                if text:
                    if self._process_maphub_uri_drop(text):
                        event.acceptProposedAction()
                        return True
                if hasattr(md, 'hasUrls') and md.hasUrls():
                    # Build combined list
                    lines = []
                    for url in md.urls():
                        try:
                            lines.append(url.toString())
                        except Exception:
                            pass
                    if lines and self._process_maphub_uri_drop('\n'.join(lines)):
                        event.acceptProposedAction()
                        return True
                # Decode QGIS URIs
                try:
                    uris = QgsMimeDataUtils.decodeUriList(md)
                    lines = []
                    for u in uris:
                        try:
                            s = getattr(u, 'uri', None) or getattr(u, 'layerUri', None) or ''
                            if isinstance(s, str):
                                lines.append(s)
                        except Exception:
                            pass
                    if lines and self._process_maphub_uri_drop('\n'.join(lines)):
                        event.acceptProposedAction()
                        return True
                except Exception:
                    pass
            except Exception:
                pass
        
        # Standard event processing
        return super(MapHubPlugin, self).eventFilter(obj, event)
        
    def processDrop(self, mime_data):
        """
        Process the dropped data from the MapBrowserDockWidget.
        
        Args:
            mime_data: The mime data containing the dropped item information
        """
        encoded_data = mime_data.data(MapBrowserTreeWidget.MIME_TYPE)
        stream = QDataStream(encoded_data, QIODevice.ReadOnly)
        
        # Read the item type and ID
        item_type = stream.readQString()
        item_id = stream.readQString()
        
        if item_type == 'map':
            # Read map data
            map_id = stream.readQString()
            map_name = stream.readQString()
            map_type = stream.readQString()
            folder_id = stream.readQString()
            
            # Create map_data dictionary
            map_data = {
                'id': map_id,
                'name': map_name,
                'type': map_type
            }
            if folder_id:
                map_data['folder_id'] = folder_id
            
            # Fetch complete map data including visuals
            try:
                from .utils.utils import get_maphub_client
                complete_map_info = get_maphub_client().maps.get_map(map_id)
                if 'map' in complete_map_info and 'visuals' in complete_map_info['map']:
                    map_data['visuals'] = complete_map_info['map']['visuals']
            except Exception as e:
                print(f"Error fetching map visuals: {str(e)}")
            
            # Call the download function
            download_map(map_data, self.iface.mainWindow())
        
        elif item_type == 'folder':
            # Call the download all function
            download_folder_maps(item_id, self.iface.mainWindow())

    def _process_maphub_uri_drop(self, text_data: str) -> bool:
        """
        Process drops from native QGIS Browser which typically provide text/uri-list.
        Expected formats:
          - maphub:/map/<id>
          - maphub:/folder/<id>
          - maphub:/ or maphub:
        Returns True if handled.
        """
        try:
            # QGIS usually separates URIs by newline
            parts = [p.strip() for p in text_data.splitlines() if p.strip()]
            if not parts:
                return False
            handled_any = False
            for p in parts:
                if p.startswith('maphub:/map/'):
                    map_id = p.split('/')[-1]
                    # Build map_data (fetch visuals)
                    map_data = {'id': map_id, 'name': f'Map {map_id}', 'type': 'unknown'}
                    try:
                        from .utils.utils import get_maphub_client
                        info = get_maphub_client().maps.get_map(map_id)
                        if 'map' in info:
                            m = info['map']
                            map_data['name'] = m.get('name', map_data['name'])
                            map_data['type'] = m.get('type', map_data['type'])
                            if 'visuals' in m:
                                map_data['visuals'] = m['visuals']
                    except Exception:
                        pass
                    download_map(map_data, self.iface.mainWindow())
                    handled_any = True
                elif p.startswith('maphub:/folder/'):
                    folder_id = p.split('/')[-1]
                    download_folder_maps(folder_id, self.iface.mainWindow())
                    handled_any = True
                elif p == 'maphub:/' or p == 'maphub:':
                    # No-op for root
                    handled_any = True
            return handled_any
        except Exception as e:
            print(f"MapHub: Failed to process URI drop: {str(e)}")
            return False
