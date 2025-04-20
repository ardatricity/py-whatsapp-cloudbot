# wa_cloud/http_client.py

"""
Internal asynchronous HTTP client utility.

This module provides a centralized function (`make_request`) for sending
HTTP requests, primarily intended for use by the `wa_cloud.Bot` class to interact
with the WhatsApp Cloud API. It leverages the `httpx` library.
"""

import httpx # Async HTTP client library
import logging
import json
from typing import Optional, Dict, Any, Union
from http.client import responses as http_responses # For status code descriptions

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests in seconds. Can be overridden per-request.
DEFAULT_TIMEOUT = 15.0

async def make_request(
    method: str,
    url: Union[str, httpx.URL], # Allow httpx.URL objects as well
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None, # For multipart/form-data uploads
    timeout: Optional[float] = None # Allow overriding default timeout
) -> httpx.Response:
    """
    Sends an asynchronous HTTP request using httpx and handles basic exceptions.

    This function creates a new httpx.AsyncClient for each request to ensure
    isolation, though connection pooling might be less efficient for high volumes.
    It raises httpx exceptions on network errors or bad status codes, which
    are expected to be caught and translated by the calling code (e.g., Bot class).

    Args:
        method: The HTTP method (e.g., "GET", "POST", "DELETE").
        url: The target URL as a string or httpx.URL object.
        headers: Optional dictionary of request headers.
        params: Optional dictionary of query string parameters.
        json_data: Optional dictionary to send as JSON request body.
        files: Optional dictionary for multipart/form-data file uploads.
               Format: {'file': ('filename.jpg', file_object, 'image/jpeg')}
        timeout: Optional request timeout in seconds. Uses DEFAULT_TIMEOUT if None.

    Returns:
        The httpx.Response object on success.

    Raises:
        httpx.TimeoutException: If the request times out.
        httpx.HTTPStatusError: If the server returns a 4xx or 5xx status code.
        httpx.RequestError: For other network-level errors (DNS, connection, etc.).
    """
    request_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
    url_str = str(url) # Ensure URL is string for logging

    # Use an isolated client per request for simplicity.
    # For very high throughput, consider managing a persistent client instance.
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        try:
            # Log the request initiation at DEBUG level
            logger.debug(
                f"Sending API Request: {method} {url_str} "
                f"| Params: {params is not None} "
                f"| JSON: {json_data is not None} "
                f"| Files: {files is not None}"
            )

            response = await client.request(
                method=method,
                url=url, # httpx handles both str and URL objects
                headers=headers,
                params=params,
                json=json_data, # httpx handles JSON encoding
                files=files,   # httpx handles multipart encoding
            )

            # Log the response status at DEBUG level
            status_description = http_responses.get(response.status_code, "Unknown Status")
            logger.debug(f"Received API Response: {response.status_code} {status_description} from {response.url}")

            # Check if the response status code indicates an error (4xx or 5xx).
            # This will raise an httpx.HTTPStatusError if it's an error status.
            response.raise_for_status()

            # Return the successful response object
            return response

        except httpx.TimeoutException as e:
            # Log timeout errors specifically
            logger.error(f"API request timed out after {request_timeout}s: {method} {url_str}")
            raise # Re-raise for the caller (Bot class) to handle

        except httpx.HTTPStatusError as e:
            # Log HTTP status errors, including response text snippet for context
            response_text_snippet = e.response.text[:200] # Log only the beginning
            logger.error(
                f"API request failed with status {e.response.status_code} {http_responses.get(e.response.status_code, '')}: "
                f"{method} {e.request.url} "
                f"| Response: '{response_text_snippet}{'...' if len(e.response.text) > 200 else ''}'"
            )
            raise # Re-raise for the caller (Bot class) to translate

        except httpx.RequestError as e:
            # Log other network-level errors (connection, DNS, etc.)
            logger.error(f"Network error during API request: {method} {e.request.url} - {e}")
            raise # Re-raise for the caller (Bot class) to handle
        except Exception as e:
             # Catch any other unexpected exceptions during the request process
             logger.exception(f"Unexpected error in make_request for {method} {url_str}")
             raise # Re-raise the original unexpected error