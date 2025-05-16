"""
Your package name and brief description.

Example:
    from maphub import MapHubClient

    client = MapHubClient(api_key="your-api-key")
    response = client.get_map(map_id="...")
"""

# Import the main client class and any important submodules
from .client import MapHubClient
from importlib import metadata


__version__ = metadata.version(__package__ or __name__)
__author__ = "MapHub"
__license__ = "MIT"

# Define what should be available when using "from package import *"
__all__ = ["MapHubClient"]


# Optional: You can provide a convenience function or default client instance
def create_client(api_key: str, **kwargs) -> MapHubClient:
    """
    Create an instance of the API client.

    Args:
        api_key: The API key for authentication
        **kwargs: Additional configuration options

    Returns:
        An initialized APIClient instance
    """
    return MapHubClient(api_key=api_key, **kwargs)
