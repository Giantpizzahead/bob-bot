"""Play a game of hangman."""

import asyncio
import math
import random
import time
from typing import Callable, Optional

import editdistance

from bobbot.agents import decide_topics, get_hint_for_topic
from bobbot.utils import get_logger

logger = get_logger(__name__)

status = "idle"
condition_signal = "N/A"
condition_var: Optional[asyncio.Condition] = asyncio.Condition()
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

hint: str = "N/A"
hint_prompt: Optional[str] = None
only_hint: bool = False
followup_hints: bool = False
hint_helpfulness: float = 1.0

MAX_WRONG_GUESSES = 10
TIME_BETWEEN_COMMENTS = 5
timed_time_per_answer = 30
TIMED_NUM_ROUNDS = 20
TIMED_NUM_LIVES = 3


def display_board() -> str:
    """Returns a string representation of the hangman board."""
    if mode == "hangman":
        if only_hint:
            return f"""\
```Theme: {theme}
Correct:      {", ".join(correct_guesses)}
Wrong ({len(wrong_guesses)}/{MAX_WRONG_GUESSES}): {", ".join(wrong_guesses)}

{"".join([answer[i] if is_revealed[i] else "" for i in range(len(answer))])}

Hint: {hint}```\
"""
        elif hint_prompt:
            return f"""\
```Theme: {theme}
Correct:      {", ".join(correct_guesses)}
Wrong ({len(wrong_guesses)}/{MAX_WRONG_GUESSES}): {", ".join(wrong_guesses)}

{"".join([answer[i] if is_revealed[i] else "_" for i in range(len(answer))])}

Hint: {hint}```\
"""
        else:
            return f"""\
```Theme: {theme}
Correct:      {", ".join(correct_guesses)}
Wrong ({len(wrong_guesses)}/{MAX_WRONG_GUESSES}): {", ".join(wrong_guesses)}

{"".join([answer[i] if is_revealed[i] else "_" for i in range(len(answer))])}```\
"""
    elif mode == "timed":
        #         return f"""```Theme: {theme}
        # Lives: {' '.join(['♡'] * num_lives)}
        # Round: {curr_round}/{num_rounds}

        # {"".join([answer[i] if is_revealed[i] else "_" for i in range(len(answer))])}```"""
        if only_hint:
            return f"""\
Theme: {theme}
Lives: {' '.join(['♡'] * num_lives)}
Round: {curr_round}/{num_rounds}

Hint: {hint}\
"""
        else:
            return f"""\
```Theme: {theme}
Lives: {' '.join(['♡'] * num_lives)}
Round: {curr_round}/{num_rounds}

{"".join([answer[i] if is_revealed[i] else "_" for i in range(len(answer))])}

Hint: {hint}```\
"""
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


def check_guess_distance(guess: str) -> int:
    """Check how many edits the guess is away from the answer, allowing one typo for longer guesses."""
    # Cut off the suffix
    guess = guess.upper()[: len(answer)]
    upper_answer = answer.upper()
    # Remove non-letters
    guess = "".join([c for c in guess if c.isalpha()])
    upper_answer = "".join([c for c in upper_answer if c.isalpha()])
    # Calculate distance
    return editdistance.eval(guess, upper_answer)


async def sleep_interruptable(delay: float) -> bool:
    """Sleeps for delay seconds. Returns False if the wait was interrupted."""
    global condition_signal
    async with condition_var:
        if condition_signal != "N/A":
            return False
        try:
            await asyncio.wait_for(condition_var.wait(), timeout=delay)
            return False
        except asyncio.TimeoutError:
            return True


async def stop_hangman() -> None:
    """Stops playing hangman."""
    global status, condition_signal
    status = "idle"
    async with condition_var:
        condition_signal = "stop"
        condition_var.notify()


async def play_hangman() -> None:
    """Plays a game of hangman."""
    # Setup round
    global answer, is_revealed, correct_guesses, wrong_guesses, is_on_full_guess, last_guess_time, hint
    answer = (await decide_topics(theme, 10))[0]
    is_revealed = [not answer[i].isalpha() for i in range(len(answer))]
    correct_guesses = []
    wrong_guesses = []
    is_on_full_guess = False
    last_guess_time = time.time()

    # Generate hint if needed
    if only_hint is None:
        hint_prompt = None
    if hint_prompt or only_hint:
        hint = await get_hint_for_topic(theme, answer, 5, hint_prompt=hint_prompt)

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
        if check_guess_distance(message) == 0:
            is_revealed = [True] * len(answer)
            await cmd_handler(display_board(), output_directly=True)
            await cmd_handler("Tell the user that they won!")
            await stop_hangman()
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
        await cmd_handler("Tell the user that they won! Do NOT mention their username.")
        await stop_hangman()
        return None
    elif len(wrong_guesses) >= MAX_WRONG_GUESSES:
        is_revealed = [True] * len(answer)
        await cmd_handler(display_board(), output_directly=True)
        await cmd_handler(
            "Tell the user that they lost (too many wrong guesses) and comment on the revealed answer. Do NOT mention their username."  # noqa: E501
        )
        await stop_hangman()
        return None
    elif guess_duration > TIME_BETWEEN_COMMENTS:
        await cmd_handler(
            f"Make a *very* short comment on the game of hangman. The user just guessed '{message.upper()}', and there were {num_matches} matches in the answer. Do NOT try to print the hangman board again. Do NOT mention their username."  # noqa: E501
        )


