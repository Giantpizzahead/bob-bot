"""Manages messages received by the bot."""

import asyncio
from datetime import datetime, timedelta, timezone

import discord
from langchain.docstore.document import Document

from bobbot.activities import get_activity_status
from bobbot.agents import (
    check_openai_safety,
    decide_to_respond,
    get_response_with_tools,
)
from bobbot.discord_helpers.activity_manager import check_waiting_responses
from bobbot.discord_helpers.main_bot import Mode, bot, lazy_send_message
from bobbot.discord_helpers.text_channel_history import (
    TextChannelHistory,
    get_channel_history,
)
from bobbot.memory import query_memories
from bobbot.utils import (
    get_logger,
    log_debug_info,
    reset_debug_info,
    time_elapsed_str,
    truncate_length,
)

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
        short_history: str = history.as_string(5)
        decision, thoughts = await decide_to_respond(short_history)
        if decision is False:
            return
        async with curr_channel.typing():
            asyncio.create_task(check_waiting_responses(curr_channel))
            is_safe = await check_openai_safety(short_history)

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
                    tiny_history, limit=EACH_LIMIT, ignore_recent=False, only_tools=True, age_limit=timedelta(hours=1)
                ),  # Relevant tool calls, some context, recent only
            )

            # Fetch up to MAX_MEMORIES memories using a rough heuristic order, removing duplicates
            memory_lists = [memories_6, memories_1, memories_4, memories_3, memories_5, memories_0, memories_2]
            memories: list[Document] = []
            for i in range(EACH_LIMIT):
                for memory_list in memory_lists:
                    if i < len(memory_list) and len(memories) < MAX_MEMORIES:
                        memory = memory_list[i]
                        if memory.metadata["id"] not in [m.metadata["id"] for m in memories]:
                            memories.append(memory)

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
                        f"===== Bob memories =====\n{'\n'.join([truncate_length(m, 192) for m in formatted_memories])}",
                        1000,
                    )
                )

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
            response: str = await get_response_with_tools(
                history.as_langchain_msgs(bot.user),
                context=context,
                uncensored=(is_safe is False),
                obedient=(bot.mode == Mode.OBEDIENT),
            )
        if history.message_count == saved_message_count:
            await lazy_send_message(message.channel, response)
    except Exception as e:
        logger.exception("Error getting response")
        await lazy_send_message(message.channel, str(e), instant=True, force=True)
