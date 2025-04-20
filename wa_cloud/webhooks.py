# wa_cloud/webhooks.py

"""
Webhook integration helpers, currently focusing on FastAPI.

Provides utilities to easily integrate the wa_cloud Application
with web frameworks for receiving WhatsApp webhook events.
"""

import logging
from typing import Optional

# Attempt to import FastAPI components. These are optional dependencies.
try:
    from fastapi import (FastAPI, Request, Response, HTTPException,
                         BackgroundTasks)
    _FASTAPI_AVAILABLE = True
except ImportError:
    # Define dummy types if FastAPI is not installed, allowing type hinting
    # but preventing runtime errors if the helper function is called without FastAPI.
    FastAPI = None # type: ignore
    Request = None # type: ignore
    Response = None # type: ignore
    HTTPException = None # type: ignore
    BackgroundTasks = None # type: ignore
    _FASTAPI_AVAILABLE = False

# Use relative import for Application class
from .application import Application

logger = logging.getLogger(__name__)

def setup_fastapi_webhook(
    app: FastAPI,               # type: ignore # Ignore type check if FastAPI is None
    application: Application,
    webhook_path: str,
    verify_token: str,
    run_background_tasks: bool = True
):
    """
    Configures GET and POST endpoints on a FastAPI application for WhatsApp webhooks.

    This helper function adds two routes to your existing FastAPI `app`:
    1. GET `webhook_path`: Handles the webhook verification challenge from Meta.
    2. POST `webhook_path`: Receives event notifications (like messages) from WhatsApp,
       parses the payload, and passes it to the `application` for processing.

    It also registers FastAPI startup and shutdown event handlers to manage the
    lifecycle of the provided `wa_cloud.Application` instance.

    Args:
        app: The `fastapi.FastAPI` application instance.
        application: The initialized `wa_cloud.Application` instance.
        webhook_path: The URL path for the webhook endpoint (e.g., "/webhook").
                      It will be prefixed with '/' if not already present.
        verify_token: The secret token string configured in the Meta Developer Dashboard
                      for webhook verification.
        run_background_tasks: If True (default), webhook processing via
                              `application.process_webhook_payload` is run as a
                              FastAPI background task. This allows the endpoint to
                              return `200 OK` to WhatsApp immediately, which is
                              recommended. If False, processing happens synchronously
                              within the request handler.

    Raises:
        ImportError: If `fastapi` is not installed when this function is called.
        TypeError: If `app` is not a FastAPI instance or `application` is not
                   an Application instance (basic checks).
    """
    if not _FASTAPI_AVAILABLE:
        # Raise error immediately if FastAPI couldn't be imported
        raise ImportError("FastAPI framework not found. Please install it (`pip install fastapi uvicorn`) to use `setup_fastapi_webhook`.")

    # Basic type checks for arguments
    if FastAPI and not isinstance(app, FastAPI): # Check only if FastAPI was imported
         raise TypeError("Argument `app` must be an instance of `fastapi.FastAPI`.")
    if not isinstance(application, Application):
         raise TypeError("Argument `application` must be an instance of `wa_cloud.Application`.")

    # Ensure webhook path starts with a slash
    if not webhook_path.startswith("/"):
        webhook_path = "/" + webhook_path

    logger.info(f"Setting up FastAPI webhook endpoints on path: {webhook_path}")

    # --- Webhook Verification Endpoint (GET) ---
    @app.get(webhook_path, summary="Verify WhatsApp Webhook", tags=["WhatsApp Webhook"])
    async def verify_webhook_endpoint(request: Request): # type: ignore
        """
        Handles the GET request from Meta to verify the webhook endpoint.
        Compares the verify token and returns the challenge.
        """
        params = request.query_params
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        # Log the verification attempt details
        logger.debug(f"Webhook Verification Request: mode='{mode}', token_present={token is not None}, challenge_present={challenge is not None}")

        # Check if mode and token match expected values
        if mode == "subscribe" and token == verify_token:
            logger.info("Webhook verification successful.")
            if challenge:
                # Return the challenge value as plain text with 200 OK
                return Response(content=str(challenge), media_type="text/plain", status_code=200)
            else:
                # This case shouldn't occur per Meta docs, but handle it.
                logger.warning("Webhook verification token matched, but 'hub.challenge' parameter was missing.")
                return Response(content="OK", media_type="text/plain", status_code=200)
        else:
            # Verification failed
            logger.warning(
                f"Webhook verification failed. Received mode='{mode}', token='{token}'. Expected token was set."
            )
            # Return 403 Forbidden status code
            raise HTTPException(status_code=403, detail="Webhook verification failed: Invalid mode or token.")

    # --- Webhook Event Handling Endpoint (POST) ---
    @app.post(webhook_path, summary="Handle WhatsApp Event Notifications", status_code=200, tags=["WhatsApp Webhook"])
    # The BackgroundTasks dependency will be injected by FastAPI
    async def handle_webhook_endpoint(request: Request, background_tasks: BackgroundTasks): # type: ignore
        """
        Handles the POST request containing event notifications (e.g., messages) from WhatsApp.
        Parses the JSON payload and dispatches it for processing via the Application instance.
        """
        try:
            # Get raw body for logging snippet, then parse JSON
            payload_bytes = await request.body()
            payload_json = await request.json()

            # Log a snippet of the raw payload for debugging (avoid logging sensitive data if possible)
            log_snippet = payload_bytes[:500].decode('utf-8', errors='replace')
            logger.info(f"Webhook POST received ({len(payload_bytes)} bytes): {log_snippet}{'...' if len(payload_bytes) > 500 else ''}")

            # Process the payload using the Application instance
            if run_background_tasks:
                 # Add processing to background tasks to return 200 OK quickly
                 background_tasks.add_task(application.process_webhook_payload, payload_json)
                 logger.debug("Webhook payload processing added to background tasks.")
                 # Return standard success response expected by Meta
                 return Response(content="EVENT_RECEIVED", status_code=200, media_type="text/plain")
            else:
                 # Process synchronously (not recommended for production)
                 logger.debug("Processing webhook payload synchronously...")
                 await application.process_webhook_payload(payload_json)
                 logger.debug("Synchronous webhook processing complete.")
                 # Return success after processing (might timeout if processing is slow)
                 return Response(content="EVENT_PROCESSED", status_code=200, media_type="text/plain")

        except Exception as e:
            # Log any exception during payload parsing or dispatch initiation
            logger.exception(f"Error processing webhook POST request: {e}")
            # Raise HTTPException to return a 500 Internal Server Error response
            # This signals to Meta that processing failed for this event.
            raise HTTPException(status_code=500, detail="Internal server error processing webhook event.")

    # --- Application Lifecycle Integration ---
    # Use FastAPI's event handlers to initialize and shut down the wa_cloud Application
    @app.on_event("startup")
    async def fastapi_startup_event():
        """Initializes the wa_cloud Application when FastAPI starts."""
        logger.info("FastAPI startup event: Initializing wa_cloud Application...")
        await application.initialize()
        logger.info("wa_cloud Application initialized.")

    @app.on_event("shutdown")
    async def fastapi_shutdown_event():
        """Shuts down the wa_cloud Application gracefully when FastAPI stops."""
        logger.info("FastAPI shutdown event: Shutting down wa_cloud Application...")
        await application.shutdown()
        logger.info("wa_cloud Application shutdown complete.")

    logger.info("FastAPI webhook endpoint setup and lifecycle events registered.")