"""Generic agents."""

from bobbot.agents.llms import openai_client
from bobbot.utils import get_logger, log_debug_info

logger = get_logger(__name__)


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
