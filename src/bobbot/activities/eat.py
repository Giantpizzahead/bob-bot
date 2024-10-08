"""Simulates eating lunch or dinner."""

import asyncio
import datetime
import random
from enum import Enum
from typing import Callable, Optional


class Meal(Enum):
    """Valid meals to eat."""

    LUNCH = "lunch"
    DINNER = "dinner"


status = "idle"
meal_to_eat = Meal.LUNCH
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


def stop_eating() -> None:
    """Stops eating."""
    stop_event.set()


async def eat_meal_activity(cmd_handler: Callable) -> None:
    """Simulates eating a meal (in the background)."""
    global status, end_time
    if status != "idle":
        await cmd_handler(f"Echo this to the user. Failed to start: You are already eating {status}.")
        return
    if meal_to_eat == Meal.LUNCH:
        status = "lunch"
        base_time = 60 * 25  # 25 minutes
    else:
        status = "dinner"
        base_time = 60 * 45  # 45 minutes
    # Simulate eating time
    eating_time = base_time * random.uniform(0.8, 1.2)
    end_time = datetime.datetime.now() + datetime.timedelta(seconds=eating_time)
    await sleep_interruptable(eating_time)
    status = "idle"


def configure_meal(meal: str) -> None:
    """Configures the meal to eat (lunch or dinner)."""
    global meal_to_eat
    if meal == "lunch":
        meal_to_eat = Meal.LUNCH
    elif meal == "dinner":
        meal_to_eat = Meal.DINNER
    else:
        raise ValueError(f"Invalid meal: {meal}")


def get_eating_info() -> str:
    """Returns the current eating status."""
    if status == "idle":
        return "You are not currently eating."
    minutes_left = (end_time - datetime.datetime.now()).seconds / 60
    if minutes_left <= 1:
        return f"You are about to finish eating {status}."
    return f"You are eating {status}. You will be done in about {minutes_left:.0f} minutes."
