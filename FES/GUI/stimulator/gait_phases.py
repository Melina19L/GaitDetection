from enum import Enum

class Phase(Enum):
    UNKNOWN = 1
    STANCE = 2
    LOADING_RESPONSE = 3
    MID_STANCE = 4
    TERMINAL_STANCE = 5
    PRE_SWING = 6
    SWING = 7
    MID_SWING = 8
    TERMINAL_SWING = 9
