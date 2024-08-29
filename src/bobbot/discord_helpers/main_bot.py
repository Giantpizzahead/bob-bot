"""Contains main Discord bot functionality."""

import asyncio
import io
import json
import os
import random
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from logging import Logger
from typing import Callable, Optional

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
    stop_activity,
)
from bobbot.agents.agents import decide_to_respond, extract_answers, get_response
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
speed: Enum = Speed.INSTANT


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


@bot.hybrid_command(name="chess")
@app_commands.choices(
    against=[
        app_commands.Choice(name="Human", value="human"),
        app_commands.Choice(name="Chess.com Bot", value="bot"),
    ]
)
async def chess(ctx: commands.Context, against: str | None, elo: int) -> None:
    """Start a chess game with Bob."""
    if elo < 200 or elo > 1600:
        await ctx.send("! invalid elo, must be between 200 and 1600")
        return
    against_computer: bool = against is not None and against.lower() == "bot"
    configure_chess(elo, against_computer)
    await ctx.send(f"! ok, playing at {elo} elo vs {'a bot' if against_computer else 'u'}, lets go")
    await start_activity(Activity.CHESS, gen_command_handler(ctx.channel))


@bot.hybrid_command(name="activity")
@app_commands.choices(
    activity=[
        app_commands.Choice(name="School", value="school"),
        app_commands.Choice(name="Eat", value="eat"),
        app_commands.Choice(name="Shower", value="shower"),
        app_commands.Choice(name="Sleep", value="sleep"),
        app_commands.Choice(name="Chess", value="chess"),
        app_commands.Choice(name="League", value="league"),
    ]
)
async def do_basic_activity(ctx: commands.Context, activity: str) -> None:
    """Start an activity (without configuring parameters)."""
    try:
        act = Activity(activity)
        await ctx.send(f"! ok i {activity}")
        await start_activity(act, gen_command_handler(ctx.channel))
    except ValueError:
        await ctx.send("! invalid activity, try school, eat, shower, sleep, chess, or league")


@bot.hybrid_command(name="spectate")
async def spectate(ctx: commands.Context) -> None:
    """Spectate the current activity."""
    image_or_msg: Optional[list[str] | Image.Image] = await spectate_activity()  # Image or list of messages
    if isinstance(image_or_msg, Image.Image):
        with io.BytesIO() as image_binary:
            image_or_msg.save(image_binary, "JPEG")
            image_binary.seek(0)
            await ctx.send(file=discord.File(fp=image_binary, filename="current_chess_match.jpeg"))
        image_or_msg.close()
    elif isinstance(image_or_msg, list):
        await ctx.send(image_or_msg[0])
        for msg in image_or_msg[1:]:
            await asyncio.sleep(1)
            await lazy_send_message(ctx.channel, msg, instant=True, force=True)
    else:
        await ctx.send("! no activity D:")


@bot.hybrid_command(name="stop")
async def stop(ctx: commands.Context) -> None:
    """Stop the current activity."""
    await stop_activity()
    await ctx.send("! stopped activity")


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
        """! hi i am bob 2nd edition v1.2
command prefix is `!`, slash commands work too

activities:
`chess [elo] [human/bot]` - Start a chess game with Bob playing at the given elo (in 200-1600), against a human or bot.
`activity [school/eat/shower/sleep/chess/league]` - Start an activity (without configuring parameters).
`spectate` - Spectate the current activity.
`stop` - Stops the current activity.

config:
`mode [default/obedient/off]` - Set the mode of the bot, clearing the conversation history.
`speed [default/instant]` - Set the typing speed of the bot.
`reset` - Reset the bot's conversation history.

info:
`help` - Show this help message.
`status` - Show the current mode, speed, and activity of the bot.
`debug` - Show debug info for the last message Bob processed.
`ping` - Ping the bot."""
    )


