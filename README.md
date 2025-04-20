# py-whatsapp-cloudbot

[![PyPI version](https://badge.fury.io/py/py-whatsapp-cloudbot.svg)](https://badge.fury.io/py/py-whatsapp-cloudbot) 
[![License: LGPL-3](https://img.shields.io/badge/license-LGPL3-yellow.svg)](https://opensource.org/licenses/MIT)

An asynchronous, easy-to-use Python library for interacting with the official WhatsApp Cloud API, inspired by the structure and ease of use of `python-telegram-bot`.

This library provides an object-oriented interface to send messages, handle incoming webhooks using handlers and filters, manage media, and more, simplifying bot development for the WhatsApp Cloud platform.

## Key Features

*   **Asynchronous:** Built with `asyncio` and `httpx` for non-blocking I/O.
*   **Clean Interface:** Object-oriented design (`Bot`, `Application`, `Handlers`) for clear code structure.
*   **Message Handling:** Easily handle incoming messages (text, media, location, contacts, interactive replies, reactions) using a flexible handler system.
*   **Filtering:** Powerful filters (`filters.TEXT`, `filters.IMAGE`, `filters.Command`, `filters.Regex`, logical operators `& | ~`) to precisely target handlers.
*   **Message Sending:** Methods for sending all major message types supported by the Cloud API (text with markdown, media, templates, location, contacts, interactive messages, reactions).
*   **Media Management:** Helpers for uploading, downloading, and deleting media assets.
*   **Webhook Integration:** Utility function provided for easy integration with the FastAPI web framework.
*   **Typed:** Uses Python type hints for better code analysis and developer experience.
*   **Modeled:** Uses Pydantic models for robust validation of API responses and webhook payloads.

## Installation

Make sure you have Python 3.8 or higher installed.

```bash
pip install py-whatsapp-cloudbot
```

## Getting Started: Your First Echo Bot

This example demonstrates a simple bot that echoes back any text message it receives, using the FastAPI framework.

**1. Prerequisites:**

*   A Meta Developer Account and a configured Meta App.
*   A WhatsApp Business Account (WABA) linked to your App.
*   A Phone Number ID registered with your WABA.
*   A Permanent System User Access Token (recommended) or a temporary token from your App's "WhatsApp > API Setup" page.

**2. Environment Variables:**

Create a `.env` file in your project directory (e.g., inside `examples/`) to store your credentials securely. The library (using `python-dotenv` in the example) will load these.

```dotenv
# examples/.env.example
WHATSAPP_TOKEN="YOUR_WHATSAPP_API_TOKEN"
PHONE_NUMBER_ID="YOUR_PHONE_NUMBER_ID"
VERIFY_TOKEN="YOUR_CHOSEN_WEBHOOK_VERIFY_TOKEN" # A secret string you create
# PORT=5000 # Optional: Defaults to 5000 in the example
```

*   **`WHATSAPP_TOKEN`**: Your API access token.
*   **`PHONE_NUMBER_ID`**: The ID of the phone number sending messages.
*   **`VERIFY_TOKEN`**: A secret string *you define*. You'll need this when setting up the webhook in the Meta Developer Dashboard.

**3. Example Code (`echo_bot.py`):**

```python
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
    logger.error("FastAPI not found. Install with: pip install 'py-whatsapp-cloudbot[fastapi]'")
    exit(1)

try:
    from wa_cloud import (
        Application, Bot, Message, MessageHandler, filters, WhatsAppError, APIError,
        MessageType # Import Enums used
    )
    from wa_cloud.webhooks import setup_fastapi_webhook
except ImportError as e:
     logger.error(f"Failed to import wa_cloud components. Install with `pip install -e .` or `pip install py-whatsapp-cloudbot`: {e}")
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

```

**4. Run Your Bot Script:**

Before configuring the webhook, your bot server needs to be running to respond to Meta's verification request.

*   Make sure your virtual environment is active.
*   Navigate to the directory containing `echo_bot.py` (or run from the root if imports are set up correctly for that).
*   Start the server:
    ```bash
    # If echo_bot.py is inside examples/ and you are in the root directory:
    uvicorn examples.echo_bot:app --reload --port 5000

    # If you are inside examples/:
    # uvicorn echo_bot:app --reload --port 5000
    ```
*   You should see logs indicating Uvicorn is running (e.g., on `http://127.0.0.1:5000`).

**5. Expose Your Bot with Ngrok:**

Your local server needs a public URL.

*   Open a **new terminal**.
*   Run ngrok (adjust port if necessary):
    ```bash
    ngrok http 5000
    ```
*   Copy the **HTTPS** Forwarding URL provided by ngrok (e.g., `https://<id>.ngrok-free.app`).

**6. Configure Meta Webhook:**

Tell WhatsApp where to send events.

*   Go to your Meta App Dashboard > WhatsApp > Configuration.
*   Click "Edit" in the Webhook section.
*   **Callback URL:** Paste the ngrok HTTPS URL + your `WEBHOOK_PATH` (e.g., `https://<id>.ngrok-free.app/webhook`).
*   **Verify token:** Enter the exact `VERIFY_TOKEN` string from your `.env` file.
*   Click "Verify and save". Check your Uvicorn logs – you should see a `GET /webhook` request and a "Webhook verification successful" log message.
*   **Subscribe:** Click "Manage" next to Webhook fields and ensure `messages` is subscribed.

**7. Test:**

*   Send a text message from your personal WhatsApp to your bot's number.
*   You should see activity in the Uvicorn logs (webhook POST received, message processed).
*   Your bot should reply with "Echo: [Your Message]".
*   Try sending `/start`.

## Core Concepts

*   **`Bot` (`wa_cloud.Bot`)**: Handles communication *to* the WhatsApp API (sending messages, uploading media). Requires token and phone number ID.
*   **`Application` (`wa_cloud.Application`)**: Orchestrates incoming updates. It holds the `Bot` instance and a list of handlers. It processes webhook payloads and dispatches updates.
*   **Handlers (e.g., `wa_cloud.MessageHandler`)**: Define *how* to react to updates. You register these with the `Application`. They consist of filters and a callback function.
*   **Filters (`wa_cloud.filters`)**: Determine *if* a handler should process an update based on criteria (message type, text content, command, etc.). Combine filters using `&` (AND), `|` (OR), `~` (NOT).
*   **Models (`wa_cloud.models`)**: Pydantic models representing WhatsApp objects (`Message`, `Contact`, etc.) for data validation and easier access.

## Sending Messages (Examples)

All `send_*` methods are asynchronous and available on the `Bot` instance.

```python
import wa_cloud
from wa_cloud.models import MediaBase # For media headers/params

# Assume 'bot' is an initialized wa_cloud.Bot instance
# Assume 'chat_id' is the recipient's WA ID (e.g., "16505551234")

# Send Text
await bot.send_text(chat_id, "Simple text message.")
await bot.send_text(chat_id, "*Bold* and _italic_ text.", preview_url=False)

# Send Image (using previously uploaded media ID)
try:
    # response = await bot.upload_media("path/to/image.jpg")
    # media_id = response.id
    media_id = "YOUR_UPLOADED_IMAGE_MEDIA_ID" # Replace
    if media_id:
         await bot.send_image(chat_id, media_id=media_id, caption="Optional caption.")
except Exception as e:
    print(f"Error sending image: {e}")

# Send Document (using link - not recommended for performance)
# await bot.send_document(
#     chat_id,
#     link="https://www.example.com/report.pdf",
#     filename="Annual Report.pdf",
#     caption="See attached report."
# )

# Send Location
# await bot.send_location(chat_id, latitude=..., longitude=..., name="...")

# Send Reaction
# await bot.send_reaction(chat_id, message_id="wamid_of_target_message", emoji="👍")
```

*(See the `full_test_bot.py` example in the repository for more sending methods like interactive messages, templates, contacts, etc.)*

## Handling Updates

Create `async` functions (callbacks) and register them with `MessageHandler` using appropriate `filters`.

```python
from wa_cloud import filters, Message, Bot, MessageType

async def handle_images(message: Message, bot: Bot):
    if message.image: # Check if image object exists
        print(f"Received image! Media ID: {message.media_id}")
        await bot.send_text(message.chat_id, f"Got your image! Caption: {message.caption or 'None'}")
        await bot.mark_as_read(message.id)

async def handle_order_command(message: Message, bot: Bot):
    # Example: /order 12345
    match = re.match(r"/order\s+(\d+)", message.text.body)
    if match:
        order_id = match.group(1)
        print(f"Processing order command for ID: {order_id}")
        await bot.send_text(message.chat_id, f"Looking up order {order_id}...")
        await bot.mark_as_read(message.id)

# In your setup:
# application.add_handler(MessageHandler(filters.IMAGE, handle_images))
# application.add_handler(MessageHandler(filters.Command("order"), handle_order_command))
```

## Error Handling

API calls made via the `Bot` instance can raise exceptions defined in `wa_cloud.error`. Wrap calls in `try...except` blocks.

```python
from wa_cloud import APIError, NetworkError, WhatsAppError

try:
    await bot.send_text(chat_id, "Risky message!")
except APIError as e:
    logger.error(f"API Error: {e} - Response Data: {e.response_data}")
except NetworkError as e:
    logger.error(f"Network Error: {e}")
    # Maybe implement retry logic
except WhatsAppError as e:
    logger.error(f"Library Error: {e}")
except Exception as e:
    logger.exception("An unexpected error occurred.")
```

## Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request on the [GitHub repository](https://github.com/ardatricity/py-whatsapp-cloudbot).

## License


You may copy, modify, and distribute this software under the terms of the [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html>). Any modifications or derivative works must also be licensed under LGPL‑3, but applications that merely use or link to the library are exempt from its requirements.
