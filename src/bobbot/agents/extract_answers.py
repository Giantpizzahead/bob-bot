"""Agent that extracts answers to questions from a message history."""

from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from bobbot.agents.llms import llm_gpt4omini_factual
from bobbot.utils import get_logger, log_debug_info

logger = get_logger(__name__)

ANSWER_EXTRACTION_PROMPT = """You are an expert investigator named Bob chatting in a Discord server. Given the chat history and a list of waiting questions, determine if another user directly or completely answers any of your questions. If a question is directly answered, call `save_answer(question_num, answer)` with the corresponding question number and the user's answer. If the user only vaguely addresses a question and doesn't provide enough information to fully answer it, call `request_clarification(question_num, clarifying_command)` with the appropriate question number and a command in the 2nd person to clarify. If the user does not address any questions, call `do_nothing()` exactly one time.

### Examples

#### Example 1

Chat history:
Axoa1: bob let's play league!
bob: aight, what role do u want me to go
MagicJunk: idk, maybe mid? actually uhh

Question list:
1. Ask the user what you should eat for dinner.
2. Ask the user what role they want you to play in League of Legends.

Output: request_clarification(2, "Ask the user to confirm they want you to play mid.")

#### Example 2

Chat history:
bob: hmm i got a midterm tmrw, when should i sleep? would 3 am work :p
Axoa1: o shit u got a midterm? sameeeeee mine is at 8 pm too AHHHHHH :no_mouth:
Axoa1: ig try to sleep at 1 am ish, sleeping is more important than studying

Question list:
1. Ask the user what time you should sleep.
2. Ask the user what their favorite color is.

Output: save_answer(1, "around 1 am")

#### Example 3

Chat history:
Axoa1: so she asked the math question
bob: wait what champ should i play
Axoa1: and i was sure the answer was 42

Question list:
1. Ask the user what champion they want you to play in League of Legends.

Output: do_nothing()

Now, based on the provided chat history and question list, decide which action(s) to take.
"""  # noqa: E501


@tool(parse_docstring=True)
def save_answer(question_num: int, answer: str) -> None:
    """Save the user's answer to a question.

    Args:
        question_num: The question number that is being answered.
        answer: A concise version of the user's answer, without any extra info.
    """
    print(f"Saving answer for question {question_num}: {answer}")


@tool(parse_docstring=True)
def request_clarification(question_num: int, clarifying_command: str) -> None:
    """Request clarification for a user's partial answer to a question.

    Args:
        question_num: The question number that needs clarification.
        clarifying_command: The command to clarify the question directed at Bob.
    """
    print(f"Requesting clarification for question {question_num}: {clarifying_command}")


@tool(parse_docstring=True)
def do_nothing() -> None:
    """Indicate that no questions were answered."""
    print("No questions were answered.")


async def extract_answers(msg_history: str, questions: list[str]) -> dict[int, tuple[bool, str]]:
    """Extract answers to a list of questions from a message history.

    Args:
        msg_history: The message history.
        questions: The list of questions.

    Returns:
        A dictionary mapping question numbers to tuples. Each tuple contains a boolean indicating whether the
        question was answered (True) or needs clarification (False), and the answer or clarifying command.
    """
    numbered_questions = "\n".join([f"{i + 1}. {question}" for i, question in enumerate(questions)])
    messages = [
        SystemMessage(content=ANSWER_EXTRACTION_PROMPT),
        HumanMessage(content=f"Chat history:\n{msg_history}\n\nQuestion list:\n{numbered_questions}"),
    ]
    log_debug_info(f"===== Answer extraction history =====\n{msg_history}")
    log_debug_info(f"===== Answer extraction questions =====\n{numbered_questions}")
    llm_with_tools = llm_gpt4omini_factual.bind_tools(
        [save_answer, request_clarification, do_nothing], tool_choice="any", strict=True
    )
    response = await llm_with_tools.ainvoke(messages)

    # Process tool call(s)
    results = {}
    for tool_call in response.tool_calls:
        if tool_call["name"] == "save_answer":
            question_num = tool_call["args"]["question_num"]
            answer = tool_call["args"]["answer"]
            results[question_num] = (True, answer)
        elif tool_call["name"] == "request_clarification":
            question_num = tool_call["args"]["question_num"]
            clarifying_command = tool_call["args"]["clarifying_command"]
            results[question_num] = (False, clarifying_command)
    log_debug_info(f"===== Answer extraction results =====\n{results}")
    return results


# # TODO: Add tests for agents
# async def test_extract_answers():
#     print(
#         await extract_answers(
#             "bob: so who is AlexiKeys irl\nAxoa1: shes alex\nAxoa1: i like her ;)",
#             ["Ask the user what game they want to play.", "Ask the user who AlexiKeys is in real life."],
#         )
#     )
# import asyncio
# asyncio.run(test_extract_answers())
