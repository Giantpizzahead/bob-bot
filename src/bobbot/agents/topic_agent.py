"""Agent that comes up with a random answer/topic given a theme."""

import ast
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


FILTER_TOPIC_PROMPT = """You are a helpful AI assistant. The user will provide you with a theme for a game of hangman, along with a list of potential answers. You must decide whether each answer matches the theme or not. Here are some examples:

## Example 1
Theme: champions in league of legends
Answers: ['zoe', 'tranquil', 'LeBlanc', 'aatrox', 'Zoe', 'Symmetra']
Output: [True, False, True, True, True, False]

## Example 2
Theme: movie quotes
Answers: ["It's her sandwich.", 'Houston, we have a problem.', 'According to all known laws of aviation, there is no way a bee should be able to fly.']
Output: [False, True, True]

## Example 4
Theme: household items that start with a 'l'
Answer: ['vaccum cleaner', 'desk', 'laptop', 'lamp']
Output: [False, False, True, True]

You must output a Python list of booleans with the results, depending on whether each answer matches the theme. Do not output anything else."""  # noqa: E501


async def filter_topics(theme: str, topics: list[str]) -> list[str]:
    """Filter topics given a theme.

    Args:
        theme: The theme to verify.
        topics: The topics to verify.

    Returns:
        The topics that match the theme.
    """
    try:
        messages = [
            SystemMessage(content=FILTER_TOPIC_PROMPT),
            HumanMessage(content=f"Theme: {theme}\nAnswers: {topics}"),
        ]
        response = await llm_gpt4omini.ainvoke(messages)
        logger.info(f"[Filter] Theme: {theme}, Answers: {topics} -> {response.content}")
        results = ast.literal_eval(response.content)
        assert isinstance(results, list)
        assert len(results) <= len(topics)
        return [topics[i] for i, result in enumerate(results) if result]
    except Exception as e:
        logger.error(f"Error filtering topics: {e}")
        return [str(e)]


def get_topic_prompt(num_topics: int) -> str:
    """Gets the topic prompt, asking the LLM to generate up to `num_topics` options."""
    assert num_topics >= 1, "Need at least 1 topic"
    TOPIC_PROMPT = f"""You are a helpful AI assistant. The user will provide you with a theme for a game of hangman, along with a context containing a few words. You should then choose a few words or phrases for the user to guess that match the theme. Match the creativity/rarity of chosen words/phrases to the given rarity. Chosen words/phrases should directly relate to the context. Here are some examples:

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

You must output only a Python list with the words/phrases you decide on. You should output up to {num_topics} options - the more options you provide, the better. Your words/phrases MUST fit the provided theme. Do not output anything else."""  # noqa: E501
    return TOPIC_PROMPT


async def decide_topics(theme: str, num_topics: int) -> list[str]:
    """Decide on a list of topics given a theme.

    Args:
        theme: The theme to decide on.

    Returns:
        Up to `num_topics` decided topics (pre-filtered). May return less.
    """
    assert 1 <= num_topics <= 50, "Number of topics must be between 1 and 50"
    try:
        seed = await decide_seed()
        # Do this twice, eliminating any options that show up too often
        topic_counts = {}
        for _ in range(2):
            rarity = random.randint(1, 10)
            # Decide on the answers
            messages = [
                SystemMessage(content=get_topic_prompt(num_topics=num_topics)),
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

        # Decide on random verified topics (removing duplicates)
        topics = [topic for topic in topic_counts.keys()]
        logger.info(f"Candidate topics: {topics}")
        filtered_topics = await filter_topics(theme, topics)
        if not filtered_topics:
            logger.warning("No matching topics found, using unfiltered topics")
            filtered_topics = topics

        # Remove duplicated (common) topics
        # min_count = min(topic_counts.values())
        # topics = [topic for topic, count in topic_counts.items() if count <= min_count]
        random.shuffle(filtered_topics)
        return filtered_topics[:num_topics]
    except Exception as e:
        logger.error(f"Error parsing topics: {e}")
        return str(e)
