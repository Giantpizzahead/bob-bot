"""Main runner for the bot."""

import os
import pprint
from pprint import pprint

from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from bobbot.agents.llms import llm_gpt4omini_factual


@tool(parse_docstring=True)
def do_calc(reasoning: str, a: int, b: int, c: int) -> None:
    """Do a calculation.

    Args:
        reasoning: Justification for why you chose valid numbers for a, b, and c.
        a: Must be an integer.
        b: Must be a divided by 3.
        c: Must be b divided by 2.
    """
    pass  # Result: 6, 3, 1, some bs reasoning


# @tool(parse_docstring=True)
# def do_calc(c: int, b: int, a: int, reasoning: str) -> None:
#     """Do a calculation.

#     Args:
#         c: Must be b divided by 2.
#         b: Must be a divided by 3.
#         a: Must be an integer.
#         reasoning: Justification for why you chose valid numbers for a, b, and c.
#     """
#     pass  # Result: 4, 6, 9, some bs reasoning


# messages = [
#     SystemMessage(
#         content="Call the given function with valid arguments. BUT DO NOT ACTUALLY CALL DO_CALC. Instead, outupt exactly what you would have outputted if you were to call the function, but don't call it."
#     ),
# ]
# llm_with_tools = llm_gpt4omini_factual.bind_tools([do_calc], tool_choice="any", strict=True)
# response = llm_with_tools.invoke(messages)

# # Process tool call(s)
# results = {}
# for tool_call in response.tool_calls:
#     print(tool_call)


messages = [
    SystemMessage(
        content="Please generate 3 numbers, a, b, and c. a must be an integer, b must be a divided by 3, and c must be b divided by 2. Provide a reasoning for why you chose the numbers you did."
    ),
]
response = llm_gpt4omini_factual.invoke(messages)
print(response)
