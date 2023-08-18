import os

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from pinhead.config import create_config


@pytest.fixture
async def db():
    cfg = create_config(os.environ)
    client = AsyncIOMotorClient(cfg.mongo_uri)
    db = client[cfg.mongo_db_name]
    yield db
    await db.drop_collection("actions")


@pytest.fixture
async def setup_db(db):
    db_collections = await db.list_collection_names()
    for collection in db_collections:
        await db.drop_collection(collection)
