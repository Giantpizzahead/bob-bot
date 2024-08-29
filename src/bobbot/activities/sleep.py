"""Simulates sleeping."""

import asyncio
import datetime
from typing import Callable, Optional

status = "idle"
end_time: Optional[datetime.datetime] = None
sleep_duration: float = 6 * 60 * 60  # 6 hours
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


def stop_sleeping() -> None:
    """Stops sleeping."""
    stop_event.set()


async def sleep_activity(cmd_handler: Callable) -> None:
    """Simulates sleeping (in the background)."""
    global status, end_time
    if status != "idle":
        await cmd_handler("Echo this to the user. Failed to start: You are already sleeping.")
        return
    status = "sleeping"
    end_time = datetime.datetime.now() + datetime.timedelta(seconds=sleep_duration)
    await sleep_interruptable(sleep_duration)
    status = "idle"


def configure_sleep_length(duration: float) -> None:
    """Configures how long the bot will sleep."""
    global sleep_duration
    sleep_duration = duration


def get_sleep_info() -> str:
    """Returns the current sleeping status."""
    if status == "idle":
        return "You are not currently sleeping."
    minutes_left = (end_time - datetime.datetime.now()).seconds / 60
    if minutes_left <= 1:
        return "You are asleep, but about to wake up."
    return f"You are currently fast asleep. You will be awake in about {minutes_left:.0f} minutes."
