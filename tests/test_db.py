import datetime

import marshmallow_recipe as mr
import pytest
from more_itertools import one
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.results import InsertOneResult

from pinhead.data import ActionData, PipelineStep
from pinhead.db import (
    fetch_action_by_id,
    fetch_action_by_poll_id,
    fetch_ready_actions,
    store_action,
    store_poll,
    store_vote,
)
from tests.data import (
    generate_action_data,
    generate_poll_data,
    generate_vote_data,
)

NOW = datetime.datetime.now(tz=datetime.UTC)


async def test_store_action(db: AsyncIOMotorDatabase) -> None:
    action_data = generate_action_data()
    result: InsertOneResult = await store_action(db, action_data)
    assert result.acknowledged
    assert result.inserted_id is not None

    raw_inserted = await db.actions.find_one(
        result.inserted_id
    )  # type: ignore
    assert raw_inserted
    inserted = mr.load(ActionData, raw_inserted)
    assert inserted.action_id == action_data.action_id
    assert inserted.chat_id == action_data.chat_id
    assert inserted.target_message_id == action_data.target_message_id
    assert inserted.target_user_id == action_data.target_user_id
    assert inserted.action_type == action_data.action_type
    assert inserted.step == action_data.step
    assert inserted.start_at == action_data.start_at
    assert inserted.execute_at == action_data.execute_at
    assert inserted.duration == action_data.duration
    assert inserted.poll is None


@pytest.mark.parametrize(
    "step, expect_result",
    (
        (
            PipelineStep.START,
            True,
        ),
        (
            PipelineStep.POLL,
            True,
        ),
        (
            PipelineStep.CONSENSUS,
            True,
        ),
        (
            PipelineStep.EXECUTE,
            True,
        ),
        (
            PipelineStep.REVERT,
            True,
        ),
        (
            PipelineStep.ERROR,
            False,
        ),
        (
            PipelineStep.ERROR,
            False,
        ),
    ),
)
async def test_fetch_ready_single_action_now(
    db: AsyncIOMotorDatabase,
    step: PipelineStep,
    expect_result: bool,
) -> None:
    action = generate_action_data(execute_at=NOW, step=step)
    await store_action(db, action)

    ready_actions = await fetch_ready_actions(db)

    if expect_result:
        assert len(ready_actions) == 1
        assert one(ready_actions) == action
    else:
        assert ready_actions == []


@pytest.fixture
async def prepared_actions(db: AsyncIOMotorDatabase) -> None:
    for action in [
        generate_action_data(execute_at=NOW, step=PipelineStep.START),
        generate_action_data(
            execute_at=NOW + datetime.timedelta(seconds=10),
            step=PipelineStep.POLL,
        ),
        generate_action_data(
            execute_at=NOW - datetime.timedelta(seconds=10),
            step=PipelineStep.CONSENSUS,
        ),
        generate_action_data(
            execute_at=NOW - datetime.timedelta(days=300),
            step=PipelineStep.EXECUTE,
        ),
        generate_action_data(
            execute_at=NOW + datetime.timedelta(seconds=1),
            step=PipelineStep.REVERT,
        ),
        generate_action_data(execute_at=NOW, step=PipelineStep.ERROR),
        generate_action_data(execute_at=NOW, step=PipelineStep.DONE),
    ]:
        await store_action(db, action)


async def test_fetch_ready_action_list(
    db: AsyncIOMotorDatabase, prepared_actions
) -> None:
    # insert several actions and check what returns
    ready_actions = await fetch_ready_actions(db)

    assert {x.step for x in ready_actions} == {
        PipelineStep.START,
        PipelineStep.CONSENSUS,
        PipelineStep.EXECUTE,
    }


async def test_store_poll(db: AsyncIOMotorDatabase) -> None:
    action = generate_action_data(execute_at=NOW, step=PipelineStep.START)
    await store_action(db, action)
    stored = await fetch_action_by_id(db, action.action_id)
    assert stored and stored.poll is None
    poll_data = generate_poll_data()
    await store_poll(db, action_data=stored, poll_data=poll_data)

    updated = await fetch_action_by_id(db, action.action_id)
    assert updated and updated.poll
    assert updated.poll == poll_data


async def test_fetch_action_by_poll_id(db: AsyncIOMotorDatabase) -> None:
    action = generate_action_data(execute_at=NOW, step=PipelineStep.START)
    await store_action(db, action)
    stored = await fetch_action_by_id(db, action.action_id)
    assert stored is not None
    assert stored.poll is None
    poll_data = generate_poll_data()
    not_there_yet = await fetch_action_by_poll_id(db, poll_data.id)
    assert not_there_yet is None

    await store_poll(db, action_data=stored, poll_data=poll_data)
    result = await fetch_action_by_poll_id(db, poll_data.id)
    assert result and result.poll
    assert result.poll == poll_data


async def test_store_vote(db: AsyncIOMotorDatabase) -> None:
    action = generate_action_data(execute_at=NOW, step=PipelineStep.START)
    poll_data = generate_poll_data()
    await store_action(db, action)
    await store_poll(db, action_data=action, poll_data=poll_data)

    with_poll = await fetch_action_by_poll_id(db, poll_data.id)
    assert with_poll and with_poll.poll
    assert with_poll.poll.votes == []

    vote1 = generate_vote_data()
    vote2 = generate_vote_data(user_id=999)
    await store_vote(db, action.action_id, vote1)
    await store_vote(db, action.action_id, vote2)

    result = await fetch_action_by_poll_id(db, poll_data.id)
    assert result and result.poll
    assert len(result.poll.votes) == 2
    assert result.poll.votes == [vote1, vote2]


async def test_store_vote_duplicate(db: AsyncIOMotorDatabase) -> None:
    action = generate_action_data(execute_at=NOW, step=PipelineStep.START)
    poll_data = generate_poll_data()
    await store_action(db, action)
    await store_poll(db, action_data=action, poll_data=poll_data)

    with_poll = await fetch_action_by_poll_id(db, poll_data.id)
    assert with_poll and with_poll.poll is not None
    assert with_poll.poll.votes == []

    vote = generate_vote_data()
    await store_vote(db, action.action_id, vote)
    await store_vote(db, action.action_id, vote)

    result = await fetch_action_by_poll_id(db, poll_data.id)
    assert result and result.poll
    assert len(result.poll.votes) == 1
    assert result.poll.votes == [vote]
