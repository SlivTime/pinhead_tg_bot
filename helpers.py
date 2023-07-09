import logging
import random
import string
from collections.abc import Generator
from typing import Any, TypeVar

import marshmallow_recipe as mr
from telegram.ext import CallbackContext

from data import ActionData, PollData

logger = logging.getLogger(__name__)

JOB_PREFIX = "job"
POLL_PREFIX = "poll"
_SEP = ":"


async def store_action(ctx: CallbackContext, action: ActionData) -> None:
    action_key = get_action_key(action)
    action_dump = mr.dump(action)
    ctx.bot_data.update({action_key: action_dump})
    logger.debug(f"Stored action: {action_key} - {action_dump}")


async def store_poll(ctx: CallbackContext, poll_data: PollData) -> None:
    poll_key = get_poll_key(poll_data)
    poll_dump = mr.dump(poll_data)
    ctx.bot_data.update({poll_key: poll_dump})
    logger.debug(f"Stored poll: {poll_key} - {poll_dump}")


async def remove_action(ctx: CallbackContext, action: ActionData) -> None:
    action_key = get_action_key(action)
    ctx.bot_data.pop(action_key)
    logger.debug(f"Removed action: {action_key}")


async def remove_poll(ctx: CallbackContext, poll_data: PollData) -> None:
    poll_key = get_poll_key(poll_data)
    ctx.bot_data.pop(poll_key)
    logger.debug(f"Removed poll: {poll_key}")


def find_poll_data(context, poll_id: str) -> PollData | None:
    for poll_data in iterate_polls(context.bot_data):
        if poll_data.id == poll_id:
            return poll_data
    return None


def get_action_key(action_data: ActionData) -> str:
    return f"{JOB_PREFIX}{_SEP}{action_data.action_type}{_SEP}{action_data.id}"


def get_poll_key(poll_data: PollData) -> str:
    return f"{POLL_PREFIX}{_SEP}{poll_data.action_id}{_SEP}{poll_data.id}"


def unpack_poll_key(poll_key) -> tuple[str, str]:
    prefix, action_id, poll_id = poll_key.split(_SEP)
    return action_id, poll_id


def unpack_action_key(action_key) -> tuple[str, str]:
    prefix, action_type, action_id = action_key.split(_SEP)
    return action_type, action_id


def iterate_polls(bot_data: dict[str, Any]) -> Generator[PollData, None, None]:
    polls = [
        mr.load(PollData, v)
        for k, v in bot_data.items()
        if k.startswith(POLL_PREFIX)
    ]
    yield from polls


def iterate_scheduled_actions(
    bot_data: dict[str, Any]
) -> Generator[ActionData, None, None]:
    actions = [
        mr.load(ActionData, v)
        for k, v in bot_data.items()
        if k.startswith(JOB_PREFIX)
    ]
    logger.info(f"Found actions: {actions}")
    yield from actions


def generate_random_str(length: int = 10) -> str:
    return "".join(
        random.choices(string.ascii_letters + string.digits, k=length)
    )


T = TypeVar("T")


def ensured(x: T | None) -> T:
    assert x
    return x
