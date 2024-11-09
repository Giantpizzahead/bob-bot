"""Play a game of hangman."""

import asyncio
import random
from typing import Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from bobbot.agents.llms import llm_gpt4omini

status = "idle"
stop_event: Optional[asyncio.Event] = asyncio.Event()
cmd_handler: Optional[Callable] = None

# Hangman variables
theme = "N/A"
answer = "N/A"
is_revealed = []
correct_guesses = []
wrong_guesses = []
is_on_full_guess = False
MAX_WRONG_GUESSES = 11


def display_board() -> str:
    """Returns a string representation of the hangman board."""
    return f"""Theme: {theme}
Correct guesses: {", ".join(correct_guesses)}
Wrong guesses ({len(wrong_guesses)}/{MAX_WRONG_GUESSES}): {", ".join(wrong_guesses)}

{" ".join([answer[i] if is_revealed[i] else "\\_" for i in range(len(answer))])}"""


def guess_character(c: str) -> int:
    """Make a single character guess, revealing characters that match and returning how many were matched.

    Assumes that c has not yet been guessed and is a valid uppercase letter.
    """
    global is_revealed
    num_matches = 0
    for i in range(len(answer)):
        if answer[i].upper() == c:
            num_matches += 1
            is_revealed[i] = True

    if num_matches == 0:
        wrong_guesses.append(c)
    else:
        correct_guesses.append(c)

    return num_matches


async def sleep_interruptable(delay: float) -> bool:
    """Sleeps for delay seconds. Returns False if the wait was interrupted."""
    global stop_event
    stop_event = asyncio.Event()
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=delay)
        return False
    except asyncio.TimeoutError:
        return True


def stop_hangman() -> None:
    """Stops playing hangman."""
    global status
    status = "idle"
    stop_event.set()


async def hangman_activity(new_cmd_handler: Callable) -> None:
    """Starts a game of hangman."""
    global status, cmd_handler
    try:
        cmd_handler = new_cmd_handler
        if status != "idle":
            await cmd_handler("Echo this to the user. Failed to start: You are already playing hangman.")
            return
        status = "playing"

        HANGMAN_PROMPT = """You are a helpful AI assistant. The user will provide you with a theme for a game of hangman. You should then choose a word or phrase for the user to guess that matches the theme. Try to choose a creative word/phrase. You will be given a seed to help with picking an answer. Here are some examples:

    ## Example 1
    Seed: 293847293
    Theme: league of legends champions
    Output: Zoe

    ## Example 2
    Seed: 1239182
    Theme: household items
    Output: vaccum cleaner

    ## Example 3
    Seed: 981274736
    Theme: movie quotes
    Output: May the force be with you.

    You must output only the word or phrase you decide on. Do not output anything else."""  # noqa: E501

        # Decide on the answer
        messages = [
            SystemMessage(content=HANGMAN_PROMPT),
            HumanMessage(content=f"Seed: {random.randint(0, 10 ** 9)}\nTheme: {theme}"),
        ]
        response = await llm_gpt4omini.ainvoke(messages)

        # Setup round
        global answer, is_revealed, correct_guesses, wrong_guesses, is_on_full_guess
        answer = response.content
        is_revealed = [not answer[i].isalpha() for i in range(len(answer))]
        correct_guesses = []
        wrong_guesses = []
        is_on_full_guess = False

        # Start game
        print(f"Hangman answer: {answer}")
        await cmd_handler(display_board(), output_directly=True)
        await cmd_handler(
            "Briefly instruct the user to message a single letter to guess it, and to message 'guess' to guess the solution. Do NOT try to print the hangman board again. Do NOT mention their username."  # noqa: E501
        )

        await sleep_interruptable(1 * 60 * 60)  # 1 hour
        status = "idle"
    except Exception as e:
        await cmd_handler(f"Tell the user that this error occurred: {e}")
        stop_hangman()


async def hangman_on_message(message: str) -> Optional[str]:
    """Handles a message during a hangman game."""
    global is_on_full_guess, is_revealed
    if len(message) != 1 and message.upper() != "CANCEL" and is_on_full_guess:
        # Check if the message is the answer
        if message.upper()[: len(answer)] == answer.upper():
            is_revealed = [True] * len(answer)
            await cmd_handler(display_board(), output_directly=True)
            await cmd_handler("Tell the user that they won!")
            stop_hangman()
            return
        else:
            wrong_guesses.append(f"'{message}'")
            await cmd_handler(display_board(), output_directly=True)
            await cmd_handler(
                "Tell the user that they guessed wrong and to keep trying. Do NOT mention their username."
            )
            is_on_full_guess = False
            return
    elif is_on_full_guess:
        await cmd_handler(
            "The user canceled their full guess. Tell the user that they can now guess letters again. Do NOT mention their username."  # noqa: E501
        )
        is_on_full_guess = False  # Must've been an accident
        return

    if message.upper() == "GUESS" and not is_on_full_guess:
        is_on_full_guess = True
        await cmd_handler(
            "Tell the user to send a message with what they think the answer is, or 'cancel' to go back to guessing individual letters, and that their guess must match the answer exactly to count. Do NOT mention their username."  # noqa: E501
        )
        return None
    elif len(message) != 1 or not message.isalpha():
        await cmd_handler("Tell the user they can only guess a single letter. Do NOT mention their username.")
        return None

    if message.upper() in correct_guesses or message.upper() in wrong_guesses:
        await cmd_handler(
            f"Tell the user they have already guessed the letter '{message}'. Do NOT mention their username."
        )
        return None

    num_matches = guess_character(message.upper())
    await cmd_handler(display_board(), output_directly=True)
    await cmd_handler(
        f"Make a *very* short comment on the game of hangman. The user just guessed '{message.upper()}', and there were {num_matches} matches in the answer. Do NOT try to print the hangman board again. Do NOT mention their username."  # noqa: E501
    )
    if all(is_revealed):
        await cmd_handler("Tell the user that they won!")
        stop_hangman()
        return None
    elif len(wrong_guesses) >= MAX_WRONG_GUESSES:
        is_revealed = [True] * len(answer)
        await cmd_handler(display_board(), output_directly=True)
        await cmd_handler("Tell the user that they lost and comment on the revealed answer.")
        stop_hangman()
        return None


def configure_hangman(new_theme: str) -> None:
    """Configures the hangman game."""
    global theme
    theme = new_theme


def get_hangman_info() -> str:
    """Returns the current hangman status."""
    if status == "idle":
        return "You are not currently playing hangman."
    return "You are currently playing hangman."
