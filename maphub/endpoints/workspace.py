import uuid
from typing import Dict, Any, Optional

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