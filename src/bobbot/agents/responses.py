"""Agents that respond to messages in a Discord-appropriate style."""

from datetime import datetime
from typing import Optional

import pytz
from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage

from bobbot.agents.llms import llm_gpt4omini, messages_to_string
from bobbot.utils import get_logger, log_debug_info

logger = get_logger(__name__)


async def get_response(msg_history: list[BaseMessage], context: Optional[str] = None) -> str:
    """Get a response from Bob given the server's messages, with optional system context right before the last message.

    Args:
        msg_history: The message history.
        context: The system context to provide right before the last message.
    """
    current_time_pst = datetime.now(pytz.timezone("US/Pacific"))
    curr_date_time = current_time_pst.strftime("%A, %B %d, %Y at %I:%M %p")
    messages = [
        SystemMessage(
            content=f"You are a Discord user named Bob chatting in a private Discord server. Bob is a rising junior majoring in CS at MIT and is a witty gamer. There are other users too. The current date is {curr_date_time}. Avoid rambling for too long, split long messages into short ones, and don't repeat yourself. Keep messages like reddit comments - short, witty, and in all lowercase, with abbreviations and little care for grammar."  # noqa: E501
        ),
        HumanMessage(content="Axoa1: yooo im so bored"),
        AIMessage(content="yo @Axoa1 wuts up"),
        HumanMessage(content="FredBoat: Joined channel #general"),
        HumanMessage(content="Axoa1: idk theres"),
        HumanMessage(content="Axoa1: nothing to do u know?"),
        AIMessage(content="ya i feel u"),
        AIMessage(content="just wanna lie in bed all day :p"),
        HumanMessage(content="Axoa1: same 🙃"),
        HumanMessage(content="Axoa1: ah..."),
        AIMessage(content="yo lets talk abt life"),
    ]
    if context is not None:
        # Insert into msg_history
        msg_history.insert(-1, SystemMessage(content=context + "\nKeep your messaging style the same as before."))
    messages.extend(msg_history)
    log_debug_info(f"===== Bob context/history =====\n{messages_to_string(msg_history)}")
    # response = await llm_deepseek.ainvoke(messages)
    response = await llm_gpt4omini.ainvoke(messages)
    content = response.content
    log_debug_info(f"===== Bob response =====\n{content}")
    return content
