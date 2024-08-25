"""Contains main Discord bot functionality."""

import asyncio
import json
import os
import random
import re
from logging import Logger

import discord
from discord.ext import commands

from ..agents.sender import get_response
from ..utils import get_logger
from .text_channel_history import TextChannelHistory

logger: Logger = get_logger(__name__)


def init_bot() -> commands.Bot:
    """Initialize the bot."""
    intents: discord.Intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    return commands.Bot(command_prefix="!", intents=intents)


def run_bot() -> None:
    """Run the bot. Blocks until the bot is stopped."""
    # Show debug logs
    bot.run(os.getenv("DISCORD_TOKEN"))
    # bot.run(os.getenv("DISCORD_TOKEN"), log_handler=None)


bot: commands.Bot = init_bot()
active_channel: discord.TextChannel | None = None


CHANNELS: list[int] = list(map(int, json.loads(os.getenv("DISCORD_CHANNELS", "[]"))))

channel_history: dict[int, TextChannelHistory] = {}


@bot.hybrid_command(name="mode")
async def set_mode(ctx: commands.Context, mode: str) -> None:
    """Set the mode of the bot."""
    valid_modes = ["default", "obedient", "off"]
    if mode not in valid_modes:
        await ctx.send(f"Invalid mode: {mode}. Valid modes are {valid_modes}")
        return
    await ctx.send(f"Setting mode to {mode} (WIP)")


@bot.event
async def on_ready() -> None:
    """Log when Bob is online."""
    logger.info("Syncing slash commands...")
    await bot.tree.sync()  # Sync slash commands
    logger.info("Bob is online!")


@bot.event
async def on_message(message: discord.Message):
    """Respond to messages."""
    # Only respond to messages in DMs and specified channels
    if not (message.channel.id in CHANNELS or isinstance(message.channel, discord.DMChannel)):
        return
    # For now, don't respond to self messages
    if message.author == bot.user:
        return
    # Also don't respond to commands
    if message.content.startswith(bot.command_prefix):
        return
    curr_channel: discord.TextChannel = message.channel
    # Make sure we have history for the current channel
    if curr_channel.id not in channel_history:
        channel_history[curr_channel.id] = TextChannelHistory(curr_channel)
    # Set the active channel
    global active_channel
    active_channel = message.channel
    # Update the history
    history: TextChannelHistory = channel_history[curr_channel.id]
    await history.aupdate()
    # Get a response
    try:
        # response: str = history.get_history_str()
        response: str = await get_response(history.get_history_str())
        await send_discord_message(response)
    except Exception as e:
        logger.error(e)
        await send_discord_message(str(e))


@bot.event
async def on_typing(channel, user, when):
    """Respond to typing events."""
    if not (channel.id in CHANNELS or isinstance(channel, discord.DMChannel)):
        return
    curr_channel: discord.TextChannel = channel
    # Make sure we have history for the current channel
    if curr_channel.id not in channel_history:
        channel_history[curr_channel.id] = TextChannelHistory(curr_channel)
    history: TextChannelHistory = channel_history[curr_channel.id]
    history.on_typing(user, when)


async def send_discord_message(message_str: str) -> bool:
    """Send a message to the active channel."""
    if not message_str.strip():
        return
    channel = active_channel

    # Fetch all guild members to replace display names with mentions
    async for member in channel.guild.fetch_members():
        display_name = member.display_name
        # Escape spaces in display name for regex matching
        escaped_display_name = re.escape(display_name)
        underscore_display_name = display_name.replace(" ", "_")
        # Create a regex pattern to match both versions of the display name
        mention_pattern = re.compile(f"@{escaped_display_name}|@{underscore_display_name}")
        # Replace all occurrences of the display name with the member's mention
        message_str = mention_pattern.sub(f"<@{member.id}>", message_str)

    # Emulate typing time
    async with channel.typing():
        chunk_size_limit = 2000
        i = 0
        while i < len(message_str):
            j = min(i + chunk_size_limit, len(message_str))  # Ending of this message
            chunk = message_str[i:j]
            i = j
            # Calculate typing time: ~200 WPM or 8-12 seconds max
            typing_time = min(
                random.random() * 2000 + (random.random() / 2 + 1) * 75 * len(chunk), 8000 + random.random() * 4000
            )
            await asyncio.sleep(typing_time / 1000)
            # Only send if message is not outdated
            try:
                await channel.send(chunk, suppress_embeds=True)
            except discord.DiscordException as error:
                logger.error(error)
