"""Play a game of hangman."""

import asyncio
import math
import random
import time
from typing import Callable, Optional

from bobbot.agents import decide_topics
from bobbot.utils import get_logger

logger = get_logger(__name__)

status = "idle"
stop_event: Optional[asyncio.Event] = asyncio.Event()
sleep_event: Optional[asyncio.Event] = asyncio.Event()
cmd_handler: Optional[Callable] = None

# Hangman variables
theme = "N/A"
answer = "N/A"
mode = "hangman"
is_revealed = []
correct_guesses = []
wrong_guesses = []
is_on_full_guess = False
last_guess_time: float = 0
num_rounds: int = 0
curr_round: int = 0
num_lives: int = 0
MAX_WRONG_GUESSES = 10
TIME_BETWEEN_COMMENTS = 5
TIMED_TIME_PER_ANSWER = 30
TIMED_NUM_ROUNDS = 20
TIMED_NUM_LIVES = 3


def display_board() -> str:
    """Returns a string representation of the hangman board."""
    if mode == "hangman":
        return f"""```Theme: {theme}
Correct:      {", ".join(correct_guesses)}
Wrong ({len(wrong_guesses)}/{MAX_WRONG_GUESSES}): {", ".join(wrong_guesses)}

{"".join([answer[i] if is_revealed[i] else "_" for i in range(len(answer))])}```"""
    elif mode == "timed":
        return f"""```Theme: {theme}
Lives: {' '.join(['♡'] * num_lives)}
Round: {curr_round}/{num_rounds}

{"".join([answer[i] if is_revealed[i] else "_" for i in range(len(answer))])}```"""
    else:
        return f"Error: Invalid mode {mode}"


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
    global stop_event, sleep_event
    stop_event = asyncio.Event()
    sleep_event = asyncio.Event()
    try:
        await asyncio.wait_for(sleep_event.wait(), timeout=delay)
        return False
    except asyncio.TimeoutError:
        return True


def stop_hangman() -> None:
    """Stops playing hangman."""
    global status
    status = "idle"
    stop_event.set()
    sleep_event.set()


async def play_hangman() -> None:
    """Plays a game of hangman."""
    # Setup round
    global answer, is_revealed, correct_guesses, wrong_guesses, is_on_full_guess, last_guess_time
    answer = (await decide_topics(theme, 10))[0]
    is_revealed = [not answer[i].isalpha() for i in range(len(answer))]
    correct_guesses = []
    wrong_guesses = []
    is_on_full_guess = False
    last_guess_time = time.time()

    # Start game
    logger.info(f"Hangman answer: {answer}")
    await cmd_handler(display_board(), output_directly=True)
    await cmd_handler(
        "Briefly instruct the user to message a single letter to guess it, to message 'guess' to guess the solution, and to message 'help' for other shortcuts. Do NOT try to print the hangman board again. Do NOT mention their username."  # noqa: E501
    )
    await sleep_interruptable(1 * 60 * 60)  # Play for a maximum of 1 hour


