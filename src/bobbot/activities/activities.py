"""Combines all activities into a single API."""

from enum import Enum
from typing import Optional

from PIL import Image

from bobbot.activities.chess_player import (
    get_chess_info,
    play_chess_activity,
    screenshot_chess_activity,
)


class Activity(Enum):
    """Valid activities for the bot."""

    WORK = "work"
    EAT = "eat"
    SLEEP = "sleep"
    CHESS = "chess"
    LEAGUE = "league_of_legends"
    SKRIBBL = "skribbl"


current_activity: Optional[Activity] = None


async def start_activity(activity: Activity, *args, **kwargs) -> str:
    """Starts the given activity. Returns a readable response message explaining if the activity was started."""
    global current_activity
    if current_activity is not None:
        return "You're already doing something!"
    current_activity = activity
    result: str
    if activity == Activity.CHESS:
        result = await play_chess_activity(*args, **kwargs)
    else:
        raise NotImplementedError
    current_activity = None
    return result


async def stop_activity() -> None:
    """Stops the current activity."""
    pass


async def get_activity_status() -> str:
    """Returns a readable version of the current activity status, in the 2nd person."""
    if current_activity is None:
        return "You're free right now."
    elif current_activity == Activity.CHESS:
        return get_chess_info()
    else:
        raise NotImplementedError


async def spectate_activity() -> Optional[Image.Image]:
    """Returns an image of the current activity (if available)."""
    if current_activity is None:
        return None
    if current_activity == Activity.CHESS:
        return await screenshot_chess_activity()
    else:
        raise NotImplementedError
