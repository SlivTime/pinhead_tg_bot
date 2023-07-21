import dataclasses
from datetime import datetime
from enum import StrEnum


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
class VoteData:
    user_id: int
    user_name: str
    answer: list[int]
    voted_at: datetime


@dataclasses.dataclass(slots=True, kw_only=True)
class PollData:
    id: str
    options: list[str]
    message_id: str
    consensus: int
    votes: list[VoteData]
    win_result: bool | None = None


@dataclasses.dataclass(slots=True, kw_only=True)
class ActionData:
    action_id: str
    chat_id: int
    target_message_id: str
    target_user_id: str | None
    action_type: ActionType
    step: PipelineStep
    start_at: datetime
    execute_at: datetime
    poll: PollData | None = None
    executed_at: datetime | None = None
    finished_at: datetime | None = None
    duration: int | None = None  # in seconds


CHAT_ID = 123
