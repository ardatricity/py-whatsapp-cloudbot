# examples/full_test_bot.py
"""
Example Bot using the wa_cloud library with FastAPI.

This script demonstrates how to set up the Application, Bot, handlers,
and use various sending methods provided by the library. It includes
commands to test different message types and media operations.
"""

import asyncio
import logging
import mimetypes
import os
from pathlib import Path
from typing import Dict, Optional

# Third-party imports
from dotenv import load_dotenv

# --- Setup Logging and Environment ---
# Basic logging configuration
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Optional: Enable debug logging for the library itself
# logging.getLogger("wa_cloud").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file located in the same directory
script_dir = Path(__file__).parent
dotenv_path = script_dir / '.env'
if dotenv_path.is_file():
    load_dotenv(dotenv_path=dotenv_path)
    logger.info(f"Loaded environment variables from: {dotenv_path}")
else:
    logger.warning(f".env file not found at: {dotenv_path}. Environment variables might be missing.")

# --- Attempt to import FastAPI and library components ---
try:
    from fastapi import FastAPI
except ImportError:
    logger.error("FastAPI not found. Please install it (`pip install wa_cloud[fastapi]`) to run this example.")
    exit(1)

try:
    # Import components using the 'wa_cloud' import name
    from wa_cloud import (
        Application, Bot, Message, MessageHandler, filters, WhatsAppError, APIError, NetworkError,
        InteractiveType, MessageType # Enums needed for comparisons
    )
    # Import specific models needed for constructing payloads or type hinting
    from wa_cloud.models import (
        ContactSend, ContactNameSend, ContactPhoneSend, ContactEmailSend,
        InteractiveHeader, MediaBase, Location,
        InteractiveActionFlow, InteractiveActionFlowParameters, InteractiveFlowActionPayload,
        TemplateSend, TemplateLanguage, TemplateComponent, TemplateButtonComponent,
        TemplateParameter, TemplateCurrency, TemplateDateTime, TemplateLocationSend
    )
    # Import the webhook helper
    from wa_cloud.webhooks import setup_fastapi_webhook
except ImportError as e:
     logger.error(f"Failed to import wa_cloud components. Make sure the library is installed correctly (`pip install -e .`): {e}")
     exit(1)

# --- Load Configuration from Environment ---
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WEBHOOK_PATH = "/webhook" # URL path for the webhook endpoint

# Validate essential configuration
logger.info(f"WHATSAPP_TOKEN loaded: {'Yes' if WHATSAPP_TOKEN else 'No'}")
logger.info(f"PHONE_NUMBER_ID loaded: {'Yes' if PHONE_NUMBER_ID else 'No'}")
logger.info(f"VERIFY_TOKEN loaded: {'Yes' if VERIFY_TOKEN else 'No'}")

if not all([WHATSAPP_TOKEN, PHONE_NUMBER_ID, VERIFY_TOKEN]):
    logger.critical("CRITICAL: Required environment variables missing (WHATSAPP_TOKEN, PHONE_NUMBER_ID, VERIFY_TOKEN). Check your .env file.")
    exit(1)

# --- Global State / Helpers (Example Only - Use Database in Production) ---
last_received_wamid: Optional[str] = None # Stores the WAMID of the last message received from a user
last_media_ids: Dict[str, str] = {} # Stores uploaded media IDs { 'image_jpg': id1, 'video': id2, ...}
SAMPLE_FILES_DIR = script_dir / "sample_files" # Directory containing sample media
DOWNLOADS_DIR = script_dir / "downloads" # Directory to save downloaded media

async def upload_sample_files(bot: Bot):
    """Helper function to upload sample files on startup or via command."""
    logger.info("Attempting to upload sample files...")
    # Ensure the sample files directory exists
    if not SAMPLE_FILES_DIR.is_dir():
        logger.warning(f"Sample files directory not found: {SAMPLE_FILES_DIR}. Skipping uploads.")
        return

    sample_files_map = {
        "image_jpg": SAMPLE_FILES_DIR / "test.jpg",
        "image_png": SAMPLE_FILES_DIR / "test.png",
        "video": SAMPLE_FILES_DIR / "test.mp4",
        "audio": SAMPLE_FILES_DIR / "test.mp3",
        "document": SAMPLE_FILES_DIR / "test.pdf",
        "sticker": SAMPLE_FILES_DIR / "test.webp",
        # Add a sample image intended for headers if available
        # "header_image": SAMPLE_FILES_DIR / "header_test.jpg",
    }

    # Create an isolated task group for uploads if needed, or run sequentially
    for key, file_path in sample_files_map.items():
        if file_path.is_file():
            try:
                # Let upload_media guess the MIME type
                response = await bot.upload_media(file_path)
                if response and response.id:
                    last_media_ids[key] = response.id
                    logger.info(f"Uploaded '{key}' ({file_path.name}) -> Media ID: {response.id}")
                else:
                    logger.warning(f"Upload successful for {key} but no Media ID received in response.")
            except (APIError, NetworkError, WhatsAppError, ValueError, FileNotFoundError) as e:
                logger.error(f"Failed to upload sample file '{key}' ({file_path.name}): {e}")
            except Exception as e:
                 logger.exception(f"Unexpected error uploading sample file '{key}' ({file_path.name})")
        else:
            logger.warning(f"Sample file not found, skipping upload: {file_path}")
    logger.info("Sample file upload process finished.")


