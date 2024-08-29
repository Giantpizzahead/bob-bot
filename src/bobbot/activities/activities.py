"""Combines all activities into a single API.

Directed at Bob means the message is a readable string meant to be given as context to Bob.
Ex: "You are at work right now."
"""

from enum import Enum
from typing import Callable, Optional

from PIL import Image

from bobbot.activities.chess_player import (
    get_chess_info,
    play_chess_activity,
    screenshot_chess_activity,
)
from bobbot.activities.eat import eat_meal_activity, get_eating_info


class Activity(Enum):
    """Valid activities for the bot."""

    WORK = "work"
    EAT = "eat"
    SHOWER = "shower"
    SLEEP = "sleep"
    CHESS = "chess"
    LEAGUE = "league"


current_activity: Optional[Activity] = None


async def start_activity(activity: Activity, cmd_handler: Callable) -> bool:
    """Starts the given activity.

    Args:
        activity: The activity to start.
        cmd_handler: The callback to send commands directed at Bob.
        The callback should be an async function that accepts exactly one string argument.
        If the activity fails to start, it will be called with the reason.
        Otherwise, it will be called the activity goes on and important things happen.

    Returns:
        Whether the activity successfully ran to completion (no errors or early stopping).
    """
    global current_activity
    if current_activity is not None:
        await cmd_handler(
            f"The user just tried to get you to do an activity '{activity.value}'. Let them know you can't do that because you are already doing something: {await get_activity_status()}"  # noqa: E501
        )
        return False
    current_activity = activity
    result: bool
    if activity == Activity.EAT:
        result = await eat_meal_activity(cmd_handler)
    elif activity == Activity.CHESS:
        result = await play_chess_activity(cmd_handler)
    else:
        raise NotImplementedError
    current_activity = None
    return result


async def stop_activity() -> None:
    """Stops the current activity."""
    pass


async def get_activity_status() -> str:
    """Returns a readable version of the current activity status directed at Bob."""
    if current_activity is None:
        return "You're free right now."
    elif current_activity == Activity.EAT:
        return get_eating_info()
    elif current_activity == Activity.CHESS:
        return get_chess_info()
    else:
        raise NotImplementedError


async def spectate_activity() -> Optional[Image.Image]:
    """Returns an image of the current activity (if available)."""
    if current_activity is None:
        return None
    elif current_activity == Activity.EAT:
        return None
    elif current_activity == Activity.CHESS:
        return await screenshot_chess_activity()
    else:
        raise NotImplementedError
