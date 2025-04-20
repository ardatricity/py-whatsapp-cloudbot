# wa_cloud/application.py

"""
Defines the Application class responsible for processing incoming updates
and dispatching them to appropriate handlers.
"""
import asyncio
import logging
from typing import List, Optional, Type, Any, Set # Added Set for task tracking

from pydantic import ValidationError

# Use relative imports within the library
from .bot import Bot
from .models import WebhookPayload, Message # Import only needed models here
from .ext.basehandler import BaseHandler
from .error import WhatsAppError # Import base error if needed

logger = logging.getLogger(__name__)

class Application:
    """
    The main class that orchestrates the bot's update processing.

    It receives webhook payloads, parses them, extracts relevant updates
    (like messages), and dispatches them to registered handlers.

    Attributes:
        bot (Bot): The Bot instance used for API interactions.
        handlers (List[BaseHandler]): The list of registered handlers.
    """
    def __init__(self, bot: Bot):
        """
        Initializes the Application.

        Args:
            bot: An initialized Bot instance.
        """
        if not isinstance(bot, Bot):
             raise TypeError("Application requires a valid wa_cloud.Bot instance.")
        self.bot = bot
        self.handlers: List[BaseHandler] = []
        self._running = False # State flag, potentially useful for future features
        # Use a set for efficient addition/removal of tasks
        self._tasks: Set[asyncio.Task] = set()

    def add_handler(self, handler: BaseHandler):
        """
        Registers a handler to process updates.

        Handlers are checked in the order they are added.

        Args:
            handler: An instance of a class derived from BaseHandler.

        Raises:
            TypeError: If the provided handler is not a BaseHandler instance.
        """
        if not isinstance(handler, BaseHandler):
            raise TypeError("Handler must be an instance of a BaseHandler subclass.")
        self.handlers.append(handler)
        logger.info(f"Handler added: {type(handler).__name__}")

    def add_handlers(self, handlers: List[BaseHandler]):
        """
        Registers multiple handlers at once.

        Args:
            handlers: A list of BaseHandler instances.
        """
        for handler in handlers:
            self.add_handler(handler) # Reuse single add_handler for validation

    async def process_webhook_payload(self, payload: dict):
        """
        Processes a raw webhook payload received from WhatsApp.

        Validates the payload structure, extracts messages or other relevant updates,
        and initiates the dispatch process.

        Args:
            payload: The raw dictionary payload received from the webhook POST request.
        """
        try:
            # 1. Validate the payload against the Pydantic model
            webhook_data = WebhookPayload.model_validate(payload)
            logger.debug(f"Webhook payload validated for object: {webhook_data.object}")

            # 2. Extract processable updates (currently focusing on messages)
            updates_to_process: List[Any] = []
            if webhook_data.entry:
                for entry in webhook_data.entry:
                    if entry.changes:
                        for change in entry.changes:
                            # Currently, we primarily handle 'messages' field changes
                            if change.field == "messages" and change.value and change.value.messages:
                                for msg in change.value.messages:
                                    # Future enhancement: Could enrich message objects here if needed
                                    updates_to_process.append(msg)
                                    logger.info(f"Message update found: {msg.id} (Type: {msg.type})")
                            # TODO: Implement handling for other change fields like 'statuses'
                            elif change.field == "statuses" and change.value and change.value.statuses:
                                 logger.debug(f"Received status updates: {change.value.statuses}")
                                 # for status in change.value.statuses:
                                 #    status_update = StatusUpdate.model_validate(status) # Assuming a StatusUpdate model
                                 #    updates_to_process.append(status_update)
                            # Handle other fields if necessary
                            else:
                                logger.debug(f"Ignoring unhandled change field: {change.field}")


            # 3. Dispatch extracted updates to handlers
            if updates_to_process:
                 logger.debug(f"Dispatching {len(updates_to_process)} update(s) to handlers.")
                 # Process updates sequentially for predictable handler execution order
                 # within a single webhook payload. Parallel processing across different
                 # payloads happens naturally due to async nature.
                 for update in updates_to_process:
                      await self._dispatch_update(update)
            else:
                logger.debug("No processable updates found in the webhook payload.")

        except ValidationError as e:
            # Log validation errors clearly, showing the problematic payload parts if possible
            logger.error(f"Webhook payload validation failed: {e}")
        except Exception as e:
            # Catch-all for unexpected errors during processing
            logger.exception(f"Unexpected error processing webhook payload: {e}")


    async def _dispatch_update(self, update: Any):
         """
         Finds appropriate handlers for a given update and schedules their execution.

         Args:
             update: The extracted update object (e.g., a Message instance).
         """
         logger.debug(f"Dispatching update of type {type(update).__name__}")
         found_handler = False
         for handler in self.handlers:
             # Check if the handler is appropriate for this update
             if handler.check_update(update):
                 found_handler = True
                 logger.debug(f"Matching handler found for update: {type(handler).__name__}")

                 # Schedule handler execution as an independent asyncio task
                 # This allows the webhook endpoint to return quickly
                 task = asyncio.create_task(self._execute_handler(handler, update))

                 # Keep track of running tasks for graceful shutdown
                 self._tasks.add(task)

                 # Add a callback to remove the task from the set when it's done
                 # and log any potential errors from the handler execution.
                 task.add_done_callback(self._handle_task_result)

                 # --- Handler Execution Strategy ---
                 # Currently, all matching handlers will be executed.
                 # To implement PTB-style groups where only the first match in a group runs,
                 # additional logic involving handler groups and returning a specific signal
                 # from check_update/handle_update would be needed.
                 # For now, we proceed to check the next handler.
                 # If 'break' was uncommented here, only the first matching handler would run.
                 # break

         if not found_handler:
             logger.debug(f"No matching handler found for update of type {type(update).__name__}")


    async def _execute_handler(self, handler: BaseHandler, update: Any):
        """
        Executes a single handler's callback safely within an asyncio task.

        Args:
            handler: The handler instance to execute.
            update: The update object to pass to the handler.
        """
        handler_name = type(handler).__name__
        try:
            logger.debug(f"Executing handler: {handler_name}")
            await handler.handle_update(update, self.bot)
            logger.debug(f"Handler execution finished: {handler_name}")
        except Exception as e:
            # Log exceptions occurring within the handler's callback
            logger.exception(f"Exception occurred in handler {handler_name}: {e}")
            # Future: Implement custom error handling logic if needed (e.g., notify admin)


    def _handle_task_result(self, task: asyncio.Task):
        """
        Callback attached to handler tasks to log errors and clean up the task set.
        """
        try:
            # Calling result() will re-raise any exception that occurred within the task
            task.result()
        except asyncio.CancelledError:
             logger.info(f"Handler task {task.get_name()} was cancelled.") # Expected during shutdown
        except Exception as e:
            # Log exceptions that weren't caught inside _execute_handler (should be rare)
            # or exceptions raised by task.result() itself.
            logger.exception(f"Exception bubbled up from handler task {task.get_name()}: {e}")
        finally:
            # Remove the completed/cancelled task from the tracking set
            self._tasks.discard(task)
            logger.debug(f"Removed task {task.get_name()} from tracking set. Remaining tasks: {len(self._tasks)}")


    # --- Application Lifecycle Methods ---
    # These are typically called by the web server integration (e.g., via FastAPI events).

    async def initialize(self):
        """
        Performs asynchronous initialization tasks for the application.
        (Currently logs only, can be expanded).
        """
        logger.info("Initializing Application...")
        self._running = True
        # Potential future use: Validate bot token, fetch bot info, etc.
        # try:
        #     # Example: Hypothetical method to verify connection
        #     # await self.bot.verify_connection()
        #     logger.info("Bot connection verified.")
        # except Exception as e:
        #     logger.error(f"Failed to initialize application or verify bot connection: {e}")
        #     # Decide if failure here should prevent startup


    async def shutdown(self):
        """
        Performs graceful shutdown tasks for the application.

        Waits for currently running handler tasks to complete (with a timeout)
        and cancels any remaining tasks.
        """
        logger.info("Shutting down Application...")
        self._running = False

        if self._tasks:
             # Wait for tasks to complete, but with a timeout
             timeout_seconds = 10.0
             logger.info(f"Waiting up to {timeout_seconds}s for {len(self._tasks)} pending handler tasks to complete...")
             # Use asyncio.wait to wait for tasks with a timeout
             done, pending = await asyncio.wait(self._tasks, timeout=timeout_seconds)

             if pending:
                 logger.warning(f"{len(pending)} handler tasks did not complete within timeout.")
                 # Cancel tasks that didn't finish
                 for task in pending:
                     task.cancel()
                     logger.info(f"Cancelled pending task: {task.get_name()}")
                 # Wait briefly for cancelled tasks to finish cancelling
                 await asyncio.gather(*pending, return_exceptions=True)

             remaining_tasks = len(self._tasks) # Should be 0 if cleanup worked
             if remaining_tasks > 0:
                 logger.warning(f"Shutdown complete, but {remaining_tasks} tasks might remain in the tracking set.")
             else:
                 logger.info("All handler tasks completed or cancelled.")
        else:
            logger.info("No pending handler tasks to wait for.")

        logger.info("Application shutdown complete.")