import logging
import random
import string
from typing import TypeVar, cast

from motor.motor_asyncio import AsyncIOMotorDatabase
from telegram.ext import CallbackContext

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
