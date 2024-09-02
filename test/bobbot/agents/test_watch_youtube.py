"""Integration tests for watching a youtube video."""

import os

import pytest
from langchain_core.tracers.context import tracing_v2_enabled

from bobbot.discord_helpers import ManualHistory, bot

if os.getenv("OPENAI_KEY"):
    from bobbot.agents import get_response_with_tools


# Skip if no OpenAI key is provided
pytestmark = pytest.mark.skipif(
    os.getenv("OPENAI_KEY") is None,
    reason="Missing OPENAI_KEY environment variable",
)

bot.is_incognito = True


async def test_watch_youtube() -> None:
    """Should contain the correct answer in the response, which can only be gotten from the transcript or comments."""
    history = ManualHistory(
        [
            "Lax: bob, what is the shape of the barrier in this youtube vid? answer in the format 'X-shaped' https://www.youtube.com/shorts/pa7Zomh_Q60"  # noqa: E501
        ]  # noqa: E501
    )
    with tracing_v2_enabled(tags=["test_watch_youtube"]):
        response = await get_response_with_tools(history.as_langchain_msgs(), store_memories=False)
        # Look for the expected answer in some format
        for keyword in ["l-shaped"]:
            assert keyword in response.lower(), "Expected answer (L-shaped) not in response"
