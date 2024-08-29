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
    stop_playing_chess,
)
from bobbot.activities.eat import eat_meal_activity, get_eating_info, stop_eating
from bobbot.activities.school import get_school_info, school_activity, stop_school
from bobbot.activities.shower import get_shower_info, shower_activity, stop_showering
from bobbot.activities.sleep import get_sleep_info, sleep_activity, stop_sleeping


class Activity(Enum):
    """Valid activities for the bot."""

    SCHOOL = "school"
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
            Optionally, it can have a second boolean argument, which specifies when a response from
            the user is expected. If True, the returned string from the callback is used as the response.

    Returns:
        Whether the activity successfully began running.
    """
    global current_activity
    if current_activity is not None:
        await cmd_handler(
            f"The user just tried to get you to do an activity '{activity.value}'. Let them know you can't do that because you are already doing something, tell them WHAT you're doing, and say the ROUGH amount of time left in that activity (in hours if it's large, else minutes): {await get_activity_status()}"  # noqa: E501
        )
        return False
    current_activity = activity
    result = None
    if activity == Activity.SCHOOL:
        result = await school_activity(cmd_handler)
    elif activity == Activity.EAT:
        result = await eat_meal_activity(cmd_handler)
    elif activity == Activity.SHOWER:
        result = await shower_activity(cmd_handler)
    elif activity == Activity.SLEEP:
        result = await sleep_activity(cmd_handler)
    elif activity == Activity.CHESS:
        result = await play_chess_activity(cmd_handler)
    else:
        raise NotImplementedError
    current_activity = None
    result = True
    return result


async def stop_activity() -> None:
    """Stops the current activity."""
    if current_activity is None:
        return
    elif current_activity == Activity.SCHOOL:
        stop_school()
    elif current_activity == Activity.EAT:
        stop_eating()
    elif current_activity == Activity.SHOWER:
        stop_showering()
    elif current_activity == Activity.SLEEP:
        stop_sleeping()
    elif current_activity == Activity.CHESS:
        stop_playing_chess()
    else:
        raise NotImplementedError


async def get_activity_status() -> str:
    """Returns a readable version of the current activity status directed at Bob."""
    if current_activity is None:
        return "You're free right now."
    elif current_activity == Activity.SCHOOL:
        return get_school_info()
    elif current_activity == Activity.EAT:
        return get_eating_info()
    elif current_activity == Activity.SHOWER:
        return get_shower_info()
    elif current_activity == Activity.SLEEP:
        return get_sleep_info()
    elif current_activity == Activity.CHESS:
        return get_chess_info()
    else:
        raise NotImplementedError


async def spectate_activity() -> Optional[list[str] | Image.Image]:
    """Returns an image or list of messages for the current activity (if available)."""
    if current_activity is None:
        return None
    elif current_activity == Activity.SCHOOL:
        return [
            "https://tenor.com/view/mochi-peach-work-annoying-gif-11281690480465316781",
            "sorry i am studying rn, u should too :)",
        ]
    elif current_activity == Activity.EAT:
        return [
            "https://tenor.com/view/couplegoals-peachmad-peach-and-goma-gif-22393884",
            "eating :yum:",
        ]
    elif current_activity == Activity.SHOWER:
        return [
            "https://tenor.com/view/mochi-peach-shower-gif-7317826607873000669",
            "im in the shower ;)",
        ]
    elif current_activity == Activity.SLEEP:
        return ["https://tenor.com/view/zzz-hello-kitty-gif-12194146", "go to sleep..."]
    elif current_activity == Activity.CHESS:
        return await screenshot_chess_activity()
    else:
        return NotImplementedError
