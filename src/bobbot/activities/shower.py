"""Simulates showering."""

import asyncio
import datetime
import random
from typing import Callable, Optional

status = "idle"
end_time: Optional[datetime.datetime] = None
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


def stop_showering() -> None:
    """Stops showering."""
    stop_event.set()


async def shower_activity(cmd_handler: Callable) -> None:
    """Simulates showering (in the background)."""
    global status, end_time
    if status != "idle":
        await cmd_handler("Echo this to the user. Failed to start: You are already showering.")
        return
    status = "showering"
    # Simulate shower time
    duration = 60 * 15 * random.uniform(0.8, 1.2)  # 15 minutes
    end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration)
    await sleep_interruptable(duration)
    status = "idle"


def get_shower_info() -> str:
    """Returns the current showering status."""
    if status == "idle":
        return "You are not currently showering."
    minutes_left = (end_time - datetime.datetime.now()).seconds / 60
    if minutes_left <= 1:
        return "You are about to finish showering."
    return f"You are currently showering. You will be done in about {minutes_left:.0f} minutes."
