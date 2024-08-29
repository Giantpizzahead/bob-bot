"""Agent that decides what messages to send in Discord."""

import os
from datetime import datetime
from typing import Optional

import pytz
from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from openai import OpenAI

from bobbot.utils import get_logger, log_debug_info

logger = get_logger(__name__)

# Setup OpenAI LLMs
openai_key: Optional[str] = os.getenv("OPENAI_KEY")
if openai_key is None:
    raise ValueError("OPENAI_KEY environment variable is not set.")
openai_client = OpenAI(api_key=openai_key)
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
    for raw_tool_call in response.tool_calls:
        tool_call = raw_tool_call
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


DECISION_PROMPT = """You are an expert decision maker named Bob chatting in a private Discord server. You are a rising junior majoring in CS at MIT and a witty gamer. There are other users too. Your goal is to decide whether or not to send a message in the server, given the chat history. Follow this example:

Example chat history 1:
[2 minutes ago] AlexiKeys: yooo @bob
[Recent] bob: yo wuts up
[Recent, deleted] Donahue4: bob whats 9+10
[Recent] bob: 21
[Recent] bob: ur so original
[Now] Donahue4: who u talking to? :p

Example response format 1:
Thoughts: Donahue4 is asking me a question, so respond.
Answer: RESPOND

Example chat history 2:
[Recent] AlexiKeys: cute
[Recent] AlexiKeys: very cute
[Recent] Donahue4: ikr
[Now] AlexiKeys: wait do u have a ps5?

Example response format 2:
Thoughts: AlexiKeys and Donahue4 are chatting. Nothing relevant to add, so wait.
Answer: WAIT

Example chat history 3:
[Recent] Donahue4: hey bob wut games u play?
[Now] bob: league and val

Example response format 3:
Thoughts: I just finished responding to Donahue4 with the games I play. Nothing important to add, so wait.
Answer: WAIT

Here is the message history of the server, including the most recent message. You'll also be given info about what you are currently doing, take this status into account (ex: If you're asleep, then you should never respond). Respond with brainstorming thoughts, followed by your answer of RESPOND or WAIT. Remember that if a user is directly addressing, pinging, or replying to you, or if a user sends a general message looking for someone to chat with or saying they're heading out, you should respond. For safety concerns or sensitive topics, you should respond instead of avoiding engagement. If you sent the most recent message, only send another to finish a thought or add important info. Keep thoughts concise.

You MUST follow the example response formats!"""  # noqa: E501


async def decide_to_respond(msg_history: str, status: Optional[str] = None) -> tuple[bool, str]:
    """Decide whether to send a response message, given the current message history.

    Args:
        msg_history: The message history.
        status: Bob's current activity status.

    Returns:
        A tuple containing a boolean indicating whether to respond and the decision agent's thoughts.
    """
    messages = [SystemMessage(content=DECISION_PROMPT)]
    if not status:
        messages.append(HumanMessage(content=msg_history))
    else:
        messages.append(HumanMessage(content=f"Your status: {status}\n\nChat history:\n{msg_history}"))

    log_debug_info(f"===== Decision agent status/history =====\n{messages[1].content}")
    response = await llm_gpt4omini_factual.ainvoke(messages)
    content = response.content
    log_debug_info(f"===== Decision agent response =====\n{content}")
    # Get the LLM's thoughts only
    first_index = content.find("Thoughts:")
    last_index = content.rfind("Answer:")
    if first_index != -1 and last_index != -1:
        thoughts = content[first_index + 10 : last_index - 1].strip()
    else:
        logger.warning("Decision agent did not output thoughts/answer in the requested format.")
        thoughts = content
    # Get the decision
    if "RESPOND" in content:
        return True, thoughts
    elif "WAIT" in content:
        return False, thoughts
    logger.warning("Decision agent did not output a valid response - defaulting to True.")
    return True, thoughts


async def check_openai_safety(msg_history: str) -> bool:
    """Determine whether the message history would be handled well by OpenAI's models.

    Uses OpenAI's moderation API. Messages containing self-harm related content should be treated seriously.
    Serious threats toward a person or group of people should also be treated seriously.
    However, other NSFW messages should not be censored, and therefore should not be handled by OpenAI.

    Args:
        msg_history: The message history to check.

    Returns:
        Whether the message history would be handled well by OpenAI's models.
    """
    response = openai_client.moderations.create(input=msg_history)
    categories = response.results[0].categories  # https://platform.openai.com/docs/api-reference/moderations/object
    true_categories: list[str] = [category for category, is_true in vars(categories).items() if is_true]
    log_debug_info(f"===== Check OpenAI safety =====\nFlagged: {true_categories}")
    if (
        categories.self_harm
        or categories.self_harm_instructions
        or categories.self_harm_intent
        or categories.hate_threatening
        or categories.harassment_threatening
        or categories.violence
        or categories.violence_graphic
    ):
        return True
    elif categories.sexual or categories.hate:
        return False
    return True
