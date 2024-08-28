"""Contains main Discord bot functionality."""

import asyncio
import io
import json
import os
import random
import re
from datetime import datetime, timezone
from enum import Enum
from logging import Logger
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image

from bobbot.activities import (  # stop_activity,
    Activity,
    configure_chess,
    get_activity_status,
    spectate_activity,
    start_activity,
)
from bobbot.agents.agents import decide_to_respond, get_response
from bobbot.discord_helpers.text_channel_history import (
    TextChannelHistory,
    get_users_in_channel,
)
from bobbot.utils import (
    get_debug_info,
    get_logger,
    log_debug_info,
    reset_debug_info,
    truncate_length,
)


class Mode(Enum):
    """Valid modes of the bot."""

    DEFAULT = "default"
    OBEDIENT = "obedient"
    OFF = "off"


class Speed(Enum):
    """Valid speeds of the bot."""

    DEFAULT = "default"
    INSTANT = "instant"


logger: Logger = get_logger(__name__)
mode: Enum = Mode.DEFAULT
speed: Enum = Speed.DEFAULT


def init_bot() -> commands.Bot:
    """Initialize the bot."""
    intents: discord.Intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    return commands.Bot(command_prefix="!", help_command=None, intents=intents)


def run_bot() -> None:
    """Run the bot. Blocks until the bot is stopped."""
    token: Optional[str] = os.getenv("DISCORD_TOKEN")
    if token is None:
        raise ValueError("DISCORD_TOKEN environment variable is not set.")
    bot.run(token, log_handler=None)


bot: commands.Bot = init_bot()
active_channel: Optional[discord.TextChannel] = None


CHANNELS: list[int] = list(map(int, json.loads(os.getenv("DISCORD_CHANNELS", "[]"))))

channel_history: dict[int, TextChannelHistory] = {}


def get_channel_history(channel: discord.TextChannel) -> TextChannelHistory:
    """Get the history for a channel, creating it if it doesn't exist."""
    if channel.id not in channel_history:
        channel_history[channel.id] = TextChannelHistory(channel)
    return channel_history[channel.id]


@bot.hybrid_command(name="mode")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="default", value="default"),
        app_commands.Choice(name="obedient", value="obedient"),
        app_commands.Choice(name="off", value="off"),
    ]
)
async def set_mode(ctx: commands.Context, mode: str) -> None:
    """Set the mode of the bot, clearing the conversation history."""
    try:
        selected_mode = Mode(mode.lower())
        globals()["mode"] = selected_mode
        await ctx.send(f"! mode set to {selected_mode.value}")
    except ValueError:
        valid_modes = ", ".join([m.value for m in Mode])
        await ctx.send(f"! invalid mode. valid modes: {valid_modes}")


@bot.hybrid_command(name="speed")
@app_commands.choices(
    speed=[
        app_commands.Choice(name="default", value="default"),
        app_commands.Choice(name="instant", value="instant"),
    ]
)
async def set_speed(ctx: commands.Context, speed: str) -> None:
    """Set the typing speed of the bot."""
    try:
        selected_speed = Speed(speed.lower())
        globals()["speed"] = selected_speed
        await ctx.send(f"! speed set to {selected_speed.value}")
    except ValueError:
        valid_speeds = ", ".join([s.value for s in Speed])
        await ctx.send(f"! invalid speed. valid speeds: {valid_speeds}")


@bot.hybrid_command(name="reset")
async def reset(ctx: commands.Context) -> None:
    """Reset the bot's conversation history."""
    await ctx.send("! reset conversation history")


@bot.hybrid_command(name="help")
async def help(ctx: commands.Context) -> None:
    """Show the help message."""
    await ctx.send(
        """! hi i am bob 2nd edition v1.1
command prefix is `!`, slash commands work too

config:
`mode [default/obedient/off]` - Set the mode of the bot, clearing the conversation history.
`speed [default/instant]` - Set the typing speed of the bot.
`reset` - Reset the bot's conversation history.

info:
`help` - Show this help message.
`status` - Show the current mode and speed of the bot.
`debug` - Show debug info for the last message Bob sent.
`ping` - Ping the bot."""
    )


@bot.hybrid_command(name="ping")
async def ping(ctx: commands.Context) -> None:
    """Ping the bot."""
    # Get time taken in ms
    ms_taken = (datetime.now(timezone.utc) - ctx.message.created_at).total_seconds() * 1000
    msg = f"! pong ({ms_taken:.0f} ms)"
    # React with pin if not slash command
    if ctx.interaction is None:
        await ctx.message.add_reaction("📍")
        await ctx.reply(msg)
    else:
        await ctx.send(msg)


@bot.hybrid_command(name="status")
async def status(ctx: commands.Context) -> None:
    """Show the current mode, speed, and activity of the bot."""
    await ctx.send(f"! mode: {mode.value}, speed: {speed.value}\nactivity: {await get_activity_status()}")


