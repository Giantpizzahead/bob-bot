"""This module contains helper functions and classes for interacting with Discord."""

from bobbot.discord_helpers.activity_manager import (
    check_waiting_responses,
    chess,
    command_handler,
    discord_stop_activity,
    discord_stop_spectating,
    do_basic_activity,
    gen_command_handler,
    spectate,
)
from bobbot.discord_helpers.main_bot import (
    BobBot,
    Mode,
    Speed,
    bot,
    lazy_send_message,
    run_bot,
)
from bobbot.discord_helpers.message_manager import on_message
from bobbot.discord_helpers.misc_commands import (
    debug,
    help,
    ping,
    reset,
    set_mode,
    set_speed,
    status,
)
from bobbot.discord_helpers.text_channel_history import (
    ParsedMessage,
    TextChannelHistory,
    get_channel_history,
    get_users_in_channel,
)

# Other imports


__all__ = [
    "check_waiting_responses",
    "chess",
    "command_handler",
    "do_basic_activity",
    "gen_command_handler",
    "spectate",
    "discord_stop_activity",
    "discord_stop_spectating",
    "BobBot",
    "Mode",
    "Speed",
    "bot",
    "lazy_send_message",
    "run_bot",
    "on_message",
    "debug",
    "help",
    "ping",
    "reset",
    "set_mode",
    "set_speed",
    "status",
    "ParsedMessage",
    "TextChannelHistory",
    "get_channel_history",
    "get_users_in_channel",
]
