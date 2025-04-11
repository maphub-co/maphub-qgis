import json
import uuid
from typing import Dict, Any, List, Optional
import requests

from .exceptions import APIException


class MapHubClient:
    def __init__(self, api_key: Optional[str], base_url: str = "https://api-main-432878571563.europe-west4.run.app"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({
                "X-API-Key": f"{self.api_key}"
            })

    def _make_request(self, method: str, endpoint: str, **kwargs):
        response = self.session.request(
            method,
            f"{self.base_url}/{endpoint.lstrip('/')}",
            **kwargs
        )
        try:
            response.raise_for_status()
        except:
            raise APIException(response.status_code, response.json()['detail'])

        return response

    # Project endpoints
    def get_project(self, project_id: uuid.UUID) -> Dict[str, Any]:
        """
        Fetches the details of a specific project based on the provided project ID.

        :param project_id: The unique identifier of the project to be retrieved.
        :type project_id: uuid.UUID
        :return: A dictionary containing the project details.
        :rtype: Dict[str, Any]
        """
        return self._make_request("GET", f"/projects/{project_id}").json()

    def get_projects(self) -> List[Dict[str, Any]]:
        """
        Fetches a list of projects.

        :raises APIError: If there is an error during the API request.
        :return: A list of projects.
        :rtype: List[Dict[str, Any]]
        """
        return self._make_request("GET", "/projects").json()

    def create_project(self, project_name: str) -> Dict[str, Any]:
        """
        Creates a new project with the given project name.

        :param project_name: The name of the project to be created.
        :type project_name: str
        :return: Response containing the created project.
        :rtype: Dict[str, Any]
        """
        return self._make_request("POST", "/projects", params={"project_name": project_name}).json()

    # Maps endpoints
    def get_project_maps(self, project_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        Fetches a list of maps associated with a specific project.

        :param project_id: A UUID identifying the project whose maps are being fetched.
        :type project_id: uuid.UUID
        :return: A list of dictionaries containing map data. Each dictionary represents
                 a map associated with the specified project.
        :rtype: List[Dict[str, Any]]
        """
        return self._make_request("GET", f"/maps", params={"project_id": project_id}).json()

    def get_public_maps(self, sort_by: str = None, page: int = None, page_size: int = None) -> Dict[str, Any]:
        """
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
        params = {}
        if sort_by:
            params["sort_by"] = sort_by
        if page:
            params["page"] = page
        if page_size:
            params["page_size"] = page_size

        return self._make_request("GET", "/maps/list", params=params).json()

    def search_maps(self, query: str = None, map_type: str = None, tags: List[str] = None, author_uid: str = None) -> List[Dict[str, Any]]:
        """
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
        return self._make_request("POST", "/maps/search", data=json.dumps({
            "search_query": query,
            "map_type": map_type,
            "tags": tags,
            "author_uid": author_uid,
        })).json()

    # Map endpoints
    def get_map(self, map_id: uuid.UUID) -> Dict[str, Any]:
        """
        Retrieves a map resource based on the provided map ID.

        :param map_id: The unique identifier of the map to retrieve.
        :type map_id: uuid.UUID
        :return: The specified map.
        :rtype: Dict[str, Any]
        """
        return self._make_request("GET", f"/maps/{map_id}").json()

    def get_thumbnail(self, map_id: uuid.UUID) -> bytes:
        """
        Fetches the thumbnail image for a given map using its unique identifier.

        :param map_id: The universally unique identifier (UUID) of the map for
                       which the thumbnail image is to be fetched.
        :type map_id: uuid.UUID
        :return: The binary content of the thumbnail image associated with the
                 specified map.
        :rtype: bytes
        """
        return self._make_request("GET", f"/maps/{map_id}/thumbnail").content

    def get_tiler_url(self, map_id: uuid.UUID, version_id: uuid.UUID = None, alias: str = None) -> str:
        """
        Constructs a request to retrieve the tiler URL for a given map.

        :param map_id: The UUID of the map for which the tiler URL is being requested.
        :param version_id: An optional UUID specifying the particular version of the
            map to retrieve the tiler URL for.
        :param alias: An optional string specifying an alias for the map version.
        :return: A string representing the tiler URL.
        """
        params = {}

        if version_id is None:
            params["version_id"] = version_id

        if alias is None:
            params["alias"] = alias

        return self._make_request("GET", f"/maps/{map_id}/tiler_url", params=params).json()

    def get_layer_info(self, map_id: uuid.UUID, version_id: uuid.UUID = None, alias: str = None) -> Dict[str, Any]:
        """
        Constructs a request to retrieve the tiler URL for a given map.

        :param map_id: The UUID of the map for which the tiler URL is being requested.
        :param version_id: An optional UUID specifying the particular version of the
            map to retrieve the tiler URL for.
        :param alias: An optional string specifying an alias for the map version.
        :return: A string representing the tiler URL.
        """
        params = {}

        if version_id is None:
            params["version_id"] = version_id

        if alias is None:
            params["alias"] = alias

        return self._make_request("GET", f"/maps/{map_id}/layer_info", params=params).json()

    def upload_map(self, map_name: str, project_id: uuid.UUID, public: bool, path: str):
        """
        Uploads a map to the server.

        :param map_name: The name of the map to be uploaded.
        :type map_name: str
        :param project_id: The unique identifier of the project to which the map belongs.
        :type project_id: uuid.UUID
        :param public: A flag indicating whether the map should be publicly accessible or not.
        :type public: bool
        :param path: The file path to the map data to be uploaded.
        :type path: str
        :return: The response returned from the server after processing the map upload request.
        """
        params = {
            "project_id": str(project_id),
            "map_name": map_name,
            "public": public,
            # "colormap": "viridis",
            # "vector_lod": 8,
        }

        with open(path, "rb") as f:
            return self._make_request("POST", f"/maps", params=params, files={"file": f})

    def download_map(self, map_id: uuid.UUID, path: str):
        """
        Downloads a map from a remote server and saves it to the specified path.

        :param map_id: Identifier of the map to download.
        :type map_id: uuid.UUID
        :param path: File system path where the downloaded map will be stored.
        :type path: str
        :return: None
        """
        response = self._make_request("GET", f"/maps/{map_id}/download")
        with open(path, "wb") as f:
            f.write(response.content)
