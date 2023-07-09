import dataclasses
from datetime import datetime
from enum import StrEnum


@dataclasses.dataclass(slots=True, kw_only=True)
class PollData:
    id: str
    action_id: str
    options: list[str]
    message_id: str
    chat_id: int
    yes: int
    no: int


class PipelineStep(StrEnum):
    START = "start"
    POLL = "poll"
    CONSENSUS = "consensus"
    EXECUTE = "execute"
    REVERT = "revert"
    DONE = "done"
    ERROR = "error"


class ActionType(StrEnum):
    PIN = "pin"
    DELETE = "delete"
    MUTE = "mute"
    BAN = "ban"
    PURGE = "purge"


@dataclasses.dataclass(slots=True, kw_only=True)
class ActionData:
    id: str
    chat_id: int
    target_id: str
    action_type: ActionType
    step: PipelineStep
    start_at: datetime
    execute_at: datetime
    poll_id: str | None = None
    consensus: int | None = None
    poll_decision: bool = False
    executed_at: datetime | None = None
    finished_at: datetime | None = None
    duration: int | None = None  # in seconds
