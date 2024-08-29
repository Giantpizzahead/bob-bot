"""This module is the main entry point for the bot."""

from bobbot.discord_helpers import bot, lazy_send_message, run_bot
from bobbot.utils import get_debug_info, get_logger

__all__ = [
    "bot",
    "lazy_send_message",
    "run_bot",
    "get_debug_info",
    "get_logger",
]
