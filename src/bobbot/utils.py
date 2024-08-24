"""Logging and other utility functions."""

import logging
import logging.config

from discord.utils import _ColourFormatter as ColourFormatter


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
