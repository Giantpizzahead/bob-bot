"""Manages messages received by the bot."""

import discord

from bobbot.activities import get_activity_status
from bobbot.agents import decide_to_respond, get_response_with_tools
from bobbot.discord_helpers.activity_manager import check_waiting_responses
from bobbot.discord_helpers.main_bot import Mode, bot, lazy_send_message
from bobbot.discord_helpers.text_channel_history import (
    TextChannelHistory,
    get_channel_history,
)
from bobbot.utils import get_logger, reset_debug_info

logger = get_logger(__name__)


@bot.event
async def on_message(message: discord.Message):
    """Respond to messages."""
    # Only respond to messages in DMs and specified channels
    if not (message.channel.id in bot.CHANNELS or isinstance(message.channel, discord.DMChannel)):
        return
    curr_channel: discord.TextChannel = message.channel
    # Set the active channel
    bot.active_channel = message.channel
    await bot.process_commands(message)
    # Don't respond if the bot is off, or if it's a command message
    if bot.mode == Mode.OFF or message.content.startswith(bot.command_prefix):
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
            context = f"Context that may be helpful:\nYour status: {await get_activity_status()}"
            if "You're free right now." in context:
                context = None
            # response: str = await get_response(
            #     history.as_langchain_msgs(bot.user),
            #     context=context,
            # )
            response: str = await get_response_with_tools(
                history.as_langchain_msgs(bot.user),
                context=context,
            )
            if history.message_count == saved_message_count:
                await lazy_send_message(message.channel, response)
    except Exception as e:
        logger.exception("Error getting response")
        await lazy_send_message(message.channel, str(e), instant=True, force=True)
