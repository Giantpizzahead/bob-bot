"""Contains miscellaneous commands for the bot."""

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bobbot.activities import get_activity_status
from bobbot.discord_helpers.main_bot import Mode, Speed, bot
from bobbot.discord_helpers.text_channel_history import (
    TextChannelHistory,
    get_channel_history,
)
from bobbot.utils import get_debug_info, get_logger, truncate_length

logger = get_logger(__name__)


@bot.hybrid_command(name="help")
async def help(ctx: commands.Context) -> None:
    """Show the help message."""
    await ctx.send(
        """! hi i am bob 2nd edition v1.5
command prefix is `!`, slash commands work too

activities:
`chess [elo] [human/bot]` - Start a chess game with Bob playing at the given elo (in 200-1600), against a human or bot.
`activity [school/eat/shower/sleep/chess/league]` - Start an activity (without configuring parameters).
`spectate` - Spectate the current activity.
`stop_spectating` - Stop spectating the current activity.
`stop_activity` - Stops the current activity.

config:
`mode [default/obedient/off]` - Set the mode of the bot, clearing the conversation history.
`speed [default/instant]` - Set the typing speed of the bot.
`reset` - Reset the bot's conversation history.
`delete_last [count]` - Delete up to count messages sent by the bot in recent history.
`reboot` - Reboot the bot. May take a while.

info:
`help` - Show this help message.
`status` - Show the current mode, speed, and activity of the bot.
`debug` - Show debug info for the last message Bob processed.
`ping` - Ping the bot."""
    )


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
        bot.mode = selected_mode
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
        bot.speed = selected_speed
        await ctx.send(f"! speed set to {selected_speed.value}")
    except ValueError:
        valid_speeds = ", ".join([s.value for s in Speed])
        await ctx.send(f"! invalid speed. valid speeds: {valid_speeds}")


@bot.hybrid_command(name="reset")
async def reset(ctx: commands.Context) -> None:
    """Reset the bot's conversation history."""
    await ctx.send("! reset conversation history")


@bot.hybrid_command(name="status")
async def status(ctx: commands.Context) -> None:
    """Show the current mode, speed, and activity of the bot."""
    await ctx.send(f"! mode: {bot.mode.value}, speed: {bot.speed.value}\nactivity: {await get_activity_status()}")


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


@bot.hybrid_command(name="delete_last")
async def delete_last(ctx, count: int):
    """Delete up to count messages sent by the bot in recent history."""
    if count > 5:
        await ctx.send("! can only delete up to 5 msgs at a time")
        return
    num_deleted = 0
    async for message in ctx.channel.history(limit=20):
        if message.author == bot.user:
            await message.delete()
            num_deleted += 1
            if num_deleted == count:
                break
    if num_deleted == 0:
        await ctx.send(f"! {ctx.author.mention} no bot msgs in recent history (last 20 msgs)")
    else:
        await ctx.send(f"! {ctx.author.mention} deleted last {num_deleted} bot msgs")
    await ctx.message.delete()


@bot.event
async def on_typing(channel, user, when):
    """Respond to typing events."""
    if not (channel.id in bot.CHANNELS or isinstance(channel, discord.DMChannel)):
        return
    curr_channel: discord.TextChannel = channel
    history: TextChannelHistory = get_channel_history(curr_channel)
    history.on_typing(user, when)
