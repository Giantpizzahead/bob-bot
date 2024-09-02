"""Contains base LLMs and functions for agents."""

import os
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import OpenAI

from bobbot.utils import get_logger

logger = get_logger(__name__)

# Setup OpenAI LLMs
openai_key: Optional[str] = os.getenv("OPENAI_KEY")
if openai_key is None:
    raise ValueError("OPENAI_KEY environment variable is not set.")
openai_client = OpenAI(api_key=openai_key)
openai_embeddings = OpenAIEmbeddings(api_key=openai_key)
llm_gpt35 = ChatOpenAI(
    api_key=openai_key,
    model="gpt-3.5-turbo",
    temperature=1,
    max_tokens=512,
    top_p=1,
    frequency_penalty=0.05,
    presence_penalty=0.05,
)
llm_gpt4omini = ChatOpenAI(
    api_key=openai_key,
    model="gpt-4o-mini",
    temperature=1,
    max_tokens=512,
    top_p=1,
    frequency_penalty=0.05,
    presence_penalty=0.05,
)
llm_gpt4omini_factual = ChatOpenAI(
    api_key=openai_key,
    model="gpt-4o-mini",
    temperature=0,
    max_tokens=512,
    top_p=0.5,
    frequency_penalty=0.05,
    presence_penalty=0.05,
)
del openai_key

# Setup OpenRouter LLMs
openrouter_key: Optional[str] = os.getenv("OPENROUTER_KEY")
if openrouter_key is None:
    raise ValueError("OPENROUTER_KEY environment variable is not set.")
llm_deepseek = ChatOpenAI(
    openai_api_key=openrouter_key,
    openai_api_base="https://openrouter.ai/api/v1",
    model_name="deepseek/deepseek-chat",
    temperature=1,
    max_tokens=512,
    top_p=0.8,
    frequency_penalty=0.05,
    presence_penalty=0.05,
)
llm_deepseek_factual = ChatOpenAI(
    openai_api_key=openrouter_key,
    openai_api_base="https://openrouter.ai/api/v1",
    model_name="deepseek/deepseek-chat",
    temperature=0,
    max_tokens=512,
    frequency_penalty=0.05,
    presence_penalty=0.05,
)
llm_mythomax = ChatOpenAI(
    openai_api_key=openrouter_key,
    openai_api_base="https://openrouter.ai/api/v1",
    model_name="gryphe/mythomax-l2-13b",
    temperature=1,
    max_tokens=512,
    top_p=0.8,
    frequency_penalty=0.05,
    presence_penalty=0.05,
)
del openrouter_key


def messages_to_string(messages):
    """Convert a list of messages to a single string, for debugging."""
    message_strings = []
    for message in messages:
        if isinstance(message, SystemMessage):
            message_strings.append(f"System - {message.content}")
        elif isinstance(message, HumanMessage):
            message_strings.append(f"Human - {message.content}")
        elif isinstance(message, AIMessage):
            message_strings.append(f"AI - {message.content}")
        else:
            raise ValueError(f"Unknown message type: {type(message)}")
    return "\n".join(message_strings)
