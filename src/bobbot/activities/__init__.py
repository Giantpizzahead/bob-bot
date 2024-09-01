"""This module contains activites that the bot can perform."""

from bobbot.activities.activities import (
    Activity,
    get_activity,
    get_activity_status,
    spectate_activity,
    start_activity,
    stop_activity,
)
from bobbot.activities.chess_player import configure_chess
from bobbot.activities.eat import configure_meal

__all__ = [
    "Activity",
    "get_activity",
    "get_activity_status",
    "spectate_activity",
    "start_activity",
    "stop_activity",
    "configure_chess",
    "configure_meal",
]
