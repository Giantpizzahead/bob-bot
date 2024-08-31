"""Manages the bot's activity status."""

import asyncio
import uuid
from pathlib import Path
from typing import Callable, Optional

import discord
import psutil
from discord import app_commands
from discord.ext import commands

from bobbot.activities import (  # stop_activity,
    Activity,
    configure_chess,
    spectate_activity,
    start_activity,
    stop_activity,
)
from bobbot.agents import extract_answers, get_response
from bobbot.discord_helpers.main_bot import bot, lazy_send_message
from bobbot.discord_helpers.text_channel_history import (
    TextChannelHistory,
    get_channel_history,
)
from bobbot.utils import get_logger

logger = get_logger(__name__)
waiting_cmd_events: dict[str, asyncio.Event] = {}
waiting_responses: dict[str, str] = {}
spectate_status: str = "idle"


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
    if "start_spectating" in command:
        await spectate(channel)
        return

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


@bot.hybrid_command(name="chess")
@app_commands.choices(
    against=[
        app_commands.Choice(name="Human", value="human"),
        app_commands.Choice(name="Chess.com Bot", value="bot"),
    ]
)
async def chess(ctx: commands.Context, elo: int, against: str | None) -> None:
    """Start a chess game with Bob."""
    if elo < 200 or elo > 1600:
        await ctx.send("! invalid elo, must be between 200 and 1600")
        return
    against_computer: bool = against is not None and against.lower() == "bot"
    configure_chess(elo, against_computer)
    await ctx.send(
        f"ok, ill play chess at {elo} elo vs {'a bot' if against_computer else f'u <@{ctx.author.id}>'}, lets go!"
    )
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
        await ctx.send(f" ok i {activity} now")
        await start_activity(act, gen_command_handler(ctx.channel))
    except ValueError:
        await ctx.send("! invalid activity, try school, eat, shower, sleep, chess, or league")


@bot.hybrid_command(name="spectate")
async def spectate(ctx: commands.Context, video: bool = True) -> None:
    """Spectate the current activity.

    Either uses a low quality/frame rate video or a screenshot. If given messages, sends them instead.
    """
    global spectate_status
    if spectate_status in ["stopping"]:
        await ctx.send("! too fast, try again in a bit")
        return
    elif spectate_status == "spectating":
        spectate_status = "stopping"
        # Wait for previous spectate to stop
        while spectate_status == "stopping":
            await asyncio.sleep(1)
    spectate_status = "spectating"
    curr_message: Optional[discord.Message] = None
    image_or_msg: Optional[list[str] | Path] = await spectate_activity()  # Image or list of messages
    if image_or_msg is None:
        await ctx.send("! no activity D:")
        spectate_status = "idle"
        return
    try:
        while spectate_status == "spectating":
            if isinstance(image_or_msg, Path):
                memory_info = psutil.Process().memory_info()
                memory_mb = memory_info.rss / (1024**2)
                content = f"Spectating: (Using {memory_mb:.0f} MB of RAM)" if video else None
                if curr_message is not None:
                    # Edit previous message
                    await curr_message.edit(
                        content=content, attachments=[discord.File(fp=image_or_msg, filename="spectate.jpeg")]
                    )
                else:
                    curr_message = await ctx.send(
                        content=content, file=discord.File(fp=image_or_msg, filename="spectate.jpeg")
                    )
                await asyncio.sleep(1)  # Slow down editing rate
            elif isinstance(image_or_msg, list):
                await ctx.send(image_or_msg[0])
                for msg in image_or_msg[1:]:
                    await asyncio.sleep(1)
                    await lazy_send_message(ctx.channel, msg, instant=True, force=True)
                break
            else:
                if curr_message is not None:
                    await curr_message.edit(content="Done spectating.")
                else:
                    await ctx.send("Done spectating.")
                break
            if not video:
                break
            image_or_msg = await spectate_activity()
    except Exception:
        logger.exception("Error during spectating")
        await ctx.send("! error during spectating")
    if spectate_status == "stopping":
        spectate_status = "spectating"  # Let the next spectate start
    else:
        spectate_status = "idle"


@bot.hybrid_command(name="stop_spectating")
async def discord_stop_spectating(ctx: commands.Context) -> None:
    """Stop spectating the current activity."""
    global spectate_status
    if spectate_status == "spectating":
        spectate_status = "stopping"
    await ctx.send("! ok D:")


@bot.hybrid_command(name="stop_activity")
async def discord_stop_activity(ctx: commands.Context) -> None:
    """Stops the current activity."""
    await stop_activity()
    await ctx.send("! stopped activity")