async def guess_hangman(message: str) -> None:
    """Handles a guess during a hangman game."""
    global is_on_full_guess, is_revealed, last_guess_time
    guess_duration = time.time() - last_guess_time
    last_guess_time = time.time()
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
            "Tell the user they canceled their full guess, and can now guess letters again. Do NOT mention their username."  # noqa: E501
        )
        is_on_full_guess = False  # Must've been an accident
        return

    if message.upper() == "GUESS" and not is_on_full_guess:
        is_on_full_guess = True
        await cmd_handler(
            "Tell the user to send a message with what they think the answer is, or 'cancel' to go back to guessing individual letters, and that their guess must match the answer exactly to count. Do NOT mention their username."  # noqa: E501
        )
        return None
    elif message.upper() == "HELP" and not is_on_full_guess:
        await cmd_handler(
            "Tell the user they can message 'guess' to guess the full word, 'vowels' to guess all vowels, or 'rstlne' to guess those letters."  # noqa: E501
        )
        return None
    elif message.upper() == "VOWELS" and not is_on_full_guess:
        num_matches = 0
        for c in "AEIOU":
            if c.upper() in correct_guesses or c.upper() in wrong_guesses:
                continue
            num_matches += guess_character(c)
    elif message.upper() == "RSTLNE" and not is_on_full_guess:
        num_matches = 0
        for c in "RSTLNE":
            if c.upper() in correct_guesses or c.upper() in wrong_guesses:
                continue
            num_matches += guess_character(c)
    elif len(message) != 1 or not message.isalpha():
        if guess_duration > TIME_BETWEEN_COMMENTS:
            await cmd_handler(
                "If relevant, remind the user they can only guess a single letter or message 'guess' to guess the full answer. Do NOT mention their username."  # noqa: E501
            )
        return None

    if message.upper() in correct_guesses or message.upper() in wrong_guesses:
        if guess_duration > TIME_BETWEEN_COMMENTS:
            await cmd_handler(
                f"Tell the user they have already guessed the letter '{message}'. Do NOT mention their username."
            )
        return None

    if len(message) == 1:
        num_matches = guess_character(message.upper())
    await cmd_handler(display_board(), output_directly=True)
    if all(is_revealed):
        await cmd_handler("Tell the user that they won!")
        stop_hangman()
        return None
    elif len(wrong_guesses) >= MAX_WRONG_GUESSES:
        is_revealed = [True] * len(answer)
        await cmd_handler(display_board(), output_directly=True)
        await cmd_handler("Tell the user that they lost (too many wrong guesses) and comment on the revealed answer.")
        stop_hangman()
        return None
    elif guess_duration > TIME_BETWEEN_COMMENTS:
        await cmd_handler(
            f"Make a *very* short comment on the game of hangman. The user just guessed '{message.upper()}', and there were {num_matches} matches in the answer. Do NOT try to print the hangman board again. Do NOT mention their username."  # noqa: E501
        )


async def play_timed() -> None:
    """Plays a game of timed hangman."""
    # Get answers
    answers = await decide_topics(theme, TIMED_NUM_ROUNDS)

    global answer, is_revealed, num_rounds, curr_round, num_lives, is_on_full_guess
    num_rounds = len(answers)
    num_lives = TIMED_NUM_LIVES
    for i in range(num_rounds):
        # Setup round
        curr_round = i + 1
        answer = answers[i]
        # Reveal part of the answer (less for future rounds)
        is_on_full_guess = False
        is_revealed = [not answer[i].isalpha() for i in range(len(answer))]
        unrevealed_locs = [i for i in range(len(answer)) if not is_revealed[i]]
        random.shuffle(unrevealed_locs)
        percent_to_reveal = 0.7 - 0.5 * curr_round / num_rounds
        percent_to_reveal -= (
            0.3 * num_lives / TIMED_NUM_LIVES * curr_round / num_rounds
        )  # Make it gradually harder with more lives
        percent_to_reveal += 0.3 * (TIMED_NUM_LIVES - num_lives) / TIMED_NUM_LIVES  # Make it easier with lost lives
        percent_to_reveal = min(0.9, max(0.1, percent_to_reveal))
        # await cmd_handler(f"Percent revealed: {round(percent_to_reveal * 100, 1)}%", output_directly=True)
        logger.info(f"Hangman percent revealed: {round(percent_to_reveal * 100, 1)}%")
        num_to_reveal = min(len(unrevealed_locs) - 1, math.ceil(percent_to_reveal * len(unrevealed_locs)))
        for j in range(num_to_reveal):
            is_revealed[unrevealed_locs[j]] = True

        # Start game
        print(f"Hangman answer: {answer}")
        await cmd_handler(display_board(), output_directly=True)

        # Explain rules on the first round
        if curr_round == 1:
            await cmd_handler(
                f"Tell the user they need to guess the words/phrases correctly to win. Tell them they have {TIMED_TIME_PER_ANSWER} seconds to guess each one, and must message the exact answer for it to count. Do NOT try to reprint the clues you've already given. Do NOT mention their username."  # noqa: E501
            )

        # Run a timer
        await sleep_interruptable(1)
        if not sleep_event.is_set():
            await sleep_interruptable(TIMED_TIME_PER_ANSWER / 2)
            time_left = TIMED_TIME_PER_ANSWER - TIMED_TIME_PER_ANSWER / 2
        if not sleep_event.is_set():
            await cmd_handler(f"{round(time_left)} seconds left!", output_directly=True)
            await sleep_interruptable(time_left - 3)
        if not sleep_event.is_set():
            await cmd_handler("3...", output_directly=True)
            await sleep_interruptable(1.5)
        if not sleep_event.is_set():
            await cmd_handler("2...", output_directly=True)
            await sleep_interruptable(1.5)
        if not sleep_event.is_set():
            await cmd_handler("1...", output_directly=True)
            await sleep_interruptable(2)

        if stop_event.is_set():
            # Quit
            return
        if not is_on_full_guess:
            # Ran out of time
            num_lives -= 1
            if num_lives == 0:
                await cmd_handler(
                    f"Tell the user that they lost (ran out of time). They made it to round {curr_round} out of {num_rounds}. Echo that the answer was **{answer}** and comment on it."  # noqa: E501
                )
                stop_hangman()
                return
            else:
                await cmd_handler(
                    f"Tell the user that they ran out of time, and that they have {num_lives} lives left. Echo that the answer was **{answer}** and comment on it."  # noqa: E501
                )

    # Got through all rounds
    await cmd_handler(f"Congratulate the user on making it through all {num_rounds} rounds!")
    stop_hangman()


