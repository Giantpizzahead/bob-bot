import os
import warnings

warnings.filterwarnings("ignore", "Valid config keys have changed in V2.*")

from crewai import Agent, Crew, Task
from dotenv import load_dotenv
from langchain.callbacks.base import BaseCallbackHandler
from langchain_openai import ChatOpenAI


class LoggingCallbackHandler(BaseCallbackHandler):
    """A custom callback handler that logs all interactions with the LLM."""

    def on_llm_start(self, serialized, prompts, **kwargs):
        formatted_prompts = "\n\n".join(prompts)
        print(f"========== LLM invoked ==========\n{formatted_prompts}")

    def on_llm_end(self, response, **kwargs):
        formatted_response = "\n\n".join([chunk.text for chunk in response.generations[0]])
        print(f"========== Response ==========\n{formatted_response}")

    def on_llm_error(self, error, **kwargs):
        print(f"[LLM Error] {error}")

    def on_chain_start(self, serialized, inputs, **kwargs):
        print(f"[Chain Start] Inputs:\n{inputs}")

    def on_chain_end(self, outputs, **kwargs):
        print(f"[Chain End] Outputs:\n{outputs}")

    def on_chain_error(self, error, **kwargs):
        print(f"[Chain Error] {error}")

    def on_tool_start(self, serialized, input_str, **kwargs):
        print(f"[Tool Start] Input:\n{input_str}")

    def on_tool_end(self, output, **kwargs):
        print(f"[Tool End] Output:\n{output}")

    def on_tool_error(self, error, **kwargs):
        print(f"[Tool Error] {error}")


# Load environment variables from .env file
load_dotenv()


llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_KEY"),
    model="gpt-4o-mini",
    temperature=1,
    max_tokens=256,
    top_p=1,
    frequency_penalty=0.05,
    presence_penalty=0.05,
    callbacks=[LoggingCallbackHandler()],
)

chat_parser = Agent(
    role="Discord Chat Parser Agent",
    goal="Summarize recent text messages while keeping them accurate and concise.",
    # verbose=True,
    backstory=("You are a Discord user named Bob chatting in a private Discord server."),
    llm=llm,
)

parser_task = Task(
    description=(
        "Get the gist of recent/new text messages, turning long texts into a more useable form.\n\nChat log:\n{chat_log}"
    ),
    expected_output=("A 1 sentence summary of the chat log."),
    agent=chat_parser,
)

crew = Crew(
    agents=[chat_parser],
    tasks=[parser_task],
    # verbose=True,
)

crew_inputs = {
    "chat_log": "pizza: hey bob, how are u?\nbob: i'm good, how about u?\npizza: i'm good too, thanks for asking!",
}

result = crew.kickoff(inputs=crew_inputs)
# print(result)
