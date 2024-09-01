"""This module contains helper functions and classes for interacting with Discord."""

from bobbot.discord_helpers.activity_manager import (
    activity,
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
    Speed,
    bot,
    lazy_send_message,
    run_bot,
)
from bobbot.discord_helpers.memory_manager import discord_delete_memory, memories, reset
from bobbot.discord_helpers.message_manager import on_message
from bobbot.discord_helpers.misc_commands import (  # help,
    config,
    config_incognito,
    config_obedient,
    config_on,
    config_speed,
    debug,
    ping,
    prune,
)
from bobbot.discord_helpers.text_channel_history import (
    ParsedMessage,
    TextChannelHistory,
    get_channel_history,
    get_users_in_channel,
)

# Other imports


__all__ = [
    "activity",
    "BobBot",
    "Speed",
    "bot",
    "check_waiting_responses",
    "chess",
    "command_handler",
    "config",
    "config_incognito",
    "config_obedient",
    "config_on",
    "config_speed",
    "debug",
    "discord_delete_memory",
    "discord_stop_activity",
    "discord_stop_spectating",
    "do_basic_activity",
    "gen_command_handler",
    "get_channel_history",
    "get_users_in_channel",
    "help",
    "lazy_send_message",
    "memories",
    "on_message",
    "ping",
    "prune",
    "reset",
    "run_bot",
    "spectate",
    "TextChannelHistory",
    "ParsedMessage",
]
