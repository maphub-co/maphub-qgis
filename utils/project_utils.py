import os.path
import tempfile

from qgis._core import QgsProject
from qgis.core import Qgis

from .utils import get_maphub_client, get_default_download_location


def get_project_folder_id() -> str:
    """
    Get the folder ID associated with the current project.
    
    Returns:
        str: The folder ID, or None if not found
    """
    project = QgsProject.instance()
    folder_id, _ = project.readEntry("maphub", "folder_id", "")
    return folder_id if folder_id else None


def folder_has_project(folder_id):
    """
    Check if the folder already has a QGIS project.

    Args:
        folder_id: The ID of the folder to check

    Returns:
        bool: True if the folder has a project, False otherwise
    """
    return get_maphub_client().folder.get_is_project(folder_id)


def save_project_to_maphub(folder_id):
    if not folder_id:
        raise Exception("Cloud not infer folder_id from project.")

    # Get the current project
    project = QgsProject.instance()

    # Check if the project has been saved
    if project.fileName() == "":
        # Create a temporary file to save the project
        temp_file = tempfile.NamedTemporaryFile(suffix=".qgz", delete=False)
        temp_file.close()
        temp_path = temp_file.name

        # Save the project to the temporary file
        project.write(temp_path)
        local_path = temp_path
    else:
        # Save the project to its current location
        local_path = project.fileName()
        project.write()

    # Upload the project to MapHub
    get_maphub_client().folder.put_qgis_project(folder_id, local_path)


def load_maphub_project(folder_id):
    base_folder = get_default_download_location()
    project_path = os.path.join(base_folder, f"{folder_id}.qgz")

    # Download the project from MapHub
    get_maphub_client().folder.get_qgis_project(folder_id, project_path)

    # Load the project into QGIS
    project = QgsProject.instance()
    readflags = Qgis.ProjectReadFlags()
    readflags |= Qgis.ProjectReadFlag.DontResolveLayers
    project.read(project_path, readflags)

    # Apply custom properties
    project.writeEntry("maphub", "folder_id", folder_id)