# --- Handler Callback Functions ---

# 1. Command Handlers (Triggered by user sending commands like /help)

async def handle_help_command(message: Message, bot: Bot):
    """Sends a help message listing available test commands."""
    help_text = """*wa_cloud Test Bot Commands:*
/help - Show this message
/text - Send a simple text message
/format - Send text with Markdown formatting
/image - Send sample JPG image (run /upload first)
/video - Send sample MP4 video (run /upload first)
/audio - Send sample MP3 audio (run /upload first)
/document - Send sample PDF document (run /upload first)
/sticker - Send sample WEBP sticker (run /upload first)
/location - Send a sample static location pin
/contact - Send a sample contact card message
/buttons - Send a message with interactive reply buttons
/list - Send a message with an interactive list
/cta - Send a message with an interactive Call-To-Action URL button
/flow - Send a sample Flow message (requires valid Flow ID in code)
/template - Send the 'hello_world' template message
/react - React ❤️ to the last received message
/unreact - Remove reaction from the last received message
/mark_read - Mark the last received message as read
/upload - Re-upload sample media files from ./sample_files
/download <media_id> - Download media by its ID to ./downloads
/delete <media_id> - Delete uploaded media by its ID"""
    try:
        await bot.send_text(message.chat_id, help_text)
    except Exception as e: logger.error(f"Failed to send help message: {e}")

async def handle_send_text_command(message: Message, bot: Bot):
    """Handles /text command: Sends a plain text message."""
    logger.info(f"Command /text received from {message.chat_id}. Sending sample text.")
    try:
        # Show typing indicator immediately upon receipt
        await bot.mark_as_read(message.id, show_typing=True)

        # Simulate some processing time
        # await asyncio.sleep(0.5)

        await bot.send_text(message.chat_id, "This is a test text message from the wa_cloud bot!")
    
    except Exception as e: 
        logger.error(f"Error sending text command response: {e}")

async def handle_send_format_command(message: Message, bot: Bot):
    """Handles /format command: Sends text with Markdown."""
    logger.info(f"Command /format received from {message.chat_id}. Sending formatted text.")
    formatted_message = "*Bold*, _Italic_, ~Strikethrough~, ```Monospace```"
    try:
        await bot.mark_as_read(message.id, show_typing=True)
        await bot.send_text(message.chat_id, formatted_message)
    except Exception as e: logger.error(f"Error sending formatted text: {e}")

async def _send_sample_media(media_key: str, msg_type: str, bot: Bot, chat_id: str, **kwargs):
    """Internal helper to send different media types based on stored IDs."""
    logger.info(f"Command /{msg_type} received from {chat_id}.")
    media_id = last_media_ids.get(media_key)
    if media_id:
        logger.info(f"Sending sample {msg_type} using ID: {media_id}")
        try:
            if msg_type == "image":
                await bot.send_image(chat_id, media_id=media_id, **kwargs)
            elif msg_type == "video":
                await bot.send_video(chat_id, media_id=media_id, **kwargs)
            elif msg_type == "audio":
                await bot.send_audio(chat_id, media_id=media_id, **kwargs)
            elif msg_type == "document":
                await bot.send_document(chat_id, media_id=media_id, **kwargs)
            elif msg_type == "sticker":
                await bot.send_sticker(chat_id, media_id=media_id, **kwargs)
        except Exception as e: logger.error(f"Error sending {msg_type}: {e}")
    else:
        logger.warning(f"Cannot send {msg_type}: Sample media key '{media_key}' not found in uploaded IDs. Run /upload first.")
        await bot.send_text(chat_id, f"Sample {msg_type} media not uploaded. Run /upload first.")

