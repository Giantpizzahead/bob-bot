"""Agent that checks if a message is appropriate for OpenAI's models or not."""

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from bobbot.agents.llms import llm_gpt4omini_factual, openai_client
from bobbot.utils import get_logger, log_debug_info

logger = get_logger(__name__)


async def check_openai_safety(msg_history: str) -> Optional[bool]:
    """Determine whether the message history would be handled well by OpenAI's models.

    Uses OpenAI's moderation API and an LLM.
    Messages containing self-harm related content should be treated seriously.
    Serious threats toward a person or group of people should also be treated seriously.
    However, other NSFW messages should not be censored, and therefore should not be handled by OpenAI.

    Args:
        msg_history: The message history to check.

    Returns:
        Whether OpenAI's models would handle these messages well.
    """
    # Preliminary check with OpenAI's moderation API
    response = openai_client.moderations.create(input=msg_history)
    categories = response.results[0].categories  # https://platform.openai.com/docs/api-reference/moderations/object
    true_categories: list[str] = [category for category, is_true in vars(categories).items() if is_true]
    log_debug_info(f"===== Safety agent moderations =====\nFlagged: {true_categories}")
    if (
        categories.self_harm
        or categories.self_harm_instructions
        or categories.self_harm_intent
        or categories.hate_threatening
        or categories.harassment_threatening
        or categories.violence
        or categories.violence_graphic
    ):
        return True  # Handle these seriously
    elif categories.sexual or categories.hate:
        return False  # Don't handle these

    # Precise check with LLM (to find cases like cheating on an exam)
    SAFETY_PROMPT = """You are an expert decision maker named Bob chatting in a private Discord server. In this server, being toxic, edgy, using profanity, suggestive jokes, etc. is all acceptable. Your goal is to evaluate whether the most recent message in the chat history is appropriate.

1. For messages that are appropriate, respond with "ACCEPT". Most messages should be accepted.
2. For messages that are inappropriate, immoral, or violate ethical standards, respond with "REJECT".
3. For messages in a gray area, respond with "GRAY".

Here is the server's message history, including the most recent message. You MUST follow the response format of 'Thoughts:', followed by brainstorming thoughts, then 'Answer:', followed by the answer as one of ACCEPT, REJECT, or GRAY. Keep thoughts very concise."""  # noqa: E501"""

    messages = [SystemMessage(content=SAFETY_PROMPT), HumanMessage(content=msg_history)]

    # log_debug_info(f"===== Safety agent history =====\n{messages[1].content}")
    response = await llm_gpt4omini_factual.ainvoke(messages)
    content = response.content
    log_debug_info(f"===== Safety agent LLM response =====\n{content}")
    # Get the decision
    if "ACCEPT" in content:
        return True
    elif "GRAY" in content:
        return True
    elif "REJECT" in content:
        return False
    logger.warning("Decision agent did not output a valid response - defaulting to REJECT.")
    return True
