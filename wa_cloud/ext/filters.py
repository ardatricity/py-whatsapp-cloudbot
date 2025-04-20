# wa_cloud/ext/filters.py

"""
Defines filters used by handlers (e.g., MessageHandler) to determine
if an incoming update should be processed.

Provides filters for common message types, commands, regular expressions,
and logical combinations (AND, OR, NOT).
"""

import re
from typing import Pattern, Optional, Union, Callable, List

# Use relative imports for library components
from ..models import Message
from ..constants import MessageType # Assuming only MessageType is needed here for now

# --- Base Filter Class and Logical Operators ---

class BaseFilter:
    """
    Abstract base class for all filters.

    Filters are callable objects that take a `Message` object and return `True`
    if the message should be handled, `False` otherwise. Subclasses must
    implement the `filter` method.

    Filters can be combined using `&` (AND), `|` (OR), and `~` (NOT) operators.
    """
    def __call__(self, message: Message) -> bool:
        """Makes the filter instance callable."""
        # Basic error handling: if a filter tries to access a non-existent
        # attribute (e.g., message.text on an image message), treat it as False.
        try:
            return self.filter(message)
        except AttributeError:
            return False

    def filter(self, message: Message) -> bool:
        """
        The core filtering logic to be implemented by subclasses.

        Args:
            message: The incoming `wa_cloud.models.Message` object.

        Returns:
            True if the message matches the filter's criteria, False otherwise.
        """
        raise NotImplementedError("Subclasses must implement the filter method.")

    # --- Operator Overloading for Combining Filters ---
    def __and__(self, other: "BaseFilter") -> "AndFilter":
        """Combines this filter with another using logical AND (&)."""
        if not isinstance(other, BaseFilter):
            return NotImplemented # Necessary for correct operator behavior
        return AndFilter(self, other)

    def __or__(self, other: "BaseFilter") -> "OrFilter":
        """Combines this filter with another using logical OR (|)."""
        if not isinstance(other, BaseFilter):
            return NotImplemented
        return OrFilter(self, other)

    def __invert__(self) -> "InvertFilter":
        """Negates this filter using logical NOT (~)."""
        return InvertFilter(self)

# --- Logical Filter Combiners ---

class AndFilter(BaseFilter):
    """Applies logical AND to two filters."""
    def __init__(self, f1: BaseFilter, f2: BaseFilter):
        self.f1 = f1
        self.f2 = f2

    def filter(self, message: Message) -> bool:
        # Call the filters themselves to leverage their __call__ (with error handling)
        return self.f1(message) and self.f2(message)

class OrFilter(BaseFilter):
    """Applies logical OR to two filters."""
    def __init__(self, f1: BaseFilter, f2: BaseFilter):
        self.f1 = f1
        self.f2 = f2

    def filter(self, message: Message) -> bool:
        return self.f1(message) or self.f2(message)

class InvertFilter(BaseFilter):
    """Applies logical NOT to a filter."""
    def __init__(self, f: BaseFilter):
        self.f = f

    def filter(self, message: Message) -> bool:
        return not self.f(message)

# --- Concrete Filter Implementations ---

class AllFilter(BaseFilter):
    """Matches all messages."""
    def filter(self, message: Message) -> bool:
        return True

class TextFilter(BaseFilter):
    """Matches messages of type 'text' that have a non-empty body."""
    def filter(self, message: Message) -> bool:
        # Check type using the MessageType enum and ensure text object exists
        return message.message_type == MessageType.TEXT and message.text is not None

class ImageFilter(BaseFilter):
    """Matches messages of type 'image'."""
    def filter(self, message: Message) -> bool:
        return message.message_type == MessageType.IMAGE and message.image is not None

class VideoFilter(BaseFilter):
    """Matches messages of type 'video'."""
    def filter(self, message: Message) -> bool:
        return message.message_type == MessageType.VIDEO and message.video is not None

class AudioFilter(BaseFilter):
    """Matches messages of type 'audio'."""
    def filter(self, message: Message) -> bool:
        return message.message_type == MessageType.AUDIO and message.audio is not None

class DocumentFilter(BaseFilter):
    """Matches messages of type 'document'."""
    def filter(self, message: Message) -> bool:
        return message.message_type == MessageType.DOCUMENT and message.document is not None

class StickerFilter(BaseFilter):
    """Matches messages of type 'sticker'."""
    def filter(self, message: Message) -> bool:
        return message.message_type == MessageType.STICKER and message.sticker is not None

class LocationFilter(BaseFilter):
    """Matches messages of type 'location'."""
    def filter(self, message: Message) -> bool:
        return message.message_type == MessageType.LOCATION and message.location is not None