@bot.hybrid_command(name="status")
async def status(ctx: commands.Context) -> None:
    """Show the current mode, speed, and activity of the bot."""
    await ctx.send(f"! mode: {mode.value}, speed: {speed.value}\nactivity: {await get_activity_status()}")


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


@bot.hybrid_command(name="debug")
async def debug(ctx: commands.Context) -> None:
    """Show debug info for the last message Bob processed."""
    debug_info = get_debug_info()
    if not debug_info:
        await ctx.send("! No trace available.")
    else:
        await ctx.send(truncate_length("!```Trace:\n" + debug_info + "```", 2000))


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
            await check_waiting_responses(curr_channel)
            response: str = await get_response(
                history.as_langchain_msgs(bot.user),
                context=f"Context that may be helpful:\nYour status: {await get_activity_status()}",
            )
            if history.message_count == saved_message_count:
                await lazy_send_message(message.channel, response)
    except Exception as e:
        logger.exception("Error getting response")
        await lazy_send_message(message.channel, str(e), instant=True, force=True)


@bot.event
async def on_typing(channel, user, when):
    """Respond to typing events."""
    if not (channel.id in CHANNELS or isinstance(channel, discord.DMChannel)):
        return
    curr_channel: discord.TextChannel = channel
    history: TextChannelHistory = get_channel_history(curr_channel)
    history.on_typing(user, when)


waiting_cmd_events: dict[str, asyncio.Event] = {}
waiting_responses: dict[str, str] = {}


async def command_handler(channel: discord.TextChannel, command: str, expect_response: bool = False) -> Optional[str]:
    """Handle a command from the current activity.

    Commands are directions to Bob, with info or requests to be relayed to the user.
    If expect_response is True, the user's response will be waited for and returned.

    Args:
        channel: The channel the command is associated with.
        command: The command to give to Bob.
        expect_response: Whether to wait for the user's response.
    """
    # Command-specific handlers
    if "Comment on your chess match" in command:
        # Send screenshot first
        await spectate(channel)

    # Update history
    history: TextChannelHistory = get_channel_history(channel)
    await history.aupdate()

    # In-character response
    response: str = await get_response(history.as_langchain_msgs(bot.user), context=command)
    logger.info(f"Command: {command} -> Response: {response}")
    await lazy_send_message(channel, response, force=True)

    if expect_response:
        # Wait for the user's response
        id = str(uuid.uuid4())
        event: asyncio.Event = asyncio.Event()
        waiting_cmd_events[id] = event
        waiting_responses[id] = command
        logger.info(f"Waiting for response to '{command}'...")
        await event.wait()
        waiting_cmd_events.pop(id, None)
        return waiting_responses.pop(id, None)


def gen_command_handler(channel: discord.TextChannel) -> Callable:
    """Generate a command handler for the given channel."""

    async def _channel_command_handler(command: str, expect_response: bool = False) -> str:
        """Handle a command from the current activity."""
        return await command_handler(channel, command, expect_response)

    return _channel_command_handler


async def check_waiting_responses(channel: discord.TextChannel) -> None:
    """Check if any waiting responses were answered."""
    if not waiting_cmd_events:
        return  # No waiting responses
    history: TextChannelHistory = get_channel_history(channel)
    assert len(waiting_cmd_events) == len(waiting_responses)  # Check for race conditions
    waiting_ids = list(waiting_cmd_events.keys())
    answers = await extract_answers(history.as_string(10), list(waiting_responses.values()))
    for question_num, [is_answer, text] in answers.items():
        curr_id = waiting_ids[question_num - 1]
        if curr_id in waiting_cmd_events:  # Still waiting (not answered by another call)
            question = waiting_responses[curr_id]
            if is_answer:
                logger.info(f"Answer to '{question}': {text}")
                waiting_responses[curr_id] = text
                waiting_cmd_events[curr_id].set()
            else:
                logger.info(f"Clarification for '{question}': {text}")
                await command_handler(channel, text)  # Send clarification


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
            if instant or speed == Speed.INSTANT:
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
