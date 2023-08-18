from datetime import UTC, datetime

from pinhead.constants import DEFAULT_CONSENSUS, YES_NO_OPTIONS
from pinhead.data import (
    CHAT_ID,
    ActionData,
    ActionType,
    PipelineStep,
    PollData,
    VoteData,
)
from pinhead.helpers import generate_random_str

TEST_USER_ID = 313


def generate_action_data(
    action_type: ActionType | None = None,
    execute_at: datetime | None = None,
    step=PipelineStep.START,
) -> ActionData:
    now = datetime.now(tz=UTC)
    return ActionData(
        action_id=generate_random_str(),
        chat_id=CHAT_ID,
        target_message_id="321",
        trigger_message_id="322",
        target_user_id="333",
        action_type=action_type or ActionType.PIN,
        step=step or PipelineStep.START,
        start_at=now,
        execute_at=execute_at or now,
        duration=0,
    )


def generate_poll_data() -> PollData:
    return PollData(
        id="444",
        options=YES_NO_OPTIONS,
        message_id="555",
        consensus=DEFAULT_CONSENSUS,
        win_result=None,
        votes=[],
    )


def generate_vote_data(user_id: int | None = TEST_USER_ID) -> VoteData:
    if user_id is None:
        user_id = TEST_USER_ID
    return VoteData(
        user_id=user_id,
        user_name="@AlexDarkStalker",
        answer=[0],
        voted_at=datetime.now(tz=UTC),
    )
