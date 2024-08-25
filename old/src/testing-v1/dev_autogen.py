"""
Example AutoGen usage.
See https://www.youtube.com/watch?v=JmjxwTEJSE8.
"""

import json
import os
import warnings
from typing import Annotated

warnings.filterwarnings("ignore", "Valid config keys have changed in V2.*")

from autogen import ConversableAgent
from dotenv import load_dotenv

load_dotenv()


def get_weather(location: Annotated[str, "The location to get the weather for"]) -> Annotated[str, "The weather"]:
    """Get the weather for a location.

    Args:
        location: The location to get the weather for.

    Returns:
        The weather for the location.
    """
    return f"The weather in {location} is sunny. The chance of rain is 10% today, 30% tomorrow, 60% on Friday, and 80% on Saturday. The high is 87 F and the low is 48 F. See the webpage link below for more information."


assistant = ConversableAgent(
    name="Bob",
    system_message="You are Bob, a Discord user, ready to help with a variety of tasks. Answer in one concise sentence. Return 'TERMINATE' when the task is done.",
    llm_config={
        "config_list": [
            {
                "model": "gpt-4o-mini",
                "api_key": os.getenv("OPENAI_KEY"),
            }
        ]
    },
)

user_proxy: ConversableAgent = ConversableAgent(
    name="User",
    is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"],
    human_input_mode="NEVER",
)

assistant.register_for_llm(name="get_weather", description="Get the weather for a location")(get_weather)
user_proxy.register_for_execution(name="get_weather")(get_weather)

user_proxy.initiate_chat(assistant, message="What is the weather in Sunnyvale?")

print(f"System message: {assistant.system_message}")
print(json.dumps(assistant.chat_messages_for_summary(user_proxy), indent=2))