async def handle_send_image_command(message: Message, bot: Bot):
    await _send_sample_media("image_jpg", "image", bot, message.chat_id, caption="Sample JPG Image")

async def handle_send_video_command(message: Message, bot: Bot):
    await _send_sample_media("video", "video", bot, message.chat_id, caption="Sample Video")

async def handle_send_audio_command(message: Message, bot: Bot):
    await _send_sample_media("audio", "audio", bot, message.chat_id)

async def handle_send_document_command(message: Message, bot: Bot):
    await _send_sample_media("document", "document", bot, message.chat_id, filename="SampleDoc.pdf", caption="Sample PDF Document")

async def handle_send_sticker_command(message: Message, bot: Bot):
    await _send_sample_media("sticker", "sticker", bot, message.chat_id)

async def handle_send_location_command(message: Message, bot: Bot):
    """Handles /location command: Sends a static location pin."""
    logger.info(f"Command /location received from {message.chat_id}. Sending sample location.")
    try:
        await bot.mark_as_read(message.id, show_typing=True)
        await bot.send_location(
            message.chat_id,
            latitude=34.052235, longitude=-118.243683, # Los Angeles
            name="Sample Location Pin", address="123 Example Blvd, Fakesville"
        )
    except Exception as e: logger.error(f"Error sending location: {e}")

async def handle_send_contact_command(message: Message, bot: Bot):
    """Handles /contact command: Sends a sample contact card."""
    logger.info(f"Command /contact received from {message.chat_id}. Sending sample contact.")
    try:
        await bot.mark_as_read(message.id, show_typing=True)
        # Construct the ContactSend object using models
        contact = ContactSend(
            name=ContactNameSend(formatted_name="Sam T. Test", first_name="Sam", last_name="Test"),
            phones=[ContactPhoneSend(phone="+15550001111", type="Mobile", wa_id="15550001111")], # Include wa_id for message button
            emails=[ContactEmailSend(email="sam.test@example.com", type="Work")]
        )
        await bot.send_contacts(message.chat_id, contacts=[contact])
    except Exception as e: logger.error(f"Error sending contact: {e}")

async def handle_send_buttons_command(message: Message, bot: Bot):
    """Handles /buttons command: Sends an interactive message with reply buttons."""
    logger.info(f"Command /buttons received from {message.chat_id}. Sending interactive buttons.")
    try:
        # Define buttons as list of dicts
        buttons = [
            {"id": "reply_yes", "title": "Yes"},
            {"id": "reply_no", "title": "No"},
            {"id": "reply_maybe", "title": "Maybe"},
        ]
        # Optionally define a header (text, image, video, document)
        header_image_id = last_media_ids.get("image_png") # Use PNG for example
        header = None
        if header_image_id:
             header = InteractiveHeader(type="image", image=MediaBase(id=header_image_id))
        else:
             header = InteractiveHeader(type="text", text="Button Demo Header")
             logger.warning("Sample PNG for button header not uploaded, using text header.")

        await bot.mark_as_read(message.id, show_typing=True)
        await bot.send_interactive_button(
            message.chat_id,
            body_text="Please select one of the options below.",
            buttons=buttons,
            header=header,
            footer_text="Interactive Buttons Footer"
        )
    except Exception as e: logger.error(f"Error sending buttons: {e}")

async def handle_send_list_command(message: Message, bot: Bot):
    """Handles /list command: Sends an interactive list message."""
    logger.info(f"Command /list received from {message.chat_id}. Sending interactive list.")
    try:
        # Define sections and rows
        sections = [
            {
                "title": "Category A",
                "rows": [
                    {"id": "a_item_1", "title": "Item A1", "description": "Description for A1"},
                    {"id": "a_item_2", "title": "Item A2"}
                ]
            },
            {
                "title": "Category B",
                "rows": [{"id": "b_item_1", "title": "Item B1"}]
            }
        ]
        
        await bot.mark_as_read(message.id, show_typing=True)
        
        # Lists only support text headers
        header = InteractiveHeader(type="text", text="Choose from List")
        await bot.send_interactive_list(
            message.chat_id,
            body_text="Select one item from the categories.",
            button_text="Show Items", # Text on button to open list
            sections=sections,
            header=header,
            footer_text="List Message Footer"
        )
    except Exception as e: logger.error(f"Error sending list: {e}")

