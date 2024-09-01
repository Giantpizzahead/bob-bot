"""Manages the bot's long term memory."""

from datetime import datetime, timezone

from discord.ext import commands

from bobbot.discord_helpers.main_bot import bot
from bobbot.memory import delete_memory, query_memories
from bobbot.utils import get_logger, time_elapsed_str, truncate_length

logger = get_logger(__name__)


@bot.hybrid_group(name="memory", fallback="query")
async def memories(ctx: commands.Context, query: str) -> None:
    """Query Bob's long term memory."""
    memories = await query_memories(query, limit=5)
    # Format memories as strings
    formatted_memories: list[str] = []
    for memory in memories:
        timestamp = memory.metadata["creation_time"]
        time_str = time_elapsed_str(datetime.fromtimestamp(timestamp, tz=timezone.utc))
        mem_title = f"({time_str}, ID: {memory.metadata['id']})"
        mem_content = truncate_length(memory.page_content, 256)
        formatted_memories.append(f"{mem_title}\n{mem_content}")
    if formatted_memories:
        await ctx.send(
            truncate_length(
                f"! memories (most relevant first):\n{'\n\n'.join([m for m in formatted_memories])}",
                2000,
            )
        )
    else:
        await ctx.send("! no relevant memories found")


@memories.command(name="delete")
async def discord_delete_memory(ctx: commands.Context, id: str) -> None:
    """Delete a long term memory by ID."""
    if await delete_memory(id):
        await ctx.send("! memory deleted")
    else:
        await ctx.send(f"! memory with id {id} not found")


@memories.command(name="reset")
async def reset(ctx: commands.Context) -> None:
    """Wipes the bot's short term conversation history. No effect on long term memories."""
    await ctx.send("! reset conversation history")
