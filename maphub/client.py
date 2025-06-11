import hashlib
import json
import uuid
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import requests

from .endpoints.workspace import WorkspaceEndpoint
from .endpoints.folder import FolderEndpoint
from .endpoints.project import ProjectEndpoint
from .endpoints.maps import MapsEndpoint
from .endpoints.versions import VersionEndpoint
from .exceptions import APIException


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
        self.versions = VersionEndpoint(api_key, base_url, self.session)

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
        DEPRECATED: Use maps.get_map() instead. Will be removed in a future version.

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
        DEPRECATED: Use maps.get_thumbnail() instead. Will be removed in a future version.

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
        DEPRECATED: Use maps.get_tiler_url() instead. Will be removed in a future version.

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
        DEPRECATED: Use maps.get_layer_info() instead. Will be removed in a future version.

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

    def upload_map(self, map_name: str, project_id: uuid.UUID = None, public: bool = False,
                   path: str = None):
        """
        DEPRECATED: Use maps.upload_map() instead. Will be removed in a future version.

        Uploads a map to the server.

        :param map_name: The name of the map to be uploaded.
        :type map_name: str
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
        return self.maps.upload_map(map_name, project_id, public, path)

    def download_map(self, map_id: uuid.UUID, path: str):
        """
        DEPRECATED: Use maps.download_map() instead. Will be removed in a future version.

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

    # Helper methods for clone, pull, and push operations
    def _calculate_checksum(self, file_path: str) -> str:
        """
        Calculate the MD5 checksum of a file.

        Args:
            file_path: Path to the file

        Returns:
            MD5 checksum as a hexadecimal string
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _get_file_path_for_map(self, map_data: Dict[str, Any], save_dir: Path) -> str:
        """
        Determine the file path for a map based on its metadata.

        Args:
            map_data: Map metadata
            save_dir: Directory to save the map in

        Returns:
            File path for the map
        """
        # Get the map name and type
        map_name = map_data.get("name", "unnamed")
        map_type = map_data.get("type", "unknown")

        # Sanitize the map name for use as a filename
        map_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in map_name)

        # Determine the file extension based on the map type
        extension = ".fgb"  # Default to FlatGeoBuf
        if map_type == "raster":
            extension = ".tif"
        elif map_type == "vector":
            extension = ".fgb"  # FlatGeoBuf format

        # Create the file path
        file_path = str(save_dir / f"{map_name}{extension}")

        return file_path

    def _save_map_metadata(self, map_data: Dict[str, Any], map_id: uuid.UUID, file_path: str, output_dir: Path, maphub_dir: Path) -> None:
        """
        Save map metadata to the .maphub directory.

        Args:
            map_data: Map metadata
            map_id: UUID of the map
            file_path: Path to the map file
            output_dir: Root directory of the repository
            maphub_dir: Path to the .maphub directory
        """
        # Create metadata
        metadata = {
            "id": str(map_id),
            "name": map_data.get("name", "unnamed"),
            "type": map_data.get("type", "unknown"),
            "version_id": map_data["latest_version_id"],
            "checksum": self._calculate_checksum(file_path),
            "path": str(Path(file_path).relative_to(output_dir)),
            "last_modified": map_data.get("updated_at")
        }

        # Save metadata
        with open(maphub_dir / "maps" / f"{map_id}.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def _save_folder_metadata(self, folder_id: uuid.UUID, folder_name: str, parent_id: Optional[str], maps: List[str], subfolders: List[str], maphub_dir: Path) -> None:
        """
        Save folder metadata to the .maphub directory.

        Args:
            folder_id: UUID of the folder
            folder_name: Name of the folder
            parent_id: UUID of the parent folder, or None if this is a root folder
            maps: List of map IDs in this folder
            subfolders: List of subfolder IDs in this folder
            maphub_dir: Path to the .maphub directory
        """
        # Create metadata
        metadata = {
            "id": str(folder_id),
            "name": folder_name,
            "parent_id": parent_id,
            "maps": maps,
            "subfolders": subfolders
        }

        # Save metadata
        with open(maphub_dir / "folders" / f"{folder_id}.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def _save_folder_metadata_recursive(self, folder_id: uuid.UUID, root_dir: Path, maphub_dir: Path) -> None:
        """
        Recursively save metadata for a folder and its contents.

        Args:
            folder_id: UUID of the folder
            root_dir: Root directory of the repository
            maphub_dir: Path to the .maphub directory
        """
        # Get folder info
        folder_info = self.folder.get_folder(folder_id)
        folder_name = folder_info.get("folder", {}).get("name", "root")

        # Track maps and subfolders
        map_ids = []
        subfolder_ids = []

        # Process maps
        maps = folder_info["map_infos"]
        for map_data in maps:
            map_id = uuid.UUID(map_data["id"])
            map_ids.append(str(map_id))

            # Save map metadata
            file_path = self._get_file_path_for_map(map_data, root_dir / folder_name)
            self._save_map_metadata(map_data, map_id, file_path, root_dir, maphub_dir)

        # Process subfolders
        subfolders = folder_info["child_folders"]
        for subfolder in subfolders:
            subfolder_id = uuid.UUID(subfolder["id"])
            subfolder_ids.append(str(subfolder_id))

            # Recursively save metadata for subfolders
            self._save_folder_metadata_recursive(subfolder_id, root_dir / folder_name, maphub_dir)

        # Save folder metadata
        parent_id = folder_info.get("folder", {}).get("parent_folder_id")
        self._save_folder_metadata(folder_id, folder_name, parent_id, map_ids, subfolder_ids, maphub_dir)

    def _init_dot_maphub_dir(self, folder_id: uuid.UUID, path: Path) -> Path:
        # Then create .maphub directory inside the cloned folder
        maphub_dir = path / ".maphub"
        maphub_dir.mkdir(exist_ok=True)
        (maphub_dir / "maps").mkdir(exist_ok=True)
        (maphub_dir / "folders").mkdir(exist_ok=True)

        # Save config
        with open(maphub_dir / "config.json", "w") as f:
            json.dump({
                "remote_id": str(folder_id),
                "last_sync": datetime.now().isoformat()
            }, f, indent=2)

        return maphub_dir

    # Main methods for clone, pull, and push operations
    def clone_map(self, map_id: uuid.UUID, output_dir: Path, maphub_dir: Path) -> None:
        """
        Clone a single map from MapHub.

        Args:
            map_id: UUID of the map to clone
            output_dir: Directory to save the map in
            maphub_dir: Path to the .maphub directory
        """
        try:
            map_data = self.maps.get_map(map_id)['map']
            print(f"Cloning map: {map_data.get('name', 'Unnamed Map')}")

            # Get the file path for the map
            file_path = self._get_file_path_for_map(map_data, output_dir)

            # Download the map
            self.maps.download_map(map_id, file_path)

            # Save map metadata
            self._save_map_metadata(map_data, map_id, file_path, output_dir, maphub_dir)

            print(f"Successfully cloned map to {file_path}")
        except Exception as e:
            print(f"Error cloning map {map_id}: {e}")
            raise

    def pull_map(self, map_id: uuid.UUID, map_metadata: Dict[str, Any], root_dir: Path, maphub_dir: Path) -> None:
        """
        Pull updates for a single map from MapHub.

        Args:
            map_id: UUID of the map to pull
            map_metadata: Current map metadata
            root_dir: Root directory of the repository
            maphub_dir: Path to the .maphub directory
        """
        try:
            # Get the latest map info
            map_data = self.maps.get_map(map_id)['map']

            # Check if the version has changed
            if map_data["latest_version_id"] != map_metadata["version_id"]:
                print(f"Pulling updates for map: {map_data.get('name', 'Unnamed Map')}")

                # Get the current map path
                map_path = root_dir / map_metadata["path"]

                # Get the new file path for the map
                file_path = self._get_file_path_for_map(map_data, map_path.parent)

                # Download the map
                self.maps.download_map(map_id, file_path)

                # Update metadata
                map_metadata["version_id"] = map_data["latest_version_id"]
                map_metadata["checksum"] = map_data.get("checksum", self._calculate_checksum(file_path))
                map_metadata["last_modified"] = map_data.get("updated_at")
                map_metadata["path"] = str(Path(file_path).relative_to(root_dir))
                map_metadata["type"] = map_data.get("type", "unknown")

                with open(maphub_dir / "maps" / f"{map_id}.json", "w") as f:
                    json.dump(map_metadata, f, indent=2)

                print(f"Successfully updated map: {map_data.get('name', 'Unnamed Map')}")
            else:
                print(f"Map is already up to date: {map_data.get('name', 'Unnamed Map')}")
        except Exception as e:
            print(f"Error pulling map {map_id}: {e}")

    def push_map(self, map_id: uuid.UUID, map_metadata: Dict[str, Any], root_dir: Path, maphub_dir: Path,
                 version_description: Optional[str] = None) -> None:
        """
        Push updates for a single map to MapHub.

        Args:
            map_id: UUID of the map to push
            map_metadata: Current map metadata
            root_dir: Root directory of the repository
            maphub_dir: Path to the .maphub directory
            version_description: Optional description for the new version
        """
        try:
            # Check if the local file has changed
            map_path = root_dir / map_metadata["path"]

            if not map_path.exists():
                print(f"Warning: Map file not found: {map_path}")
                return

            current_checksum = self._calculate_checksum(str(map_path))

            if current_checksum != map_metadata["checksum"]:
                print(f"Pushing updates for map: {map_path.stem}")

                # Set default version description if not provided
                if version_description is None:
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    version_description = f"Update from CLI at {current_time}"

                # Upload a new version of the map using version endpoint
                response = self.versions.upload_version(
                    map_id=map_id,
                    version_description=version_description,
                    path=str(map_path)
                )

                # Update metadata
                map_metadata["version_id"] = response["task_id"]
                map_metadata["checksum"] = response.get("checksum", current_checksum)
                map_metadata["last_modified"] = response.get("updated_at")

                with open(maphub_dir / "maps" / f"{map_id}.json", "w") as f:
                    json.dump(map_metadata, f, indent=2)

                print(f"Successfully pushed map updates: {map_path.stem}")
            else:
                print(f"No changes to push for map: {map_path.stem}")
        except Exception as e:
            print(f"Error pushing map {map_id}: {e}")

    def clone_folder(self, folder_id: uuid.UUID, local_path: Path, output_dir: Path,
                     maphub_dir: Optional[Path] = None) -> Path:
        """
        Recursively clone a folder and its contents from MapHub.

        Args:
            folder_id: UUID of the folder to clone
            local_path: Local path to save the folder in
            output_dir: Root directory of the repository
            maphub_dir: Path to the .maphub directory, or None if metadata should not be saved yet

        Returns:
            Path to the cloned folder
        """
        folder_info = self.folder.get_folder(folder_id)
        folder_name = folder_info.get("folder", {}).get("name", "root")

        print(f"Cloning folder: {folder_name}")

        # Create local folder
        folder_path = local_path / folder_name
        folder_path.mkdir(exist_ok=True)
        if maphub_dir is None:
            maphub_dir = self._init_dot_maphub_dir(folder_id, folder_path)

        # Track maps and subfolders
        map_ids = []
        subfolder_ids = []

        # Clone maps in this folder
        maps = folder_info["map_infos"]
        for map_data in maps:
            try:
                map_id = uuid.UUID(map_data["id"])
                self.clone_map(map_id, folder_path, maphub_dir)
                map_ids.append(str(map_id))
            except APIException as e:
                print(f"Skipping {map_data.get('id')}, Error: {e.status_code}, {e.message}")
                continue

        # Recursively clone subfolders
        subfolders = folder_info["child_folders"]

        for subfolder in subfolders:
            subfolder_id = uuid.UUID(subfolder["id"])
            subfolder_ids.append(str(subfolder_id))
            self.clone_folder(subfolder_id, folder_path, output_dir, maphub_dir)

        # Save folder metadata if maphub_dir is provided
        parent_id = folder_info.get("folder", {}).get("parent_folder_id")
        self._save_folder_metadata(folder_id, folder_name, parent_id, map_ids, subfolder_ids, maphub_dir)

        return folder_path


    def pull_folder(self, folder_id: uuid.UUID, local_path: Path, root_dir: Path, maphub_dir: Path) -> None:
        """
        Recursively pull updates for a folder and its contents from MapHub.

        Args:
            folder_id: UUID of the folder to pull
            local_path: Local path of the folder
            root_dir: Root directory of the repository
            maphub_dir: Path to the .maphub directory
        """
        try:
            # Load folder metadata
            with open(maphub_dir / "folders" / f"{folder_id}.json", "r") as f:
                folder_metadata = json.load(f)

            # Get folder info from server
            folder_info = self.folder.get_folder(folder_id)
            folder_name = folder_info.get("folder", {}).get("name", "root")

            print(f"Pulling updates for folder: {folder_name}")

            # Pull maps in this folder
            maps = folder_info["map_infos"]
            for map_data in maps:
                map_id = uuid.UUID(map_data["id"])

                # Check if we have metadata for this map
                map_file = maphub_dir / "maps" / f"{map_id}.json"
                if map_file.exists():
                    with open(map_file, "r") as f:
                        map_metadata = json.load(f)
                    self.pull_map(map_id, map_metadata, root_dir, maphub_dir)
                else:
                    try:
                        # New map, clone it
                        print(f"  New map found: {map_data.get('name', 'Unnamed Map')}")
                        map_id = uuid.UUID(map_data["id"])
                        self.clone_map(map_id, local_path, maphub_dir)

                        # Add to folder metadata
                        if str(map_id) not in folder_metadata["maps"]:
                            folder_metadata["maps"].append(str(map_id))
                    except APIException as e:
                        print(f"Skipping {map_data.get('id')}, Error: {e.status_code}, {e.message}")
                        continue

            # Pull subfolders
            subfolders = folder_info["child_folders"]
            for subfolder in subfolders:
                subfolder_id = uuid.UUID(subfolder["id"])
                subfolder_name = subfolder.get("name", "unnamed")

                # Check if we have metadata for this subfolder
                subfolder_file = maphub_dir / "folders" / f"{subfolder_id}.json"
                if subfolder_file.exists():
                    # Existing subfolder, pull it
                    subfolder_path = local_path / subfolder_name
                    self.pull_folder(subfolder_id, subfolder_path, root_dir, maphub_dir)
                else:
                    # New subfolder, clone it
                    print(f"  New subfolder found: {subfolder_name}")
                    self.clone_folder(subfolder_id, local_path, root_dir, maphub_dir)

                    # Add to folder metadata
                    if str(subfolder_id) not in folder_metadata["subfolders"]:
                        folder_metadata["subfolders"].append(str(subfolder_id))

            # Update folder metadata
            with open(maphub_dir / "folders" / f"{folder_id}.json", "w") as f:
                json.dump(folder_metadata, f, indent=2)

        except Exception as e:
            print(f"Error pulling folder {folder_id}: {e}")
            import traceback
            traceback.print_exc()

    def push_folder(self, folder_id: uuid.UUID, local_path: Path, root_dir: Path, maphub_dir: Path,
                    version_description: Optional[str] = None) -> None:
        """
        Recursively push updates for a folder and its contents to MapHub.

        Args:
            folder_id: UUID of the folder to push
            local_path: Local path of the folder
            root_dir: Root directory of the repository
            maphub_dir: Path to the .maphub directory
            version_description: Optional description for the new version
        """
        try:
            # Load folder metadata
            with open(maphub_dir / "folders" / f"{folder_id}.json", "r") as f:
                folder_metadata = json.load(f)

            folder_name = folder_metadata["name"]
            print(f"Pushing updates for folder: {folder_name}")

            # Push maps in this folder
            for map_id in folder_metadata["maps"]:
                # Load map metadata
                map_file = maphub_dir / "maps" / f"{map_id}.json"
                if map_file.exists():
                    with open(map_file, "r") as f:
                        map_metadata = json.load(f)
                    self.push_map(uuid.UUID(map_id), map_metadata, root_dir, maphub_dir, version_description)

            # Check for new GIS files in the folder
            gis_extensions = ['.gpkg', '.tif', '.fgb', '.shp', '.geojson']
            tracked_files = []

            # Get all tracked files from map metadata
            for map_id in folder_metadata["maps"]:
                map_file = maphub_dir / "maps" / f"{map_id}.json"
                if map_file.exists():
                    with open(map_file, "r") as f:
                        map_metadata = json.load(f)
                    tracked_files.append(root_dir / map_metadata["path"])

            # Find new GIS files
            for file_path in local_path.glob('*'):
                if file_path.is_file() and file_path.suffix.lower() in gis_extensions:
                    # Check if this file is already tracked
                    if file_path not in tracked_files:
                        print(f"Found new GIS file: {file_path}")

                        # Upload the new map
                        try:
                            map_name = file_path.stem
                            response = self.maps.upload_map(
                                map_name=map_name,
                                folder_id=folder_id,
                                public=False,
                                path=str(file_path)
                            )

                            # Get the map ID from the response
                            map_id = response.get("map_id")
                            if map_id:
                                print(f"Successfully uploaded new map: {map_name} with ID: {map_id}")

                                # Add the map to the folder metadata
                                folder_metadata["maps"].append(map_id)

                                # Save map metadata
                                map_data = {
                                    "id": map_id,
                                    "name": map_name,
                                    "type": "unknown",  # Could be determined based on file extension
                                    "version_id": response.get("id"),  # Version ID from response
                                    "latest_version_id": response.get("id"),
                                    "updated_at": response.get("created_time")  # Use created_time as updated_at
                                }

                                # Save the map metadata
                                self._save_map_metadata(
                                    map_data=map_data,
                                    map_id=uuid.UUID(map_id),
                                    file_path=str(file_path),
                                    output_dir=root_dir,
                                    maphub_dir=maphub_dir
                                )
                        except Exception as e:
                            print(f"Error uploading new map {file_path}: {e}")

            # Save updated folder metadata
            with open(maphub_dir / "folders" / f"{folder_id}.json", "w") as f:
                json.dump(folder_metadata, f, indent=2)

            # Push subfolders
            for subfolder_id in folder_metadata["subfolders"]:
                # Load subfolder metadata
                subfolder_file = maphub_dir / "folders" / f"{subfolder_id}.json"
                if subfolder_file.exists():
                    with open(subfolder_file, "r") as f:
                        subfolder_metadata = json.load(f)

                    subfolder_path = local_path / subfolder_metadata["name"]
                    self.push_folder(uuid.UUID(subfolder_id), subfolder_path, root_dir, maphub_dir, version_description)

        except Exception as e:
            print(f"Error pushing folder {folder_id}: {e}")
            import traceback
            traceback.print_exc()

    def clone(self, folder_id: uuid.UUID, output_dir: Path) -> Optional[Path]:
        """
        Clone a folder from MapHub to local directory.

        Args:
            folder_id: ID of the folder to clone
            output_dir: Path to the output directory
        """
        # Create output directory if it doesn't exist
        output_dir.mkdir(exist_ok=True)

        try:
            # For folders, first clone the folder structure
            result_path = self.clone_folder(folder_id, output_dir, output_dir, None)

            print(f"Successfully cloned folder structure to {result_path}")
            return result_path
        except Exception as e:
            print(f"Error: Failed to clone folder with ID {folder_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def pull(self, root_dir: Path) -> None:
        """
        Pull latest changes from MapHub.

        This method should be called from within a directory that was previously cloned.
        It will update any maps in the folder that have changed on the server.

        Args:
            root_dir: Root directory of the repository
        """
        maphub_dir = root_dir / ".maphub"

        # Load config
        try:
            with open(maphub_dir / "config.json", "r") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error: Failed to load MapHub configuration: {e}")
            raise

        # Get the remote ID
        folder_id = uuid.UUID(config["remote_id"])

        # Pull the folder
        try:
            self.pull_folder(folder_id, root_dir, root_dir, maphub_dir)

            # Update config
            config["last_sync"] = datetime.now().isoformat()
            with open(maphub_dir / "config.json", "w") as f:
                json.dump(config, f, indent=2)

            print("Pull completed successfully")
        except Exception as e:
            print(f"Error during pull: {e}")
            import traceback
            traceback.print_exc()
            raise

    def push(self, root_dir: Path, version_description: Optional[str] = None) -> None:
        """
        Push local changes to MapHub.

        This method should be called from within a directory that was previously cloned.
        It will upload any maps in the folder that have changed locally.

        Args:
            root_dir: Root directory of the repository
            version_description: Optional description for the new version
        """
        maphub_dir = root_dir / ".maphub"

        # Load config
        try:
            with open(maphub_dir / "config.json", "r") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error: Failed to load MapHub configuration: {e}")
            raise

        # Get the remote ID
        folder_id = uuid.UUID(config["remote_id"])

        # Push the folder
        try:
            self.push_folder(folder_id, root_dir, root_dir, maphub_dir, version_description)

            # Update config
            config["last_sync"] = datetime.now().isoformat()
            with open(maphub_dir / "config.json", "w") as f:
                json.dump(config, f, indent=2)

            print("Push completed successfully")
        except Exception as e:
            print(f"Error during push: {e}")
            import traceback
            traceback.print_exc()
            raise