async def handle_send_cta_command(message: Message, bot: Bot):
    """Handles /cta command: Sends an interactive Call-To-Action URL button."""
    logger.info(f"Command /cta received from {message.chat_id}. Sending CTA URL.")
    try:
        await bot.mark_as_read(message.id, show_typing=True)

        header = InteractiveHeader(type="text", text="Learn More")
        await bot.send_interactive_cta_url(
            message.chat_id,
            body_text="Visit the official WhatsApp Cloud API documentation.",
            display_text="Visit Docs", # Button text
            url="https://developers.facebook.com/docs/whatsapp/cloud-api/",
            header=header,
            footer_text="Opens developer portal"
        )
    except Exception as e: logger.error(f"Error sending CTA URL: {e}")

async def handle_send_flow_command(message: Message, bot: Bot):
    """Handles /flow command: Sends a sample Flow message (requires configuration)."""
    logger.info(f"Command /flow received from {message.chat_id}. Sending sample Flow.")
    # !!! IMPORTANT: Replace 'YOUR_FLOW_ID_HERE' with an actual Flow ID from your WhatsApp Manager !!!
    flow_id_to_use = "YOUR_FLOW_ID_HERE"
    # !!! IMPORTANT: Replace 'YOUR_START_SCREEN_ID' with the ID of the first screen in your Flow !!!
    start_screen_id = "YOUR_START_SCREEN_ID"

    if flow_id_to_use == "YOUR_FLOW_ID_HERE" or start_screen_id == "YOUR_START_SCREEN_ID":
         await bot.mark_as_read(message.id, show_typing=True)

         logger.warning("Flow ID or Start Screen ID placeholder not replaced in the code.")
         await bot.send_text(message.chat_id, "Cannot send Flow: Please replace placeholders 'YOUR_FLOW_ID_HERE' and 'YOUR_START_SCREEN_ID' in the `full_test_bot.py` script with your actual Flow details.")
         return

    try:
        # Construct the Flow action payload
        action_payload = InteractiveFlowActionPayload(
            screen=start_screen_id,
            data={"customer_name": "Test User", "initial_step": "greeting"} # Optional initial data
        )
        flow_params = InteractiveActionFlowParameters(
            flow_id=flow_id_to_use,
            flow_cta="Start Interactive Flow", # Button text
            flow_action="navigate",
            flow_action_payload=action_payload,
            mode="published" # Use "draft" to test draft versions
        )
        action = InteractiveActionFlow(parameters=flow_params)
        header = InteractiveHeader(type="text", text="Initiate Flow")

        await bot.mark_as_read(message.id, show_typing=True)

        await bot.send_interactive_flow(
            message.chat_id,
            body_text="Tap the button below to begin the interactive flow.",
            action=action,
            header=header,
            footer_text="Flow testing"
        )
    except Exception as e: logger.error(f"Error sending Flow: {e}")

async def handle_send_template_command(message: Message, bot: Bot):
    """Handles /template command: Sends the standard 'hello_world' template."""
    logger.info(f"Command /template received from {message.chat_id}. Sending 'hello_world' template.")
    # Assumes the default 'hello_world' template is available and approved in your WABA.
    template_name = "hello_world"
    language_code = "en_US" # Default language for hello_world
    try:
        # Construct the TemplateSend object (hello_world has no variables/components)
        template_payload = TemplateSend(
            name=template_name,
            language=TemplateLanguage(code=language_code)
            # No components needed for the basic hello_world template
        )
        await bot.mark_as_read(message.id, show_typing=True)

        await bot.send_template(message.chat_id, template=template_payload)
    except APIError as e:
         logger.error(f"API Error sending template '{template_name}': {e}")
         await bot.mark_as_read(message.id, show_typing=True)
         await bot.send_text(message.chat_id, f"Failed to send template '{template_name}'. Check if it exists and is approved. Error: {e}")
    except Exception as e: logger.error(f"Unexpected error sending template: {e}")

async def handle_react_command(message: Message, bot: Bot):
    """Handles /react command: Sends a ❤️ reaction to the last user message."""
    logger.info(f"Command /react received from {message.chat_id}.")

    target_id = message.id
    logger.info(f"Attempting to react to message ID: {target_id}")
    try:
        await bot.send_reaction(message.chat_id, message_id=target_id, emoji="❤️")
        logger.info(f"Reaction sent to message {target_id}")
    except Exception as e:
        logger.error(f"Error sending reaction to {target_id}: {e}")
        await bot.send_text(message.chat_id, f"Failed to react to message {target_id}. Error: {e}")

