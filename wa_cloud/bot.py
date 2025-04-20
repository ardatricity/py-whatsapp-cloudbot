# wa_cloud/bot.py

"""
This module defines the Bot class, which serves as the primary interface
for interacting with the WhatsApp Cloud API.
"""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Third-party imports
import httpx
from pydantic import HttpUrl # For type hinting and validation

# Library specific imports
from . import constants
from .error import (APIError, AuthenticationError, BadRequestError,
                    NetworkError, RateLimitError, ServerError, WhatsAppError)
from .http_client import make_request # Use the centralized request function
from .models import ( # Import necessary models for payloads and responses
    ContactSend, DeleteMediaResponse, ErrorData,
    InteractiveActionButton, InteractiveButton,
    InteractiveActionCtaUrl, InteractiveActionCtaUrlParameters,
    InteractiveActionFlow, InteractiveActionFlowParameters, InteractiveFlowActionPayload, # Added missing flow param model
    InteractiveActionList, InteractiveListSection, InteractiveListRow,
    InteractiveBody, InteractiveFooter, InteractiveHeader,
    InteractiveMessageSend, Location, MediaBase,
    MediaInfoResponse, ReactionSend, SendMessageResponse,
    SuccessResponse, TemplateSend, UploadMediaResponse
)

logger = logging.getLogger(__name__)

