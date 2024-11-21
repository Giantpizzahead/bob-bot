"""Simulates being at school."""

import asyncio
import datetime
import random
from typing import Callable, Optional

status = "idle"
curr_task: Optional[str] = None
end_time: Optional[datetime.datetime] = None
school_duration: float = 6 * 60 * 60  # 6 hours
stop_event: Optional[asyncio.Event] = asyncio.Event()


async def sleep_interruptable(delay: float) -> bool:
    """Sleeps for delay seconds. Returns False if the wait was interrupted."""
    global stop_event
    stop_event = asyncio.Event()
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=delay)
        return False
    except asyncio.TimeoutError:
        return True


def stop_school() -> None:
    """Stops being at school."""
    stop_event.set()


async def school_activity(cmd_handler: Callable) -> None:
    """Simulates begin at school (in the background)."""
    global status, end_time
    if status != "idle":
        await cmd_handler("Echo this to the user. Failed to start: You are already at school.")
        return
    status = "school"
    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(seconds=school_duration)
    await sleep_interruptable(school_duration)
    if curr_task is not None:
        # Get actual time elapsed
        time_elapsed = (datetime.datetime.now() - start_time).seconds
        # Reward should be max(25 + Uniform[75, 125] * Uniform[# hours - 0.5, # hours + 0.5], 50), multiple of 25
        reward = random.uniform(75, 125) * random.uniform(time_elapsed / 3600 - 0.5, time_elapsed / 3600 + 0.5)
        reward = max(round(reward / 25) * 25, 50)
        # Punishment with the same formula
        punishment = random.uniform(75, 125) * random.uniform(time_elapsed / 3600 - 0.5, time_elapsed / 3600 + 0.5)
        punishment = max(round(punishment / 25) * 25, 50)
        await cmd_handler(
            f"Ask the user if they finished their task '{curr_task}' or not (for accountability). Tell them that if they did (or are close), they get {reward} HP. If they didn't, they lose {punishment} HP."  # noqa: E501
        )
    status = "idle"


def configure_school(duration: float, task: Optional[str] = None) -> None:
    """Configures the length of the school day."""
    global school_duration, curr_task
    school_duration = duration * 60  # Minutes to seconds
    curr_task = task


def get_school_info() -> str:
    """Returns the current school status."""
    if status == "idle":
        return "You are not currently at school."
    minutes_left = (end_time - datetime.datetime.now()).seconds / 60
    if minutes_left <= 1:
        return "You are about to finish your last class at school."
    return f"You are currently at school. Your last class finishes in about {minutes_left:.0f} minutes."
