import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import cast

import telegram
from telegram import ChatPermissions
from telegram.ext import CallbackContext, JobQueue

from pinhead.db import (
    change_step,
    fetch_ready_actions,
    postpone_action,
    store_poll,
    store_poll_result,
)

from .constants import (
    DEFAULT_CONSENSUS,
    NO_IDX,
    YES_IDX,
    YES_NO_OPTIONS,
)
from .data import ActionData, ActionType, PipelineStep, PollData
from .helpers import get_db, log_format_action

logger = logging.getLogger(__name__)
lock = asyncio.Lock()


async def start_poll(ctx: CallbackContext, action: ActionData) -> PipelineStep:
    message = await ctx.bot.send_poll(
        action.chat_id,
        f"{action.action_type.lower().capitalize()}?",
        YES_NO_OPTIONS,
        is_anonymous=False,
        allows_multiple_answers=False,
        reply_to_message_id=action.target_message_id,
    )
    poll_data = PollData(
        id=message.poll.id,
        options=YES_NO_OPTIONS,
        message_id=message.message_id,
        consensus=DEFAULT_CONSENSUS,
        win_result=None,
        votes=[],
    )
    await store_poll(get_db(ctx), action_data=action, poll_data=poll_data)
    return PipelineStep.POLL


async def check_poll_state(
    ctx: CallbackContext, action: ActionData
) -> PipelineStep:
    if action.poll is None:
        logger.error(f"Poll data not found: {action}")
        return PipelineStep.ERROR
    current_vote_results = calculate_poll_results(action)
    max_vote_count = max([0, *current_vote_results.values()])
    if max_vote_count >= action.poll.consensus:
        await ctx.bot.stop_poll(
            chat_id=action.chat_id, message_id=action.poll.message_id
        )
        logger.info("Poll is done, consensus reached")
        return PipelineStep.CONSENSUS
    logger.info("Poll is still running, keep current step")
    return action.step


def calculate_poll_results(action: ActionData) -> dict[int, int]:
    current_vote_results: dict[int, int] = defaultdict(int)
    if action.poll:
        for vote in action.poll.votes:
            for answer in vote.answer:
                current_vote_results[answer] += 1
    return current_vote_results


async def handle_consensus(
    ctx: CallbackContext, action: ActionData
) -> PipelineStep:
    if action.poll is None:
        logger.error(f"Poll data not found: {action.action_id}")
        return PipelineStep.ERROR
    results = calculate_poll_results(action)
    should_execute = results[YES_IDX] >= results[NO_IDX]
    logger.info(f"Poll results are ready: {results}")
    logger.info(f"Should execute: {should_execute}")
    await store_poll_result(get_db(ctx), action=action, result=should_execute)

    # cleanup poll and trigger
    await ctx.bot.delete_message(
        action.chat_id,
        action.poll.message_id,
    )
    await ctx.bot.delete_message(
        action.chat_id,
        action.trigger_message_id,
    )
    if should_execute:
        return PipelineStep.EXECUTE
    return PipelineStep.DONE


async def execute_action(
    ctx: CallbackContext, action: ActionData
) -> PipelineStep:
    match action.action_type:
        case ActionType.PIN:
            await ctx.bot.pin_chat_message(
                action.chat_id,
                action.target_message_id,
            )
        case ActionType.DELETE:
            await ctx.bot.delete_message(
                action.chat_id,
                action.target_message_id,
            )
        case ActionType.BAN:
            await ctx.bot.delete_message(
                action.chat_id,
                action.target_message_id,
            )
            duration = float(action.duration) if action.duration else 0
            await ctx.bot.ban_chat_member(
                action.chat_id,
                action.target_user_id,
                until_date=datetime.utcnow() + timedelta(seconds=duration),
            )
        case ActionType.PURGE:
            await ctx.bot.ban_chat_member(
                action.chat_id,
                action.target_user_id,
                until_date=0,
                revoke_messages=True,
            )
        case ActionType.MUTE:
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            )
            duration = float(action.duration) if action.duration else 0
            await ctx.bot.restrict_chat_member(
                action.chat_id,
                action.target_user_id,
                until_date=datetime.utcnow() + timedelta(seconds=duration),
                permissions=permissions,
            )
        case _:
            logger.warning("Not implemented yet")

    if action.duration:
        next_execution = datetime.utcnow() + timedelta(seconds=action.duration)
        await postpone_action(
            get_db(ctx),
            action_id=action.action_id,
            next_execution=next_execution,
        )

        return PipelineStep.REVERT
    return PipelineStep.DONE


async def execute_revert(ctx, action) -> PipelineStep:
    match action.action_type:
        case ActionType.PIN:
            try:
                await ctx.bot.unpin_chat_message(
                    action.chat_id,
                    action.target_message_id,
                )
            except telegram.error.BadRequest as e:
                match e.message:
                    case "Chat not found":
                        logger.warning(
                            f"Chat {action.chat_id} not found, skip unpin"
                        )
                    case "Message to unpin not found":
                        logger.warning(
                            "Message not found, probably unpinned by hand"
                        )
                        pass
                    case _:
                        logger.error("unhandled")
                        raise e

        case _:
            logger.warning("Not implemented yet")

    return PipelineStep.DONE


async def process_pipeline_step(
    ctx: CallbackContext, action: ActionData
) -> None:
    now = datetime.now(tz=UTC)
    if action.execute_at > now:
        logger.info(f"Not ready to execute\n {log_format_action(action)}")
        return

    current_step = action.step
    next_step = None
    match action.step:
        case PipelineStep.START:
            next_step = await start_poll(ctx, action)
        case PipelineStep.POLL:
            logger.debug("Start the poll")
            next_step = await check_poll_state(ctx, action)
        case PipelineStep.CONSENSUS:
            logger.debug(
                "Need to decide if we should execute base on consensus"
            )
            next_step = await handle_consensus(ctx, action)
        case PipelineStep.EXECUTE:
            try:
                next_step = await execute_action(ctx, action)
            except telegram.error.BadRequest as e:
                logger.exception("Failed to execute action")
                await report_error(ctx, action, e)
                next_step = PipelineStep.ERROR
            logger.debug("Execute action")
        case PipelineStep.REVERT:
            next_step = await execute_revert(ctx, action)
        case PipelineStep.DONE:
            logger.info(
                "Pipeline executed successfully", extra={"action": action}
            )

    if next_step:
        await change_step(
            get_db(ctx), action_id=action.action_id, step=next_step
        )
        if current_step != next_step:
            run_pipeline_now(ctx)
    else:
        logger.info("We are done with this action")


async def report_error(
    ctx: CallbackContext, action: ActionData, err: telegram.error.BadRequest
) -> None:
    await ctx.bot.send_message(
        chat_id=action.chat_id,
        text=f"Я попробовал, но чот не получается, сорян:\n\t{err.message}",
    )


async def execute_scheduled_actions(ctx: CallbackContext) -> None:
    logger.debug("Execute scheduled actions")
    async with lock:
        logger.info("Got lock")
        for action in await fetch_ready_actions(get_db(ctx)):
            logger.info(f"Got scheduled action: {log_format_action(action)}")
            await process_pipeline_step(ctx, action)
        logger.info("Processed tasks")
    logger.debug("Lock released")


def run_pipeline_now(ctx: CallbackContext) -> None:
    if not ctx.job_queue:
        raise RuntimeError("Job queue is required to run this bot")
    q = cast(JobQueue, ctx.job_queue)
    q.run_once(execute_scheduled_actions, when=0)
