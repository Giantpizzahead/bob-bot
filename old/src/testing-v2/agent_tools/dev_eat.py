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
eating_end_time: Optional[datetime.datetime] = None


async def eat_meal_activity(cmd_handler: Callable) -> None:
    """Simulates eating a meal."""
    global status, eating_end_time
    if status != "idle":
        await cmd_handler(f"Echo this to the user. Failed to start: You are already eating {status}.")
        return
    if meal_to_eat == Meal.LUNCH:
        status = "lunch"
        base_time = 60 * 20  # 20 minutes
    else:
        status = "dinner"
        base_time = 60 * 40  # 40 minutes
    # Simulate eating time
    eating_time = base_time * random.uniform(0.8, 1.2)
    eating_end_time = datetime.datetime.now() + datetime.timedelta(seconds=eating_time)
    food = await cmd_handler(
        f"You are about to eat {status}. Ask the user what you should eat for {status}.", expect_response=True
    )
    await cmd_handler(
        f"Tell the user you are now going to eat {food} for {status}. You will be back in about {eating_time / 60:.0f} minutes."  # noqa: E501
    )
    await asyncio.sleep(eating_time)
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
    minutes_left = (eating_end_time - datetime.datetime.now()).seconds / 60
    if minutes_left <= 1:
        return f"You are about to finish eating {status}."
    return f"You are eating {status}. You will be done in about {minutes_left:.0f} minutes."
