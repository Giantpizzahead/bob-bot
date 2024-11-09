"""Manages messages received by the bot."""

import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from langchain.docstore.document import Document

from bobbot.activities import (
    Activity,
    get_activity,
    get_activity_status,
    hangman_on_message,
)
from bobbot.agents import (  # decide_to_respond,
    check_openai_safety,
    get_response,
    get_response_with_tools,
)
from bobbot.discord_helpers.activity_manager import check_waiting_responses
from bobbot.discord_helpers.main_bot import bot, lazy_send_message
from bobbot.discord_helpers.text_channel_history import (
    TextChannelHistory,
    get_channel_history,
)
from bobbot.memory import is_sparse_encoder_loaded, query_memories
from bobbot.utils import (
    get_logger,
    is_playwright_browser_open,
    log_debug_info,
    on_heroku,
    reset_debug_info,
    time_elapsed_str,
    truncate_length,
)

logger = get_logger(__name__)


@bot.event
async def on_message(message: discord.Message, use_perplexity: bool = False):
    """Respond to messages, using or not using smart search (Perplexity)."""
    # Only respond to messages in DMs and specified channels
    if not (use_perplexity or message.channel.id in bot.CHANNELS or isinstance(message.channel, discord.DMChannel)):
        return
    curr_channel: discord.TextChannel = message.channel
    # Set the active channel
    bot.active_channel = message.channel
    await bot.process_commands(message)
    # Don't respond if the bot is off, or if it's a command message
    if message.content.startswith(bot.command_prefix):
        return
    elif not bot.is_on:
        if bot.user in message.mentions:
            await lazy_send_message(
                curr_channel, "! im off rn, see help with /help, turn on with /config on", instant=True, force=True
            )
        return
    # For now, don't respond to self messages
    if not use_perplexity and message.author == bot.user:
        return

    # Call play hangman if activity is hangman
    if get_activity() == Activity.HANGMAN:
        response = await hangman_on_message(message.content)
        if response:
            await lazy_send_message(message.channel, response)
        return

    # Don't respond further unless pinged or in a DM
    if not (use_perplexity or bot.user in message.mentions or isinstance(message.channel, discord.DMChannel)):
        return

    # Get history for the current channel
    history: TextChannelHistory = get_channel_history(curr_channel)
    await history.aupdate()
    history.clear_users_typing()
    saved_message_count: int = history.message_count
    # Get a response
    if on_heroku():
        logger.info(
            f"Before message, playwright: {is_playwright_browser_open()}, sparse encoder: {is_sparse_encoder_loaded()}"
        )
    try:
        reset_debug_info()
        short_history: str = history.as_string(5)
        # decision, thoughts = await decide_to_respond(short_history)
        # Bypass decision agent (due to pings)
        # if decision is False:
        #     return
        async with curr_channel.typing():
            asyncio.create_task(check_waiting_responses(curr_channel))
            is_safe = await check_openai_safety(short_history)
            heroku_override = False
            if on_heroku() and get_activity() == Activity.CHESS:
                heroku_override = True  # Can't query memories while playing chess on Heroku
            elif on_heroku() and bot.voice_clients:
                heroku_override = True  # Can't query memories while in a voice channel on Heroku
            if on_heroku():
                logger.info(f"Heroku memory saver override: {heroku_override}")
            if not bot.is_incognito and not heroku_override:
                # Find relevant memories using varying methods
                EACH_LIMIT = 2
                MAX_MEMORIES = 4

                # Run all memory queries in parallel
                tiny_history: str = history.as_string(3)
                only_message: str = history.as_string(1, with_author=False, with_context=False, with_reactions=False)
                (
                    memories_0,
                    memories_1,
                    memories_2,
                    memories_3,
                    memories_4,
                    memories_5,
                    memories_6,
                ) = await asyncio.gather(
                    query_memories(short_history, limit=EACH_LIMIT),  # More context
                    query_memories(tiny_history, limit=EACH_LIMIT),  # Some context
                    query_memories(
                        tiny_history, limit=EACH_LIMIT, age_limit=timedelta(hours=1)
                    ),  # Some context, recent only
                    query_memories(only_message, limit=EACH_LIMIT),  # Last message with no author
                    query_memories(
                        only_message, limit=EACH_LIMIT, age_limit=timedelta(hours=1)
                    ),  # Last message with no author, recent only
                    query_memories(
                        tiny_history, limit=EACH_LIMIT, ignore_recent=False, only_tools=True
                    ),  # Relevant tool calls, some context
                    query_memories(
                        tiny_history,
                        limit=EACH_LIMIT,
                        ignore_recent=False,
                        only_tools=True,
                        age_limit=timedelta(hours=1),
                    ),  # Relevant tool calls, some context, recent only
                )

                # Fetch up to MAX_MEMORIES memories using a rough heuristic order, removing duplicates
                memory_lists = [memories_6, memories_1, memories_4, memories_3, memories_5, memories_0, memories_2]
                memories: list[Document] = []
                for i in range(EACH_LIMIT):
                    for j, memory_list in enumerate(memory_lists):
                        if i < len(memory_list) and len(memories) < MAX_MEMORIES:
                            memory = memory_list[i]
                            if memory.metadata["id"] not in [m.metadata["id"] for m in memories]:
                                memories.append(memory)
                                if len(memories) == MAX_MEMORIES:
                                    logger.info(f"Hit max of {MAX_MEMORIES} memories on iter {i}, memory list {j}.")

                # Format memories as strings
                formatted_memories: list[str] = []
                for memory in memories:
                    timestamp = memory.metadata["creation_time"]
                    time_str = time_elapsed_str(datetime.fromtimestamp(timestamp, tz=timezone.utc))
                    mem_title = f"({time_str})"
                    mem_content = truncate_length(memory.page_content, 2048)
                    formatted_memories.append(f"{mem_title}\n{mem_content}")
                if formatted_memories:
                    log_debug_info(
                        truncate_length(
                            f"===== Bob memories (found {len(memories)}) =====\n{'\n'.join([truncate_length(m, 192) for m in formatted_memories])}",  # noqa: E501
                            1000,
                        )
                    )
            else:
                formatted_memories = []

            # Get activity status
            activity_status = await get_activity_status()
            has_activity_status = "You're free right now." not in activity_status
            if has_activity_status:
                log_debug_info(f"===== Bob activity status =====\n{activity_status}")

            # Provide context
            context = "Here is some context that may be helpful."
            has_context = False
            if formatted_memories:
                has_context = True
                context += "\n\nMemories from past conversations and tool calls (be wary of outdated info):\n"
                context += "\n\n".join(formatted_memories)
            if has_activity_status:
                has_context = True
                context += f"\n\nYour status: {activity_status}"
            context = context.strip() if has_context else None
            # logger.info(f"Context:\n{context}")

            # Get response and send message
            if not use_perplexity:
                response: str = await get_response_with_tools(
                    history.as_langchain_msgs(bot.user),
                    context=context,
                    uncensored=not is_safe,
                    obedient=bot.is_obedient,
                    store_memories=not bot.is_incognito and not heroku_override,
                )
            else:
                response: str = await get_response(
                    history.as_langchain_msgs(bot.user),
                    context=context,
                    obedient=bot.is_obedient,
                    store_memories=not bot.is_incognito and not heroku_override,
                    use_perplexity=True,
                )
        if history.message_count == saved_message_count:
            await lazy_send_message(message.channel, response)
    except Exception as e:
        logger.exception("Error getting response")
        await lazy_send_message(message.channel, str(e), instant=True, force=True)


@bot.hybrid_command(name="research")
async def research(ctx: commands.Context, query: str) -> None:
    """Return a response using research from online."""
    message = await ctx.send(f'researching query: "{query}"')
    await on_message(message, use_perplexity=True)