async def play_timed() -> None:
    """Plays a game of timed hangman."""
    # Get answers
    answers = await decide_topics(theme, TIMED_NUM_ROUNDS)

    global answer, hint, is_revealed, num_rounds, curr_round, num_lives, is_on_full_guess, hint_prompt, condition_signal
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
        percent_to_reveal = max(0.1, percent_to_reveal * hint_helpfulness)
        if only_hint:
            # Adjustment to make it easier if we can't see letters
            curr_hint_prompt = f"{hint_prompt} " if hint_prompt else ""
            percent_to_reveal = min(0.9, percent_to_reveal * 1.3 + 0.1)
            curr_hint_prompt += "(Give a detailed hint that **uniquely identifies** the topic. Do not re-mention the theme.)"  # noqa: E501
            #  If helpfulness is near 1, use revealing, signature facts. Ex: If the theme is league champs, you can mention the position they're played in, signature ability names, and memorable aspects of the champ.  # noqa: E501
        else:
            curr_hint_prompt = hint_prompt
            percent_to_reveal = min(0.9, percent_to_reveal)
        # Give a hint with this helpfulness instead
        curr_hint = await get_hint_for_topic(
            theme, answer, (percent_to_reveal + 0.1) * 10, hint_prompt=curr_hint_prompt
        )
        hint = curr_hint
        # await cmd_handler(f"Percent revealed: {round(percent_to_reveal * 100, 1)}%", output_directly=True)
        logger.info(f"Hangman percent revealed: {round(percent_to_reveal * 100, 1)}%")
        num_to_reveal = min(len(unrevealed_locs) - 1, math.ceil(percent_to_reveal * len(unrevealed_locs)))
        for j in range(num_to_reveal):
            if random.random() < 0.5:
                continue  # Already have a hint
            is_revealed[unrevealed_locs[j]] = True

        # Start game
        print(f"Hangman answer: {answer}")
        if not only_hint:
            await cmd_handler(display_board(), output_directly=True)
        else:
            await cmd_handler(
                f'Relay this ENTIRE hint to the user in a casual way so they can guess the word/phrase: {hint}. The first line of your message must be "**round {curr_round}/{num_rounds}**: " exactly, with the ending space, followed by 1 blank line. Do NOT mention their username, and do not add any comments after the hint.'  # noqa: E501
            )

        # Explain rules on the first round
        if curr_round == 1:
            await cmd_handler(
                f"Tell the user they need to guess the words/phrases correctly to win. Tell them they have {timed_time_per_answer} seconds to guess each one, and must message the exact answer for it to count. Do NOT try to reprint the clues you've already given. Do NOT mention their username."  # noqa: E501
            )

        # Run a timer
        condition_signal = "N/A"
        await sleep_interruptable(1)
        if condition_signal == "N/A" and status != "idle":
            await sleep_interruptable(timed_time_per_answer / 2)
            time_left = timed_time_per_answer - timed_time_per_answer / 2
        if condition_signal == "N/A" and status != "idle" and timed_time_per_answer >= 10:
            await cmd_handler(f"{round(time_left)} seconds left!", output_directly=True)
            await sleep_interruptable(time_left - 3)
        if condition_signal == "N/A" and status != "idle":
            await cmd_handler("3...", output_directly=True)
            await sleep_interruptable(1.5)
        if condition_signal == "N/A" and status != "idle":
            await cmd_handler("2...", output_directly=True)
            await sleep_interruptable(1.5)
        if condition_signal == "N/A" and status != "idle":
            await cmd_handler("1...", output_directly=True)
            await sleep_interruptable(2.5)

        if condition_signal == "stop" or status == "idle":
            # Quit
            return
        if not is_on_full_guess:
            # Ran out of time
            is_on_full_guess = True
            num_lives -= 1
            if num_lives == 0:
                await cmd_handler(
                    f"Tell the user that they lost (ran out of time). They made it to round {curr_round} out of {num_rounds}. Echo that the answer was **{answer}** and comment on it. Do NOT mention their username."  # noqa: E501
                )
                await stop_hangman()
                return
            else:
                await cmd_handler(
                    f"Tell the user that they ran out of time, and that they have {num_lives} lives left. Echo that the answer was **{answer}** and comment on it."  # noqa: E501
                )
        else:
            # Wait a bit
            await sleep_interruptable(1)

    # Got through all rounds
    await cmd_handler(
        f"Congratulate the user on making it through all {num_rounds} rounds with {num_lives} lives left! Do NOT mention their username."  # noqa: E501
    )
    await stop_hangman()


