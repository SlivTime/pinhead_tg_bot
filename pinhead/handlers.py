import logging
from datetime import UTC, datetime

from telegram import Message, Update, User
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

from pinhead.db import fetch_action_by_poll_id, store_action, store_vote

from .constants import DEFAULT_ACTION_DURATION, WAKEUP_PERIOD
from .data import ActionData, ActionType, PipelineStep, VoteData
from .helpers import ensured, generate_random_str, get_db
from .pipeline import execute_scheduled_actions, run_pipeline_now

logger = logging.getLogger(__name__)


def pipeline_start_fabric(action_type: ActionType):
    async def start_pipeline(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        now = datetime.utcnow()
        target_msg, target_user = _extract_targets(update.message)
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not any([target_msg, target_user]):
            logger.warning("Can't extract any target, ignore")
            return
        if not chat_id:
            logger.error("Chat id not found, ignore")
            return
        action = ActionData(
            action_id=generate_random_str(),
            chat_id=chat_id,
            target_message_id=str(ensured(target_msg).id),
            target_user_id=str(target_user.id) if target_user else None,
            action_type=action_type,
            step=PipelineStep.START,
            start_at=now,
            execute_at=now,
            # TODO: parse command args, get duration first
            duration=_get_action_duration(action_type),
        )
        await store_action(get_db(context), action)
        logger.info("Action stored, run pipeline")
        run_pipeline_now(context)

    return start_pipeline


def _get_action_duration(action_type: ActionType) -> int:
    if action_type in {ActionType.PIN, ActionType.BAN, ActionType.MUTE}:
        return DEFAULT_ACTION_DURATION
    return 0


def _extract_targets(
    message: Message | None,
) -> tuple[Message | None, User | None]:
    if message is None:
        return None, None

    target_msg = message.reply_to_message
    target_user = target_msg.from_user if target_msg else None
    return target_msg, target_user


async def register_poll_answer(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    logger.info(f"receive poll answer: {update}")
    answer = update.poll_answer
    if not answer:
        logger.error("Poll answer not found")
        return
    logger.info(f"got answer: {answer}")
    action = await fetch_action_by_poll_id(
        get_db(context), poll_id=answer.poll_id
    )
    if action is None:
        logger.error(f"Action data not found: {answer.poll_id}")
        return

    vote_data = VoteData(
        user_id=answer.user.id,
        user_name=answer.user.name,
        answer=list(answer.option_ids),
        voted_at=datetime.now(tz=UTC),
    )
    await store_vote(get_db(context), action.action_id, vote_data=vote_data)

    run_pipeline_now(context)


async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"receive help command: {update}")
    votes_count = await get_db(context).actions.count_documents({})
    logger.info(f"Count: {votes_count}")
    await ensured(update.message).reply_text(
        "Available commands:\n"
        "/pin - pin message\n"
        "/mute - mute user\n"
        "/delete - delete message\n"
        "/ban - ban user\n"
        "/purge - ban user and delete all messages (hello crypto-boys!)\n"
    )


def setup_handlers(app: Application) -> Application:
    app.add_handler(
        CommandHandler("pin", pipeline_start_fabric(ActionType.PIN))
    )
    app.add_handler(
        CommandHandler("mute", pipeline_start_fabric(ActionType.MUTE))
    )
    app.add_handler(
        CommandHandler("delete", pipeline_start_fabric(ActionType.DELETE))
    )
    app.add_handler(
        CommandHandler("ban", pipeline_start_fabric(ActionType.BAN))
    )
    app.add_handler(
        CommandHandler("purge", pipeline_start_fabric(ActionType.PURGE))
    )
    app.add_handler(CommandHandler("help", bot_help))
    app.add_handler(PollAnswerHandler(register_poll_answer))
    if not app.job_queue:
        raise RuntimeError("Job queue is required to run this bot")
    app.job_queue.run_repeating(
        execute_scheduled_actions, interval=WAKEUP_PERIOD, first=0
    )
    return app
