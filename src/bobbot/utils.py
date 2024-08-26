"""Logging, environment variables, and other utility functions."""

import logging
import logging.config
from datetime import datetime, timezone

from discord.utils import _ColourFormatter as ColourFormatter
from dotenv import load_dotenv

load_dotenv()


def get_logger(name: str, level: int = logging.INFO, formatter: logging.Formatter | None = None) -> logging.Logger:
    """Get a logger with the specified name and logging level.

    Args:
        name: The name of the logger.
        level: The logging level. Defaults to logging.INFO.
        formatter: The log formatter to use. Defaults to a color formatter.

    Returns:
        The logger.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info('Here is some info.')
        2024-01-31 06:42:00 INFO     package.module Here is some info.
    """
    if formatter is None:
        formatter = ColourFormatter()
    # Create a logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Print logs to console
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger


def truncate_middle(text: str, max_len: int = 255, replace_newlines: bool = False) -> str:
    """Get a concise version of the text (start and end, up to max_len characters).

    Args:
        text: The text to truncate.
        max_len: The maximum length of the text.
        replace_newlines: Whether to replace newlines with 4 spaces.
    """
    if replace_newlines:
        text = text.replace("\n", "    ")
    text = text if len(text) <= max_len else text[: (max_len + 1) // 2] + "..." + text[-max_len // 2 :]
    return text


def time_elapsed_str(before: datetime, after: datetime | None = None) -> str:
    """Get a human-readable string representing the time elapsed between two times, or from a time to now."""
    if after is None:
        after = datetime.now(timezone.utc)
    diff = after - before
    seconds = diff.total_seconds()
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    weeks = days // 7
    months = days // 30
    years = days // 365

    if int(seconds) == 0:
        return "Now"
    elif seconds < 60:
        return "Recent"
        # return f"{int(seconds)} second{'s' if seconds != 1 else ''} ago"
    elif minutes < 60:
        return f"{int(minutes)} minute{'s' if minutes != 1 else ''} ago"
    elif hours < 24:
        return f"{int(hours)} hour{'s' if hours != 1 else ''} ago"
    elif days < 7:
        return f"{int(days)} day{'s' if days != 1 else ''} ago"
    elif weeks < 5:
        return f"{int(weeks)} week{'s' if weeks != 1 else ''} ago"
    elif months < 12:
        return f"{int(months)} month{'s' if months != 1 else ''} ago"
    else:
        return f"~{int(years)} year{'s' if years != 1 else ''} ago"