async def guess_timed(message: str) -> None:
    """Handles a guess during a timed hangman game."""
    # Check for correct guess
    guess = message.upper()[: len(answer)]
    upper_answer = answer.upper()
    if guess == upper_answer:
        global is_on_full_guess
        is_on_full_guess = True
        sleep_event.set()  # Signal a correct guess
        await cmd_handler(
            "Tell the user that they got it right and comment on the answer. This should be a brief comment, don't output anything else. Do NOT try to print another hangman board."  # noqa: E501
        )
        return

    # Check for one letter off
    if (
        len(guess) == len(upper_answer)
        and sum([guess[i] == upper_answer[i] for i in range(len(answer))]) == len(answer) - 1
    ):  # noqa: E501
        await cmd_handler("Tell the user that their guess is only 1 letter off.")  # noqa: E501
        return

    # Wrong guess, send a response
    responses = [
        "nope!",
        "try again.",
        "wrong!",
        "not it.",
        "guess again.",
        "nope.",
        "keep trying!",
        "not quite.",
        "sorry, no.",
        "incorrect.",
        "nah.",
        "oops!",
        "nope, not it.",
        "wrong guess!",
        "negative.",
        "not this time.",
        "guess better!",
        "wrong again.",
        "no, try harder.",
        "not even close.",
        "no way!",
        "are u even trying?",
        "bro come on...",
    ]
    await cmd_handler(random.choice(responses), output_directly=True)


async def hangman_activity(new_cmd_handler: Callable) -> None:
    """Starts a game of hangman."""
    global status, cmd_handler, mode
    try:
        cmd_handler = new_cmd_handler
        if status != "idle":
            await cmd_handler("Echo this to the user. Failed to start: You are already playing hangman.")
            return
        status = "playing"
        if mode == "hangman":
            await play_hangman()
        elif mode == "timed":
            await play_timed()
        else:
            await cmd_handler(f"Echo this to the user. Failed to start: Invalid mode {mode}.")
        status = "idle"
    except Exception as e:
        await cmd_handler(f"Tell the user that this error occurred: {e}")
        stop_hangman()


async def hangman_on_message(message: str) -> Optional[str]:
    """Handles a message during a hangman game."""
    if mode == "hangman":
        return await guess_hangman(message)
    elif mode == "timed":
        return await guess_timed(message)
    else:
        return None


def configure_hangman(new_theme: str, timed: bool = False) -> None:
    """Configures the hangman game."""
    global status, theme, mode
    if status != "idle":
        return  # Can't configure while playing
    theme = new_theme
    mode = "hangman" if not timed else "timed"


def get_hangman_info() -> str:
    """Returns the current hangman status."""
    if status == "idle":
        return "You are not currently playing hangman."
    return "You are currently playing hangman."
