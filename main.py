import logging
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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


def read_token() -> str:
    token = os.environ.get("TG_API_TOKEN")
    if token is None:
        raise RuntimeError("Token should be in environment as TG_API_TOKEN")
    return token


if __name__ == "__main__":
    application = ApplicationBuilder().token(read_token()).build()

    start_handler = CommandHandler("start", start)
    application.add_handler(start_handler)

    application.run_polling()
