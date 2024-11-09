"""Contains miscellaneous commands for the bot."""

import sys
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bobbot.discord_helpers.main_bot import Speed, bot
from bobbot.discord_helpers.text_channel_history import (
    TextChannelHistory,
    get_channel_history,
)
from bobbot.utils import (
    close_playwright_browser,
    get_debug_info,
    get_logger,
    truncate_length,
)

logger = get_logger(__name__)


# ===== Info Commands =====


@bot.hybrid_command(name="help")
async def help(ctx: commands.Context) -> None:
    """Show the help message."""
    await ctx.send(
        """! hi i am bob 2nd edition v2.0
command prefix is `!`, slash commands work too

`activity status` - Check Bob's current activity status.
`activity [school/eat/shower/sleep/chess/league]` - Start an activity with default parameters.
`activity stop` - Stops the current activity.
`chess [elo] [human/bot]` - Start a chess game with Bob playing at the given elo (in 200-1600), against a human or bot.
`hangman "[theme]"` - Start a game of hangman with Bob. If using command prefix, include the double quotes.
`spectate start` - Spectate the current activity.\t\t`spectate stop` - Stop spectating the current activity.

`vc join` - Tell Bob to join your voice channel.\t\t`vc leave` - Tell Bob to leave your voice channel.
`tts [text]` - Speak the given text in a familiar voice.\t\t`vc log` - Show the current VC conversation history.

`memory reset` - Wipes the bot's short term conversation history. No effect on long term memories.
`memory query [query]` - Query Bob's long term memory. Must provide a search query.
`memory delete [id]` - Delete a long term memory by ID. Use to remove private/unwanted info.

`config on` - Turn the bot on.\t\t`config off` - Turn the bot off.
`config get` - Show the bot's current configuration.
`config speed [default/instant]` - Set the typing speed of the bot.
`config obedient [true/false]` - Force the bot to try to fulfill all requests.
`config incognito [true/false]` - Prevent the bot from accessing or storing long term memories.

`admin debug` - Show debug info for the last message Bob processed.
`admin prune [count]` - Delete up to count messages sent by the bot in recent history.
`admin reboot` - Reboot the bot. May take a while.

`help` - Show this help message.\t\t`ping` - Ping the bot."""
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


# ===== Config Commands =====


@bot.hybrid_group(name="config", fallback="get")
async def config(ctx: commands.Context):
    """Show the bot's current configuration."""
    await ctx.send(
        f"! on: {bot.is_on}, speed: {bot.speed.value}, obedient: {bot.is_obedient}, incognito: {bot.is_incognito}"  # noqa: E501
    )


@config.command("on")
async def config_on(ctx: commands.Context) -> None:
    """Turn the bot on or off."""
    bot.is_on = True
    await ctx.send("! bot turned on")


@config.command("off")
async def config_off(ctx: commands.Context) -> None:
    """Turn the bot off."""
    bot.is_on = False
    await ctx.send("! bot turned off")


@config.command("speed")
@app_commands.choices(
    speed=[
        app_commands.Choice(name="Default", value="default"),
        app_commands.Choice(name="Instant", value="instant"),
    ]
)
async def config_speed(ctx: commands.Context, speed: str) -> None:
    """Set the typing speed of the bot."""
    try:
        selected_speed = Speed(speed.lower())
        bot.speed = selected_speed
        await ctx.send(f"! typing speed set to {selected_speed.value}")
    except ValueError:
        valid_speeds = ", ".join([s.value for s in Speed])
        await ctx.send(f"! invalid typing speed. valid speeds: {valid_speeds}")


@config.command("obedient")
async def config_obedient(ctx: commands.Context, obedient: bool) -> None:
    """Force the bot to try to fulfill all requests."""
    bot.is_obedient = obedient
    if obedient:
        await ctx.send("! bot is now obedient and will try to fulfill all requests")
    else:
        await ctx.send("! bot is now normal")


@config.command("incognito")
async def config_incognito(ctx: commands.Context, incognito: bool) -> None:
    """Prevent the bot from accessing or storing long term memories."""
    bot.is_incognito = incognito
    if incognito:
        await ctx.send("! bot is now incognito and will not use or make new long term memories")
    else:
        await ctx.send("! bot is now normal and will use and make new long term memories")


# ===== Admin Commands =====


@bot.hybrid_group(name="admin", fallback="debug")
async def debug(ctx: commands.Context) -> None:
    """Show debug info for the last message Bob processed."""
    debug_info = get_debug_info()
    if not debug_info:
        await ctx.send("! No trace available.")
    else:
        await ctx.send(truncate_length("!```Trace:\n" + debug_info + "```", 2000))


@debug.command(name="reboot")
async def reboot(ctx: commands.Context):
    """Reboot the bot. May take a while."""
    await ctx.send("! ok, rebooting...")
    await close_playwright_browser()
    sys.exit(0)  # Exit the process, triggering a reboot on Heroku


@debug.command(name="prune")
async def prune(ctx, count: int):
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


# ===== Misc =====


@bot.event
async def on_typing(channel, user, when):
    """Respond to typing events."""
    if not (channel.id in bot.CHANNELS or isinstance(channel, discord.DMChannel)):
        return
    curr_channel: discord.TextChannel = channel
    history: TextChannelHistory = get_channel_history(curr_channel)
    history.on_typing(user, when)
