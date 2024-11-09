"""Agent that comes up with a random answer/topic given a theme."""

import json
import random

from langchain_core.messages import HumanMessage, SystemMessage

from bobbot.agents.llms import llm_gpt4omini, llm_gpt4omini_random
from bobbot.utils import get_logger

logger = get_logger(__name__)

SEED_PROMPT = """You are a helpful AI assistant. You will be given a list of letters. Output uniformly random, unique words that start with each of the given letters.

## Example 1
Input: ['d', 'u', 'x']
Output: ["Destruction", "Upper", "Xander"]

## Example 2
Input: ['m', 'a']
Output: ["Map", "Adventurous"]

You must output only a Python list with the words you decide on. Each of your words MUST start with the corresponding letter. Do not output anything else."""  # noqa: E501


async def decide_seed() -> str:
    """Decide on a seed.

    Returns:
        The decided seed.
    """
    seed_letters = [random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(random.randint(3, 5))]
    messages = [SystemMessage(content=SEED_PROMPT), HumanMessage(content=str(seed_letters))]
    response = await llm_gpt4omini_random.ainvoke(messages)
    logger.info(f"[Seed] Seeds: {seed_letters} -> {response.content}")
    try:
        seeds = json.loads(response.content)
        if seeds is list:
            raise ValueError("Seeds must be a list")
        return " ".join(seeds)
    except Exception as e:
        logger.error(f"Error parsing seeds: {e}")
        return str(e)


VERIFY_TOPIC_PROMPT = """You are a helpful AI assistant. The user will provide you with a theme for a game of hangman, along with an potential answer. You must decide whether the answer matches the theme or not. Here are some examples:

## Example 1
Theme: champions in league of legends
Answer: zoe
Output: Yes

## Example 2
Theme: champions in league of legends
Answer: tranquil
Output: No

## Example 3
Theme: movie quotes
Answer: "Houston, we have a problem."
Output: Yes

## Example 4
Theme: household items that start with a 'l'
Answer: vaccum cleaner
Output: No

You must output only the word "Yes" or "No", depending on whether the answer matches the theme. Do not output anything else."""  # noqa: E501


async def verify_matching_topic(topic: str, theme: str) -> bool:
    """Verify that the topic matches the theme.

    Args:
        topic: The topic to verify.
        theme: The theme to verify against.

    Returns:
        True if the topic matches the theme, False otherwise.
    """
    messages = [
        SystemMessage(content=VERIFY_TOPIC_PROMPT),
        HumanMessage(content=f"Theme: {theme}\nAnswer: {topic}"),
    ]
    response = await llm_gpt4omini.ainvoke(messages)
    logger.info(f"[Verify] Theme: {theme}, Answer: {topic} -> {response.content}")
    return response.content.upper() == "YES"


TOPIC_PROMPT = """You are a helpful AI assistant. The user will provide you with a theme for a game of hangman, along with a context containing a few words. You should then choose a few words or phrases for the user to guess that match the theme. Match the creativity/rarity of chosen words/phrases to the given rarity. Chosen words/phrases should directly relate to the context. Here are some examples:

## Example 1
Context: Yarn Vital Flame Forest
Rarity: 9/10
Theme: champions in league of legends
Output: ["Smolder", "Swain", "Jarvan IV", "Nilah", "Fiddlesticks", "Nunu", "Vel'Koz"]

## Example 2
Context: Paradox Symphony Xenon Serenity Eclipse
Rarity: 2/10
Theme: champions in league of legends
Output: ["Miss Fortune", "Viego", "Ahri", "Brand", "Soraka", "Seraphine", "Nidalee", "Jhin", "Yuumi"]

## Example 3
Context: Hypothesis Orchard Apple Penguin Whirp
Rarity: 1/10
Theme: movie quotes
Output: ["Here's Johnny!", "Houston, we have a problem."]

## Example 4
Context: Radiant Oblivion Legacy
Rarity: 6/10
Theme: household items
Output: ["vaccum cleaner", "laptop", "screwdriver"]

You must output only a Python list with the words/phrases you decide on. You can output anywhere from 1 to 20 options - the more options you provide, the better. Your words/phrases MUST fit the provided theme. Do not output anything else."""  # noqa: E501


async def decide_topic(theme: str) -> str:
    """Decide on a topic given a theme.

    Args:
        theme: The theme to decide on.

    Returns:
        The decided topic.
    """
    try:
        seed = await decide_seed()
        # Do this twice, eliminating any options that show up too often
        topic_counts = {}
        for _ in range(2):
            rarity = random.randint(1, 10)
            # Decide on the answer
            messages = [
                SystemMessage(content=TOPIC_PROMPT),
                HumanMessage(content=f"Context: {seed}\nRarity: {rarity}/10\nTheme: {theme}"),
            ]
            response = await llm_gpt4omini_random.ainvoke(messages)
            logger.info(f"[Topic] Context: {seed}, Rarity: {rarity}/10, Theme: {theme}\n-> {response.content}")
            topics = json.loads(response.content)
            if not isinstance(topics, list):
                continue
            topics = [str(topic) for topic in topics]
            for topic in topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # Remove duplicated (common) topics
        min_count = min(topic_counts.values())
        topics = [topic for topic, count in topic_counts.items() if count <= min_count]
        logger.info(f"Candidate topics: {topics}")
        # Decide on a random matching topic
        random.shuffle(topics)
        for topic in topics[:3]:
            if await verify_matching_topic(str(topic), theme):
                return str(topic)
        # Just pick a random topic
        logger.warning("No matching topics found, picking a random topic")
        return topics[0]
    except Exception as e:
        logger.error(f"Error parsing topics: {e}")
        return str(e)
