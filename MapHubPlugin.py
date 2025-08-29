# -*- coding: utf-8 -*-

import os
import os.path

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QEvent, QDataStream, QIODevice, QObject
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
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
            if event.mimeData().hasFormat(MapBrowserTreeWidget.MIME_TYPE):
                event.acceptProposedAction()
                return True
        elif event.type() == QEvent.Drop:
            if event.mimeData().hasFormat(MapBrowserTreeWidget.MIME_TYPE):
                # Process the drop
                self.processDrop(event.mimeData())
                event.acceptProposedAction()
                return True
        
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
