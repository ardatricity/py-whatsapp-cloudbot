# wa_cloud/__init__.py

"""
wa_cloud

A Python library for interacting with the WhatsApp Cloud API,
providing an object-oriented interface for sending messages, handling webhooks,
managing media, and more.
"""

__version__ = "0.1.0"  # Current library version

import logging

# Configure root logger for the library to avoid adding handlers
# if the user doesn't configure logging.
# Users can configure logging by getting the 'wa_cloud' logger.
logging.getLogger(__name__).addHandler(logging.NullHandler())

# --- Core Classes ---
from .bot import Bot
from .application import Application

# --- Models ---
# Export commonly used models for type hinting and direct use.
# Includes received message types, sending payloads, and API responses.
from .models import (
    # Core Received/General
    Message, WebhookPayload, Contact, Location, Reaction, Text, Image, Video,
    Audio, Document, Sticker, ButtonReply, ListReply, Profile, ErrorData,
    # Sending Payloads
    ContactSend, ReactionSend, TemplateSend, InteractiveMessageSend,
    # API Responses
    SendMessageResponse, UploadMediaResponse, MediaInfoResponse,
    DeleteMediaResponse, SuccessResponse,
    # Add other relevant models from .models as needed for the public API
)

# --- Handlers & Filters ---
from .ext.messagehandler import MessageHandler
from .ext.filters import filters  # The pre-configured filters instance

# --- Exceptions ---
from .error import (
    WhatsAppError, APIError, NetworkError, AuthenticationError,
    BadRequestError, RateLimitError, ServerError
)

# --- Constants / Enums ---
# Export enums for type checking and comparison.
from .constants import (
    MessageType,
    InteractiveType,
    TemplateComponentType,
    TemplateParameterType,
    TemplateButtonSubType
)

# --- Optional Webhook Utilities ---
# Attempt to import framework-specific helpers; will be None if dependencies aren't met.
try:
    from .webhooks import setup_fastapi_webhook
except ImportError:
    setup_fastapi_webhook = None

# --- Public API Definition (`__all__`) ---
# Defines symbols exported when using 'from wa_cloud import *'
# and helps static analysis tools understand the public interface.
__all__ = [
    # Core Classes
    "Bot",
    "Application",

    # Handlers & Filters
    "MessageHandler",
    "filters",

    # Models (Selected for common use)
    "Message", "WebhookPayload", "Contact", "Location", "Reaction", "Text",
    "Image", "Video", "Audio", "Document", "Sticker", "ButtonReply",
    "ListReply", "Profile", "ErrorData",
    "ContactSend", "ReactionSend", "TemplateSend", "InteractiveMessageSend",
    "SendMessageResponse", "UploadMediaResponse", "MediaInfoResponse",
    "DeleteMediaResponse", "SuccessResponse",

    # Enums
    "MessageType",
    "InteractiveType",
    "TemplateComponentType",
    "TemplateParameterType",
    "TemplateButtonSubType",

    # Exceptions
    "WhatsAppError", "APIError", "NetworkError", "AuthenticationError",
    "BadRequestError", "RateLimitError", "ServerError",

    # Webhook Helper
    "setup_fastapi_webhook",

    # Version
    "__version__",
]