async def handle_unreact_command(message: Message, bot: Bot):
    """Handles /unreact command: Removes reaction from the last user message."""
    logger.info(f"Command /unreact received from {message.chat_id}.")
    
    target_id = message.id
    logger.info(f"Attempting to remove reaction from message ID: {target_id}")
    try:
        # Send empty emoji string to remove reaction
        await bot.send_reaction(message.chat_id, message_id=target_id, emoji="")
        logger.info(f"Un-reaction sent for message {target_id}")
    except Exception as e:
        logger.error(f"Error removing reaction from {target_id}: {e}")
        await bot.send_text(message.chat_id, f"Failed to remove reaction from {target_id}. Error: {e}")

async def handle_mark_read_command(message: Message, bot: Bot):
    """Handles /mark_read command: Marks the last received message as read."""
    logger.info(f"Command /mark_read received from {message.chat_id}.")
    target_id = message.id

    logger.info(f"Attempting to mark message as read: {target_id}")
    try:
        success = await bot.mark_as_read(target_id)
        logger.info(f"Mark as read result for {target_id}: {success}")
        await bot.send_text(message.chat_id, f"Mark as read successful for {target_id}: {success}")
    except Exception as e:
        logger.error(f"Error marking message {target_id} as read: {e}")
        await bot.send_text(message.chat_id, f"Failed to mark message {target_id} as read. Error: {e}")


async def handle_upload_command(message: Message, bot: Bot):
    """Handles /upload command: Re-uploads sample files."""
    logger.info(f"Command /upload received from {message.chat_id}. Re-uploading sample files.")
    await bot.mark_as_read(message.id, show_typing=True)
    await bot.send_text(message.chat_id, "Starting sample file upload...")
    await bot.mark_as_read(message.id, show_typing=True)
    await upload_sample_files(bot) # Call the async helper
    await bot.send_text(message.chat_id, f"Sample file upload complete. Current Media IDs: {last_media_ids}")

async def handle_download_command(message: Message, bot: Bot):
    """Handles /download <media_id> command: Downloads specified media."""
    logger.info(f"Command /download received from {message.chat_id}")
    parts = message.text.body.split(maxsplit=1)
    await bot.mark_as_read(message.id, show_typing=True)
    if len(parts) < 2:
        await bot.send_text(message.chat_id, "Usage: /download <media_id>")
        return

    media_id_to_download = parts[1].strip()
    if not media_id_to_download:
         await bot.send_text(message.chat_id, "Please provide a valid media ID after /download.")
         return

    logger.info(f"Attempting to download media with ID: {media_id_to_download}")
    await bot.send_text(message.chat_id, f"Attempting download for media ID: {media_id_to_download}...")
    await bot.mark_as_read(message.id, show_typing=True)
    try:
        
        # 1. Get media info (URL and crucially, MIME type for extension)
        info = await bot.get_media_info(media_id_to_download)
        logger.info(f"Obtained media info: URL={info.url}, MIME={info.mime_type}")

        # 2. Construct the full destination file path
        # Ensure downloads directory exists
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        # Guess file extension from MIME type
        extension = mimetypes.guess_extension(info.mime_type) or ".bin" # Use .bin as default fallback
        # Create filename using media_id and extension
        dest_file_path = DOWNLOADS_DIR / f"{media_id_to_download}{extension}"
        logger.info(f"Calculated destination path: {dest_file_path}")

        # 3. Call the simplified download_media with the full path
        file_path = await bot.download_media(info.url, dest_path=dest_file_path)

        logger.info(f"Successfully downloaded media to {file_path}")
        await bot.send_text(message.chat_id, f"Successfully downloaded media to: {dest_file_path.name}") # Send only filename back

    except ValueError as e: # Catch specific errors like missing mime type if logic changes
        logger.error(f"Value error during download for {media_id_to_download}: {e}")
        await bot.send_text(message.chat_id, f"Download error: {e}")
    except (APIError, NetworkError, WhatsAppError) as e: # Catch library-specific errors
        logger.error(f"Library error downloading media {media_id_to_download}: {e}")
        await bot.send_text(message.chat_id, f"Failed to download media (Error: {type(e).__name__}). Check logs.")
    except FileNotFoundError as e: # If get_media_info fails for bad ID
        logger.error(f"Could not get info for media {media_id_to_download}: {e}")
        await bot.send_text(message.chat_id, f"Cannot get info for media ID '{media_id_to_download}'. Does it exist?")
    except Exception as e: # Catch any other unexpected errors
        logger.exception(f"Unexpected error during download command for {media_id_to_download}")
        await bot.send_text(message.chat_id, "An unexpected error occurred during download. Please check server logs.")

