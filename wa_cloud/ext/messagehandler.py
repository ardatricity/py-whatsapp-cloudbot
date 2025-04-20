# wa_cloud/ext/messagehandler.py

"""
Defines the MessageHandler class for processing incoming WhatsApp messages.
"""
import asyncio
import logging
from typing import Any, Union, Type

# Use relative imports for library components
from .basehandler import BaseHandler, HandlerCallbackType
from .filters import BaseFilter
from ..models import Message 
from ..bot import Bot

logger = logging.getLogger(__name__)

class MessageHandler(BaseHandler[Message]):
    """
    A handler specifically designed to process incoming `Message` updates.

    It uses filter objects to determine if a `Message` should be processed
    and executes the provided callback function if the filters match.

    Attributes:
        filters (BaseFilter): The filter criteria that a message must satisfy
                              for the handler to be triggered.
        callback (HandlerCallbackType[Message]): The function to execute for
                                                  matching messages.
    """
    def __init__(self, filters: BaseFilter, callback: HandlerCallbackType[Message]):
        """
        Initializes the MessageHandler.

        Args:
            filters: A `wa_cloud.ext.filters.BaseFilter` instance (or combination)
                     that determines which messages this handler will process.
            callback: The function (sync or async) to call when the filters match.
                      It must accept two arguments: the `wa_cloud.models.Message` object
                      and the `wa_cloud.Bot` instance.

        Raises:
            TypeError: If `filters` is not a BaseFilter instance or `callback` is not callable.
        """
        # Initialize the BaseHandler with the callback
        super().__init__(callback)

        # Validate and store the filters
        if not isinstance(filters, BaseFilter):
            raise TypeError("MessageHandler 'filters' argument must be an instance of BaseFilter (e.g., created using wa_cloud.ext.filters).")
        self.filters = filters
        logger.debug(f"MessageHandler initialized with filters: {type(filters).__name__}")

    def check_update(self, update: Any) -> bool:
        """
        Checks if the given update is a `Message` and if it matches the handler's filters.

        Args:
            update: The incoming update object (expected to be Any by the dispatcher).

        Returns:
            True if the update is a `Message` and passes the filters, False otherwise.
        """
        # Ensure the update is actually a Message object, as this handler only processes messages.
        if not isinstance(update, Message):
            # This check assumes the Application dispatcher sends parsed Message objects.
            # If it sent raw dicts or other types, this logic would need adjustment.
            return False

        # Apply the configured filters to the Message object.
        # The filter's __call__ method handles its specific logic.
        try:
            match = self.filters(update)
            logger.debug(f"Checking message {update.id} against filter {type(self.filters).__name__}: {'Match' if match else 'No match'}")
            return match
        except Exception as e:
             # Log unexpected errors during filter execution, treat as non-match
             logger.exception(f"Error executing filter {type(self.filters).__name__} on message {update.id}: {e}")
             return False


    async def handle_update(self, update: Message, bot: Bot) -> Any:
        """
        Executes the callback function for a message that matched the filters.

        This method is called by the Application dispatcher. It handles both
        synchronous and asynchronous callback functions.

        Args:
            update: The `wa_cloud.models.Message` object that passed `check_update`.
            bot: The `wa_cloud.Bot` instance.

        Returns:
            The result returned by the user's callback function.

        Raises:
            Any exception raised by the user's callback function will be caught
            and logged by the Application's task handler (`_handle_task_result`).
        """
        filter_type_name = type(self.filters).__name__
        callback_name = getattr(self.callback, '__name__', repr(self.callback))
        logger.debug(f"Executing MessageHandler callback '{callback_name}' for filter '{filter_type_name}' on message {update.id}")

        try:
            # Check if the user provided an async callback
            if asyncio.iscoroutinefunction(self.callback):
                # If async, await its execution
                return await self.callback(update, bot)
            else:
                # If synchronous, call it directly.
                # Note: Long-running synchronous callbacks can block the asyncio event loop.
                # Users should use async callbacks or manage blocking operations appropriately
                # (e.g., using asyncio.to_thread in Python 3.9+ or executor pools).
                # The library currently doesn't manage threading for sync callbacks automatically.
                logger.debug(f"Running synchronous callback '{callback_name}'. Consider using async for I/O operations.")
                return self.callback(update, bot)
        except Exception as e:
             # Although the Application's task handler logs exceptions, logging here
             # provides immediate context within the handler execution.
             logger.exception(f"Exception raised during execution of callback '{callback_name}': {e}")
             # Re-raise the exception so the Application's task handler sees it
             raise