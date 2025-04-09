"""Manages the bot's activity status."""

import asyncio
import os
import uuid
from pathlib import Path
from typing import Callable, Optional

import discord
from discord import app_commands
from discord.ext import commands

from bobbot.activities import (
    Activity,
    configure_chess,
    configure_hangman,
    configure_school,
    get_activity,
    get_activity_status,
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
from bobbot.memory import is_sparse_encoder_loaded
from bobbot.utils import get_logger, is_playwright_browser_open, on_heroku

logger = get_logger(__name__)
waiting_cmd_events: dict[str, asyncio.Event] = {}
waiting_responses: dict[str, str] = {}
spectate_status: str = "idle"


async def command_handler(
    channel: discord.TextChannel,
    command: str,
    expect_response: bool = False,
    output_directly: bool = False,
    hide_output: bool = False,
    use_history: bool = True,
) -> Optional[str]:
    """Handle a command from the current activity.

    Commands are directions to Bob, with info or requests to be relayed to the user.
    If expect_response is True, the user's response will be waited for and returned.
    Otherwise, the response given to the user is returned.

    Args:
        channel: The channel the command is associated with.
        command: The command to give to Bob.
        expect_response: Whether to wait for the user's response.
        output_directly: Whether to send the literal command directly to the user.
        hide_output: Whether to avoid sending the message to the user (just return it instead).
        use_history: Whether to include any channel history.
    """
    # Command-specific handlers
    if "start_spectating" in command:
        await spectate(channel)
        return

    if output_directly:
        logger.info(f"Direct response: {command}")
        if not hide_output:
            await lazy_send_message(channel, command, force=True)
        if not expect_response:
            return command
    else:
        # Update history
        history: TextChannelHistory = get_channel_history(channel)
        await history.aupdate()

        # In-character response
        if use_history:
            response: str = await get_response(
                history.as_langchain_msgs(bot.user), context=command, store_memories=False
            )
        else:
            response: str = await get_response([], context=command, store_memories=False)
        logger.info(f"Command: {command} -> Response: {response}")
        if not hide_output:
            await lazy_send_message(channel, response, force=True)
        if not expect_response:
            return response

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

    async def _channel_command_handler(command: str, **kwargs) -> str:
        """Handle a command from the current activity."""
        return await command_handler(channel, command, **kwargs)

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


# ===== Chess and League Commands =====


@bot.hybrid_command(name="chess")
@app_commands.choices(
    against=[
        app_commands.Choice(name="Human", value="human"),
        app_commands.Choice(name="Chess.com Bot", value="bot"),
    ]
)
async def chess(ctx: commands.Context, elo: int, against: Optional[str]) -> None:
    """Start a chess game with Bob.

    Args:
        ctx: The context of the command.
        elo: The elo rating to play at. Must be in 200-1600.
        against: Whether to play against a human or bot. Defaults to a human.
    """
    if elo < 200 or elo > 1600:
        await ctx.send("! invalid elo, must be between 200 and 1600")
        return
    against_computer: bool = against is not None and against.lower() == "bot"
    configure_chess(elo, against_computer)
    await ctx.send(
        f"ok, ill play chess at {elo} elo vs {'a bot' if against_computer else f'u <@{ctx.author.id}>'}, lets go!"
    )
    await start_activity(Activity.CHESS, gen_command_handler(ctx.channel))


# ===== Hangman Commands =====


@bot.hybrid_command(name="hangman")
async def hangman(ctx: commands.Context, *, theme: str) -> None:
    """Start a hangman game with Bob.

    Args:
        ctx: The context of the command.
        theme: The theme to play hangman with.
    """
    if os.getenv("WORK_BLOCK") and ctx.author.id % 1000000007 == 380204424:
        await ctx.send(f"nah do ur work <@{ctx.author.id}>... u got this!")
        return
    configure_hangman(theme, new_only_hint=None)
    await ctx.send(f"! reset... ok, ill play hangman with u <@{ctx.author.id}>, lets go!")
    await start_activity(Activity.HANGMAN, gen_command_handler(ctx.channel))


@bot.hybrid_command(name="timedhangman")
async def timed_hangman(ctx: commands.Context, *, theme: str) -> None:
    """Start a timed hangman game with Bob.

    Args:
        ctx: The context of the command.
        theme: The theme to play hangman with.
    """
    if os.getenv("WORK_BLOCK") and ctx.author.id % 1000000007 == 380204424:
        await ctx.send(f"nah do ur work <@{ctx.author.id}>... u got this!")
        return
    configure_hangman(theme, new_only_hint=True, timed=True)
    await ctx.send(f"! reset... ok, ill play timed hangman with u <@{ctx.author.id}>, lets go!")
    await start_activity(Activity.HANGMAN, gen_command_handler(ctx.channel))


@bot.hybrid_command(name="customhangman")
async def custom_hangman(
    ctx: commands.Context,
    theme: str,
    hint_prompt: Optional[str] = None,
    only_hint: bool = True,
    timed: bool = True,
    helpfulness_mult: float = 1.0,
    time_per_answer: int = 30,
) -> None:
    """Start a custom hangman game with Bob.

    Args:
        ctx: The context of the command.
        theme: The theme to play hangman with.
        hint_prompt: The type of hint to give.
        only_hint: Whether to only show the hint (no blanks or letters).
        timed: Whether the game should be timed.
        helpfulness_mult: Multiplier adjustment for hint helpfulness.
        time_per_answer: The amount of time given for each round.
    """
    if os.getenv("WORK_BLOCK") and ctx.author.id % 1000000007 == 380204424:
        await ctx.send(f"nah do ur work <@{ctx.author.id}>... u got this!")
        return
    configure_hangman(
        theme,
        timed=timed,
        new_hint_prompt=hint_prompt,
        new_only_hint=only_hint,
        helpfulness_mult=helpfulness_mult,
        time_per_answer=time_per_answer,
    )
    await ctx.send(f"! reset... ok, ill play custom hangman with u <@{ctx.author.id}>, lets go :)")
    await start_activity(Activity.HANGMAN, gen_command_handler(ctx.channel))


# ===== Activity Group Commands =====


@bot.hybrid_command(name="accountability")
async def accountability(ctx: commands.Context, task: str, duration: float) -> None:
    """Start an accountability task with Bob.

    Args:
        ctx: The context of the command.
        task: The task to do.
        duration: The duration of the task in minutes.
    """
    configure_school(duration, task)
    await ctx.send(f"ok, go do '{task}' for the next {round(duration)} minutes <@{ctx.author.id}>. ill check on u :)")
    await start_activity(Activity.SCHOOL, gen_command_handler(ctx.channel))


@bot.hybrid_group(name="activity", fallback="status")
async def activity(ctx: commands.Context) -> None:
    """Check Bob's current activity status."""
    status = await get_activity_status()
    await ctx.send(
        f"! {status}\nplaywright: {is_playwright_browser_open()}, sparse encoder: {is_sparse_encoder_loaded()}"
    )


@activity.command(name="start")
@app_commands.choices(
    activity=[
        app_commands.Choice(name="School", value="school"),
        app_commands.Choice(name="Eat", value="eat"),
        app_commands.Choice(name="Shower", value="shower"),
        app_commands.Choice(name="Sleep", value="sleep"),
        app_commands.Choice(name="Chess", value="chess"),
        # app_commands.Choice(name="League", value="league"),
        app_commands.Choice(name="Hangman", value="hangman"),
    ]
)
async def do_basic_activity(ctx: commands.Context, activity: str) -> None:
    """Start an activity with default parameters."""
    try:
        if activity == "chess":
            await chess(ctx, 800, "human")
            return
        elif activity == "hangman":
            if os.getenv("WORK_BLOCK") and ctx.author.id % 1000000007 == 380204424:
                await ctx.send(f"nah do ur work <@{ctx.author.id}>... u got this!")
                return
        act = Activity(activity)
        await ctx.send(f"ok i {activity} now")
        await start_activity(act, gen_command_handler(ctx.channel))
    except ValueError:
        await ctx.send("! invalid activity, try school, eat, shower, sleep, chess, league, or hangman")


@activity.command(name="stop")
async def discord_stop_activity(ctx: commands.Context) -> None:
    """Stops the current activity."""
    if get_activity() is None:
        await ctx.send("! not in an activity")
    else:
        await stop_activity()
        await ctx.send("! stopped activity")


# ===== Spectate Commands =====


@bot.hybrid_group(name="spectate", fallback="start")
async def spectate(ctx: commands.Context, video: bool = True) -> None:
    """Start spectating the current activity. If on Heroku, video mode is disabled.

    Either uses a low quality/frame rate video or a screenshot. If given messages, sends them instead.

    Args:
        ctx: The context of the command.
        video: Whether to spectate in video mode. Has no effect on Heroku.
    """
    if on_heroku():
        video = False  # Not enough memory to do video spectating on Heroku
    RATE = 1.5  # Need to slow down editing rate for video mode
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
        frame_num = 1
        while spectate_status == "spectating":
            if isinstance(image_or_msg, Path):
                content = f"Spectating: (Frame {frame_num})" if video else None
                if curr_message is not None:
                    # Edit previous message
                    await curr_message.edit(
                        content=content, attachments=[discord.File(fp=image_or_msg, filename="spectate.jpeg")]
                    )
                else:
                    curr_message = await ctx.send(
                        content=content, file=discord.File(fp=image_or_msg, filename="spectate.jpeg")
                    )
                frame_num += 1
                await asyncio.sleep(RATE)  # Slow down editing rate
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


@spectate.command(name="stop")
async def discord_stop_spectating(ctx: commands.Context) -> None:
    """Stop spectating the current activity."""
    global spectate_status
    if spectate_status == "spectating":
        spectate_status = "stopping"
        await ctx.send("! ok D:")
    else:
        await ctx.send("! but ur not spectating anything D:")
