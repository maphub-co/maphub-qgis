import uuid
import warnings
from typing import Dict, Any, List, Optional

import requests

from .endpoints.workspace import WorkspaceEndpoint
from .endpoints.folder import FolderEndpoint
from .endpoints.project import ProjectEndpoint
from .endpoints.maps import MapsEndpoint


class MapHubClient:
    def __init__(self, api_key: Optional[str], base_url: str = "https://api-main-432878571563.europe-west4.run.app"):
        self.api_key = api_key
        self.base_url = base_url

        # Create a session for all endpoint classes to share
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({
                "X-API-Key": f"{self.api_key}"
            })

        # Initialize endpoint classes with the shared session
        self.workspace = WorkspaceEndpoint(api_key, base_url, self.session)
        self.folder = FolderEndpoint(api_key, base_url, self.session)
        self.project = ProjectEndpoint(api_key, base_url, self.session)
        self.maps = MapsEndpoint(api_key, base_url, self.session)

    # Workspace endpoints
    def get_personal_workspace(self) -> Dict[str, Any]:
        """
        DEPRECATED: Use workspace.get_personal_workspace() instead. Will be removed in a future version.

        Fetches the details of a specific workspace based on the provided folder ID.

        :return: A dictionary containing the workspace details.
        :rtype: Dict[str, Any]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use workspace.get_personal_workspace() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.workspace.get_personal_workspace()

    # Folder endpoints
    def get_folder(self, folder_id: uuid.UUID) -> Dict[str, Any]:
        """
        DEPRECATED: Use folder.get_folder() instead. Will be removed in a future version.

        Fetches the details of a specific folder based on the provided folder ID.

        :param folder_id: The unique identifier of the folder to be retrieved.
        :type folder_id: uuid.UUID
        :return: A dictionary containing the folder details.
        :rtype: Dict[str, Any]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use folder.get_folder() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.folder.get_folder(folder_id)

    def get_root_folder(self) -> Dict[str, Any]:
        """
        DEPRECATED: Use folder.get_root_folder() instead. Will be removed in a future version.

        Fetches the root folder for the authenticated user.

        The root folder is the top-level container that holds all other folders.

        :return: A dictionary containing the root folder details.
        :rtype: Dict[str, Any]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use folder.get_root_folder() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        personal_workspace = self.workspace.get_personal_workspace()
        return self.folder.get_root_folder(personal_workspace["id"])

    def create_folder(self, folder_name: str, parent_folder_id: uuid.UUID) -> Dict[str, Any]:
        """
        DEPRECATED: Use folder.create_folder() instead. Will be removed in a future version.

        Creates a new folder with the given folder name.

        :param folder_name: The name of the folder to be created.
        :type folder_name: str
        :param parent_folder_id: The unique identifier of the parent folder.
        :type parent_folder_id: uuid.UUID
        :return: Response containing the created folder.
        :rtype: Dict[str, Any]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use folder.create_folder() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.folder.create_folder(folder_name, parent_folder_id)

    # Project endpoints (deprecated, use folder endpoints instead)
    def get_project(self, project_id: uuid.UUID) -> Dict[str, Any]:
        """
        DEPRECATED: Use folder.get_folder() instead. Will be removed in a future version.

        Fetches the details of a specific project based on the provided project ID.

        :param project_id: The unique identifier of the project to be retrieved.
        :type project_id: uuid.UUID
        :return: A dictionary containing the project details.
        :rtype: Dict[str, Any]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use folder.get_folder() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.project.get_project(project_id)

    def get_projects(self) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Use folder.get_root_folder() instead. Will be removed in a future version.

        Fetches a list of projects.

        :raises APIError: If there is an error during the API request.
        :return: A list of projects.
        :rtype: List[Dict[str, Any]]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use folder.get_root_folder() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.project.get_projects()

    def create_project(self, project_name: str) -> Dict[str, Any]:
        """
        DEPRECATED: Use folder.create_folder() instead. Will be removed in a future version.

        Creates a new project with the given project name.

        :param project_name: The name of the project to be created.
        :type project_name: str
        :return: Response containing the created project.
        :rtype: Dict[str, Any]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use folder.create_folder() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.project.create_project(project_name)

    # Maps endpoints
    def get_folder_maps(self, folder_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Use folder.get_folder_maps() instead. Will be removed in a future version.

        Fetches a list of maps associated with a specific folder.

        :param folder_id: A UUID identifying the folder whose maps are being fetched.
        :type folder_id: uuid.UUID
        :return: A list of dictionaries containing map data. Each dictionary represents
                 a map associated with the specified folder.
        :rtype: List[Dict[str, Any]]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use folder.get_folder_maps() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.folder.get_folder_maps(folder_id)

    def get_project_maps(self, project_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Use folder.get_folder_maps() instead. Will be removed in a future version.

        Fetches a list of maps associated with a specific project.

        :param project_id: A UUID identifying the project whose maps are being fetched.
        :type project_id: uuid.UUID
        :return: A list of dictionaries containing map data. Each dictionary represents
                 a map associated with the specified project.
        :rtype: List[Dict[str, Any]]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use folder.get_folder_maps() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.project.get_project_maps(project_id)

    def get_public_maps(self, sort_by: str = None, page: int = None, page_size: int = None) -> Dict[str, Any]:
        """
        DEPRECATED: Use maps.get_public_maps() instead. Will be removed in a future version.

        Fetches a list of public maps with optional sorting and pagination.

        This method retrieves the available public maps from the server. The results
        can be customized by specifying the sorting criteria, the page number to
        retrieve, and the desired number of results per page.

        You can omit any of the optional parameters if their functionality is not
        required.

        :param sort_by: Specifies the field by which the public maps should be sorted.
            Optional parameter.
        :param page: Determines the page index to retrieve if the results are paginated.
            Optional parameter.
        :param page_size: Defines the number of results to return per page. Optional
            parameter.
        :return: A list of dictionaries where each dictionary represents a public map
            and its associated details.
        :rtype: List[Dict[str, Any]]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use maps.get_public_maps() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.maps.get_public_maps(sort_by, page, page_size)

    def search_maps(self, query: str = None, map_type: str = None, tags: List[str] = None, author_uid: str = None) -> \
    List[Dict[str, Any]]:
        """
        DEPRECATED: Use maps.search_maps() instead. Will be removed in a future version.

        Searches for maps based on the specified criteria and returns a list of matching maps.
        This method allows the user to search through maps by specifying various filters like
        query string, map type, associated tags, or author unique identifier. Results are returned
        as a list of dictionaries with the matching maps' details.

        :param query: A string used to search for maps with matching titles, descriptions, or
                      other relevant fields. Defaults to None if not specified.
        :param map_type: A string indicating the type/category of maps to filter the search by.
                         Defaults to None if not specified.
        :param tags: A list of strings representing specific tags to filter the maps. Only maps
                     associated with any of these tags will be included in the results. Defaults
                     to None if not specified.
        :param author_uid: A string representing the unique identifier of the author. Filters
                           the search to include only maps created by this author. Defaults to
                           None if not specified.
        :return: A list of dictionaries, each containing details of a map that matches the
                 specified search criteria.
        :rtype: List[Dict[str, Any]]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use maps.search_maps() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.maps.search_maps(query, map_type, tags, author_uid)

    # Map endpoints
    def get_map(self, map_id: uuid.UUID) -> Dict[str, Any]:
        """
        DEPRECATED: Use map.get_map() instead. Will be removed in a future version.

        Retrieves a map resource based on the provided map ID.

        :param map_id: The unique identifier of the map to retrieve.
        :type map_id: uuid.UUID
        :return: The specified map.
        :rtype: Dict[str, Any]
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use map.get_map() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.maps.get_map(map_id)

    def get_thumbnail(self, map_id: uuid.UUID) -> bytes:
        """
        DEPRECATED: Use map.get_thumbnail() instead. Will be removed in a future version.

        Fetches the thumbnail image for a given map using its unique identifier.

        :param map_id: The universally unique identifier (UUID) of the map for
                       which the thumbnail image is to be fetched.
        :type map_id: uuid.UUID
        :return: The binary content of the thumbnail image associated with the
                 specified map.
        :rtype: bytes
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use map.get_thumbnail() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.maps.get_thumbnail(map_id)

    def get_tiler_url(self, map_id: uuid.UUID, version_id: uuid.UUID = None, alias: str = None) -> str:
        """
        DEPRECATED: Use map.get_tiler_url() instead. Will be removed in a future version.

        Constructs a request to retrieve the tiler URL for a given map.

        :param map_id: The UUID of the map for which the tiler URL is being requested.
        :param version_id: An optional UUID specifying the particular version of the
            map to retrieve the tiler URL for.
        :param alias: An optional string specifying an alias for the map version.
        :return: A string representing the tiler URL.
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use map.get_tiler_url() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.maps.get_tiler_url(map_id, version_id, alias)

    def get_layer_info(self, map_id: uuid.UUID, version_id: uuid.UUID = None, alias: str = None) -> Dict[str, Any]:
        """
        DEPRECATED: Use map.get_layer_info() instead. Will be removed in a future version.

        Constructs a request to retrieve layer information for a given map.

        :param map_id: The UUID of the map for which the layer information is being requested.
        :param version_id: An optional UUID specifying the particular version of the
            map to retrieve the layer information for.
        :param alias: An optional string specifying an alias for the map version.
        :return: A dictionary containing layer information.
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use map.get_layer_info() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.maps.get_layer_info(map_id, version_id, alias)

    def upload_map(self, map_name: str, folder_id: uuid.UUID = None, project_id: uuid.UUID = None, public: bool = False,
                   path: str = None):
        """
        DEPRECATED: Use map.upload_map() instead. Will be removed in a future version.

        Uploads a map to the server.

        :param map_name: The name of the map to be uploaded.
        :type map_name: str
        :param folder_id: The unique identifier of the folder to which the map belongs.
        :type folder_id: uuid.UUID
        :param project_id: DEPRECATED: Use folder_id instead. The unique identifier of the project to which the map belongs.
        :type project_id: uuid.UUID
        :param public: A flag indicating whether the map should be publicly accessible or not.
        :type public: bool
        :param path: The file path to the map data to be uploaded.
        :type path: str
        :return: The response returned from the server after processing the map upload request.
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use map.upload_map() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.maps.upload_map(map_name, folder_id, project_id, public, path)

    def download_map(self, map_id: uuid.UUID, path: str):
        """
        DEPRECATED: Use map.download_map() instead. Will be removed in a future version.

        Downloads a map from a remote server and saves it to the specified path.

        :param map_id: Identifier of the map to download.
        :type map_id: uuid.UUID
        :param path: File system path where the downloaded map will be stored.
        :type path: str
        :return: None
        """
        warnings.warn(
            "Direct endpoint methods are deprecated. Use map.download_map() instead. "
            "This method will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.maps.download_map(map_id, path)


if __name__ == "__main__":
    client = MapHubClient("19Vnp5vD6P0CG7d61fr2dkfic7Z5nk7gE-xAntxppXI", "http://localhost:8000")

    # print(client.get_thumbnail(uuid.UUID("0161e302-d82f-4e52-9041-52037f210ac9")))
    # print(client.get_tiler_url(uuid.UUID("0161e302-d82f-4e52-9041-52037f210ac9")))
    print(client.get_public_maps())
    # client.download_map(uuid.UUID("0161e302-d82f-4e52-9041-52037f210ac9"), "test.tif")
