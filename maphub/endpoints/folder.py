import uuid
from typing import Dict, Any, List

from .base import BaseEndpoint


class FolderEndpoint(BaseEndpoint):
    """Endpoints for folder operations."""
    
    def get_folder(self, folder_id: uuid.UUID) -> Dict[str, Any]:
        """
        Fetches the details of a specific folder based on the provided folder ID.
        
        :param folder_id: The unique identifier of the folder to be retrieved.
        :type folder_id: uuid.UUID
        :return: A dictionary containing the folder details.
        :rtype: Dict[str, Any]
        """
        return self._make_request("GET", f"/folders/{folder_id}").json()
    
    def get_root_folder(self, workspace_id: uuid.UUID) -> Dict[str, Any]:
        """
        Fetches the root folder for the authenticated user.
        
        The root folder is the top-level container that holds all other folders.

        :param workspace_id: The unique identifier of the workspace.
        :type workspace_id: uuid.UUID
        :return: A dictionary containing the root folder details.
        :rtype: Dict[str, Any]
        """
        return self._make_request("GET", f"/folders?workspace_id={workspace_id}").json()
    
    def create_folder(self, folder_name: str, parent_folder_id: uuid.UUID) -> Dict[str, Any]:
        """
        Creates a new folder with the given folder name.
        
        :param folder_name: The name of the folder to be created.
        :type folder_name: str
        :param parent_folder_id: The unique identifier of the parent folder.
        :type parent_folder_id: uuid.UUID
        :return: Response containing the created folder.
        :rtype: Dict[str, Any]
        """
        return self._make_request("POST", f"/folders?folder_name={folder_name}&parent_folder_id={parent_folder_id}").json()
    
    def get_folder_maps(self, folder_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        Fetches a list of maps associated with a specific folder.
        
        :param folder_id: A UUID identifying the folder whose maps are being fetched.
        :type folder_id: uuid.UUID
        :return: A list of dictionaries containing map data. Each dictionary represents
                 a map associated with the specified folder.
        :rtype: List[Dict[str, Any]]
        """
        return self.get_folder(folder_id)["map_infos"]

    def get_all_folders(self, workspace_id: uuid.UUID) -> [Dict[str, Any]]:
        """
        Retrieves all folders associated with a given workspace ID.

        :param workspace_id: The unique identifier of the workspace whose folders
            are to be retrieved.
        :type workspace_id: uuid.UUID
        :return: A list of dictionaries containing folder information for the
            specified workspace.
        :rtype: list[Dict[str, Any]]
        """
        return self._make_request("GET", f"/folders/all?workspace_id={workspace_id}").json()