import uuid
from typing import Dict, Any
import requests


class MapHubClient:
    def __init__(self, api_key: str | None, base_url: str = "https://api-main-432878571563.europe-west4.run.app"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({
                "X-API-Key": f"{self.api_key}"
            })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        response = self.session.request(
            method,
            f"{self.base_url}/{endpoint.lstrip('/')}",
            **kwargs
        )
        try:
            response.raise_for_status()
        except:
            raise Exception(f"Status code {response.status_code}: {response.text}")

        return response.json()

    def get_map(self, map_id: uuid.UUID) -> Dict[str, Any]:
        return self._make_request("GET", f"/maps/{map_id}")

    def upload_map(self, map_name: str, project_id: uuid.UUID, public: bool, path: str):
        params = {
            "project_id": str(project_id),
            "map_name": map_name,
            "public": public,
            # "colormap": "viridis",
            # "vector_lod": 8,
        }

        with open(path, "rb") as f:
            return self._make_request("POST", f"/maps", params=params, files={"file": f})