async def handle_delete_media_command(message: Message, bot: Bot):
    """Handles /delete <media_id> command: Deletes specified uploaded media."""
    logger.info(f"Command /delete received from {message.chat_id}")
    parts = message.text.body.split(maxsplit=1)
    
    await bot.mark_as_read(message.id, show_typing=True)

    if len(parts) < 2:
        await bot.send_text(message.chat_id, "Usage: /delete <media_id>")
        return

    media_id_to_delete = parts[1].strip()
    if not media_id_to_delete:
         await bot.send_text(message.chat_id, "Please provide a valid media ID after /delete.")
         return

    logger.info(f"Attempting to delete media with ID: {media_id_to_delete}")
    await bot.send_text(message.chat_id, f"Attempting to delete media ID: {media_id_to_delete}...")
    await bot.mark_as_read(message.id, show_typing=True)

    try:
        success = await bot.delete_media(media_id_to_delete)
        logger.info(f"Deletion result for {media_id_to_delete}: {success}")
        # Remove from our simple cache if successful
        if success:
             keys_to_del = [key for key, value in last_media_ids.items() if value == media_id_to_delete]
             for key in keys_to_del:
                 del last_media_ids[key]
                 logger.info(f"Removed '{key}' from cached media IDs.")
        await bot.send_text(message.chat_id, f"Delete media result for '{media_id_to_delete}': {success}")
    except Exception as e: # Catch potential errors during the delete call itself
        logger.exception(f"Unexpected error during delete command for {media_id_to_delete}")
        await bot.send_text(message.chat_id, f"An error occurred while trying to delete media {media_id_to_delete}.")

# 2. Handlers for Processing Incoming User Messages
async def handle_incoming_text(message: Message, bot: Bot):
    """Handles regular text messages (non-commands). Stores WAMID."""
    global last_received_wamid
    last_received_wamid = message.id
    text_body = message.text.body if message.text else "[No Text Body]"
    logger.info(f"Incoming text from {message.chat_id}: '{text_body}' (Stored WAMID: {message.id})")
    # Simple acknowledgement - avoid echoing back directly to prevent loops
    try:
        await bot.mark_as_read(message.id, show_typing=True)
        await bot.send_text(message.chat_id, f"Received text. Use /help for test commands.")
    except Exception as e: logger.error(f"Error sending ACK for incoming text: {e}")

async def handle_incoming_media(message: Message, bot: Bot):
    """Handles incoming media messages (image, video, etc.). Stores WAMID."""
    global last_received_wamid
    last_received_wamid = message.id
    media_type = message.message_type.value # Get the string value like "image"
    media_id = message.media_id or "[No Media ID]"
    caption_info = f" Caption: '{message.caption}'" if message.caption else ""
    filename_info = f" Filename: '{message.filename}'" if message.filename else ""
    logger.info(f"Incoming {media_type} from {message.chat_id}. Media ID: {media_id}{caption_info}{filename_info}")
    try:
        await bot.mark_as_read(message.id, show_typing=True)
        await bot.send_text(message.chat_id, f"Received your {media_type}! Media ID: {media_id}. Use `/download {media_id}` to test download.")
    except Exception as e: logger.error(f"Error sending ACK for incoming media: {e}")

async def handle_incoming_location(message: Message, bot: Bot):
    """Handles incoming location messages. Stores WAMID."""
    global last_received_wamid
    last_received_wamid = message.id
    loc = message.location
    loc_str = f"Lat={loc.latitude}, Lon={loc.longitude}" if loc else "[No Location Data]"
    if loc:
        if loc.name: loc_str += f", Name='{loc.name}'"
        if loc.address: loc_str += f", Address='{loc.address}'"
    logger.info(f"Incoming location from {message.chat_id}: {loc_str}")
    try:
        ack_text = f"Received location: {loc.latitude}, {loc.longitude}" if loc else "Received location message, but data was missing."
        await bot.mark_as_read(message.id, show_typing=True)
        await bot.send_text(message.chat_id, ack_text)
    except Exception as e: logger.error(f"Error sending ACK for incoming location: {e}")

