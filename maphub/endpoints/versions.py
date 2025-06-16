import uuid
import os
import zipfile
import tempfile
from typing import Dict, Any

from .base import BaseEndpoint


class VersionEndpoint(BaseEndpoint):
    def get_versions(self, map_id: uuid.UUID) -> Dict[str, Any]:
        """
        Fetches the available versions for a given map.

        This method sends a GET request to fetch all versions associated with the
        given map identifier. The result is returned as a JSON object.

        :param map_id: The UUID of the map for which versions need to be fetched.
        :type map_id: uuid.UUID
        :return: A dictionary containing the versions related to the specified map.
        :rtype: Dict[str, Any]
        """
        return self._make_request("GET", f"/versions?map_id={map_id}").json()

    def upload_version(self, map_id: uuid.UUID, version_description: str, path: str) -> Dict[str, Any]:
        """
        Uploads a new version of a map with the given description and file. The method
        constructs the request parameters using the provided map ID and version
        description, and sends a POST request to upload the file located at the specified
        path. The response containing details about the upload is returned.

        :param map_id: Unique identifier of the map
        :type map_id: uuid.UUID
        :param version_description: Description of the new version being uploaded
        :type version_description: str
        :param path: Path to the file containing the map data to be uploaded
        :type path: str
        :return: Response in the form of a dictionary containing details about the
            uploaded version
        :rtype: Dict[str, Any]
        """
        params = {
            "map_id": str(map_id),
            "version_description": version_description,
        }

        with open(path, "rb") as f:
            return self._make_request("POST", f"/versions", params=params, files={"file": f}).json()

    def get_version(self, version_id: uuid.UUID) -> Dict[str, Any]:
        """
        Fetches the details of a specific version identified by the provided version_id.

        This method performs a GET request to retrieve the details associated with
        the given version_id. The response is returned as a dictionary containing
        the relevant data. The version_id parameter should be a valid UUID that
        is used to uniquely identify the version.

        :param version_id: The unique identifier (UUID) of the version to retrieve.
        :type version_id: uuid.UUID
        :return: A dictionary containing the details of the requested version.
        :rtype: Dict[str, Any]
        """
        return self._make_request("GET", f"/versions/{version_id}").json()

    def download_version(self, version_id: uuid.UUID, path: str, file_format: str = None):
        """
        Downloads a specific version of a resource and writes its content to a specified file path.

        This function sends an HTTP GET request to retrieve the content of the specified version
        using the version ID. The content is then written to the provided file path in binary mode.

        If file_format is "shp", the returned file is a zip file that will be extracted to the
        specified path.

        :param version_id: Unique identifier of the version to download.
        :type version_id: uuid.UUID
        :param path: The file path where the downloaded version content will be saved.
        :type path: str
        :param file_format: Defines the file format to be used for downloading the version.
        :type file_format: str | None
        :return: None
        """
        endpoint = f"/versions/{version_id}/download"

        if file_format:
            endpoint += f"?file_format={file_format}"

        response = self._make_request("GET", endpoint)

        # If file_format is "shp", the returned file is a zip file that needs to be extracted
        if file_format == "shp":
            # Create a temporary file to store the zip content
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip_file:
                temp_zip_path = temp_zip_file.name
                temp_zip_file.write(response.content)

            # Create a temporary directory for extraction
            temp_dir = tempfile.mkdtemp()

            try:
                # Extract the zip file to the temporary directory
                with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                # Get the target directory and base name from the path
                target_dir = os.path.dirname(os.path.abspath(path))
                base_name = os.path.basename(os.path.splitext(path)[0])

                # Create the target directory if it doesn't exist
                os.makedirs(target_dir, exist_ok=True)

                # Rename and move each file to the target directory
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path):
                        # Get the extension of the original file
                        _, ext = os.path.splitext(file)
                        # Create the new filename with the target base name and original extension
                        new_filename = f"{base_name}{ext}"
                        # Move and rename the file to the target directory
                        os.rename(file_path, os.path.join(target_dir, new_filename))
            finally:
                # Clean up the temporary zip file and directory
                if os.path.exists(temp_zip_path):
                    os.unlink(temp_zip_path)
                if os.path.exists(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir)
        else:
            # For other formats, just write the content to the file
            with open(path, "wb") as f:
                f.write(response.content)

    def set_alias(self, version_id: uuid.UUID, alias: str) -> Dict[str, Any]:
        """
        Sets or updates an alias for a specific version identified by its UUID. The alias is a
        string identifier that can be used to reference the version more conveniently.

        :param version_id: Unique identifier for the version to which the alias belongs
        :param alias: Alias to set or update for the specified version
        :return: Dictionary containing the response from the alias update operation
        :rtype: Dict[str, Any]
        """
        return self._make_request("PUT", f"/versions/{version_id}/alias?alias={alias}").json()
