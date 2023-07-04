import logging
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config import create_config

logger = logging.getLogger(__name__)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Update: {update}")
    logger.info(f"ctx: {context}")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,  # type: ignore
        text="I'm a bot, please talk to me!",
    )


if __name__ == "__main__":
    cfg = create_config(os.environ)

    application = ApplicationBuilder().token(cfg.tg_api_token).build()

    start_handler = CommandHandler("start", start)
    application.add_handler(start_handler)

    application.run_webhook(
        listen="0.0.0.0",
        port=cfg.service_port,
        webhook_url=cfg.service_url,
        secret_token=cfg.secret_token,
    )
