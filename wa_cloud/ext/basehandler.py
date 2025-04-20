# wa_cloud/ext/basehandler.py

"""
This module defines the abstract base class for all update handlers.
"""

from abc import ABC, abstractmethod
# Import necessary types for hinting
from typing import Any, Callable, TypeVar, Generic, Coroutine
import logging

# Use relative imports for library components
from ..models import Message # Assuming Message is the primary update type for now
from ..bot import Bot

logger = logging.getLogger(__name__)

# --- Type Hint Definitions ---

# Define a generic type variable 'T' representing the specific update type
# that a concrete handler subclass will work with (e.g., Message).
UpdateType = TypeVar("UpdateType")

# Define the type for the callback function provided by the user.
# It should accept the specific update object (UpdateType) and a Bot instance.
# It can be a regular synchronous function or an async coroutine.
# The return type can be anything (Any), as the library doesn't enforce it.
HandlerCallbackType = Callable[[UpdateType, Bot], Coroutine[Any, Any, Any] | Any]


# --- Base Handler Class ---

class BaseHandler(ABC, Generic[UpdateType]):
    """
    Abstract base class for all update handlers.

    Subclasses must implement the `check_update` and `handle_update` methods.
    This class uses generics (`UpdateType`) to allow subclasses to specify
    the type of update object they expect.

    Attributes:
        callback (HandlerCallbackType): The function to be called when the handler
                                        matches an update.
    """

    def __init__(self, callback: HandlerCallbackType[UpdateType]):
        """
        Initializes the BaseHandler.

        Args:
            callback: The function (sync or async) to execute when this handler
                      is triggered. It must accept two arguments: the update object
                      and the `wa_cloud.Bot` instance.

        Raises:
            TypeError: If the provided `callback` is not callable.
        """
        if not callable(callback):
            raise TypeError("Handler callback must be a callable function or method.")
        self.callback: HandlerCallbackType[UpdateType] = callback

    @abstractmethod
    def check_update(self, update: Any) -> bool:
        """
        Abstract method to determine if this handler should process the given update.

        Subclasses must implement this method. It should inspect the `update` object
        and return `True` if the handler's criteria (e.g., filters) are met,
        otherwise `False`.

        Args:
            update: The incoming update object (e.g., a `wa_cloud.models.Message` instance).
                    Typed as `Any` here, but concrete implementations will expect specific types.

        Returns:
            `True` if the handler should handle this update, `False` otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    async def handle_update(self, update: UpdateType, bot: Bot) -> Any:
        """
        Abstract method to process the update and execute the callback.

        This method is called by the Application's dispatcher only if `check_update`
        returned `True` for the same update. Subclasses must implement this to
        prepare context (if any) and call `self.callback`.

        Args:
            update: The update object that matched (`check_update` returned True).
                    The type should match the `UpdateType` generic parameter.
            bot: The `wa_cloud.Bot` instance for performing API calls.

        Returns:
            The result returned by the user's callback function. The library
            doesn't typically use this return value directly.
        """
        raise NotImplementedError