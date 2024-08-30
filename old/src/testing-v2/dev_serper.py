"""Main runner for the bot."""

import os
import pprint
from pprint import pprint

from dotenv import load_dotenv
from langchain.tools import Tool, tool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from bobbot.agents.llms import llm_gpt4omini_factual

load_dotenv()


def parse_results(results: dict) -> str:
    snippets = []
    if results.get("answerBox"):
        answer_box = results.get("answerBox", {})
        if answer_box.get("answer"):
            return [answer_box.get("answer")]
        elif answer_box.get("snippet"):
            return [answer_box.get("snippet").replace("\n", " ")]
        elif answer_box.get("snippetHighlighted"):
            return answer_box.get("snippetHighlighted")

    if results.get("knowledgeGraph"):
        kg = results.get("knowledgeGraph", {})
        title = kg.get("title")
        entity_type = kg.get("type")
        if entity_type:
            snippets.append(f"{title}: {entity_type}.")
        description = kg.get("description")
        if description:
            snippets.append(description)
        for attribute, value in kg.get("attributes", {}).items():
            snippets.append(f"{title} {attribute}: {value}.")

    # for result in results[self.result_key_for_type[self.type]][: self.k]:
    #     if "snippet" in result:
    #         snippets.append(result["snippet"])
    #     for attribute, value in result.get("attributes", {}).items():
    #         snippets.append(f"{attribute}: {value}.")

    if len(snippets) == 0:
        return ["No good Google Search Result was found"]
    return snippets


@tool(parse_docstring=True)
def perform_google_search(query: str) -> str:
    """Performs a Google search and returns the search results.

    Args:
        query: The query to search for.

    Returns:
        A structured string representation of the search results, including links, snippets, and titles.
    """
    search = GoogleSerperAPIWrapper()
    # TODO: Format results nicer
    # search._parse_snippets
    return search.results(query)
    # return str(search.results(query))


pprint(perform_google_search.args_schema.schema())

messages = [
    SystemMessage(content="Answer the given query, using tools if needed."),
    HumanMessage(content="How many league champs are there as of today (August 29, 2024)?"),
]

TOOLS = {
    "perform_google_search": perform_google_search,
}

llm_with_tools = llm_gpt4omini_factual.bind_tools([tool for tool in TOOLS.values()], strict=True)

# Self loop
for i in range(3):
    ai_message = llm_with_tools.invoke(messages)
    messages.append(ai_message)
    if ai_message.tool_calls:
        for tool_call in ai_message.tool_calls:
            tool: Tool = TOOLS[tool_call["name"]]
            print(f"Calling tool {tool_call['name']} with args {tool_call['args']}")
            result: ToolMessage = tool.invoke(tool_call)
            print(f"Result: {result}")
            result.artifact = result.content
            result.content = "168"
            messages.append(result)
    else:
        break

# Output response
print(messages)
response = ai_message.content if ai_message.content.strip() else "Unable to answer within 7 iterations D:"
print(response)
