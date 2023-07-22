# method to store ActionData to mongo to separate collection
from datetime import UTC, datetime

import marshmallow_recipe as mr
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.results import InsertOneResult, UpdateResult

from pinhead.data import (
    ActionData,
    ActionType,
    PipelineStep,
    PollData,
    VoteData,
)


async def store_action(
    db: AsyncIOMotorDatabase, action_data: ActionData
) -> InsertOneResult:
    return await db.actions.insert_one(mr.dump(action_data))


async def store_poll(
    db: AsyncIOMotorDatabase,
    action_data: ActionData,
    poll_data: PollData,
) -> UpdateResult:
    return await db.actions.update_one(
        {"action_id": action_data.action_id},
        {"$set": {"poll": mr.dump(poll_data)}},
    )


async def change_step(
    db: AsyncIOMotorDatabase,
    action_id: str,
    step: PipelineStep,
):
    return await db.actions.update_one(
        {"action_id": action_id},
        {"$set": {"step": step}},
    )


async def postpone_action(
    db: AsyncIOMotorDatabase,
    action_id: str,
    next_execution: datetime,
):
    return await db.actions.update_one(
        {"action_id": action_id},
        {"$set": {"execute_at": next_execution}},
    )


async def store_vote(
    db: AsyncIOMotorDatabase,
    action_id: str,
    vote_data: VoteData,
) -> UpdateResult:
    return await db.actions.update_one(
        {"action_id": action_id},
        {"$addToSet": {"poll.votes": mr.dump(vote_data)}},
    )


async def store_poll_result(
    db: AsyncIOMotorDatabase,
    action: ActionData,
    result: bool,
):
    return await db.actions.update_one(
        {"action_id": action.action_id}, {"$set": {"poll.win_result": result}}
    )


async def fetch_action_by_id(
    db: AsyncIOMotorDatabase, action_id: str
) -> ActionData | None:
    item = await db.actions.find_one({"action_id": action_id})  # type: ignore
    if item:
        return mr.load(ActionData, item)
    return None


async def fetch_action_by_poll_id(
    db: AsyncIOMotorDatabase, poll_id: str
) -> ActionData | None:
    item = await db.actions.find_one({"poll.id": poll_id})  # type: ignore
    if item:
        return mr.load(ActionData, item)
    return None


async def fetch_ready_actions(
    db: AsyncIOMotorDatabase, type: ActionType | None = None
) -> list[ActionData]:
    now = datetime.now(tz=UTC)

    filter_ = {
        "step": {"$nin": [PipelineStep.ERROR, PipelineStep.DONE]},
        "execute_at": {"$lte": now.isoformat()},
    }
    if type is not None:
        filter_["action_type"] = type

    query = db.actions.find(filter_)
    items = [mr.load(ActionData, item) async for item in query]  # type: ignore
    return items
