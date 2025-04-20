# examples/echo_bot.py
import logging
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# --- Logging and Environment Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
script_dir = Path(__file__).parent
dotenv_path = script_dir / '.env'
if dotenv_path.is_file():
    load_dotenv(dotenv_path=dotenv_path)
    logger.info(f"Loaded environment variables from: {dotenv_path}")
else:
    logger.warning(f".env file not found at: {dotenv_path}")

# --- Imports ---
try:
    from fastapi import FastAPI
except ImportError:
    logger.error("FastAPI not found. Install with: pip install 'python-whatsapp-cloudbot[fastapi]'")
    exit(1)

try:
    from wa_cloud import (
        Application, Bot, Message, MessageHandler, filters, WhatsAppError, APIError,
        MessageType # Import Enums used
    )
    from wa_cloud.webhooks import setup_fastapi_webhook
except ImportError as e:
     logger.error(f"Failed to import wa_cloud components. Install with `pip install -e .` or `pip install python-whatsapp-cloudbot`: {e}")
     exit(1)

# --- Configuration ---
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WEBHOOK_PATH = "/webhook"

if not all([WHATSAPP_TOKEN, PHONE_NUMBER_ID, VERIFY_TOKEN]):
    logger.critical("Missing required environment variables. Check .env file.")
    exit(1)

# --- Bot Logic ---
async def echo_handler(message: Message, bot: Bot):
    """Handles incoming text messages (excluding commands) and echoes them."""
    if message.text: # Ensure text object exists
        sender_id = message.chat_id
        received_text = message.text.body
        logger.info(f"Received text from {sender_id}: '{received_text}'")
        try:
            # Mark as read and show typing (optional, good UX)
            await bot.mark_as_read(message.id, show_typing=True)
            # Add a small delay to simulate processing
            await asyncio.sleep(1)
            # Send the echo reply
            await bot.send_text(to=sender_id, text=f"Echo: {received_text}")
            logger.info(f"Echo sent to {sender_id}")
        except APIError as e:
            logger.error(f"API Error sending echo to {sender_id}: {e}")
        except WhatsAppError as e:
            logger.error(f"Library Error sending echo to {sender_id}: {e}")
        except Exception as e:
             logger.exception(f"Unexpected error in echo_handler for {sender_id}")

async def start_command_handler(message: Message, bot: Bot):
     """Handles the /start command."""
     logger.info(f"Received /start command from {message.chat_id}")
     await bot.send_text(message.chat_id, "Hello! I'm an echo bot using wa_cloud.")

# --- Application Setup ---
def setup_app() -> FastAPI:
    """Configures and returns the FastAPI application."""
    logger.info("Setting up wa_cloud application...")
    bot = Bot(token=WHATSAPP_TOKEN, phone_number_id=PHONE_NUMBER_ID)
    application = Application(bot=bot)

    # Register handlers
    application.add_handler(MessageHandler(filters.Command("start"), start_command_handler))
    # Use ~filters.ANY_COMMAND to exclude commands from the echo handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.ANY_COMMAND, echo_handler))

    logger.info("Handlers registered.")

    # Create FastAPI app and setup webhook routes
    fastapi_app = FastAPI(title="wa_cloud Echo Bot")
    setup_fastapi_webhook(
        app=fastapi_app,
        application=application,
        webhook_path=WEBHOOK_PATH,
        verify_token=VERIFY_TOKEN,
        run_background_tasks=True # Recommended
    )
    logger.info("FastAPI webhook configured.")
    return fastapi_app

# --- Run the App ---
app = setup_app() # Initialize the app when the script loads

# Allow running with `python echo_bot.py`
if __name__ == "__main__":
     import uvicorn
     logger.info("Starting Uvicorn server for development...")
     port = int(os.getenv("PORT", 5000))
     uvicorn.run(
         "echo_bot:app", # Point to the app object in this file
         host="0.0.0.0", # Listen on all interfaces
         port=port,
         reload=True   # Enable auto-reload for development
      )