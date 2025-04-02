# -*- coding: utf-8 -*-
import uuid

from qgis.core import QgsMapLayer, QgsVectorLayer, QgsRasterLayer
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from .MapHubPlugin_apikey_dialog import ApiKeyDialog
# Initialize Qt resources from file resources.py
# Import the code for the dialog
from .MapHubPlugin_dialog import MapHubPluginDialog
import os.path


# def load_bundled_libraries():
#     """Add the bundled libraries to the Python path"""
#     lib_dir = os.path.join(os.path.dirname(__file__), 'lib')
#     if os.path.exists(lib_dir) and lib_dir not in sys.path:
#         sys.path.insert(0, lib_dir)
#
# # Add the lib directory to the Python path
# lib_dir = os.path.join(os.path.dirname(__file__), 'lib')
# if lib_dir not in sys.path:
#     sys.path.insert(0, lib_dir)

# Now import normally
# from .maphub import MapHubClient
from .maphub.client import MapHubClient


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

        icon_path = ':/plugins/MapHubPlugin/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Upload to HapHub'),
            callback=self.run,
            parent=self.iface.mainWindow())

        self.add_action(
            icon_path,
            text=self.tr(u'Set API Key'),
            callback=self.show_api_key_settings,
            parent=self.iface.mainWindow()
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

    def show_api_key_settings(self):
        """Show API key settings dialog to update the key."""
        dlg = ApiKeyDialog(self.iface.mainWindow())
        dlg.exec_()

    def run(self):
        """Run method that performs all the real work"""

        api_key = self.check_api_key()
        if api_key is None:
            return show_error_dialog("API key is required. Please enter it in the plugin settings or click the 'Set API Key' button to set it.")

        client = MapHubClient(
            # base_url="https://api-dev-432878571563.europe-west4.run.app",
            api_key=api_key,
            base_url="http://localhost:8000"
        )

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            self.dlg = MapHubPluginDialog()

        # Get all open layers that are either vector or raster layers with a file location.
        layers = [
            layer for layer in self.iface.mapCanvas().layers()
            if (layer.type() in [QgsMapLayer.VectorLayer,
                                 QgsMapLayer.RasterLayer] and layer.dataProvider().dataSourceUri())
        ]
        if len(layers) == 0:
            return show_error_dialog("No layers that have local files detected. Please add a layer and try again.")

        # Populate the layers combobox
        self.dlg.populate_layers_combobox(layers)

        # Connect layer combobox to map name field
        def update_map_name(index):
            if index >= 0:
                layer = self.dlg.comboBox_layer.currentData()
                if layer:
                    self.dlg.set_default_map_name(layer.name())

        # Connect the signal
        self.dlg.comboBox_layer.currentIndexChanged.connect(update_map_name)

        # Set initial value if there's a layer selected
        update_map_name(0)

        # Get options from your function
        projects = client.get_projects()
        if len(projects) == 0:
            return show_error_dialog("You do not yet have any projects. Please create one on https://maphub.co/dashboard/projects and try again.")

        # Populate the options combobox
        self.dlg.populate_projects_combobox(projects)

        # Show the dialog
        result = self.dlg.exec_()

        # See if OK was pressed
        if result:
            # Get selected values
            selected_name = self.dlg.get_map_name()
            if selected_name is None:
                return show_error_dialog("No name selected")

            selected_layer = self.dlg.get_selected_layer()
            if selected_layer is None:
                return show_error_dialog("No layer selected")
            file_path = selected_layer.dataProvider().dataSourceUri().split('|')[0]

            selected_project = self.dlg.get_selected_project()
            if selected_project is None:
                return show_error_dialog("No project selected")

            selected_public = self.dlg.get_selected_public()

            # Upload layer to MapHub
            try:
                client.upload_map(
                    map_name=selected_name,
                    project_id=selected_project["id"],
                    public=selected_public,
                    path=file_path,
                )
            except Exception as e:
                show_error_dialog(f"{e}", "Error uploading map to MapHub")
                return


def show_error_dialog(message, title="Error"):
    """Display a modal error dialog.

    Args:
        message (str): The error message
        title (str): Dialog title
    """
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setText(message)
    msg_box.setWindowTitle(title)
    msg_box.setStandardButtons(QMessageBox.Ok)
    msg_box.exec_()
