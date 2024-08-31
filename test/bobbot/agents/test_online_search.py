"""Integration test for finding an answer online."""

import os

import pytest
from langchain_core.tracers.context import tracing_v2_enabled
from mock_history import MockHistory

from bobbot.agents import get_response_with_tools

# Skip if API keys are not provided
pytestmark = pytest.mark.skipif(
    os.getenv("OPENAI_KEY") is None or os.getenv("SERPER_API_KEY") is None,
    reason="Missing OPENAI_KEY or SERPER_API_KEY environment variable",
)


async def test_online_search() -> None:
    """Should contain the correct answer in the response."""
    history = MockHistory(
        [
            "Lax: bob, when was aurora released in league of legends? please format the date exactly like 'March 28, 2002'."  # noqa: E501
        ]
    )
    with tracing_v2_enabled(tags=["test_online_search"]):
        response = await get_response_with_tools(history.as_langchain_msgs())
        # Look for the expected answer in some format
        for keyword in ["july", "17", "2024"]:
            assert keyword in response.lower(), "Expected answer (July 17, 2024) not in response"
