"""Simple, unambiguous, concise tests for the decision agent's behavior."""

import os
from typing import Optional

import pytest
from langchain_core.tracers.context import tracing_v2_enabled

from bobbot.discord_helpers import ManualHistory, bot

if os.getenv("OPENAI_KEY"):
    from bobbot.agents import decide_to_respond

# Skip if no OpenAI key is provided
pytestmark = pytest.mark.skipif(os.getenv("OPENAI_KEY") is None, reason="Missing OPENAI_KEY environment variable")

bot.is_incognito = True


async def assert_decision(should_respond: bool, msg_history: str, status: Optional[str]) -> None:
    """Assert that the decision agent's decision matches the expected decision."""
    with tracing_v2_enabled(tags=["test_decision_agent"]):
        decision, thoughts = await decide_to_respond(msg_history, status)
        assert (
            decision == should_respond
        ), f"Decision: {'RESPOND' if decision else 'WAIT'} (wrong), Thoughts: {thoughts}"


async def test_question_respond() -> None:
    """Should respond to a direct question."""
    history = ManualHistory(
        [
            "Lax: i wanna apex",
            "Mora: @bob what do u think?",
        ]
    )
    await assert_decision(True, history.as_string(), None)


async def test_question_wait() -> None:
    """Should not respond to a question targetted at someone else."""
    history = ManualHistory(
        [
            "Lax: i wanna apex",
            "Mora: @Neal what do u think?",
        ]
    )
    await assert_decision(False, history.as_string(), None)


async def test_thank_you_respond() -> None:
    """Should respond to a thank you from the user."""
    history = ManualHistory(
        [
            "Mora: bob what time is it",
            "bob: it's 5:25 PM, why? you lost track of time in the void? 😄",
            "Mora: ty",
        ]
    )
    await assert_decision(True, history.as_string(), None)


async def test_good_night_wait() -> None:
    """Should not respond to a good night message twice."""
    history = ManualHistory(
        [
            "Mora: ok bob ima sleep now",
            "bob: rip mora, sweet dreams dude 💤",
            "Mora: gn",
        ]
    )
    await assert_decision(False, history.as_string(), None)
