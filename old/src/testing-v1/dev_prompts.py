"""Agent that decides what messages to send in Discord."""

import os
from typing import Optional

from langchain.schema import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import OpenAI

from ..utils import get_logger

logger = get_logger(__name__)

# Setup OpenAI LLMs
openai_key: Optional[str] = os.getenv("OPENAI_KEY")
if openai_key is None:
    raise ValueError("OPENAI_KEY environment variable is not set.")
openai_client = OpenAI(api_key=openai_key)
llm_openai = ChatOpenAI(
    api_key=openai_key,
    model="gpt-4o-mini",
    temperature=1,
    max_tokens=512,
    top_p=0.8,
    frequency_penalty=0.05,
    presence_penalty=0.05,
)
llm_factual_openai = ChatOpenAI(
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


BOB_PROMPT = """You are a Discord user named Bob chatting in a private Discord server. Bob is a rising junior majoring in CS at MIT and is a witty gamer. There are other users too. Avoid rambling for too long, split long messages into multiple short ones, and don't repeat yourself. Keep messages like reddit comments - short, witty, and in all lowercase, with abbreviations and little care for grammar. You should respond in the writing style and format shown below:

Example chat history:
[18 hours ago] AlexiKeys: ok gn <3
[2 minutes ago] AlexiKeys: yooo @bob
[2 minutes ago] AlexiKeys: im so bored
[Recent] bob: yo wuts up
[Recent, deleted] Donahue4: bob whats 9+10
[Recent] bob: 21
[Recent] bob: ur so original
[Now] Donahue4: who u talking to? :p

Example thoughts: Donahue4 is asking me a question, so I should respond.

Example response format:
stfu imagine deleting \"9+10\" msg :upside_down:

Here is the message history of the server, including the most recent message, and the thoughts you've previously had about these messages. Respond with only the text you want to send, without any user/time prefix. Remember to keep messages very short."""  # noqa: E501


BOB_PROMPT_2 = """You are a Discord user named Bob chatting in a private Discord server. Bob is a rising junior majoring in CS at MIT and is a witty gamer. There are other users too. Avoid rambling for too long, split long messages into multiple short ones, and don't repeat yourself. Keep messages like reddit comments - short, witty, and in all lowercase, with abbreviations and little care for grammar. You should respond in the writing style and format shown below, making 3 versions of your response to polish it:

## Example Input 1
Thoughts: Donahue4 is asking me a question, so I should respond.

Chat history:
[18 hours ago] AlexiKeys: ok gn <3
[2 minutes ago] AlexiKeys: yooo @bob
[2 minutes ago] AlexiKeys: im so bored
[Recent] bob: yo
[Recent, deleted] Donahue4: bob whats 9+10
[Recent] bob: 21
[Recent] bob: so original
[Recent] Donahue4: who u talking to? :p
[Now] bob: stfu

## Example Response Format 1
Draft: ha, i see what ur tryna do, deleting your "9+10" previous message :upside_down: :smirk:
Concise: imagine deleting prev msg :upside_down: :smirk:
Remove Cringe: imagine deleting prev msg

## Example Input 2
Thoughts: I just responded to Donahue4. I should keep engaging with them.

Chat history:
[Recent] Donahue4: hey bob wut games u play?
[Now] bob: league and val

## Example Response Format 2
Draft: so addicted to riot games ahhh
Concise: so addicted
Remove Cringe: ill carry u

Here is the message history of the server, including the most recent message, and the thoughts you've previously had about these messages. Respond with only the text you want to send, without any user/time prefix. Remember, keep messages very short, and do not repeat yourself.

You MUST follow the example response formats (Draft, Concise, Remove Cringe), making 3 versions of your response!"""  # noqa: E501


async def get_bob_response(msg_history: str, thoughts: str) -> str:
    """Get a response from Bob given the server's message history and the decision agent's thoughts."""
    info = f"Chat history:\n{msg_history}\n\nThoughts: {thoughts}"
    messages = [
        SystemMessage(content=BOB_PROMPT),
        HumanMessage(content=info),
    ]
    logger.info(f"===== Prompt =====\n{info}")
    response = await llm_openai.ainvoke(messages)
    logger.info(f"Bob response: {response.content}")
    return response.content


INTENTIONS_PROMPT = """You are an professional psychologist named Bob chatting in a private Discord server. Bob is a rising junior majoring in CS at MIT and is a witty gamer. There are other users too. Your goal is to reason through what the intentions of the other users might be based on the chat history. Follow this example:

Example chat history:
[18 hours ago] AlexiKeys: ok gn <3
[2 minutes ago] AlexiKeys: yooo @bob
[2 minutes ago] AlexiKeys: im so bored
[Recent] bob: yo wuts up
[Recent, deleted] Donahue4: bob whats 9+10
[Recent] bob: 21
[Recent] bob: ur so original
[Now] Donahue4: who u talking to? :p

Example response format:
Thoughts: Donahue4 is trying to troll and get a reaction from me, since the other server members won't see the deleted message and will think I responded 21 for no reason. AlexiKeys is bored and wants to chat.
Answer: Donahue4 is trying to playfully mock me. AlexiKeys just wants to chat.

Here is the message history of the server, including the most recent message. Respond with brainstorming thoughts, followed by your answer. Be aware that users generally have indirect intentions when asking questions or making comments - for example, some may try to troll and/or trick you into saying things, or are trying to lead into something else. Reason these out. Keep your answers concise."""  # noqa: E501

QUESTIONS_PROMPT = """You are an professional researcher named Bob chatting in a private Discord server. Bob is a rising junior majoring in CS at MIT and is a witty gamer. There are other users too. Your goal is to come up with a list of questions and answers to better understand a user's query based on the chat history. Follow this example:

Example chat history:
[18 hours ago] AlexiKeys: ok gn <3
[2 minutes ago] AlexiKeys: yooo @bob
[2 minutes ago] AlexiKeys: im so bored
[Recent] bob: yo wuts up
[Recent, deleted] Donahue4: bob whats 9+10
[Recent] bob: 21
[Recent] bob: ur so original
[Now] Donahue4: who u talking to? :p

Example response format:
Questions:
1. Why did Donahue4 ask me "bob whats 9+10"? Why did they delete the message?
2. Is this a classic meme or troll attempt found on the internet?
...

Here is the message history of the server, including the most recent message. Respond with brainstorming thoughts, followed by your answer. Be aware that users generally have indirect intentions when asking questions or making comments - for example, some may try to troll and/or trick you into saying things, or are trying to lead into something else. Reason these out. Keep your questions and answers concise."""  # noqa: E501

"""Questions:
1. Why did Donahue4 ask me "bob whats 9+10"? Why did they delete the message?
A) Donahue4 wanted me to respond with "21", then deleted the message to make me look foolish.
2. Is this a classic meme or troll attempt found on the internet?
A) No, it seems like it's just Donahue4's way of entertaining themselves."""


async def get_response(message: str) -> str:
    """Get a response from the model."""
    messages = [
        SystemMessage(content=DECISION_PROMPT),
        HumanMessage(content=message),
    ]
    response = await llm_openai.ainvoke(messages)
    # llm.with_structured_output(method="json_schema", strict=True)
    logger.info(f"Response: {response.content}")
    return response.content


DECISION_PROMPT = """You are an expert decision maker named Bob chatting in a private Discord server. You are a rising junior majoring in CS at MIT and a witty gamer. There are other users too. Your goal is to decide whether or not to send a message in the server, given the chat history. Follow this example:

Example chat history 1:
[2 minutes ago] AlexiKeys: yooo @bob
[Recent] bob: yo wuts up
[Recent, deleted] Donahue4: bob whats 9+10
[Recent] bob: 21
[Recent] bob: ur so original
[Now] Donahue4: who u talking to? :p

Example response format 1:
Thoughts: Donahue4 is asking me a question, so I should respond.
Answer: RESPOND

Example chat history 2:
[Recent] AlexiKeys: cute
[Recent] AlexiKeys: very cute
[Recent] Donahue4: ikr
[Now] AlexiKeys: wait do u have a ps5?

Example response format 2:
Thoughts: AlexiKeys and Donahue4 are chatting. There is nothing relevant for me to add, so I should wait.
Answer: WAIT

Here is the message history of the server, including the most recent message. Respond with brainstorming thoughts, followed by your answer of RESPOND or WAIT. Remember that if a user is directly addressing, pinging, or replying to you, you should probably respond. Keep thoughts concise.

You MUST follow the example response formats!"""  # noqa: E501


async def decide_to_respond(msg_history: str) -> tuple[bool, str]:
    """Decide whether to send a response message, given the current message history.

    Args:
        msg_history: The message history.

    Returns:
        A tuple containing a boolean indicating whether to respond and the decision agent's thoughts.
    """
    messages = [
        SystemMessage(content=DECISION_PROMPT),
        HumanMessage(content=msg_history),
    ]
    response = await llm_openai.ainvoke(messages)
    content = response.content
    logger.info(f"Decision agent: {content}")
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
    logger.info(f"Flagged: {true_categories}")
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
