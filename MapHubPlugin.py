# -*- coding: utf-8 -*-

import os
import os.path
import tempfile
import zipfile
import glob

from qgis.core import QgsMapLayer, QgsVectorLayer, QgsRasterLayer
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from .ui.dialogs.CloneFolderDialog import CloneFolderDialog
from .ui.dialogs.GetMapDialog import GetMapDialog
from .ui.dialogs.CreateFolderDialog import CreateFolderDialog
from .utils import handled_exceptions, show_error_dialog
from .ui.dialogs.ApiKeyDialog import ApiKeyDialog
from .ui.dialogs.UploadMapDialog import UploadMapDialog
from .ui.dialogs.PullProjectDialog import PullProjectDialog
from .ui.dialogs.PushProjectDialog import PushProjectDialog



class MapHubPlugin:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """

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

        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            os.path.join(self.plugin_dir, 'get.png'),
            text=self.tr(u'Get map'),
            callback=self.get_map,
            parent=self.iface.mainWindow(),
            add_to_toolbar=True
        )

        self.add_action(
            icon_path,
            text=self.tr(u'Upload to MapHub'),
            callback=self.upload_map,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )

        self.add_action(
            icon_path,
            text=self.tr(u'Create folder'),
            callback=self.create_folder,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )

        self.add_action(
            icon_path,
            text=self.tr(u'Set API Key'),
            callback=self.show_api_key_settings,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )

        self.add_action(
            os.path.join(self.plugin_dir, 'clone.png'),
            text=self.tr(u'Clone Project From MapHub'),
            callback=self.clone_project,
            parent=self.iface.mainWindow(),
            add_to_toolbar=True
        )

        self.add_action(
            os.path.join(self.plugin_dir, 'pull.png'),
            text=self.tr(u'Pull Project from MapHub'),
            callback=self.pull_project,
            parent=self.iface.mainWindow(),
            add_to_toolbar=True
        )

        self.add_action(
            os.path.join(self.plugin_dir, 'push.png'),
            text=self.tr(u'Push Project to MapHub'),
            callback=self.push_project,
            parent=self.iface.mainWindow(),
            add_to_toolbar=True
        )

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&MapHub'),
                action)
            self.iface.removeToolBarIcon(action)

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
    def clone_project(self, checked=False):
        """Show the clone project dialog to clone a directory from MapHub."""
        dlg = CloneFolderDialog(self.iface, self.iface.mainWindow())

        def on_clone_completed(project_path):
            if project_path:
                self.iface.addProject(project_path)

        dlg.cloneCompleted.connect(on_clone_completed)

        result = dlg.exec_()