class ContactsFilter(BaseFilter):
    """Matches messages of type 'contacts'."""
    def filter(self, message: Message) -> bool:
        # Ensure contacts list is not None (it can be empty list if received that way)
        return message.message_type == MessageType.CONTACTS and message.contacts is not None

class InteractiveFilter(BaseFilter):
    """Matches messages of type 'interactive' (typically button or list replies)."""
    def filter(self, message: Message) -> bool:
        # Checks the top-level type and the presence of the nested interactive object
        return message.message_type == MessageType.INTERACTIVE and message.interactive is not None

class ReactionFilter(BaseFilter):
    """Matches messages of type 'reaction'."""
    def filter(self, message: Message) -> bool:
        return message.message_type == MessageType.REACTION and message.reaction is not None

# --- Content-Based Filters ---

class RegexFilter(BaseFilter):
    """
    Matches text messages whose body matches a given regular expression pattern.
    """
    def __init__(self, pattern: Union[str, Pattern]):
        """
        Args:
            pattern: The regular expression pattern (string or compiled Pattern object).
        """
        if isinstance(pattern, str):
             self.pattern = re.compile(pattern)
        elif isinstance(pattern, Pattern):
             self.pattern = pattern
        else:
             raise TypeError("RegexFilter pattern must be a string or a compiled regex pattern.")
        # Pre-create a TextFilter instance for efficiency
        self._text_filter = TextFilter()

    def filter(self, message: Message) -> bool:
        """Checks if the message is text and its body matches the regex."""
        # Ensure it's a text message first
        if not self._text_filter(message):
            return False
        # message.text is guaranteed to exist here
        # Search for the pattern anywhere within the text body
        return bool(self.pattern.search(message.text.body))

class CommandFilter(RegexFilter):
    """
    Filters messages that start with specific commands (e.g., '/start', '/help').
    A command is defined as a '/' followed by one or more word characters (letters, numbers, underscore),
    ending either at the end of the message or before a space.
    """
    def __init__(self, command: Union[str, List[str]]):
        """
        Args:
            command: A single command string (without '/') or a list of command strings.

        Raises:
            TypeError: If `command` is not a string or list.
            ValueError: If any command string is empty or contains invalid characters.
        """
        if isinstance(command, str):
            commands = [command]
        elif isinstance(command, list):
            commands = command
        else:
            raise TypeError("CommandFilter 'command' must be a string or a list of strings.")

        # Validate command names (must not be empty, basic format check)
        valid_commands = []
        for cmd in commands:
            if not cmd or not isinstance(cmd, str):
                 raise ValueError("Command names cannot be empty and must be strings.")
            # Allow only letters, numbers, and underscores for command names
            if not re.match(r"^[a-zA-Z0-9_]+$", cmd):
                raise ValueError(f"Invalid command name format: '{cmd}'. Use only letters, numbers, underscores.")
            valid_commands.append(cmd)

        if not valid_commands:
             raise ValueError("Command list cannot be empty.")

        # Construct regex: ^/ (start, slash) followed by (command1|command2|...)
        # ending with either end-of-string ($) or a space (\s)
        # Use re.escape to handle potential special characters in command names (though validation prevents most)
        pattern_str = r"^/(" + "|".join(re.escape(cmd) for cmd in valid_commands) + r")($|\s)"
        # Initialize the parent RegexFilter with the constructed pattern
        super().__init__(pattern_str)


# --- Filters Object ---
# Provides easy access to pre-defined filter instances and filter classes.

class Filters:
    """
    Collection of pre-defined filter instances and filter classes.

    Usage:
        from wa_cloud.ext import filters

        # Use instances for common types:
        handler = MessageHandler(filters.TEXT, callback)
        handler = MessageHandler(filters.IMAGE | filters.VIDEO, callback)
        handler = MessageHandler(filters.TEXT & ~filters.ANY_COMMAND, callback)

        # Use classes for filters requiring arguments:
        handler = MessageHandler(filters.Command("start"), start_callback)
        handler = MessageHandler(filters.Regex(r"order #(\d+)"), order_callback)
    """
    # Instances for common message types
    ALL = AllFilter()
    TEXT = TextFilter()
    IMAGE = ImageFilter()
    VIDEO = VideoFilter()
    AUDIO = AudioFilter()
    DOCUMENT = DocumentFilter()
    STICKER = StickerFilter()
    LOCATION = LocationFilter()
    CONTACTS = ContactsFilter()
    INTERACTIVE = InteractiveFilter() # Matches any Button Reply or List Reply
    REACTION = ReactionFilter()

    # Instance for matching any message starting with '/'
    ANY_COMMAND = RegexFilter(r'^/')

    # Access to classes for filters requiring arguments
    Regex = RegexFilter
    Command = CommandFilter

# Create the singleton instance for users to import
filters = Filters()