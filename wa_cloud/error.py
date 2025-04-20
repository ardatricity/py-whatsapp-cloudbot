# wa_cloud/error.py

"""
Custom exception classes used by the wa_cloud library.

These exceptions provide more specific information about errors encountered
during API interactions or internal library operations.
"""

from typing import Optional, Dict, Any

class WhatsAppError(Exception):
    """Base exception class for all custom errors raised by the wa_cloud library."""
    pass

class APIError(WhatsAppError):
    """
    Indicates an error returned directly by the WhatsApp Cloud API.

    This typically corresponds to HTTP status codes 4xx or 5xx, indicating
    issues with the request, authentication, rate limits, or server problems.

    Attributes:
        message (str): A description of the API error, often including details
                       parsed from the API's error response.
        response_data (Optional[Dict[str, Any]]): The parsed JSON error response
                                                  from the API, if available and parsable.
                                                  Contains fields like 'code', 'title', 'message', etc.
                                                  See: https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
    """
    def __init__(self, message: str, response_data: Optional[Dict[str, Any]] = None):
        """Initializes the APIError."""
        super().__init__(message)
        self.response_data = response_data

class NetworkError(WhatsAppError):
    """
    Indicates a failure during the HTTP request itself before receiving a full API response.

    This could be due to connection errors, DNS resolution failures, timeouts, etc.
    Typically wraps exceptions from the underlying HTTP client (e.g., `httpx`).
    """
    pass

class BadRequestError(APIError):
    """
    Indicates a client-side error due to an invalid request format or parameters.
    Corresponds to HTTP 400 errors, or sometimes 404 for non-existent resources
    when attempting GET/DELETE operations.
    """
    pass

class AuthenticationError(APIError):
    """
    Indicates an authentication problem, usually an invalid or expired API access token.
    Corresponds to HTTP 401 (Unauthorized) or 403 (Forbidden) errors.
    """
    pass

class RateLimitError(APIError):
    """
    Indicates that the application has exceeded the allowed number of API calls.
    Corresponds to HTTP 429 (Too Many Requests) errors. Check API rate limit documentation.
    """
    pass

class ServerError(APIError):
    """
    Indicates a problem on the WhatsApp server side prevented the request from being fulfilled.
    Corresponds to HTTP 5xx errors. These are typically temporary; retrying later may succeed.
    """
    pass

# Add other specific error subclasses here if needed in the future.
# For example, a specific error for invalid media types or sizes.
# class MediaError(BadRequestError):
#     """Indicates an error related to media processing (upload/download)."""
#     pass