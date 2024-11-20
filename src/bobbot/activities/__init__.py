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
from bobbot.activities.hangman import configure_hangman, hangman_on_message
from bobbot.activities.school import configure_school

__all__ = [
    "Activity",
    "get_activity",
    "get_activity_status",
    "spectate_activity",
    "start_activity",
    "stop_activity",
    "configure_chess",
    "configure_hangman",
    "hangman_on_message",
    "configure_school",
]
