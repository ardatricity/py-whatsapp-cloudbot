# wa_cloud/models.py

"""
Pydantic Models for WhatsApp Cloud API Objects.

This module defines Pydantic models for validating and structuring data
received from WhatsApp webhooks and for constructing payloads to send
to the WhatsApp Cloud API.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Union

# Pydantic core components and field types
from pydantic import (BaseModel, Field, HttpUrl, conlist, constr,
                      field_validator, model_validator, field_serializer)

# Import constants and enums from within the library
from .constants import (
    # Enums
    InteractiveType, MessageType, TemplateButtonSubType, TemplateComponentType,
    TemplateParameterType,
    # Limits
    MAX_CONTACT_FIELD_LENGTH, MAX_CONTACT_FORMATTED_NAME_LENGTH,
    MAX_INTERACTIVE_BODY_TEXT_LENGTH, MAX_INTERACTIVE_BUTTON_ID_LENGTH,
    MAX_INTERACTIVE_BUTTON_TEXT_LENGTH, MAX_INTERACTIVE_CTA_URL_DISPLAY_TEXT_LENGTH,
    MAX_INTERACTIVE_FOOTER_TEXT_LENGTH, MAX_INTERACTIVE_HEADER_TEXT_LENGTH,
    MAX_INTERACTIVE_LIST_ROW_DESC_LENGTH, MAX_INTERACTIVE_LIST_ROW_ID_LENGTH,
    MAX_INTERACTIVE_LIST_ROW_TITLE_LENGTH, MAX_INTERACTIVE_LIST_SECTION_TITLE_LENGTH,
    MAX_LOCATION_ADDRESS_LENGTH, MAX_LOCATION_NAME_LENGTH,
    MAX_REACTION_EMOJI_LENGTH, MAX_TEMPLATE_BUTTON_PAYLOAD_LENGTH,
    MAX_TEMPLATE_BUTTON_URL_SUFFIX_LENGTH, MAX_TEMPLATE_CURRENCY_FALLBACK_LENGTH,
    MAX_TEMPLATE_DATETIME_FALLBACK_LENGTH, MAX_TEMPLATE_LANG_CODE_LENGTH,
    MAX_TEMPLATE_NAME_LENGTH, MAX_TEMPLATE_PARAM_TEXT_LENGTH
)

logger = logging.getLogger(__name__)

# --- Base Model Configuration ---

class BaseModelWA(BaseModel):
    """
    Base Pydantic model for all WhatsApp API objects.

    Includes common configuration:
    - `extra = 'allow'`: Ignores unexpected fields from the API without errors.
    - `populate_by_name = True`: Allows using field aliases (like 'from_').
    - `use_enum_values = True`: Ensures enum members are validated/serialized using their values.
    """
    class Config:
        extra = 'allow'
        populate_by_name = True
        use_enum_values = True


# --- Common Reusable Models ---

class Profile(BaseModelWA):
    """Represents the profile information of a WhatsApp user."""
    name: str # The user's WhatsApp profile name

class WAMessageContact(BaseModelWA):
    """
    Represents contact information about the sender of a message,
    as included in the webhook payload's `value.contacts` list.
    Distinguished from the `Contact` model used for *received contact card messages*.
    """
    profile: Profile
    wa_id: str # The WhatsApp ID (typically E.164 phone number) of the sender.


# --- Models for Received Message Components ---

class MessageContext(BaseModelWA):
    """Contextual information about a received message (e.g., if it's a reply)."""
    forwarded: Optional[bool] = None # True if the message was forwarded
    frequently_forwarded: Optional[bool] = None # True if forwarded many times
    from_: str = Field(..., alias="from") # Sender's number (of the original message if this is a reply context)
    id: str # WAMID of the original message being replied to, or the message itself if no context.
    referred_product: Optional[Dict[str, Any]] = None # Context for product inquiry messages (not fully modeled).
    # TODO: Add 'mentions' field if needed (for group message mentions).

class MediaBase(BaseModelWA):
    """
    Base model for media objects included in messages (both received and sent).

    Note: For sending, either 'id' or 'link' must be provided.
          For receiving, 'id' is typically the only field present, representing the downloadable media.
    """
    id: Optional[str] = None # The Media ID (required for received media, optional for sending if link is used).
    link: Optional[HttpUrl] = None # HTTPS URL (only used for sending, not recommended).
    caption: Optional[str] = None # Caption associated with the media (used in specific subtypes).
    filename: Optional[str] = None # Filename associated with the media (primarily for sending/receiving documents).

    # Removed model_validator check for id/link here; handled in Bot sending logic.

class Image(MediaBase):
    """Represents an image object within a message."""
    pass # Inherits fields from MediaBase

class Video(MediaBase):
    """Represents a video object within a message."""
    pass # Inherits fields from MediaBase

class Audio(MediaBase):
    """Represents an audio object (standard audio file) within a message."""
    pass # Inherits fields from MediaBase

class Document(MediaBase):
    """Represents a document object within a message."""
    pass # Inherits 'filename' and 'caption' from MediaBase

class Sticker(MediaBase):
    """Represents a sticker object within a message."""
    # Sticker-specific fields if received via webhook
    animated: Optional[bool] = Field(default=False, description="True if the sticker is animated.")

class Location(BaseModelWA):
    """
    Represents a location object within a message (received or sending).

    Note: The 'url' field is only present for received location messages,
          providing a link to view the location on a map.
    """
    latitude: float # Latitude in decimal degrees.
    longitude: float # Longitude in decimal degrees.
    name: Optional[constr(max_length=MAX_LOCATION_NAME_LENGTH)] = None # Optional name of the location.
    address: Optional[constr(max_length=MAX_LOCATION_ADDRESS_LENGTH)] = None # Optional address of the location.
    url: Optional[HttpUrl] = None # URL to view map (present only in received messages).

class Text(BaseModelWA):
    """Represents the text content object of a received text message."""
    body: str # The text content of the message.


# --- Models for Received Contact Card Messages ---

class ContactName(BaseModelWA):
    """Name structure within a received Contact card."""
    formatted_name: str # Full name as displayed.
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None

class ContactAddress(BaseModelWA):
    """Address structure within a received Contact card."""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None # State/province/region.
    zip: Optional[str] = None # ZIP/postal code.
    country: Optional[str] = None
    country_code: Optional[str] = None # Two-letter country code.
    type: Optional[str] = None # Address type (e.g., "HOME", "WORK").

class ContactEmail(BaseModelWA):
    """Email structure within a received Contact card."""
    email: Optional[str] = None
    type: Optional[str] = None # Email type (e.g., "WORK", "HOME").

class ContactPhone(BaseModelWA):
    """Phone number structure within a received Contact card."""
    phone: Optional[str] = None # Phone number string.
    type: Optional[str] = None # Phone type (e.g., "CELL", "MAIN", "IPHONE", "HOME", "WORK").
    wa_id: Optional[str] = None # WhatsApp ID associated with this number, if known.

class ContactOrg(BaseModelWA):
    """Organization structure within a received Contact card."""
    company: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None # Job title.

class ContactUrl(BaseModelWA):
    """URL structure within a received Contact card."""
    url: Optional[str] = None # URL string (HttpUrl validation might be too strict).
    type: Optional[str] = None # URL type (e.g., "WORK", "HOME", "Website").

class Contact(BaseModelWA):
    """
    Represents a single contact card received in a message of type 'contacts'.
    A message can contain a list of these.
    """
    addresses: Optional[List[ContactAddress]] = None
    birthday: Optional[str] = None # Formatted as "YYYY-MM-DD".
    emails: Optional[List[ContactEmail]] = None
    name: ContactName # Name object is required.
    org: Optional[ContactOrg] = None
    phones: Optional[List[ContactPhone]] = None
    urls: Optional[List[ContactUrl]] = None


# --- Models for Received Interactive Message Replies ---

class ButtonReply(BaseModelWA):
    """Represents the payload received when a user taps an Interactive Reply Button."""
    id: str # The unique ID assigned to the button when sending.
    title: str # The text label of the button that was tapped.

class ListReply(BaseModelWA):
    """Represents the payload received when a user selects an item from an Interactive List."""
    id: str # The unique ID assigned to the selected row when sending.
    title: str # The title text of the selected row.
    description: Optional[str] = None # The description text of the row, if it was provided when sending.

class InteractiveReply(BaseModelWA):
    """
    Container for the specific reply data within a received 'interactive' message.
    The 'type' field indicates whether it's a button or list reply.
    """
    # Specifies the type of interactive reply received.
    type: Literal[InteractiveType.LIST_REPLY, InteractiveType.BUTTON_REPLY]
    button_reply: Optional[ButtonReply] = None # Present if type is BUTTON_REPLY.
    list_reply: Optional[ListReply] = None # Present if type is LIST_REPLY.
    # TODO: Model 'nfm_reply' if relevant for Flow interactions.


# --- Model for Received Reaction Messages ---

class Reaction(BaseModelWA):
    """Represents a reaction emoji applied to a previous message."""
    message_id: str # The WAMID of the message that was reacted to.
    emoji: Optional[str] = None # The emoji used. None if the reaction was removed by the user.


# --- Model for Received System Messages ---

class System(BaseModelWA):
    """Represents a system-generated message within a chat (e.g., user joined group)."""
    body: str # Text description of the system event.


# --- Model for API/Webhook Errors ---

class ErrorData(BaseModelWA):
    """
    Represents the structure of an error object returned by the API or included in webhooks.
    See: https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
    """
    code: int # WhatsApp-specific error code.
    title: str # Summary title of the error.
    message: Optional[str] = None # Detailed error message description (may alias 'details').
    error_data: Optional[Dict[str, Any]] = None # Additional error details, structure varies.
    details: Optional[str] = None # Alternative field for detailed description.


# --- Core Received Message Model ---

class Message(BaseModelWA):
    """
    Represents a single message received via webhook notification.
    This is the primary object passed to message handlers.
    """
    id: str = Field(..., alias="id", description="The unique WhatsApp Message ID (WAMID).")
    from_: str = Field(..., alias="from", description="The sender's WhatsApp ID (E.164 phone number).")
    timestamp_raw: str = Field(..., alias="timestamp", description="Unix timestamp (string) when the message was sent.")
    type: str = Field(..., description="The basic type of the message (e.g., 'text', 'image', 'interactive'). Use message_type property for enum.")

    # Optional fields depending on message type and context
    context: Optional[MessageContext] = None # Present if the message is a reply or forwarded.
    errors: Optional[List[ErrorData]] = None # Included if there was an error delivering a previous message from the business.
    identity: Optional[Dict[str, Any]] = None # Related to identity changes/verification (not fully modeled).
    referral: Optional[Dict[str, Any]] = None # For messages originating from Ads that Click to WhatsApp (not fully modeled).

    # Type-specific payload fields (only one will be present)
    audio: Optional[Audio] = None
    button: Optional[Dict[str, Any]] = None # Received button click (different from interactive button reply?) - Needs clarification/modeling if used.
    contacts: Optional[List[Contact]] = None
    document: Optional[Document] = None
    image: Optional[Image] = None
    interactive: Optional[InteractiveReply] = None
    location: Optional[Location] = None
    order: Optional[Dict[str, Any]] = None # For order messages (not fully modeled).
    reaction: Optional[Reaction] = None
    sticker: Optional[Sticker] = None
    system: Optional[System] = None
    text: Optional[Text] = None
    video: Optional[Video] = None
    # TODO: Add 'unsupported' message type handling/model if needed.

    # Processed fields
    timestamp: Optional[datetime] = Field(default=None, description="Timestamp converted to a Python datetime object.")

    @field_validator('timestamp', mode='before')
    @classmethod
    def convert_timestamp(cls, v: Any) -> Optional[datetime]:
        """Attempts to convert the raw timestamp string/int to a datetime object."""
        if isinstance(v, str) and v.isdigit():
            try:
                return datetime.fromtimestamp(int(v))
            except (ValueError, OverflowError, OSError) as e:
                logger.warning(f"Could not parse timestamp string '{v}': {e}")
                return None
        if isinstance(v, (int, float)):
             try:
                 return datetime.fromtimestamp(v)
             except (ValueError, OverflowError, OSError) as e:
                 logger.warning(f"Could not parse timestamp number '{v}': {e}")
                 return None
        # Handle if it's somehow already a datetime or explicitly None
        if isinstance(v, datetime) or v is None:
            return v
        logger.warning(f"Unparseable timestamp format: {v} (type: {type(v)})")
        return None # Return None if parsing fails

    @property
    def message_type(self) -> MessageType:
        """Returns the message type as a `wa_cloud.constants.MessageType` enum member."""
        try:
            # Directly convert the string type using the MessageType enum
            return MessageType(self.type)
        except ValueError:
            # If the type string doesn't match any enum member
            logger.warning(f"Unknown message type received: '{self.type}'")
            return MessageType.UNKNOWN

    @property
    def chat_id(self) -> str:
        """Convenience property to get the sender's WhatsApp ID (`from_` field)."""
        return self.from_

    @property
    def caption(self) -> Optional[str]:
        """Returns the caption text if the message contains media (image, video, document)."""
        if self.image and self.image.caption: return self.image.caption
        if self.video and self.video.caption: return self.video.caption
        if self.document and self.document.caption: return self.document.caption
        return None

    @property
    def media_id(self) -> Optional[str]:
        """Returns the media ID if the message contains standard media (image, video, audio, document, sticker)."""
        if self.image: return self.image.id
        if self.video: return self.video.id
        if self.audio: return self.audio.id
        if self.document: return self.document.id
        if self.sticker: return self.sticker.id
        return None

    @property
    def filename(self) -> Optional[str]:
        """Returns the filename if the message is a document."""
        if self.document and self.document.filename:
            return self.document.filename
        return None


# --- Webhook Payload Structure Models ---

class Metadata(BaseModelWA):
    """Metadata included in webhook notifications."""
    display_phone_number: str # The phone number displayed to users.
    phone_number_id: str # The specific Phone Number ID that received the event.

class Value(BaseModelWA):
    """The 'value' object within a webhook 'change' entry."""
    messaging_product: str # Should always be "whatsapp".
    metadata: Metadata # Information about the receiving phone number.
    contacts: Optional[List[WAMessageContact]] = None # Info about the user associated with the event (e.g., sender).
    messages: Optional[List[Message]] = None # List of received message objects.
    errors: Optional[List[ErrorData]] = None # Errors related to the webhook event processing itself.
    statuses: Optional[List[Dict[str, Any]]] = None # Message status updates (sent, delivered, read) - Requires detailed modeling.
    # TODO: Model the 'statuses' structure properly if status updates are handled.

class Change(BaseModelWA):
    """Represents a single change event within a webhook entry."""
    value: Value # The actual data associated with the change.
    field: str # The type of change, e.g., "messages", "statuses".

class Entry(BaseModelWA):
    """Represents a single entry within the webhook payload list."""
    id: str # The WhatsApp Business Account ID.
    changes: List[Change] # List of changes occurred.

class WebhookPayload(BaseModelWA):
    """The root model for the entire webhook notification payload."""
    object: str # Should always be "whatsapp_business_account".
    entry: List[Entry]


# --- API Response Models (for Bot methods) ---

class SendMessageResponseContact(BaseModelWA):
    """Contact information included in a successful send message response."""
    input: str # The phone number originally provided in the 'to' field.
    wa_id: str # The standardized WhatsApp ID of the recipient.

class SendMessageResponseMessages(BaseModelWA):
    """Message information included in a successful send message response."""
    id: str # The WAMID of the message that was successfully sent.

class SendMessageResponse(BaseModelWA):
    """The standard response structure after successfully sending a message via the API."""
    messaging_product: str # Should be "whatsapp".
    contacts: Optional[List[SendMessageResponseContact]] = None
    messages: Optional[List[SendMessageResponseMessages]] = None
    error: Optional[ErrorData] = None # Only present if the send API call itself failed immediately.


class MediaInfoResponse(BaseModelWA):
    """Response structure when retrieving information about uploaded media."""
    messaging_product: str # Should be "whatsapp".
    url: HttpUrl # The temporary, short-lived URL to download the media asset.
    mime_type: str
    sha256: str # Hash of the media file.
    file_size: Union[int, str] # File size in bytes (sometimes returned as string).
    id: str # The Media ID queried.

    @field_validator('file_size', mode='before')
    @classmethod
    def convert_file_size(cls, v: Any) -> int:
        """Ensures file_size is always an integer."""
        if isinstance(v, str) and v.isdigit():
            return int(v)
        elif isinstance(v, int):
            return v
        logger.warning(f"Could not parse 'file_size': {v}. Returning 0.")
        return 0

class UploadMediaResponse(BaseModelWA):
    """Response structure after successfully uploading media."""
    id: str # The unique Media ID assigned to the uploaded asset.

class DeleteMediaResponse(BaseModelWA):
    """Response structure after attempting to delete media."""
    success: bool # True if deletion was successful.

class SuccessResponse(BaseModelWA):
    """Generic response indicating success for actions like marking messages read."""
    success: bool # True if the operation was successful.


# --- Models for Constructing API Payloads (Sending Messages) ---
# These models are primarily used internally by the Bot class or by users
# to construct validated payloads before sending them via Bot methods.

# -- Reaction Payload ---
class ReactionSend(BaseModelWA):
    """Structure for the 'reaction' object when sending a reaction message."""
    message_id: str # WAMID of the message to react to.
    # min_length=0 allows empty string for removing reactions.
    emoji: constr(min_length=0, max_length=MAX_REACTION_EMOJI_LENGTH)


# -- Contact Card Sending Models ---
class ContactNameSend(BaseModelWA):
    """Structure for the 'name' object when sending a contact card."""
    formatted_name: constr(min_length=1, max_length=MAX_CONTACT_FORMATTED_NAME_LENGTH)
    first_name: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None
    last_name: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None
    middle_name: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None
    prefix: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None
    suffix: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None

class ContactAddressSend(BaseModelWA):
    """Structure for an 'address' object when sending a contact card."""
    street: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None
    city: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None
    state: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # State/province/region.
    zip: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # ZIP/postal code.
    country: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None
    country_code: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # ISO 3166-1 alpha-2 code preferred.
    type: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # e.g., "HOME", "WORK".

class ContactEmailSend(BaseModelWA):
    """Structure for an 'email' object when sending a contact card."""
    email: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # Consider adding email validation if needed.
    type: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # e.g., "WORK", "HOME".

class ContactPhoneSend(BaseModelWA):
    """Structure for a 'phone' object when sending a contact card."""
    phone: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # Phone number string.
    type: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # e.g., "CELL", "MAIN", "WORK", "HOME".
    wa_id: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # Include if known to enable direct messaging button.

class ContactOrgSend(BaseModelWA):
    """Structure for the 'org' (organization) object when sending a contact card."""
    company: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None
    department: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None
    title: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # Job title.

class ContactUrlSend(BaseModelWA):
    """Structure for a 'url' object when sending a contact card."""
    url: Optional[str] = None # Use string; HttpUrl validation might reject valid non-web URLs.
    type: Optional[constr(max_length=MAX_CONTACT_FIELD_LENGTH)] = None # e.g., "WORK", "HOME", "Website".

class ContactSend(BaseModelWA):
    """
    Structure for a single contact card payload within the `contacts` list
    when sending a contacts message.
    """
    addresses: Optional[conlist(ContactAddressSend, max_length=10)] = None # Limited list size for sanity
    birthday: Optional[str] = None # Must be "YYYY-MM-DD" format.
    emails: Optional[conlist(ContactEmailSend, max_length=10)] = None
    name: ContactNameSend # Name is required.
    org: Optional[ContactOrgSend] = None
    phones: Optional[conlist(ContactPhoneSend, max_length=10)] = None
    urls: Optional[conlist(ContactUrlSend, max_length=10)] = None

    @field_validator('birthday')
    @classmethod
    def check_birthday_format(cls, v: Optional[str]) -> Optional[str]:
        """Validates birthday string format."""
        if v is None:
            return v
        try:
            # Use date.fromisoformat for YYYY-MM-DD validation
            date.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("Contact birthday must be in YYYY-MM-DD format.")


# -- Interactive Message Sending Models ---

class InteractiveHeader(BaseModelWA):
    """
    Structure for the 'header' object when sending interactive messages.
    The content field (text, video, image, document) must match the 'type'.
    """
    type: Literal["text", "video", "image", "document"]
    text: Optional[constr(max_length=MAX_INTERACTIVE_HEADER_TEXT_LENGTH)] = None
    # Media objects should contain 'id' or 'link'
    video: Optional[MediaBase] = None
    image: Optional[MediaBase] = None
    document: Optional[MediaBase] = None

    @model_validator(mode='before')
    @classmethod
    def check_header_fields(cls, values: Any) -> Any:
        """Ensures the correct content field is present based on 'type'."""
        if not isinstance(values, dict): return values # Allow non-dict inputs for early validation
        header_type = values.get('type')
        # Check if the required field for the specified type is present
        if header_type == 'text' and not values.get('text'): raise ValueError("Header type 'text' requires the 'text' field.")
        if header_type == 'video' and not values.get('video'): raise ValueError("Header type 'video' requires the 'video' field (with id/link).")
        if header_type == 'image' and not values.get('image'): raise ValueError("Header type 'image' requires the 'image' field (with id/link).")
        if header_type == 'document' and not values.get('document'): raise ValueError("Header type 'document' requires the 'document' field (with id/link).")

        # Warn if extra fields are present (though allowed by 'extra=allow')
        allowed_fields = {'type', header_type} if header_type in values else {'type'}
        for k in values:
            if k not in allowed_fields:
                logger.warning(f"Unexpected field '{k}' found in header for type '{header_type}'.")
        return values


class InteractiveBody(BaseModelWA):
    """Structure for the 'body' object (required) when sending interactive messages."""
    text: constr(min_length=1, max_length=MAX_INTERACTIVE_BODY_TEXT_LENGTH)

class InteractiveFooter(BaseModelWA):
    """Structure for the 'footer' object (optional) when sending interactive messages."""
    text: constr(max_length=MAX_INTERACTIVE_FOOTER_TEXT_LENGTH)


class InteractiveButton(BaseModelWA):
    """
    Structure for a single button within the 'action' object when sending
    an interactive message of type 'button'.
    """
    type: Literal["reply"] = "reply" # Only 'reply' type is currently supported for buttons
    # Use a nested dictionary for 'reply' containing 'id' and 'title'
    reply: Dict[str, constr(min_length=1)]

    @field_validator('reply')
    @classmethod
    def validate_reply_button_payload(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validates the structure and content of the reply button dictionary."""
        if not isinstance(v, dict): raise ValueError("'reply' must be a dictionary.")
        button_id = v.get('id')
        title = v.get('title')
        if not button_id: raise ValueError("Button 'reply' object must contain a non-empty 'id'.")
        if not title: raise ValueError("Button 'reply' object must contain a non-empty 'title'.")
        # Check lengths against constants
        if len(button_id) > MAX_INTERACTIVE_BUTTON_ID_LENGTH: raise ValueError(f"Button ID exceeds max length ({MAX_INTERACTIVE_BUTTON_ID_LENGTH}).")
        if len(title) > MAX_INTERACTIVE_BUTTON_TEXT_LENGTH: raise ValueError(f"Button title exceeds max length ({MAX_INTERACTIVE_BUTTON_TEXT_LENGTH}).")
        return v

class InteractiveListRow(BaseModelWA):
    """Structure for a single row within a section of an interactive list message."""
    id: constr(min_length=1, max_length=MAX_INTERACTIVE_LIST_ROW_ID_LENGTH) # Unique identifier for the row
    title: constr(min_length=1, max_length=MAX_INTERACTIVE_LIST_ROW_TITLE_LENGTH) # Text displayed for the row
    description: Optional[constr(max_length=MAX_INTERACTIVE_LIST_ROW_DESC_LENGTH)] = None # Optional description below the title

class InteractiveListSection(BaseModelWA):
    """Structure for a section within an interactive list message."""
    # Title is optional for a section, but recommended if multiple sections exist
    title: Optional[constr(max_length=MAX_INTERACTIVE_LIST_SECTION_TITLE_LENGTH)] = None
    rows: conlist(InteractiveListRow, min_length=1, max_length=10) # Each section must have at least one row.

class InteractiveActionList(BaseModelWA):
    """Structure for the 'action' object when sending an interactive message of type 'list'."""
    button: constr(min_length=1, max_length=MAX_INTERACTIVE_BUTTON_TEXT_LENGTH) # Text on the button that opens the list.
    sections: conlist(InteractiveListSection, min_length=1, max_length=10) # Must have at least one section.

    @field_validator('sections')
    @classmethod
    def check_total_rows_in_list(cls, v: List[InteractiveListSection]) -> List[InteractiveListSection]:
        """Validates that the total number of rows across all sections does not exceed 10."""
        total_rows = sum(len(section.rows) for section in v)
        if total_rows > 10:
            raise ValueError("Total number of rows across all sections in an interactive list cannot exceed 10.")
        return v

class InteractiveActionButton(BaseModelWA):
    """Structure for the 'action' object when sending an interactive message of type 'button'."""
    buttons: conlist(InteractiveButton, min_length=1, max_length=3) # 1 to 3 buttons required.

class InteractiveActionCtaUrlParameters(BaseModelWA):
    """Structure for the 'parameters' object within a 'cta_url' action."""
    display_text: constr(min_length=1, max_length=MAX_INTERACTIVE_CTA_URL_DISPLAY_TEXT_LENGTH) # Text on the button.
    url: HttpUrl # The URL to open. Pydantic validates the URL format.

    @field_serializer('url', when_used='json') # Serialize only when dumping to JSON-like dicts
    def serialize_url_to_string(self, url_obj: HttpUrl) -> str:
        """Ensures HttpUrl object is serialized as a plain string for JSON."""
        return str(url_obj)

class InteractiveActionCtaUrl(BaseModelWA):
    """Structure for the 'action' object when sending an interactive message of type 'cta_url'."""
    name: Literal["cta_url"] = "cta_url" # Fixed value for this action type.
    parameters: InteractiveActionCtaUrlParameters

class InteractiveFlowActionPayload(BaseModelWA):
    """Structure for the 'flow_action_payload' used with Flow actions (typically 'navigate')."""
    screen: str # The ID of the Flow screen to navigate to.
    data: Optional[Dict[str, Any]] = None # Optional input data for the target screen (must be non-empty if provided).

    @field_validator('data', mode='before')
    @classmethod
    def check_flow_data_not_empty(cls, v: Any) -> Any:
        """Ensures 'data' is not an empty dictionary if provided."""
        if v is not None and isinstance(v, dict) and not v:
             raise ValueError("Flow 'data' cannot be an empty object if provided.")
        return v

class InteractiveActionFlowParameters(BaseModelWA):
    """Structure for the 'parameters' object within a 'flow' action."""
    flow_message_version: Literal["3"] = "3" # Currently fixed at "3".
    flow_id: Optional[str] = None # Required if flow_name is not provided.
    flow_name: Optional[str] = None # Required if flow_id is not provided.
    flow_cta: constr(min_length=1, max_length=MAX_INTERACTIVE_CTA_URL_DISPLAY_TEXT_LENGTH) # Text on the button launching the Flow.
    flow_token: Optional[str] = Field(default=None, description="Optional unique token generated by the business.") # Optional identifier.
    mode: Optional[Literal["draft", "published"]] = Field(default="published", description="Mode of the Flow ('draft' or 'published').")
    # Flow action details
    flow_action: Optional[Literal["navigate", "data_exchange"]] = Field(default="navigate")
    flow_action_payload: Optional[InteractiveFlowActionPayload] = None # Required if flow_action is 'navigate'.

    @model_validator(mode='before')
    @classmethod
    def check_flow_parameter_logic(cls, values: Any) -> Any:
        """Validates interdependencies between Flow parameters."""
        if not isinstance(values, dict): return values # Allow early validation

        # Ensure either flow_id or flow_name is provided, but not both
        flow_id = values.get('flow_id')
        flow_name = values.get('flow_name')
        if not (flow_id or flow_name): raise ValueError("Either 'flow_id' or 'flow_name' must be provided for Flow action.")
        if flow_id and flow_name: raise ValueError("Provide either 'flow_id' or 'flow_name' for Flow action, not both.")

        # Validate payload based on action type
        flow_action = values.get('flow_action', 'navigate') # Default to navigate
        payload = values.get('flow_action_payload')
        if flow_action == "navigate" and payload is None:
            # API examples imply payload is needed for navigate, even if empty 'data' inside.
            raise ValueError("'flow_action_payload' (with 'screen') is required when 'flow_action' is 'navigate'.")
        if flow_action == "data_exchange" and payload is not None:
            raise ValueError("'flow_action_payload' must be omitted when 'flow_action' is 'data_exchange'.")
        return values

class InteractiveActionFlow(BaseModelWA):
    """Structure for the 'action' object when sending an interactive message of type 'flow'."""
    name: Literal["flow"] = "flow" # Fixed value for this action type.
    parameters: InteractiveActionFlowParameters


class InteractiveMessageSend(BaseModelWA):
    """
    Root structure for the 'interactive' object when sending any interactive message.
    Validates that the 'action' object matches the specified 'type'.
    """
    type: Literal[InteractiveType.BUTTON, InteractiveType.LIST, InteractiveType.CTA_URL, InteractiveType.FLOW]
    header: Optional[InteractiveHeader] = None
    body: InteractiveBody # Body is required for all interactive types.
    footer: Optional[InteractiveFooter] = None
    # The action field structure depends on the 'type' field.
    action: Union[InteractiveActionList, InteractiveActionButton, InteractiveActionCtaUrl, InteractiveActionFlow]

    @model_validator(mode='before')
    @classmethod
    def check_action_matches_interactive_type(cls, values: Any) -> Any:
        """Ensures the structure of 'action' corresponds to the 'type'."""
        if not isinstance(values, dict): return values
        msg_type = values.get('type')
        action = values.get('action')
        if not action or not isinstance(action, dict):
            # Let specific action model validation handle missing/invalid action later
            return values

        # Check action structure based on the message type
        if msg_type == InteractiveType.LIST.value and "sections" not in action:
             raise ValueError("Action for interactive 'list' type must contain 'sections'.")
        if msg_type == InteractiveType.BUTTON.value and "buttons" not in action:
             raise ValueError("Action for interactive 'button' type must contain 'buttons'.")
        if msg_type == InteractiveType.CTA_URL.value and action.get("name") != "cta_url":
             raise ValueError("Action for interactive 'cta_url' type must have name='cta_url'.")
        if msg_type == InteractiveType.FLOW.value and action.get("name") != "flow":
             raise ValueError("Action for interactive 'flow' type must have name='flow'.")
        return values


# -- Template Message Sending Models ---

class TemplateLanguage(BaseModelWA):
    """Structure for the 'language' object within a template message payload."""
    code: constr(min_length=1, max_length=MAX_TEMPLATE_LANG_CODE_LENGTH) # Language and locale code (e.g., "en_US").
    # policy: Optional[Literal["deterministic"]] = None # Policy for language selection (rarely needed).

class TemplateCurrency(BaseModelWA):
    """Structure for a 'currency' parameter object within a template component."""
    fallback_value: constr(min_length=1, max_length=MAX_TEMPLATE_CURRENCY_FALLBACK_LENGTH) # Text displayed if device can't format.
    code: str # ISO 4217 currency code (e.g., "USD", "EUR").
    amount_1000: int # Currency amount multiplied by 1000 (e.g., $12.34 is 12340).

class TemplateDateTime(BaseModelWA):
    """Structure for a 'date_time' parameter object within a template component."""
    # Only fallback_value is currently reliably supported via API for sending.
    fallback_value: constr(min_length=1, max_length=MAX_TEMPLATE_DATETIME_FALLBACK_LENGTH)
    # Future API versions might support structured date/time components.

class TemplateLocationSend(Location):
    """
    Structure for a 'location' parameter object within a template header component.
    Inherits from base Location but excludes the receive-only 'url'.
    """
    # Sending requires latitude and longitude. Name/address are for display text.
    url: None = Field(default=None, exclude=True) # Ensure 'url' is not included in serialization.

class TemplateParameter(BaseModelWA):
    """
    Structure for a single parameter within a template component's 'parameters' list.
    Exactly one of the value fields (text, currency, date_time, image, etc.) must be provided,
    matching the 'type' field.
    """
    type: Literal[ # The type of the parameter, determines which value field is used.
        TemplateParameterType.TEXT, TemplateParameterType.CURRENCY, TemplateParameterType.DATE_TIME,
        TemplateParameterType.IMAGE, TemplateParameterType.DOCUMENT, TemplateParameterType.VIDEO,
        TemplateParameterType.LOCATION, TemplateParameterType.PAYLOAD
    ]
    # Value fields (only one should be set per parameter)
    text: Optional[constr(max_length=MAX_TEMPLATE_PARAM_TEXT_LENGTH)] = None # For text replacement or URL button suffix.
    currency: Optional[TemplateCurrency] = None
    date_time: Optional[TemplateDateTime] = None
    image: Optional[MediaBase] = None # Requires MediaBase object with 'id' or 'link'.
    document: Optional[MediaBase] = None # Requires MediaBase object with 'id' or 'link'.
    video: Optional[MediaBase] = None # Requires MediaBase object with 'id' or 'link'.
    location: Optional[TemplateLocationSend] = None # Requires TemplateLocationSend object.
    payload: Optional[constr(max_length=MAX_TEMPLATE_BUTTON_PAYLOAD_LENGTH)] = None # For quick reply button parameters.

    @model_validator(mode='before')
    @classmethod
    def check_parameter_value_matches_type(cls, values: Any) -> Any:
        """Ensures exactly one value field is provided and it matches the parameter 'type'."""
        if not isinstance(values, dict): return values
        param_type = values.get('type')
        # Map parameter types to their corresponding value field names
        value_fields_map = {
            TemplateParameterType.TEXT: 'text', TemplateParameterType.CURRENCY: 'currency',
            TemplateParameterType.DATE_TIME: 'date_time', TemplateParameterType.IMAGE: 'image',
            TemplateParameterType.DOCUMENT: 'document', TemplateParameterType.VIDEO: 'video',
            TemplateParameterType.LOCATION: 'location', TemplateParameterType.PAYLOAD: 'payload'
        }
        expected_field = value_fields_map.get(param_type)
        if not expected_field:
             # Allow unknown types for forward compatibility? Or raise error?
             logger.warning(f"Validation skipped for unknown template parameter type: {param_type}")
             return values # Skip validation for unknown types

        # Check if the expected value field is present and not None
        if values.get(expected_field) is None: # Check for None explicitly
             raise ValueError(f"Template parameter of type '{param_type}' requires field '{expected_field}' to be set.")

        # Check if any *other* value field is also set
        provided_value_fields = 0
        for field_name in value_fields_map.values():
             if values.get(field_name) is not None:
                 provided_value_fields += 1

        if provided_value_fields > 1:
             raise ValueError(f"Template parameter of type '{param_type}' should only have the '{expected_field}' field set, but found multiple value fields.")

        return values

class TemplateButtonComponent(BaseModelWA):
    """
    Structure for a 'button' component within a template message payload.
    Used for defining quick reply or URL buttons associated with the template.
    """
    type: Literal[TemplateComponentType.BUTTON] = TemplateComponentType.BUTTON # Fixed type
    sub_type: Literal[TemplateButtonSubType.QUICK_REPLY, TemplateButtonSubType.URL] # Button behavior type.
    # Index of the button (0-indexed) as defined in the template creation UI.
    # Must be provided as a string.
    index: str
    # List containing *one* parameter object defining the button's dynamic content
    # (payload for quick reply, text suffix for URL).
    parameters: List[TemplateParameter]

    @field_validator('index', mode='before')
    @classmethod
    def check_index_is_digit_string(cls, v: Any) -> str:
        """Ensures index is provided as a string containing only digits."""
        if isinstance(v, int): return str(v) # Allow integer input, convert to string
        if isinstance(v, str) and v.isdigit(): return v
        raise ValueError("Template Button 'index' must be a string containing only digits (e.g., '0', '1').")

    # Using model_validator because field_validator has limitations accessing other fields easily in Pydantic v2
    @model_validator(mode='after') # Use 'after' to ensure sub_type and parameters exist
    def check_button_parameters_match_subtype(self) -> 'TemplateButtonComponent':
        """Validates the button parameter type and count based on the button sub_type."""
        if not self.parameters or len(self.parameters) != 1:
             raise ValueError(f"Template Button component (index {self.index}) must contain exactly one parameter object.")

        param = self.parameters[0]
        sub_type = self.sub_type # Access validated sub_type

        # Validate parameter type based on button sub_type
        if sub_type == TemplateButtonSubType.QUICK_REPLY and param.type != TemplateParameterType.PAYLOAD:
            raise ValueError(f"Quick reply button (index {self.index}) parameter type must be 'payload'.")
        if sub_type == TemplateButtonSubType.URL and param.type != TemplateParameterType.TEXT:
             raise ValueError(f"URL button (index {self.index}) parameter type must be 'text' (for the URL suffix).")

        # Validate parameter content length (already handled by constr in TemplateParameter, but double-check here if needed)
        # if param.type == TemplateParameterType.PAYLOAD and param.payload and len(param.payload) > MAX_TEMPLATE_BUTTON_PAYLOAD_LENGTH:
        #      raise ValueError(f"Quick reply payload exceeds max length {MAX_TEMPLATE_BUTTON_PAYLOAD_LENGTH}")
        # if param.type == TemplateParameterType.TEXT and param.text and len(param.text) > MAX_TEMPLATE_BUTTON_URL_SUFFIX_LENGTH:
        #      raise ValueError(f"URL button text (suffix) exceeds max length {MAX_TEMPLATE_BUTTON_URL_SUFFIX_LENGTH}")
        return self

class TemplateComponent(BaseModelWA):
    """
    Structure for a generic 'header' or 'body' component within a template message payload.
    """
    type: Literal[TemplateComponentType.HEADER, TemplateComponentType.BODY]
    parameters: Optional[List[TemplateParameter]] = None # List of parameters to substitute placeholders.

class TemplateSend(BaseModelWA):
    """
    Root structure for the 'template' object when sending a template message.
    """
    name: constr(min_length=1, max_length=MAX_TEMPLATE_NAME_LENGTH) # Name of the approved template.
    language: TemplateLanguage # Language object (code required).
    # List of components (header, body, buttons) that require parameters.
    # Order might matter depending on template structure.
    components: Optional[List[Union[TemplateComponent, TemplateButtonComponent]]] = None