@bot.hybrid_command(name="debug")
async def debug(ctx: commands.Context) -> None:
    """Show debug info for the last message Bob sent."""
    debug_info = get_debug_info()
    if not debug_info:
        await ctx.send("! No trace available.")
    else:
        await ctx.send(truncate_length("!```Trace:\n" + debug_info + "```", 2000))


@bot.hybrid_command(name="chess")
@app_commands.choices(
    against=[
        app_commands.Choice(name="Human", value="human"),
        app_commands.Choice(name="Chess.com Bot", value="bot"),
    ]
)
async def chess(ctx: commands.Context, against: str | None) -> None:
    """Start a chess game with Bob."""
    against_computer: bool = against is not None and against.lower() == "bot"
    configure_chess(800, against_computer)
    await ctx.send("! ok lets go")
    await start_activity(Activity.CHESS, chess_callback)


async def chess_callback(msg: str) -> None:
    """Send a message to the active channel."""
    if "game over" in msg:
        # Also send screenshot
        await spectate(active_channel)
    await send_discord_message(msg, instant=True)


@bot.hybrid_command(name="spectate")
async def spectate(ctx: commands.Context) -> None:
    """Spectate the current activity."""
    image: Optional[Image.Image] = await spectate_activity()
    if image is not None:
        with io.BytesIO() as image_binary:
            image.save(image_binary, "JPEG")
            image_binary.seek(0)
            await ctx.send(file=discord.File(fp=image_binary, filename="current_chess_match.jpeg"))
    else:
        await ctx.send("! no activity, start a game first")


@bot.event
async def on_ready() -> None:
    """Log when Bob is online."""
    try:
        synced = await bot.tree.sync()
        logger.debug(f"Synced {len(synced)} commands.")
    except Exception:
        logger.exception("Error syncing commands")
    logger.info("Bob is online!")


@bot.event
async def on_message(message: discord.Message):
    """Respond to messages."""
    # Only respond to messages in DMs and specified channels
    if not (message.channel.id in CHANNELS or isinstance(message.channel, discord.DMChannel)):
        return
    curr_channel: discord.TextChannel = message.channel
    # Set the active channel
    global active_channel
    active_channel = message.channel
    await bot.process_commands(message)
    # Don't respond if the bot is off, or if it's a command message
    if mode == Mode.OFF or message.content.startswith(bot.command_prefix):
        return
    # For now, don't respond to self messages
    if message.author == bot.user:
        return

    # Get history for the current channel
    history: TextChannelHistory = get_channel_history(curr_channel)
    await history.aupdate()
    history.clear_users_typing()
    saved_message_count: int = history.message_count
    # Get a response
    try:
        reset_debug_info()
        decision, thoughts = await decide_to_respond(history.as_string(5))
        if decision:
            await curr_channel.typing()
            response: str = await get_response(
                history.as_langchain_msgs(bot.user), thoughts, obedient=(mode == Mode.OBEDIENT)
            )
            if history.message_count == saved_message_count:
                await send_discord_message(response)
    except Exception as e:
        logger.exception("Error getting response")
        await send_discord_message(str(e))


@bot.event
async def on_typing(channel, user, when):
    """Respond to typing events."""
    if not (channel.id in CHANNELS or isinstance(channel, discord.DMChannel)):
        return
    curr_channel: discord.TextChannel = channel
    history: TextChannelHistory = get_channel_history(curr_channel)
    history.on_typing(user, when)


async def send_discord_message(message_str: str, instant: bool = False) -> bool:
    """Send a message to the active channel.

    Args:
        message_str (str): The message to send.
        instant (bool): Whether to force send the message instantly.

    Returns:
        Whether the message was sent in full.
    """
    if not message_str.strip():
        return False
    channel: Optional[discord.TextChannel] = active_channel
    if channel is None:
        raise ValueError("No active channel.")

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
            # Calculate typing time (on top of generation time): ~150 WPM or 18-22 seconds max
            typing_time = min(
                random.random() * 1000 + (random.random() / 2 + 1) * 100 * len(chunk), 18000 + random.random() * 4000
            )
            if instant or speed == Speed.INSTANT:
                typing_time = 0
            saved_message_count: int = history.message_count
            await asyncio.sleep(typing_time / 1000)
            # Only send if no new messages were sent and no one is typing (excluding Bob)
            if history.message_count != saved_message_count:
                log_debug_info("Not sending: New message sent.")
                return False
            others_typing: list[discord.User] = get_channel_history(channel).get_users_typing()
            if bot.user in others_typing:
                others_typing.remove(bot.user)
            if others_typing:
                log_debug_info(f"Not sending: Others typing {[user.display_name for user in others_typing]}.")
                return False
            # Send the message
            try:
                await channel.send(chunk, suppress_embeds=True)
            except discord.DiscordException:
                logger.exception("Error sending message")
                return False
    return True
