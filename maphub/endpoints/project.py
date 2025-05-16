import uuid
import warnings
from typing import Dict, Any, List

from .base import BaseEndpoint
from .folder import FolderEndpoint
from .workspace import WorkspaceEndpoint


class ProjectEndpoint(BaseEndpoint):
    """Endpoints for project operations (deprecated, use folder endpoints instead)."""

    def get_project(self, project_id: uuid.UUID) -> Dict[str, Any]:
        """
        DEPRECATED: Use get_folder instead.
        
        Fetches the details of a specific project based on the provided project ID.
        
        :param project_id: The unique identifier of the project to be retrieved.
        :type project_id: uuid.UUID
        :return: A dictionary containing the project details.
        :rtype: Dict[str, Any]
        """
        warnings.warn("get_project is deprecated, use get_folder instead", DeprecationWarning, stacklevel=2)
        folder_endpoint = FolderEndpoint(self.api_key, self.base_url, self.session)
        return folder_endpoint.get_folder(project_id)
    
    def get_projects(self) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Use get_folders instead.
        
        Fetches a list of projects.
        
        :raises APIError: If there is an error during the API request.
        :return: A list of projects.
        :rtype: List[Dict[str, Any]]
        """
        warnings.warn("get_projects is deprecated, use get_folders instead", DeprecationWarning, stacklevel=2)
        personal_workspace = WorkspaceEndpoint(self.api_key, self.base_url, self.session).get_personal_workspace()
        folder_endpoint = FolderEndpoint(self.api_key, self.base_url, self.session)
        return folder_endpoint.get_root_folder(personal_workspace['id'])["child_folders"]
    
    def create_project(self, project_name: str) -> Dict[str, Any]:
        """
        DEPRECATED: Use create_folder instead.
        
        Creates a new project with the given project name.
        
        :param project_name: The name of the project to be created.
        :type project_name: str
        :return: Response containing the created project.
        :rtype: Dict[str, Any]
        """
        warnings.warn("create_project is deprecated, use create_folder instead", DeprecationWarning, stacklevel=2)
        personal_workspace = WorkspaceEndpoint(self.api_key, self.base_url, self.session).get_personal_workspace()
        folder_endpoint = FolderEndpoint(self.api_key, self.base_url, self.session)
        root_folder = folder_endpoint.get_root_folder(personal_workspace['id'])
        return folder_endpoint.create_folder(project_name, root_folder["folder"]["id"])
    
    def get_project_maps(self, project_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Use get_folder_maps instead.
        
        Fetches a list of maps associated with a specific project.
        
        :param project_id: A UUID identifying the project whose maps are being fetched.
        :type project_id: uuid.UUID
        :return: A list of dictionaries containing map data. Each dictionary represents
                 a map associated with the specified project.
        :rtype: List[Dict[str, Any]]
        """
        warnings.warn("get_project_maps is deprecated, use get_folder_maps instead", DeprecationWarning, stacklevel=2)
        folder_endpoint = FolderEndpoint(self.api_key, self.base_url, self.session)
        return folder_endpoint.get_folder_maps(project_id)