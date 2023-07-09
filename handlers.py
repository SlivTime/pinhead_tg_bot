import logging
from datetime import UTC, datetime

from telegram import Message, Update, User
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

from constants import (
    DEFAULT_ACTION_DURATION,
    DEFAULT_CONSENSUS,
    NO,
    WAKEUP_PERIOD,
    YES,
    YES_NO_OPTIONS,
)
from data import ActionData, ActionType, PipelineStep
from helpers import (
    ensured,
    find_poll_data,
    generate_random_str,
    store_action,
    store_poll,
)
from pipeline import execute_scheduled_actions, run_pipeline_now

logger = logging.getLogger(__name__)


def pipeline_start_fabric(action_type: ActionType):
    async def start_pipeline(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        now = datetime.now(tz=UTC)
        target = _extract_target(action_type, update.message)
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not target:
            logger.warning("Can't extract target, ignore")
            return
        if not chat_id:
            logger.error("Chat id not found, ignore")
            return
        action = ActionData(
            id=generate_random_str(),
            chat_id=chat_id,
            target_id=str(target.id),
            action_type=action_type,
            step=PipelineStep.START,
            start_at=now,
            consensus=DEFAULT_CONSENSUS,
            execute_at=now,
            duration=DEFAULT_ACTION_DURATION,
        )
        await store_action(context, action)
        logger.info("Action stored, run pipeline")
        run_pipeline_now(context)

    return start_pipeline


def _extract_target(
    action_type: ActionType, message: Message | None
) -> Message | User | None:
    if message is None:
        return None
    match action_type:
        case ActionType.PIN | ActionType.DELETE:
            return message.reply_to_message if message else None
        case ActionType.MUTE | ActionType.BAN | ActionType.PURGE:
            return (
                message.reply_to_message.from_user
                if message and message.reply_to_message
                else None
            )

    return None


async def register_poll_answer(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    logger.info(f"receive poll answer: {update}")
    answer = update.poll_answer
    if not answer:
        logger.error("Poll answer not found")
        return
    logger.info(f"got answer: {answer}")
    poll_data = find_poll_data(context, answer.poll_id)
    if poll_data is None:
        logger.error(f"Poll data not found: {answer.poll_id}")
        return

    choice_id, *_ = answer.option_ids
    choice_str = YES_NO_OPTIONS[choice_id]

    if choice_str == YES:
        poll_data.yes += 1
    elif choice_str == NO:
        poll_data.no += 1
    else:
        logger.error(f"Unknown choice: {choice_str}")
        return

    await store_poll(context, poll_data)


async def bot_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"receive help command: {update}")
    await ensured(update.message).reply_text(
        "Available commands:\n"
        "/pin - pin message\n"
        "/mute - mute chat\n"
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