class Bot:
    """
    The main class representing the connection to the WhatsApp Cloud API.

    Provides methods for sending various message types, managing media,
    and handling message statuses. An instance of this class is required
    by the Application to perform API calls.

    Attributes:
        token (str): The API access token.
        phone_number_id (str): The WhatsApp Business Account Phone Number ID.
        base_url (str): The base URL for the WhatsApp Graph API.
        default_timeout (float): Default timeout for HTTP requests in seconds.
    """

    def __init__(
        self,
        token: str,
        phone_number_id: str,
        api_base_url: str = constants.DEFAULT_API_BASE_URL,
        default_timeout: float = 15.0,
    ):
        """
        Initializes the Bot instance.

        Args:
            token: The WhatsApp Cloud API access token (permanent or temporary).
            phone_number_id: The Phone Number ID associated with the WhatsApp Business Account.
            api_base_url: The base URL for the WhatsApp Graph API. Defaults to the value in `wa_cloud.constants`.
            default_timeout: Default timeout in seconds for API requests.

        Raises:
            ValueError: If token or phone_number_id is empty.
        """
        if not token:
            raise ValueError("API `token` cannot be empty.")
        if not phone_number_id:
            raise ValueError("`phone_number_id` cannot be empty.")

        self.token = token
        self.phone_number_id = phone_number_id
        # Ensure base URL does not end with a slash for consistent joining
        self.base_url = api_base_url.rstrip('/')
        self.default_timeout = default_timeout
        # Pre-compose the authorization header for reuse
        self._headers = {"Authorization": f"Bearer {self.token}"}
        logger.debug(f"Bot initialized for Phone Number ID: {self.phone_number_id}")

    def _resolve_url(self, template: str, **kwargs) -> str:
        """
        Constructs the full API endpoint URL from a template and arguments.

        Internal helper method.

        Args:
            template: An endpoint template string (e.g., from `constants`).
            **kwargs: Arguments to format the template (e.g., media_id).

        Returns:
            The fully constructed URL string.
        """
        # Format the template with the bot's phone ID and any other provided args
        endpoint = template.format(
            phone_number_id=self.phone_number_id,
            **kwargs
        ).lstrip('/') # Ensure the path part doesn't start with / after formatting
        return f"{self.base_url}/{endpoint}"

    async def _make_api_request(
        self,
        method: str,
        endpoint_template: str,
        endpoint_args: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Internal core method for making HTTP requests to the WhatsApp API.

        Handles URL construction, request execution via http_client.make_request,
        and wraps potential HTTP/network errors into library-specific exceptions.

        Args:
            method: HTTP method ("GET", "POST", "DELETE", etc.).
            endpoint_template: Endpoint template string from `constants`.
            endpoint_args: Dictionary to format the template.
            params: Query parameters for the URL.
            json_data: Dictionary for the JSON request body.
            files: Dictionary for multipart/form-data uploads.
            timeout: Request-specific timeout.

        Returns:
            The parsed JSON response dictionary.

        Raises:
            AuthenticationError: For 401/403 errors.
            BadRequestError: For 400 errors or resource not found (404 on GET/DELETE).
            RateLimitError: For 429 errors.
            ServerError: For 5xx errors.
            APIError: For other 4xx API errors.
            NetworkError: For connection errors, timeouts, etc.
            WhatsAppError: For unexpected library errors during the request.
        """
        url = self._resolve_url(endpoint_template, **(endpoint_args or {}))
        request_timeout = timeout if timeout is not None else self.default_timeout
        logger.debug(f"Making API request: {method} {url}")

        try:
            # Delegate the actual HTTP request to the http_client module
            response = await make_request(
                method=method,
                url=url,
                headers=self._headers,
                params=params,
                json_data=json_data,
                files=files,
                timeout=request_timeout
            )
            # make_request raises HTTPStatusError for 4xx/5xx responses
            return response.json() # Assume successful responses are JSON

        except httpx.HTTPStatusError as e:
            # Try to parse the detailed error from WhatsApp's JSON response
            response_data = None
            error_message = f"API Error {e.response.status_code}: {e.response.text[:500]}" # Default, truncated
            try:
                response_data = e.response.json()
                if isinstance(response_data, dict) and "error" in response_data:
                    # Use the ErrorData model for structured error info
                    api_error_detail = ErrorData.model_validate(response_data["error"])
                    error_message = (
                        f"API Error {e.response.status_code} ({api_error_detail.code} - {api_error_detail.title}): "
                        f"{api_error_detail.message or api_error_detail.details or 'No details provided.'}"
                    )
                    logger.error(f"WhatsApp API error detail: Code={api_error_detail.code}, Title='{api_error_detail.title}', Message='{api_error_detail.message}', Details='{api_error_detail.details}'")
            except Exception as parse_error:
                # Log if parsing the error response fails
                logger.warning(f"Could not parse JSON from API error response: {parse_error}")

            # Map HTTP status codes to specific library exceptions
            status_code = e.response.status_code
            if status_code in (401, 403):
                raise AuthenticationError(error_message, response_data=response_data) from e
            if status_code == 400:
                 raise BadRequestError(error_message, response_data=response_data) from e
            if status_code == 429:
                raise RateLimitError(error_message, response_data=response_data) from e
            # 404 is typically a BadRequest for non-POST requests (e.g., getting/deleting non-existent media)
            if status_code == 404 and method.upper() != "POST":
                 raise BadRequestError(f"Resource not found ({e.response.status_code}) for {method} {url}", response_data=response_data) from e
            if status_code >= 500:
                raise ServerError(error_message, response_data=response_data) from e
            # Fallback for other 4xx errors
            raise APIError(error_message, response_data=response_data) from e

        except httpx.TimeoutException as e:
             raise NetworkError(f"Request timed out after {request_timeout}s for {method} {url}") from e
        except httpx.RequestError as e:
            # Covers lower-level issues like connection refused, DNS errors
            raise NetworkError(f"Network request failed for {method} {url}: {e}") from e
        except Exception as e:
            # Catch-all for unexpected issues (e.g., JSON decoding errors on success response)
            logger.exception(f"Unexpected error during API request processing for {url}")
            raise WhatsAppError(f"Unexpected error during API request to {url}: {e}") from e

    # --- HTTP Method Convenience Wrappers ---

    async def _post(
        self,
        endpoint_template: str,
        payload: Optional[Dict[str, Any]] = None,
        endpoint_args: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Internal helper for POST requests, mapping `payload` to `json_data`."""
        return await self._make_api_request(
            method="POST",
            endpoint_template=endpoint_template,
            endpoint_args=endpoint_args,
            json_data=payload, # Map the 'payload' kwarg to 'json_data'
            files=files,
            timeout=timeout,
            params=kwargs.get('params') # Allow optional query params for POST if needed
        )

    async def _get(
        self,
        endpoint_template: str,
        endpoint_args: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Internal helper for GET requests."""
        return await self._make_api_request(
            method="GET",
            endpoint_template=endpoint_template,
            endpoint_args=endpoint_args,
            params=params,
            timeout=timeout,
            **kwargs # Allow passing other args if necessary
        )

    async def _delete(
        self,
        endpoint_template: str,
        endpoint_args: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Internal helper for DELETE requests."""
        return await self._make_api_request(
            method="DELETE",
            endpoint_template=endpoint_template,
            endpoint_args=endpoint_args,
            timeout=timeout,
            **kwargs # Allow passing other args if necessary
        )

    # --- General Message Sending Method ---

    async def send_message(self, payload: Dict[str, Any]) -> SendMessageResponse:
        """
        Sends a message using a pre-constructed payload dictionary.

        This is the base method called by more specific `send_...` methods.
        Direct use is discouraged unless sending custom or unsupported message types.

        Args:
            payload: The complete message request payload dictionary, conforming to the
                     WhatsApp Cloud API message object structure. See:
                     https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#message-object

        Returns:
            SendMessageResponse: A Pydantic model representing the API response.

        Raises:
            See `_make_api_request` for potential exceptions (APIError, NetworkError etc.).
        """
        message_type = payload.get('type', 'unknown')
        recipient = payload.get('to', 'unknown')
        logger.info(f"Sending message to: {recipient} - Type: {message_type}")

        # Set default 'messaging_product' if not present
        payload.setdefault("messaging_product", "whatsapp")
        # Set default 'recipient_type' unless it's a reaction message
        if "recipient_type" not in payload and message_type != constants.MessageType.REACTION.value:
            payload.setdefault("recipient_type", "individual")

        # Use the _post helper to send the payload
        response_data = await self._post(
            constants.MESSAGES_ENDPOINT_TEMPLATE,
            payload=payload
        )
        # Validate and return the response using the Pydantic model
        return SendMessageResponse.model_validate(response_data)

    # --- Specific Message Type Sending Methods ---

    async def send_text(
        self,
        to: str,
        text: str,
        preview_url: bool = False
    ) -> SendMessageResponse:
        """
        Sends a simple text message. Supports standard WhatsApp Markdown.

        Args:
            to: The recipient's WhatsApp ID (phone number E.164 format).
            text: The message body text (max 4096 characters). Can include Markdown.
            preview_url: If True, attempts to generate a link preview for the first URL in the text.

        Returns:
            SendMessageResponse: The API response model.

        Raises:
            ValueError: If `text` is empty.
            See `send_message` for other potential exceptions.
        """
        if not text:
            raise ValueError("Text message body cannot be empty.")
        # Truncate if exceeds limit, with a warning
        if len(text) > constants.MAX_TEXT_BODY_LENGTH:
            logger.warning(f"Text message exceeds max length {constants.MAX_TEXT_BODY_LENGTH}. Truncating.")
            text = text[:constants.MAX_TEXT_BODY_LENGTH]

        payload = {
            "to": to,
            "type": constants.MessageType.TEXT.value, # Use enum value for type safety
            "text": {"preview_url": preview_url, "body": text},
        }
        return await self.send_message(payload)

    def _prepare_media_payload_for_sending(
        self,
        msg_type: constants.MessageType,
        media_id: Optional[str] = None,
        link: Optional[Union[str, HttpUrl]] = None,
        **extra: Any # e.g., caption, filename
    ) -> Dict[str, Any]:
        """
        Internal helper to create the media object payload for sending messages.
        Validates that either ID or link is provided and handles optional fields.
        """
        if not (media_id or link):
            raise ValueError(f"Either 'media_id' or 'link' must be provided for sending {msg_type.value}")
        if media_id and link:
            logger.warning(f"Both 'media_id' and 'link' provided for {msg_type.value}. Using 'media_id'.")
            link = None # Prioritize ID if both are given

        media_obj: Dict[str, Any] = {}
        if media_id:
            media_obj["id"] = media_id
        elif link:
            # Ensure URL objects are converted to string for JSON serialization
            media_obj["link"] = str(link)

        # Add extra parameters like caption or filename
        for key, value in extra.items():
            if value is not None:
                # Apply length validation if applicable
                if key == "caption" and len(value) > constants.MAX_CAPTION_LENGTH:
                     logger.warning(f"Caption for {msg_type.value} exceeds max length {constants.MAX_CAPTION_LENGTH}. Truncating.")
                     media_obj[key] = value[:constants.MAX_CAPTION_LENGTH]
                # Add other potential validations here (e.g., filename format)
                else:
                     media_obj[key] = value

        return media_obj

    async def send_media(
        self,
        to: str,
        msg_type: constants.MessageType,
        media_id: Optional[str] = None,
        link: Optional[Union[str, HttpUrl]] = None,
        **extra: Any # caption, filename
    ) -> SendMessageResponse:
        """
        Internal base method for sending media messages (image, video, audio, document, sticker).

        Constructs the payload using `_prepare_media_payload_for_sending` and calls `send_message`.
        Users should generally use the specific `send_image`, `send_video`, etc. methods.

        Args:
            to: Recipient's WhatsApp ID.
            msg_type: The MessageType enum member (e.g., MessageType.IMAGE).
            media_id: The media ID (from upload) - preferred.
            link: A public HTTPS URL to the media - not recommended.
            **extra: Additional fields for the media object (e.g., caption, filename).

        Returns:
            SendMessageResponse: The API response model.
        """
        # Prepare the specific media object (e.g., {"id": "123", "caption": "..."})
        media_obj = self._prepare_media_payload_for_sending(msg_type, media_id, link, **extra)
        # Construct the main message payload
        payload = {
            "to": to,
            "type": msg_type.value,
            # The key for the media object matches the type (e.g., "image": {...})
            msg_type.value: media_obj,
        }
        return await self.send_message(payload)

    async def send_image(
        self,
        to: str,
        media_id: Optional[str] = None,
        link: Optional[Union[str, HttpUrl]] = None,
        caption: Optional[str] = None
    ) -> SendMessageResponse:
        """Sends an image message. Requires `media_id` (recommended) or `link`."""
        return await self.send_media(to, constants.MessageType.IMAGE, media_id, link, caption=caption)

    async def send_video(
        self,
        to: str,
        media_id: Optional[str] = None,
        link: Optional[Union[str, HttpUrl]] = None,
        caption: Optional[str] = None
    ) -> SendMessageResponse:
        """Sends a video message. Requires `media_id` (recommended) or `link`."""
        return await self.send_media(to, constants.MessageType.VIDEO, media_id, link, caption=caption)

    async def send_audio(
        self,
        to: str,
        media_id: Optional[str] = None,
        link: Optional[Union[str, HttpUrl]] = None
    ) -> SendMessageResponse:
        """Sends an audio message (standard audio file, not a voice note). Requires `media_id` (recommended) or `link`."""
        # Audio messages don't typically support captions in the API payload structure
        return await self.send_media(to, constants.MessageType.AUDIO, media_id, link)

    async def send_document(
        self,
        to: str,
        media_id: Optional[str] = None,
        link: Optional[Union[str, HttpUrl]] = None,
        caption: Optional[str] = None,
        filename: Optional[str] = None
    ) -> SendMessageResponse:
        """Sends a document message. Requires `media_id` (recommended) or `link`."""
        return await self.send_media(to, constants.MessageType.DOCUMENT, media_id, link, caption=caption, filename=filename)

    async def send_sticker(
        self,
        to: str,
        media_id: Optional[str] = None,
        link: Optional[Union[str, HttpUrl]] = None
    ) -> SendMessageResponse:
        """Sends a sticker message. Requires `media_id` (recommended) or `link` of a WEBP file."""
        # Stickers do not support captions or filenames
        return await self.send_media(to, constants.MessageType.STICKER, media_id, link)

    async def send_location(
        self,
        to: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None
    ) -> SendMessageResponse:
        """
        Sends a location message with specific coordinates.

        Args:
            to: Recipient's WhatsApp ID.
            latitude: Latitude of the location (decimal degrees).
            longitude: Longitude of the location (decimal degrees).
            name: Optional name for the location pin.
            address: Optional address text displayed with the location.

        Returns:
            SendMessageResponse: The API response model.
        """
        # Use the Location model for validation before creating the payload
        location_model = Location(
            latitude=latitude,
            longitude=longitude,
            name=name,
            address=address
        )
        # Exclude 'url' field which is only present in received location messages
        location_payload = location_model.model_dump(exclude={'url'}, exclude_none=True)

        payload = {
            "to": to,
            "type": constants.MessageType.LOCATION.value,
            "location": location_payload,
        }
        return await self.send_message(payload)

    async def send_contacts(
        self,
        to: str,
        contacts: List[ContactSend] # Expect list of pre-validated ContactSend models
    ) -> SendMessageResponse:
        """
        Sends one or more contact cards in a single message.

        Args:
            to: Recipient's WhatsApp ID.
            contacts: A list of `wa_cloud.models.ContactSend` model instances.
                      Build these instances carefully before calling this method.

        Returns:
            SendMessageResponse: The API response model.

        Raises:
            ValueError: If the `contacts` list is empty.
            See `send_message` for other potential exceptions.
        """
        if not contacts:
            raise ValueError("Contacts list cannot be empty when sending contacts.")

        # Serialize each ContactSend model instance to a dictionary.
        # exclude_none=True removes optional fields that weren't set.
        # by_alias=True might be needed if model fields use aliases (not common here).
        contacts_payload = [contact.model_dump(exclude_none=True, by_alias=True) for contact in contacts]

        payload = {
            "to": to,
            "type": constants.MessageType.CONTACTS.value,
            "contacts": contacts_payload,
        }
        return await self.send_message(payload)

    async def send_reaction(
        self,
        to: str,
        message_id: str,
        emoji: Optional[str] = None # Use None or "" to remove reaction
    ) -> SendMessageResponse:
        """
        Sends an emoji reaction to a previous message or removes the reaction.

        Args:
            to: The WhatsApp ID of the user who sent the message you are reacting to.
            message_id: The WhatsApp message ID (wamid) of the message to react to.
            emoji: The emoji character (e.g., "👍") or its unicode escape sequence
                   (e.g., "\\uD83D\\uDC4D"). Provide `None` or an empty string ""
                   to remove a reaction previously sent by the bot.

        Returns:
            SendMessageResponse: The API response model.

        Raises:
            See `send_message` for potential exceptions.
        """
        # Use the ReactionSend model for validation (min_length=0 allows empty string)
        reaction_payload = ReactionSend(message_id=message_id, emoji=emoji or "")

        payload = {
            "to": to,
            "type": constants.MessageType.REACTION.value,
            "reaction": reaction_payload.model_dump(),
        }
        # Reaction messages don't use 'recipient_type' in the payload
        if "recipient_type" in payload:
             del payload["recipient_type"]

        return await self.send_message(payload)

    async def send_interactive_message(
        self,
        to: str,
        interactive: InteractiveMessageSend # Expect pre-validated model instance
    ) -> SendMessageResponse:
        """
        Sends a pre-constructed interactive message (buttons, list, cta_url, flow).

        This is a lower-level method. Prefer using the specific helper methods like
        `send_interactive_button`, `send_interactive_list`, etc., which construct the
        `InteractiveMessageSend` object and call this method.

        Args:
            to: Recipient's WhatsApp ID.
            interactive: An already validated `wa_cloud.models.InteractiveMessageSend` model instance.

        Returns:
            SendMessageResponse: The API response model.

        Raises:
            See `send_message` for potential exceptions.
        """
        # Serialize the validated InteractiveMessageSend model to a dictionary payload
        interactive_payload = interactive.model_dump(mode="json", exclude_none=True, by_alias=True)

        payload = {
            "to": to,
            "type": constants.MessageType.INTERACTIVE.value,
            "interactive": interactive_payload
        }
        return await self.send_message(payload)

    # --- Specific Interactive Message Helper Methods ---

    async def send_interactive_button(
        self,
        to: str,
        body_text: str,
        buttons: List[Dict[str, str]], # Expect list of {'id': '...', 'title': '...'}
        header: Optional[InteractiveHeader] = None,
        footer_text: Optional[str] = None
    ) -> SendMessageResponse:
        """
        Sends an interactive message featuring reply buttons.

        Args:
            to: Recipient's WhatsApp ID.
            body_text: The main text content of the message (required).
            buttons: A list of button dictionaries. Each dictionary must contain
                     'id' (unique string, max 256 chars) and 'title' (button label, max 20 chars).
                     Must provide 1 to 3 buttons.
            header: Optional. An `InteractiveHeader` model instance for a text, image, video,
                    or document header. Build this separately using `MediaBase(id=...)` etc.
                    for media headers.
            footer_text: Optional footer text (max 60 characters).

        Returns:
            SendMessageResponse: The API response model.

        Raises:
            ValueError: If the number of buttons is invalid or button data is malformed.
            See `send_interactive_message` for other potential exceptions.
        """
        if not 1 <= len(buttons) <= 3:
            raise ValueError("Interactive button message requires 1 to 3 buttons.")

        try:
            # Validate and structure buttons using the Pydantic models
            action_buttons = [InteractiveButton(reply=btn) for btn in buttons]
            action = InteractiveActionButton(buttons=action_buttons)
            body = InteractiveBody(text=body_text) # Validates body length
            footer = InteractiveFooter(text=footer_text) if footer_text else None # Validates footer length
        except Exception as e:
             # Catch validation errors during model creation
             raise ValueError(f"Invalid interactive button component data: {e}") from e

        # Construct the main interactive payload model
        interactive_payload = InteractiveMessageSend(
            type=constants.InteractiveType.BUTTON, # Use enum member
            header=header, # Pass the pre-built header model
            body=body,
            footer=footer,
            action=action
        )
        # Send using the generic interactive sender method
        return await self.send_interactive_message(to=to, interactive=interactive_payload)

    async def send_interactive_list(
        self,
        to: str,
        body_text: str,
        button_text: str,
        sections: List[Dict[str, Any]], # List of {'title': '...', 'rows': [{'id': '...', 'title': '...', 'description': '...'}]}
        header: Optional[InteractiveHeader] = None,
        footer_text: Optional[str] = None
    ) -> SendMessageResponse:
        """
        Sends an interactive list message allowing the user to select one option.

        Args:
            to: Recipient's WhatsApp ID.
            body_text: The main text content of the message (required).
            button_text: The text label for the button that opens the list (required, max 20 chars).
            sections: A list of section dictionaries. Each dict should have an optional 'title' (max 24 chars)
                      and a mandatory 'rows' list. Each row dict must have 'id' (unique string, max 200 chars),
                      'title' (max 24 chars), and an optional 'description' (max 72 chars).
                      Max 10 sections, max 10 rows total across all sections.
            header: Optional. An `InteractiveHeader` model instance (text header only supported for lists by API).
            footer_text: Optional footer text (max 60 characters).

        Returns:
            SendMessageResponse: The API response model.

        Raises:
            ValueError: If section/row data is invalid or limits are exceeded.
            See `send_interactive_message` for other potential exceptions.
        """
        if not sections:
            raise ValueError("Interactive list requires at least one section.")
        if header and header.type != "text":
             logger.warning("Interactive List Messages only support 'text' headers according to API docs. Other types may fail.")

        try:
            # Validate sections and rows using Pydantic models
            list_sections = [InteractiveListSection.model_validate(sec) for sec in sections]
            # Validate action (includes total row count check)
            action = InteractiveActionList(button=button_text, sections=list_sections)
            body = InteractiveBody(text=body_text)
            footer = InteractiveFooter(text=footer_text) if footer_text else None
        except Exception as e:
             raise ValueError(f"Invalid interactive list component data: {e}") from e

        interactive_payload = InteractiveMessageSend(
            type=constants.InteractiveType.LIST,
            header=header,
            body=body,
            footer=footer,
            action=action
        )
        return await self.send_interactive_message(to=to, interactive=interactive_payload)

    async def send_interactive_cta_url(
        self,
        to: str,
        body_text: str,
        display_text: str,
        url: Union[str, HttpUrl],
        header: Optional[InteractiveHeader] = None,
        footer_text: Optional[str] = None
    ) -> SendMessageResponse:
        """
        Sends an interactive message with a single Call-To-Action button that opens a URL.

        Args:
            to: Recipient's WhatsApp ID.
            body_text: The main text content of the message (required).
            display_text: The text label displayed on the button (required, max 30 recommended).
            url: The URL (as string or Pydantic HttpUrl) to open when the button is tapped.
            header: Optional. An `InteractiveHeader` model instance.
            footer_text: Optional footer text.

        Returns:
            SendMessageResponse: The API response model.

        Raises:
            ValueError: If button/URL data is invalid.
            See `send_interactive_message` for other potential exceptions.
        """
        try:
            # Validate parameters using models; includes HttpUrl validation and str() conversion for URL
            action_params = InteractiveActionCtaUrlParameters(display_text=display_text, url=str(url))
            action = InteractiveActionCtaUrl(parameters=action_params) # name="cta_url" automatically set
            body = InteractiveBody(text=body_text)
            footer = InteractiveFooter(text=footer_text) if footer_text else None
        except Exception as e:
            raise ValueError(f"Invalid interactive CTA URL component data: {e}") from e

        interactive_payload = InteractiveMessageSend(
            type=constants.InteractiveType.CTA_URL,
            header=header,
            body=body,
            footer=footer,
            action=action
        )
        return await self.send_interactive_message(to=to, interactive=interactive_payload)


    async def send_interactive_flow(
        self,
        to: str,
        body_text: str,
        action: InteractiveActionFlow, # User must construct this validated model instance first
        header: Optional[InteractiveHeader] = None,
        footer_text: Optional[str] = None
    ) -> SendMessageResponse:
        """
        Sends an interactive message designed to trigger a WhatsApp Flow.

        Note: Construct the `InteractiveActionFlow` object (including its `parameters`)
        carefully using the models from `wa_cloud.models` before calling this method.

        Args:
            to: Recipient's WhatsApp ID.
            body_text: The main text content of the message (required).
            action: A pre-constructed and validated `InteractiveActionFlow` model instance.
            header: Optional. An `InteractiveHeader` model instance.
            footer_text: Optional footer text.

        Returns:
            SendMessageResponse: The API response model.

        Raises:
            ValueError: If body text data is invalid.
            TypeError: If `action` is not a valid `InteractiveActionFlow` instance.
            See `send_interactive_message` for other potential exceptions.
        """
        if not isinstance(action, InteractiveActionFlow):
             raise TypeError("`action` must be an instance of `InteractiveActionFlow`")
        try:
            body = InteractiveBody(text=body_text)
            footer = InteractiveFooter(text=footer_text) if footer_text else None
        except Exception as e:
            raise ValueError(f"Invalid interactive flow component data: {e}") from e

        interactive_payload = InteractiveMessageSend(
            type=constants.InteractiveType.FLOW,
            header=header,
            body=body,
            footer=footer,
            action=action # Pass the pre-validated action object
        )
        return await self.send_interactive_message(to=to, interactive=interactive_payload)

    async def send_template(
        self,
        to: str,
        template: TemplateSend # User must construct this validated model instance first
    ) -> SendMessageResponse:
        """
        Sends a message based on a pre-approved WhatsApp template.

        Note: Construct the `TemplateSend` object (including `name`, `language`,
        and `components` with correct `parameters`) carefully using the models
        from `wa_cloud.models` before calling this method.

        Args:
            to: Recipient's WhatsApp ID.
            template: A pre-constructed and validated `TemplateSend` model instance.

        Returns:
            SendMessageResponse: The API response model.

        Raises:
            TypeError: If `template` is not a valid `TemplateSend` instance.
            See `send_message` for other potential exceptions.
        """
        if not isinstance(template, TemplateSend):
             raise TypeError("`template` must be an instance of `TemplateSend`")

        # Serialize the validated TemplateSend model to a dictionary payload
        template_payload = template.model_dump(exclude_none=True, by_alias=True)

        payload = {
            "to": to,
            "type": constants.MessageType.TEMPLATE.value,
            "template": template_payload
        }
        return await self.send_message(payload)


    # --- Media Management Methods ---

    async def upload_media(
        self,
        file_path: Union[str, Path],
        mime_type: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> UploadMediaResponse:
        """
        Uploads a local media file to WhatsApp servers.

        The returned media ID is temporary (usually valid for 30 days)
        and can be used in `send_image`, `send_video`, etc.

        Args:
            file_path: Path object or string path to the local file to upload.
            mime_type: Optional. The MIME type of the file (e.g., "image/jpeg", "video/mp4").
                       If None, the type is guessed from the file extension. Providing it
                       is recommended for accuracy.
            timeout: Optional. Timeout in seconds for this upload request. Defaults to
                     `self.default_timeout * 4`.

        Returns:
            UploadMediaResponse: A Pydantic model containing the `id` of the uploaded media.

        Raises:
            FileNotFoundError: If `file_path` does not exist or is not a file.
            ValueError: If `mime_type` cannot be determined and is not provided.
            NetworkError: For connection/timeout issues during upload.
            APIError: If WhatsApp API rejects the upload (e.g., size limit, format).
            WhatsAppError: For other errors during file handling or request processing.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Media file not found at specified path: {path}")

        # Determine MIME type if not explicitly provided
        if mime_type is None:
            mime_type, _ = mimetypes.guess_type(path.name)
            if mime_type is None:
                # Cannot proceed without a MIME type
                raise ValueError(f"Could not determine MIME type for filename '{path.name}'. Please provide the 'mime_type' argument.")

        logger.info(f"Uploading media: {path.name} (Type: {mime_type})")

        # Use a longer default timeout for uploads than standard requests
        upload_timeout = timeout if timeout is not None else self.default_timeout * 4 # e.g., 60 seconds

        try:
            # Use context manager for opening the file
            with path.open("rb") as file_handle:
                # Prepare data for multipart/form-data request
                multipart_data = {
                    "messaging_product": (None, "whatsapp"),
                    "type": (None, mime_type), # Providing type is recommended by API docs
                    "file": (path.name, file_handle, mime_type), # (filename, file_obj, content_type)
                }
                # Make the API request using the internal helper
                response_data = await self._make_api_request(
                    method="POST",
                    endpoint_template=constants.MEDIA_ENDPOINT_TEMPLATE,
                    files=multipart_data,
                    timeout=upload_timeout
                )
            # Validate and return the response
            media_id = response_data.get('id', '[missing]')
            logger.info(f"Media uploaded successfully: {path.name} -> Media ID: {media_id}")
            return UploadMediaResponse.model_validate(response_data)

        except FileNotFoundError: # Should be caught by initial check, but good practice
             logger.error(f"File not found during upload process: {path}")
             raise
        except Exception as e: # Catch potential OS errors reading the file
            logger.exception(f"Error during media file handling or upload for {path}")
            # Wrap OS/file errors in a library-specific exception if they weren't network/API errors
            if not isinstance(e, (APIError, NetworkError)):
                 raise WhatsAppError(f"Error during media upload file handling for {path}: {e}") from e
            else:
                 raise # Re-raise APIError/NetworkError


    async def get_media_info(self, media_id: str) -> MediaInfoResponse:
        """
        Retrieves details about an uploaded media asset using its ID.

        This includes the MIME type, size, hash, and critically, a temporary
        URL that can be used to download the media.

        Args:
            media_id: The ID of the media asset (obtained from `upload_media` or a webhook).

        Returns:
            MediaInfoResponse: Pydantic model containing media details.

        Raises:
            ValueError: If `media_id` is empty.
            BadRequestError: If the media ID does not exist (results in 404 from API).
            See `_make_api_request` for other potential exceptions.
        """
        if not media_id:
            raise ValueError("Cannot get media info: media_id cannot be empty.")
        logger.debug(f"Requesting media info for ID: {media_id}")
        response_data = await self._get(
            endpoint_template=constants.MEDIA_DETAIL_ENDPOINT_TEMPLATE,
            endpoint_args={"media_id": media_id} # Pass ID to format URL
        )
        # Validate the response using the Pydantic model
        return MediaInfoResponse.model_validate(response_data)

    async def download_media(
        self,
        media_url: Union[str, HttpUrl],
        dest_path: Union[str, Path],
        timeout: Optional[float] = None
    ) -> Path:
        """
        Downloads media from its temporary URL to a specified local file path.

        Note: The `media_url` is obtained via `get_media_info()` and is typically
        valid for only 5 minutes. Download attempts now include the Authorization header.

        Args:
            media_url: The temporary media download URL.
            dest_path: The full, exact destination path (including directory, filename,
                       and extension) where the file should be saved. The directory
                       will be created if it doesn't exist.
            timeout: Optional timeout in seconds for the download request. Defaults to
                     `self.default_timeout * 10`.

        Returns:
            Path: The Path object representing the saved file (same as `dest_path`).

        Raises:
            NetworkError: For connection/timeout issues during download.
            APIError: If the download URL returns an error (e.g., 401, 403, 404).
            WhatsAppError: For OS errors creating directories or writing the file.
        """
        download_timeout = timeout if timeout is not None else self.default_timeout * 10
        media_url_str = str(media_url) # Ensure URL is a string for httpx
        output_file_path = Path(dest_path).resolve() # Use absolute path for clarity

        # Ensure the target directory exists before attempting download
        output_dir = output_file_path.parent
        logger.info(f"Ensuring download directory exists: {output_dir}")
        try:
             output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.exception(f"Failed to create directory for media download: {output_dir}")
            raise WhatsAppError(f"Could not create directory '{output_dir}' to save media: {e}") from e
        except Exception as e: # Catch other potential errors
            logger.exception(f"Unexpected error creating directory: {output_dir}")
            raise WhatsAppError(f"Unexpected error creating directory '{output_dir}': {e}") from e

        # --- Perform Download ---
        logger.info(f"Attempting to download media from URL -> {output_file_path}")
        try:
            # Include Authorization header as API seems to require it for these URLs
            download_headers = {"Authorization": f"Bearer {self.token}"}

            async with httpx.AsyncClient(timeout=download_timeout, follow_redirects=True) as client:
                # Use streaming download to handle potentially large files efficiently
                async with client.stream("GET", media_url_str, headers=download_headers) as response:
                    # Raise an exception for bad status codes (4xx or 5xx)
                    response.raise_for_status()
                    # Open the destination file and write chunks as they arrive
                    with open(output_file_path, "wb") as f:
                        bytes_downloaded = 0
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
            logger.info(f"Media downloaded successfully ({bytes_downloaded} bytes) to: {output_file_path}")
            return output_file_path

        # Specific exception handling for download phase
        except httpx.HTTPStatusError as e:
            # More informative error message for download failures
            error_detail = f"(Status Code: {e.response.status_code})"
            raise APIError(f"Media download request failed {error_detail} for URL {media_url_str}", response_data=None) from e
        except httpx.TimeoutException as e:
             raise NetworkError(f"Timeout during media download from {media_url_str}") from e
        except httpx.RequestError as e:
            raise NetworkError(f"Network error during media download from {media_url_str}: {e}") from e
        except Exception as e:
            # Catch potential OS errors during file write
            logger.exception(f"Error writing downloaded media to {output_file_path}")
            # Attempt cleanup of potentially partial file
            if output_file_path.exists():
                try: output_file_path.unlink()
                except OSError: logger.warning(f"Could not remove partially downloaded file: {output_file_path}")
            raise WhatsAppError(f"Error writing downloaded media to {output_file_path}: {e}") from e

    async def delete_media(self, media_id: str) -> bool:
        """
        Deletes a media asset previously uploaded to WhatsApp servers.

        Args:
            media_id: The ID of the media to delete.

        Returns:
            bool: True if the API confirms successful deletion, False otherwise
                  (including if an error occurs).
        """
        if not media_id:
            raise ValueError("Cannot delete media: media_id cannot be empty.")
        logger.info(f"Attempting to delete media with ID: {media_id}")
        try:
            response_data = await self._delete(
                endpoint_template=constants.MEDIA_DETAIL_ENDPOINT_TEMPLATE,
                endpoint_args={"media_id": media_id} # Pass ID to format URL
            )
            # Validate response using the SuccessResponse model
            result = DeleteMediaResponse.model_validate(response_data)
            logger.info(f"Media deletion API result for {media_id}: {result.success}")
            return result.success
        except Exception as e:
             # Log the error but return False for simplicity for the caller
             logger.error(f"Failed to delete media {media_id} or parse response: {e}")
             return False # Indicate failure

    # --- Message Status Management Methods ---
    # wa_cloud/bot.py
    async def mark_as_read(
        self,
        message_id: str,
        show_typing: bool = False # ADD this parameter
    ) -> bool:
        """
        Marks a specific received message as read (double blue ticks appear for the user).
        Optionally displays a 'typing...' indicator simultaneously.
        # ... (Args/Returns) ...
        """
        if not message_id:
            raise ValueError("Cannot mark message as read: message_id cannot be empty.")

        action = "Marking as read"

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        if show_typing:
            action += " and showing typing indicator"
            payload["typing_indicator"] = {"type": "text"}

        # This logger call now always has a value for 'action'
        logger.info(f"{action}: {message_id}")

        try:
            response_data = await self._post(
                constants.MESSAGES_ENDPOINT_TEMPLATE,
                payload=payload
            )
            result = SuccessResponse.model_validate(response_data)
            # Use 'action' variable in debug log for consistency
            logger.debug(f"API result for '{action}' on {message_id}: {result.success}")
            return result.success
        except Exception as e:
            # Use 'action' variable in error log for consistency
            logger.error(f"Failed attempt for '{action}' on message {message_id}: {e}")
            return False