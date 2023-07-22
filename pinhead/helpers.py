import logging
import random
import string
from typing import TypeVar, cast

from motor.motor_asyncio import AsyncIOMotorDatabase
from telegram.ext import CallbackContext

from pinhead.data import ActionData

logger = logging.getLogger(__name__)

JOB_PREFIX = "job"
POLL_PREFIX = "poll"
_SEP = ":"


def get_db(ctx: CallbackContext) -> AsyncIOMotorDatabase:
    return cast(AsyncIOMotorDatabase, ctx.application.db)  # type: ignore


def generate_random_str(length: int = 10) -> str:
    return "".join(
        random.choices(string.ascii_letters + string.digits, k=length)
    )


T = TypeVar("T")


def ensured(x: T | None) -> T:
    assert x
    return x


def log_format_action(action: ActionData) -> str:
    poll_state = ""
    if action.poll:
        poll_state = (
            f"Poll [{len(action.poll.votes)} | {action.poll.consensus}]"
        )
    return (
        f"<{action.action_id}|{action.action_type.value}> {action.step.value} "
        f"{poll_state} "
    )