async def guess_timed(message: str) -> None:
    """Handles a guess during a timed hangman game."""
    # Check for correct guess
    global is_on_full_guess, condition_signal
    curr_num_lives = num_lives
    if is_on_full_guess:
        # No more guesses allowed
        return
    upper_answer = answer.upper()
    guess_dist = check_guess_distance(message)
    # Allow leniency
    leniency_correct = len(upper_answer) // 8
    leniency_hint = 1 + len(upper_answer) // 8
    if guess_dist <= leniency_correct:
        # Correct guess
        async with condition_var:
            is_on_full_guess = True
            condition_signal = "correct"  # Signal a correct guess
            condition_var.notify()
        if guess_dist == 0:
            await cmd_handler(
                "Tell the user that they got it right and comment on the answer. This should be a brief comment, don't output anything else. Do NOT try to print another hangman board."  # noqa: E501
            )
        else:
            await cmd_handler(
                f"Tell the user that they got it right, as their guess was close enough to the answer. Echo that the answer was **{answer}** and comment on it. This should be a brief comment, don't output anything else. Do NOT try to print another hangman board."  # noqa: E501
            )
    elif followup_hints:
        # Potentially give a hint
        judge_prompt = f"""You're playing a guessing game with the user. You gave them a hint and told them to guess, and they just guessed. Judge their answer and follow these rules:
- If it's close (similar meaning is ok), give them the exact answer (bold it like **this**). Example: Theme is 'gamer taunts', user guessed 'too easy', correct answer is 'ez', response 'close enough, the answer is **ez**.'
- If it matches the hint, give them the exact answer (bold it like **this**). Example: Hint is 'this term refers to an individual who often engages in aggressive or confrontational behavior in online discussions or gaming environments', guess is 'troll', answer is 'keyboard warrior', response 'that works, the answer is **keyboard warrior**.'
- If it's somewhat close, lead them towards the answer. Example: Theme is 'gamer taunts', user guessed 'clutch', correct answer is 'clutch or kick', response 'clutch or what?'
- If it's completely wrong, give a vague hint. Do not mention the answer in the hint. Example: Theme is 'household items', User guessed 'book', correct answer is 'spoon', response 'no, its a utensil.
- Be more lenient when the timer is under 15 seconds.

For the topic '{theme}', the hint was '{hint}', the user guessed '{message}' and the correct answer is '{answer}'."""  # noqa: E501
        judge_resp: str = await cmd_handler(judge_prompt, hide_output=True)
        if curr_num_lives != num_lives or is_on_full_guess:
            # Timed out while judging (or already guessed correct)
            return
        if answer.lower().strip() in judge_resp.lower().strip():
            # Judged as correct guess
            async with condition_var:
                is_on_full_guess = True
                condition_signal = "correct"  # Signal a correct guess
                condition_var.notify()
            await cmd_handler(
                f"Tell the user that they got it right, as their guess was close enough to the answer. Echo that the answer was **{answer}** and comment on it. This should be a brief comment, don't output anything else. Do NOT try to print another hangman board."  # noqa: E501
            )
        else:
            # Send message
            await cmd_handler(judge_resp, output_directly=True)
    elif guess_dist <= leniency_hint:
        # Close guess (but not correct)
        await cmd_handler("Tell the user that their guess is close to the answer.")  # noqa: E501
    else:
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
        await stop_hangman()


async def hangman_on_message(message: str) -> Optional[str]:
    """Handles a message during a hangman game."""
    if mode == "hangman":
        return await guess_hangman(message)
    elif mode == "timed":
        return await guess_timed(message)
    else:
        return None


def configure_hangman(
    new_theme: str,
    timed: bool = False,
    new_hint_prompt: Optional[str] = None,
    new_only_hint: bool = True,
    helpfulness_mult: float = 1.0,
    time_per_answer: int = 30,
) -> None:
    """Configures the hangman game."""
    global status, theme, mode, hint_prompt, only_hint, followup_hints, hint_helpfulness, timed_time_per_answer
    if status != "idle":
        return  # Can't configure while playing
    theme = new_theme
    mode = "hangman" if not timed else "timed"
    hint_prompt = new_hint_prompt
    only_hint = new_only_hint
    followup_hints = new_only_hint  # Give followup hints if there are no hangman clues
    hint_helpfulness = helpfulness_mult
    timed_time_per_answer = time_per_answer


def get_hangman_info() -> str:
    """Returns the current hangman status."""
    if status == "idle":
        return "You are not currently playing hangman."
    return "You are currently playing hangman."
