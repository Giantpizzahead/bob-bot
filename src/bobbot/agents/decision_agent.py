"""Agent that decides whether to send a message in Discord, given the recent chat history."""

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from bobbot.agents.llms import llm_gpt4omini_factual
from bobbot.utils import get_logger, log_debug_info

logger = get_logger(__name__)


async def decide_to_respond(msg_history: str, status: Optional[str] = None) -> tuple[bool, str]:
    """Decide whether to send a response message, given the current message history.

    Args:
        msg_history: The message history.
        status: Bob's current activity status.

    Returns:
        A tuple containing a boolean indicating whether to respond and the decision agent's thoughts.
    """
    status_addendum = (
        " You may also be given info about what you are currently doing, take this status into account (ex: If you're asleep, then you should never respond). "  # noqa: E501
        if status
        else ""
    )
    DECISION_PROMPT = f"""You are an expert decision maker named Bob chatting in a private Discord server. You are a rising junior majoring in CS at MIT and a witty gamer. There are other users too. Your goal is to decide whether or not to send a message in the server, given the chat history. Follow these examples:

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

Here is the message history of the server, including the most recent message. {status_addendum}Respond with brainstorming thoughts, followed by your answer of RESPOND or WAIT. Remember that if a user is directly addressing, pinging, or replying to you, or if a user sends a general message looking for someone to chat with or saying they're heading out, you should respond. For safety concerns or sensitive topics, you should respond instead of avoiding engagement. If you sent the most recent message, only send another to finish a thought or add important info. Keep thoughts concise.

You MUST follow the example response formats!"""  # noqa: E501
    messages = [SystemMessage(content=DECISION_PROMPT)]
    if not status:
        messages.append(HumanMessage(content=msg_history))
    else:
        messages.append(HumanMessage(content=f"Your status: {status}\n\nChat history:\n{msg_history}"))

    # log_debug_info(f"===== Decision agent status/history =====\n{messages[1].content}")
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
