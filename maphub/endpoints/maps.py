import json
import uuid
import warnings
from typing import Dict, Any, Optional, List

from .base import BaseEndpoint


class MapsEndpoint(BaseEndpoint):
    """Endpoints for map operations (single map)."""
    
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
        
        if version_id is not None:
            params["version_id"] = version_id
        
        if alias is not None:
            params["alias"] = alias
        
        return self._make_request("GET", f"/maps/{map_id}/tiler_url", params=params).json()
    
    def get_layer_info(self, map_id: uuid.UUID, version_id: uuid.UUID = None, alias: str = None) -> Dict[str, Any]:
        """
        Constructs a request to retrieve layer information for a given map.
        
        :param map_id: The UUID of the map for which the layer information is being requested.
        :param version_id: An optional UUID specifying the particular version of the
            map to retrieve the layer information for.
        :param alias: An optional string specifying an alias for the map version.
        :return: A dictionary containing layer information.
        """
        params = {}
        
        if version_id is not None:
            params["version_id"] = version_id
        
        if alias is not None:
            params["alias"] = alias
        
        return self._make_request("GET", f"/maps/{map_id}/layer_info", params=params).json()
    
    def upload_map(self, map_name: str, folder_id: uuid.UUID = None, public: bool = False,
                   path: str = None) -> Dict[str, Any]:
        """
        Uploads a map to the server.
        
        :param map_name: The name of the map to be uploaded.
        :type map_name: str
        :param folder_id: The unique identifier of the folder to which the map belongs.
        :type folder_id: uuid.UUID
        :param public: A flag indicating whether the map should be publicly accessible or not.
        :type public: bool
        :param path: The file path to the map data to be uploaded.
        :type path: str
        :return: The response returned from the server after processing the map upload request.
        """
        if folder_id is None:
            raise ValueError("folder_id must be provided")
        
        params = {
            "folder_id": str(folder_id),
            "map_name": map_name,
            "public": public,
            # "colormap": "viridis",
            # "vector_lod": 8,
        }
        
        with open(path, "rb") as f:
            return self._make_request("POST", f"/maps", params=params, files={"file": f}).json()
    
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

    def set_visuals(self, map_id: uuid.UUID, visuals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates the visuals configuration of a specified map by sending a POST request
        to the corresponding API endpoint with the provided data.

        :param map_id: Unique identifier for the map.
        :param visuals: Dictionary containing the details of the visuals configuration
                        to apply to the map.
        :return: The response obtained from executing the request to the API as returned
                 by the `_make_request` method.
        """
        return self._make_request("PUT", f"/maps/{map_id}/visuals", data=json.dumps(visuals)).json()


    ### Maps endpoints
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

    def search_maps(self, query: str = None, map_type: str = None, tags: List[str] = None, author_uid: str = None) -> \
            List[Dict[str, Any]]:
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