async def handle_incoming_contacts(message: Message, bot: Bot):
    """Handles incoming contact card messages. Stores WAMID."""
    global last_received_wamid
    last_received_wamid = message.id
    contact_names = [c.name.formatted_name for c in message.contacts] if message.contacts else []
    count = len(contact_names)
    names_str = ', '.join(contact_names) if contact_names else "[No Contacts]"
    logger.info(f"Incoming contacts ({count}) from {message.chat_id}: {names_str}")
    try:
        await bot.mark_as_read(message.id, show_typing=True)
        await bot.send_text(message.chat_id, f"Received {count} contact(s): {names_str}")
    except Exception as e: logger.error(f"Error sending ACK for incoming contacts: {e}")

async def handle_incoming_interactive(message: Message, bot: Bot):
    """Handles replies from interactive messages (buttons/lists). Stores WAMID."""
    global last_received_wamid
    last_received_wamid = message.id
    reply_type_str = "Unknown Interactive"
    reply_info_str = "N/A"

    if message.interactive:
        # Determine the type of reply and extract relevant info
        if message.interactive.type == InteractiveType.BUTTON_REPLY and message.interactive.button_reply:
            reply = message.interactive.button_reply
            reply_type_str = "Button Reply"
            reply_info_str = f"ID='{reply.id}', Title='{reply.title}'"
        elif message.interactive.type == InteractiveType.LIST_REPLY and message.interactive.list_reply:
            reply = message.interactive.list_reply
            reply_type_str = "List Reply"
            reply_info_str = f"ID='{reply.id}', Title='{reply.title}'"
            if reply.description:
                reply_info_str += f", Desc='{reply.description}'"
        else:
            reply_type_str = f"Unhandled Interactive Type ({message.interactive.type})"

    logger.info(f"Incoming {reply_type_str} from {message.chat_id}: {reply_info_str}")
    try:
        await bot.mark_as_read(message.id, show_typing=True)
        await bot.send_text(message.chat_id, f"Received your {reply_type_str}: {reply_info_str}")
    except Exception as e: logger.error(f"Error sending ACK for interactive reply: {e}")

async def handle_incoming_reaction(message: Message, bot: Bot):
    """Handles incoming reaction messages (user reacting to bot's message)."""
    # Don't store WAMID for reactions, as they can't be reacted to by the bot easily
    if message.reaction:
        emoji = message.reaction.emoji or "[Reaction Removed]"
        target_id = message.reaction.message_id
        logger.info(f"Incoming reaction from {message.chat_id}: Emoji='{emoji}', Target WAMID='{target_id}'")
        # It's often best practice *not* to send a message in response to a reaction.
        # try:
        #     await bot.send_text(message.chat_id, f"Thanks for the reaction: {emoji}")
        # except Exception as e: logger.error(f"Error sending ACK for incoming reaction: {e}")
    else:
        logger.warning(f"Received reaction message from {message.chat_id} but reaction object was missing.")
    # Cannot mark reactions as read

async def handle_unsupported(message: Message, bot: Bot):
    """Handles any message type not explicitly covered by other handlers."""
    global last_received_wamid
    last_received_wamid = message.id # Store WAMID even if unsupported
    logger.warning(f"Received unhandled message type '{message.type}' from {message.chat_id}. WAMID: {message.id}")
    try:
        await bot.mark_as_read(message.id, show_typing=True)
        await bot.send_text(message.chat_id, f"Sorry, I received a message of type '{message.type}' which I don't know how to process yet.")
    except Exception as e: logger.error(f"Error sending ACK for unsupported message type: {e}")


