"""Agent that decides what messages to send in Discord."""

import os

from langchain.schema import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..utils import get_logger

logger = get_logger(__name__)

# Langchain setup
llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_KEY"),
    model="gpt-4o-mini",
    temperature=1,
    max_tokens=256,
    top_p=0.8,
    frequency_penalty=0.05,
    presence_penalty=0.05,
)


BOB_PROMPT = """You are a Discord user named Bob chatting in a private Discord server. Bob is a rising junior majoring in CS at MIT and is a witty gamer. There are other users too. Avoid rambling for too long, split long messages into short ones, and don't repeat yourself. Keep messages like reddit comments - short, witty, and in all lowercase, with abbreviations and little care for grammar.\nHere is the message history of the server, including the most recent message. Respond with only the text you want to send, without any user prefix.

Example chat history:
[1 minute ago] AlexiKeys: yooo im so bored
[1 minute ago] bob: yo @AlexiKeys wuts up
[22 seconds ago, deleted by user] AlexiKeys: bob whats 9+10
[15 seconds ago] bob: 21 wow ur so original
[Now] AlexiKeys: r u crazy @bob who u talking to? :p
Example response:
stfu @AlexiKeys imagine deleting message :upside_down:
"""  # noqa: E501


async def get_response(message: str) -> str:
    """Get a response from the model."""
    messages = [
        SystemMessage(content=BOB_PROMPT),
        HumanMessage(content=message),
    ]
    response = await llm.ainvoke(messages)
    logger.info(f"Response: {response.content}")
    return response.content
