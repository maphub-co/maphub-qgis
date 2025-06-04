import uuid
from typing import Dict, Any, Optional, List

from .base import BaseEndpoint


class WorkspaceEndpoint(BaseEndpoint):
    """Endpoints for workspace operations."""
    
    def get_personal_workspace(self) -> Dict[str, Any]:
        """
        Fetches the details of a specific workspace based on the provided folder ID.
        
        :return: A dictionary containing the workspace details.
        :rtype: Dict[str, Any]
        """
        return self._make_request("GET", "/workspaces/personal").json()

    def get_workspaces(self) -> List[Dict[str, Any]]:
        """
        Retrieves a dictionary containing the information about available workspaces
        by making a GET request to the `/workspaces` endpoint.

        :return: A dictionary where the keys are strings and the values are of any
            type. This dictionary represents the response from the `/workspaces`
            endpoint.
        :rtype: Dict[str, Any]
        """
        return self._make_request("GET", "/workspaces").json()