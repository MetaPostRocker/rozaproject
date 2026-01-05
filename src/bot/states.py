from enum import Enum, auto


class MeterReadingState(Enum):
    """FSM states for meter reading submission flow."""
    WAITING_FOR_READING = auto()
    WAITING_FOR_RECEIPT = auto()
