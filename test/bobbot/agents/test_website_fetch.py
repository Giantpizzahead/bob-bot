"""Integration tests for fetching an online website."""

import os

import pytest
from langchain_core.tracers.context import tracing_v2_enabled

from bobbot.discord_helpers import ManualHistory, bot

if os.getenv("OPENAI_KEY"):
    from bobbot.agents import get_response_with_tools

# Skip if no OpenAI key is provided or we are on a CI environment
pytestmark = pytest.mark.skipif(
    os.getenv("OPENAI_KEY") is None or os.getenv("CI") is not None,
    reason="Missing OPENAI_KEY environment variable or running in CI",
)

bot.is_incognito = True


async def test_website_fetch_static() -> None:
    """Load a static website. Should contain the correct answer in the response."""
    history = ManualHistory(
        [
            "Lax: bob, what is the first line in this song's chorus, please print it exactly: https://genius.com/Eden-wake-up-lyrics"  # noqa: E501
        ]  # noqa: E501
    )
    with tracing_v2_enabled(tags=["test_website_fetch_static"]):
        response = await get_response_with_tools(history.as_langchain_msgs())
        # Look for the expected answer in some format
        for keyword in ["stay", "not", "leave", "me"]:
            assert keyword in response.lower(), "Expected answer (Stay, you're not gonna leave me) not in response"


async def test_website_fetch_dynamic() -> None:
    """Load a dynamic website. Should contain the correct answer in the response."""
    history = ManualHistory(
        [
            "Lax: bob please tell me the number of likes and comments this has https://www.tiktok.com/@sunisalee_/video/7407902140250754350"  # noqa: E501
        ]
    )
    with tracing_v2_enabled(tags=["test_website_fetch_dynamic"]):
        response = await get_response_with_tools(history.as_langchain_msgs())
        # Look for the expected answer in some format
        for keyword in ["likes", "comments"]:
            assert keyword in response.lower(), "Expected answer (some number of likes and comments) not in response"
