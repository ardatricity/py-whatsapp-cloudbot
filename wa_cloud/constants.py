# wa_cloud/constants.py

"""
Defines constants and enumerations used throughout the wa_cloud library.

Includes API endpoint templates, default values, message types, limits, etc.
"""

from enum import Enum

# --- API Configuration ---
# Default base URL for the WhatsApp Cloud API Graph endpoint.
# See: https://developers.facebook.com/docs/graph-api/overview#versions
DEFAULT_API_BASE_URL = "https://graph.facebook.com/v22.0"

# API Endpoint Path Templates (relative to base URL)
# These will be formatted with phone_number_id or media_id by the Bot class.
MEDIA_ENDPOINT_TEMPLATE = "/{phone_number_id}/media"
MESSAGES_ENDPOINT_TEMPLATE = "/{phone_number_id}/messages"
MEDIA_DETAIL_ENDPOINT_TEMPLATE = "/{media_id}" # Used for GET (info/URL) and DELETE


# --- Enumerations ---

class MessageType(str, Enum):
    """
    Represents the `type` field in a WhatsApp message object (both incoming and outgoing).
    Based on values from webhook payloads and message sending documentation.
    """
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACTS = "contacts"
    INTERACTIVE = "interactive" # Covers button/list replies, flows, cta_url
    REACTION = "reaction"
    TEMPLATE = "template"
    ORDER = "order"               # For order-related messages (e.g., from catalogs)
    SYSTEM = "system"             # System messages (e.g., user changed group subject)
    UNKNOWN = "unknown"           # Message type not recognized by the library
    UNSUPPORTED = "unsupported"   # Known type, but not currently handled by the library


class InteractiveType(str, Enum):
    """
    Represents the subtype for an `interactive` message object.
    Distinguishes between sending interactive messages and receiving replies.
    """
    # Types used when *sending* interactive messages
    LIST = "list"
    BUTTON = "button"
    CTA_URL = "cta_url"
    FLOW = "flow"

    # Types received in webhooks as *replies* to interactive messages
    LIST_REPLY = "list_reply"
    BUTTON_REPLY = "button_reply"
    # Note: Flow replies might come via a separate mechanism or specific events


class TemplateComponentType(str, Enum):
    """Type of component within a Template message payload."""
    HEADER = "header"
    BODY = "body"
    BUTTON = "button"


class TemplateParameterType(str, Enum):
    """Type of parameter within a Template component's parameter object."""
    TEXT = "text"
    CURRENCY = "currency"
    DATE_TIME = "date_time"
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"
    LOCATION = "location"
    PAYLOAD = "payload" # Used for quick reply button parameters


class TemplateButtonSubType(str, Enum):
    """Subtype of a button component within a Template message."""
    QUICK_REPLY = "quick_reply"
    URL = "url"
    # Future types might include: call, otp, copy_code, etc.


# --- API Field Length Limits ---
# These constants define maximum character lengths for various API fields,
# primarily for validation within Pydantic models when *sending* messages.
# Some are official limits, others are reasonable defaults based on observation.

# General
MAX_TEXT_BODY_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024    # For Image, Video, Document

# Location
MAX_LOCATION_NAME_LENGTH = 1000 # Arbitrary but reasonable limit
MAX_LOCATION_ADDRESS_LENGTH = 1000 # Arbitrary but reasonable limit

# Interactive Messages
MAX_INTERACTIVE_HEADER_TEXT_LENGTH = 60
MAX_INTERACTIVE_BODY_TEXT_LENGTH = 1024 # Note: Shorter than standard text body
MAX_INTERACTIVE_FOOTER_TEXT_LENGTH = 60
MAX_INTERACTIVE_BUTTON_TEXT_LENGTH = 20  # For reply buttons & list button label
MAX_INTERACTIVE_BUTTON_ID_LENGTH = 256   # For reply button IDs
MAX_INTERACTIVE_LIST_SECTION_TITLE_LENGTH = 24
MAX_INTERACTIVE_LIST_ROW_TITLE_LENGTH = 24
MAX_INTERACTIVE_LIST_ROW_DESC_LENGTH = 72
MAX_INTERACTIVE_LIST_ROW_ID_LENGTH = 200 # For list row IDs
MAX_INTERACTIVE_CTA_URL_DISPLAY_TEXT_LENGTH = 30 # Recommended max for CTA/Flow buttons
MAX_INTERACTIVE_CTA_URL_LENGTH = 2000 # Practical URL length limit

# Contacts
MAX_CONTACT_FORMATTED_NAME_LENGTH = 1000 # Arbitrary reasonable limit
MAX_CONTACT_FIELD_LENGTH = 1000      # Arbitrary limit for other fields (name parts, etc.)

# Reaction
MAX_REACTION_EMOJI_LENGTH = 10       # Allow some buffer for multi-byte emojis or modifiers

# Template Messages
MAX_TEMPLATE_NAME_LENGTH = 512
MAX_TEMPLATE_LANG_CODE_LENGTH = 15
MAX_TEMPLATE_PARAM_TEXT_LENGTH = 500 # Arbitrary limit for text replacement parameters
MAX_TEMPLATE_CURRENCY_FALLBACK_LENGTH = 25
MAX_TEMPLATE_DATETIME_FALLBACK_LENGTH = 50
MAX_TEMPLATE_BUTTON_PAYLOAD_LENGTH = 1000 # Official limit for quick reply button payload
MAX_TEMPLATE_BUTTON_URL_SUFFIX_LENGTH = 2000 # Official limit for URL button parameter (suffix)