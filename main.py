import logging
import os

import click
from telegram.ext import ApplicationBuilder

from config import create_config
from handlers import setup_handlers

logger = logging.getLogger(__name__)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


@click.command()
@click.option("--polling", is_flag=True)
def start_bot(polling: bool = False):
    cfg = create_config(os.environ)

    application = ApplicationBuilder().token(cfg.tg_api_token).build()

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
