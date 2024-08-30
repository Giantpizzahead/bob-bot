"""Agents that respond to messages in a Discord-appropriate style."""

from datetime import datetime
from typing import Optional

import pytz
from langchain.tools import Tool
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from bobbot.agents.llms import llm_gpt4omini, messages_to_string
from bobbot.agents.tools import TOOL_BY_NAME, TOOL_LIST
from bobbot.utils import get_logger, log_debug_info, truncate_length

logger = get_logger(__name__)


async def get_response_with_tools(msg_history: list[BaseMessage], context: Optional[str] = None) -> str:
    """Get a response from Bob given the server's messages, with optional system context right before the last message.

    Can use tools as well.

    Args:
        msg_history: The message history.
        context: The system context to provide right before the last message.
    """
    MAX_LOOPS = 3
    current_time_pst = datetime.now(pytz.timezone("US/Pacific"))
    # curr_date_time = current_time_pst.strftime("%A, %B %d, %Y at %I:%M %p")
    curr_time = current_time_pst.strftime("%I:%M %p")
    messages = [
        SystemMessage(
            content=f"You are a Discord user named Bob chatting in a private Discord server. Bob is a rising junior majoring in CS at MIT and is a witty gamer. There are other users too. The current time is {curr_time}. You can use tools up to {MAX_LOOPS-1} times to get context before sending a message, and may need to chain multiple tool calls to find this context. You can send new links and images to the user as plain URLs, do NOT use markdown to format these. Avoid rambling for too long, split long messages into short ones, and don't repeat yourself. Keep messages like reddit comments - short, witty, and in all lowercase, with abbreviations and little care for grammar. If you really don't know the answer to a factual question, say you don't know - do not make up info."  # noqa: E501
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
    # log_debug_info(f"===== Bob context/history =====\n{messages_to_string(msg_history)}")

    # Let the agent self loop
    for i in range(MAX_LOOPS):
        # Force a response on the last loop
        tool_choice = "auto" if i != MAX_LOOPS - 1 else "none"
        llm_with_tools = llm_gpt4omini.bind_tools(TOOL_LIST, tool_choice=tool_choice, strict=True)
        ai_message = await llm_with_tools.ainvoke(messages)
        messages.append(ai_message)
        if ai_message.tool_calls:
            for tool_call in ai_message.tool_calls:
                logger.info(f"Calling tool {tool_call['name']} with args {tool_call['args']}")
                tool: Tool = TOOL_BY_NAME[tool_call["name"]]
                tool_message: ToolMessage = await tool.ainvoke(tool_call)
                messages.append(tool_message)
                log_debug_info(
                    f"===== Iteration {i+1}: {tool_call['name']}, args {tool_call['args']} =====\n{truncate_length(tool_message.content, 256)}"  # noqa: E501
                )
                logger.info(f"Full tool call result: {tool_message.content}")
        else:
            break

    # Output response
    assert len(ai_message.content.strip()) > 0
    content = ai_message.content
    log_debug_info(f"===== Bob response =====\n{content}")
    return content


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
