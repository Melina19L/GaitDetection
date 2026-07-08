"""Shared gait-phase vocabulary.

Defines the ``Phase`` enum used across the whole system: the gait detection
FSMs emit these values, the stimulation model maps each one to muscle targets,
and the GUI displays them. This is the single source of truth every module
speaks.
"""
from enum import Enum

class Phase(Enum):
    """The nine gait cycle phases/subphases, in cycle order.

    STANCE and SWING are the coarse phases; the rest are subphases
    (LOADING_RESPONSE, MID_STANCE, TERMINAL_STANCE, PRE_SWING within stance;
    MID_SWING, TERMINAL_SWING within swing). UNKNOWN is the initial/undetected
    state. Integer values are ordinal and used as dict keys elsewhere.
    """
    UNKNOWN = 1
    STANCE = 2
    LOADING_RESPONSE = 3
    MID_STANCE = 4
    TERMINAL_STANCE = 5
    PRE_SWING = 6
    SWING = 7
    MID_SWING = 8
    TERMINAL_SWING = 9