# --- Main Application Setup ---
def main() -> FastAPI: # Add return type hint
    """Sets up the Bot, Application, Handlers, and FastAPI app."""
    logger.info("--- Starting Bot Setup ---")

    # 1. Create Bot instance
    bot = Bot(token=WHATSAPP_TOKEN, phone_number_id=PHONE_NUMBER_ID)
    logger.info("Bot instance created.")

    # 2. Create Application instance
    application = Application(bot=bot)
    logger.info("Application instance created.")

    # --- Schedule Initial Sample File Upload ---
    # We run this after the event loop starts using FastAPI's startup event
    async def run_startup_uploads():
        logger.info("Running startup tasks: Uploading sample files...")
        # Optional short delay if needed for event loop stabilization
        # await asyncio.sleep(0.5)
        await upload_sample_files(bot)
        logger.info("Startup sample file upload task finished.")

    # Store the task function to be added to FastAPI startup later
    startup_tasks = [run_startup_uploads]

    # 3. Define Handlers
    # Command handlers should generally come first
    command_handlers = [
        MessageHandler(filters.Command("help"), handle_help_command),
        MessageHandler(filters.Command("text"), handle_send_text_command),
        MessageHandler(filters.Command("format"), handle_send_format_command),
        MessageHandler(filters.Command("image"), handle_send_image_command),
        MessageHandler(filters.Command("video"), handle_send_video_command),
        MessageHandler(filters.Command("audio"), handle_send_audio_command),
        MessageHandler(filters.Command("document"), handle_send_document_command),
        MessageHandler(filters.Command("sticker"), handle_send_sticker_command),
        MessageHandler(filters.Command("location"), handle_send_location_command),
        MessageHandler(filters.Command("contact"), handle_send_contact_command),
        MessageHandler(filters.Command("buttons"), handle_send_buttons_command),
        MessageHandler(filters.Command("list"), handle_send_list_command),
        MessageHandler(filters.Command("cta"), handle_send_cta_command),
        MessageHandler(filters.Command("flow"), handle_send_flow_command),
        MessageHandler(filters.Command("template"), handle_send_template_command),
        MessageHandler(filters.Command("react"), handle_react_command),
        MessageHandler(filters.Command("unreact"), handle_unreact_command),
        MessageHandler(filters.Command("mark_read"), handle_mark_read_command),
        MessageHandler(filters.Command("upload"), handle_upload_command),
        MessageHandler(filters.Command("download"), handle_download_command),
        MessageHandler(filters.Command("delete"), handle_delete_media_command),
    ]
    # Incoming message handlers (use ~filters.ANY_COMMAND to exclude commands)
    message_handlers = [
        MessageHandler(filters.TEXT & ~filters.ANY_COMMAND, handle_incoming_text),
        MessageHandler(filters.IMAGE & ~filters.ANY_COMMAND, handle_incoming_media),
        MessageHandler(filters.VIDEO & ~filters.ANY_COMMAND, handle_incoming_media),
        MessageHandler(filters.AUDIO & ~filters.ANY_COMMAND, handle_incoming_media),
        MessageHandler(filters.DOCUMENT & ~filters.ANY_COMMAND, handle_incoming_media),
        MessageHandler(filters.STICKER & ~filters.ANY_COMMAND, handle_incoming_media),
        MessageHandler(filters.LOCATION & ~filters.ANY_COMMAND, handle_incoming_location),
        MessageHandler(filters.CONTACTS & ~filters.ANY_COMMAND, handle_incoming_contacts),
        MessageHandler(filters.INTERACTIVE & ~filters.ANY_COMMAND, handle_incoming_interactive),
        MessageHandler(filters.REACTION & ~filters.ANY_COMMAND, handle_incoming_reaction),
        # Catch-all (optional, should be last if used)
        MessageHandler(filters.ALL & ~filters.ANY_COMMAND & ~filters.INTERACTIVE, handle_unsupported),
    ]

    # 4. Add Handlers to Application
    application.add_handlers(command_handlers)
    application.add_handlers(message_handlers)
    logger.info("All handlers added to the application.")

    # 5. Create FastAPI App
    fastapi_app = FastAPI(
        title="wa_cloud Test Bot",
        description="A comprehensive test bot for the wa_cloud library.",
        version="0.1.0" # Correlate with library version if desired
    )
    logger.info("FastAPI application instance created.")

    # 6. Setup Webhook Routes and Application Lifecycle via Helper
    setup_fastapi_webhook(
        app=fastapi_app,
        application=application,
        webhook_path=WEBHOOK_PATH,
        verify_token=VERIFY_TOKEN,
        run_background_tasks=True # Recommended for production
    )

    # 7. Add custom startup tasks (like uploading files)
    # @fastapi_app.on_event("startup")
    # async def custom_startup():
    #      # Schedule the startup tasks to run after FastAPI starts
    #      for task_func in startup_tasks:
    #          asyncio.create_task(task_func())

    logger.info("--- Bot Setup Complete ---")
    return fastapi_app

# --- Uvicorn Entry Point ---
# Create the FastAPI app instance by calling main() when the script is loaded
app = main()

# Allow running directly using `python examples/full_test_bot.py`
if __name__ == "__main__":
     import uvicorn
     logger.info("Starting Uvicorn development server...")
     port = int(os.getenv("PORT", 5000))
     # Bind to 0.0.0.0 to be accessible from network/Docker if needed
     # Use reload=True for development to automatically pick up code changes
     uvicorn.run(
         "full_test_bot:app", # Point uvicorn to the app object in this script
         host="0.0.0.0",
         port=port,
         reload=True
     )