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

        return response.json()

    # Project endpoints
    def get_project(self, project_id: uuid.UUID) -> Dict[str, Any]:
        """
        Fetches the details of a specific project based on the provided project ID.

        :param project_id: The unique identifier of the project to be retrieved.
        :type project_id: uuid.UUID
        :return: A dictionary containing the project details.
        :rtype: Dict[str, Any]
        """
        return self._make_request("GET", f"/projects/{project_id}")

    def get_projects(self) -> List[Dict[str, Any]]:
        """
        Fetches a list of projects.

        :raises APIError: If there is an error during the API request.
        :return: A list of projects.
        :rtype: List[Dict[str, Any]]
        """
        return self._make_request("GET", "/projects")

    def create_project(self, project_name: str) -> Dict[str, Any]:
        """
        Creates a new project with the given project name.

        :param project_name: The name of the project to be created.
        :type project_name: str
        :return: Response containing the created project.
        :rtype: Dict[str, Any]
        """
        return self._make_request("POST", "/projects", params={"project_name": project_name})

    # Map endpoints
    def get_map(self, map_id: uuid.UUID) -> Dict[str, Any]:
        """
        Retrieves a map resource based on the provided map ID.

        :param map_id: The unique identifier of the map to retrieve.
        :type map_id: uuid.UUID
        :return: The specified map.
        :rtype: Dict[str, Any]
        """
        return self._make_request("GET", f"/maps/{map_id}")

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

        return self._make_request("GET", f"/maps/{map_id}/tiler_url", params=params)

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
        response = self.session.get(f"{self.base_url}/maps/{map_id}/download")
        with open(path, "wb") as f:
            f.write(response.content)
