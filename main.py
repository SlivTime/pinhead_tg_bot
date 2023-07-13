import logging
import os

import click
from mongopersistence import MongoPersistence
from telegram.ext import ApplicationBuilder

from pinhead.config import create_config
from pinhead.handlers import setup_handlers

logger = logging.getLogger(__name__)

logging.basicConfig(
    format="%(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


@click.command()
@click.option("--polling", is_flag=True)
def start_bot(polling: bool = False):
    cfg = create_config(os.environ)

    persistence = MongoPersistence(
        mongo_url=cfg.mongo_uri,
        db_name=cfg.mongo_db_name,
        name_col_user_data="user_data",
        name_col_chat_data="chat_data",
        name_col_bot_data="bot_data",
        create_col_if_not_exist=True,
        ignore_general_data=["cache"],
    )

    application = (
        ApplicationBuilder()
        .token(cfg.tg_api_token)
        .persistence(persistence)
        .build()
    )

    setup_handlers(application)

    if polling:
        application.run_polling()
    else:
        application.run_webhook(
            listen="0.0.0.0",
            port=cfg.service_port,
            webhook_url=cfg.service_url,
            secret_token=cfg.secret_token,
        )


if __name__ == "__main__":
    start_bot()
