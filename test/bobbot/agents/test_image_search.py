"""Integration test for retrieving an image."""

import os

import pytest
from langchain_core.tracers.context import tracing_v2_enabled
from mock_history import MockHistory

if os.getenv("OPENAI_KEY"):
    from bobbot.agents import get_response_with_tools
    from bobbot.utils import get_images_in


# Skip if API keys are not provided
pytestmark = pytest.mark.skipif(
    os.getenv("OPENAI_KEY") is None or os.getenv("SERPER_API_KEY") is None,
    reason="Missing OPENAI_KEY or SERPER_API_KEY environment variable",
)


async def test_image_search() -> None:
    """Should contain a single image URL in the response."""
    history = MockHistory(["Lax: bob can u send me a pic of zoe from league of legends?"])
    with tracing_v2_enabled(tags=["test_image_search"]):
        response = await get_response_with_tools(history.as_langchain_msgs())
        num_images = len(get_images_in(response))
        assert num_images == 1, f"Expected exactly 1 image URL in response, got {num_images}"
