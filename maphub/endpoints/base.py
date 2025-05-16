import requests
from typing import Optional
from ..exceptions import APIException


class BaseEndpoint:
    """Base class for all endpoint classes."""

    def __init__(self, api_key: Optional[str], base_url: str, session: Optional[requests.Session] = None):
        """
        Initialize the base endpoint.

        :param api_key: The API key for authentication.
        :param base_url: The base URL for the API.
        :param session: An optional requests.Session object. If not provided, a new one will be created.
        """
        self.api_key = api_key
        self.base_url = base_url

        # Use the provided session or create a new one
        if session:
            self.session = session
        else:
            self.session = requests.Session()
            # Only update headers if we're creating a new session
            if self.api_key:
                self.session.headers.update({
                    "X-API-Key": f"{self.api_key}"
                })

    def _make_request(self, method: str, endpoint: str, **kwargs):
        """
        Make a request to the API.

        :param method: The HTTP method to use.
        :param endpoint: The API endpoint to call.
        :param kwargs: Additional arguments to pass to the request.
        :return: The response from the API.
        :raises APIException: If the API returns an error.
        """
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
