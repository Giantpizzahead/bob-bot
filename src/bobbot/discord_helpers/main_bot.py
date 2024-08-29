"""Contains main Discord bot functionality."""

import asyncio
import json
import os
import random
import re
from enum import Enum
from typing import Optional

import discord
from discord.ext import commands

from bobbot.discord_helpers.text_channel_history import (
    TextChannelHistory,
    get_channel_history,
    get_users_in_channel,
)
from bobbot.utils import get_logger, log_debug_info

logger = get_logger(__name__)


class Mode(Enum):
    """Valid modes of the bot."""

    DEFAULT = "default"
    OBEDIENT = "obedient"
    OFF = "off"


class Speed(Enum):
    """Valid speeds of the bot."""

    DEFAULT = "default"
    INSTANT = "instant"


class BobBot(commands.Bot):
    """Bob's Discord bot."""

    CHANNELS: list[int] = list(map(int, json.loads(os.getenv("DISCORD_CHANNELS", "[]"))))
    """The channels the bot is active in."""
    mode: Mode = Mode.DEFAULT
    """The mode of the bot."""
    speed: Speed = Speed.INSTANT
    """The typing speed of the bot."""
    active_channel: Optional[discord.TextChannel] = None
    """The active channel for the bot."""

    def __init__(self, *args, **kwargs):
        """Initialize the bot."""
        super().__init__(*args, **kwargs)


def init_bot() -> BobBot:
    """Initialize the bot."""
    intents: discord.Intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    return BobBot(command_prefix="!", help_command=None, intents=intents)


bot: BobBot = init_bot()


def run_bot() -> None:
    """Run the bot. Blocks until the bot is stopped."""
    token: Optional[str] = os.getenv("DISCORD_TOKEN")
    if token is None:
        raise ValueError("DISCORD_TOKEN environment variable is not set.")
    bot.run(token, log_handler=None)


@bot.event
async def on_ready() -> None:
    """Log when Bob is online."""
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands.")
    except Exception:
        logger.exception("Error syncing commands")
    logger.info("Bob is online!")


async def lazy_send_message(
    channel: discord.TextChannel, message_str: str, instant: bool = False, force: bool = False
) -> bool:
    """Send a message to a channel with typing time. Cancels the send on new messages or others typing.

    If the message is too long, it will be split into chunks before sending.
    If instant is True, the message will be sent instantly (regardless of the bot's mode).
    If force is True, the message will not be cancelled. Note that empty messages still won't be sent.

    Args:
        channel: The channel to send the message to.
        message_str: The message to send.
        instant: Whether to try to send the message instantly. May still be cancelled.
        force: Whether to force the message to be sent.

    Returns:
        Whether the message was sent in full.
    """
    if not message_str.strip():
        return False

    # Fetch all guild members to replace display names with mentions
    for member in get_users_in_channel(channel):
        display_name = member.display_name
        # Escape spaces in display name for regex matching
        escaped_display_name = re.escape(display_name)
        underscore_display_name = display_name.replace(" ", "_")
        # Create a regex pattern to match both versions of the display name
        mention_pattern = re.compile(
            f"@{escaped_display_name}|@{underscore_display_name}|{escaped_display_name}|{underscore_display_name}"
        )
        # Replace all occurrences of the display name with the member's mention
        message_str = mention_pattern.sub(f"<@{member.id}>", message_str)

    # Emulate typing time
    history: TextChannelHistory = get_channel_history(channel)
    async with channel.typing():
        chunk_size_limit = 2000
        i = 0
        while i < len(message_str):
            j = min(i + chunk_size_limit, len(message_str))  # Ending of this message
            chunk = message_str[i:j]
            i = j
            # Calculate typing time (on top of generation time): ~200 WPM or 14-18 seconds max
            typing_time = min(random.uniform(0.7, 1.3) * 75 * len(chunk), random.uniform(14000, 18000))
            if instant or bot.speed == Speed.INSTANT:
                typing_time = 0
            saved_message_count: int = history.message_count
            await asyncio.sleep(typing_time / 1000)
            # Only send if no new messages were sent and no one is typing (excluding Bob)
            if not force and history.message_count != saved_message_count:
                log_debug_info(f"Not sending '{chunk}': New message sent.")
                return False
            others_typing: list[discord.User] = get_channel_history(channel).get_users_typing()
            if bot.user in others_typing:
                others_typing.remove(bot.user)
            if not force and others_typing:
                log_debug_info(f"Not sending '{chunk}': Others typing {[user.display_name for user in others_typing]}.")
                return False
            # Send the message
            try:
                await channel.send(chunk)
                # await channel.send(chunk, suppress_embeds=True)
            except discord.DiscordException:
                logger.exception("Error sending message")
                return False
    return True
