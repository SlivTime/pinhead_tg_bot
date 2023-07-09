import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import cast

from telegram.ext import CallbackContext, JobQueue

from constants import YES_NO_OPTIONS
from data import ActionData, ActionType, PipelineStep, PollData
from helpers import (
    find_poll_data,
    iterate_scheduled_actions,
    remove_action,
    remove_poll,
    store_action,
    store_poll,
)

logger = logging.getLogger(__name__)
lock = asyncio.Lock()


async def start_poll(
    ctx: CallbackContext, action: ActionData
) -> tuple[ActionData, PipelineStep]:
    message = await ctx.bot.send_poll(
        action.chat_id,
        f"{action.action_type.lower().capitalize()}?",
        YES_NO_OPTIONS,
        is_anonymous=False,
        allows_multiple_answers=False,
        reply_to_message_id=action.target_id,
    )
    poll_data = PollData(
        id=message.poll.id,
        action_id=action.id,
        options=YES_NO_OPTIONS,
        message_id=message.message_id,
        chat_id=action.chat_id,
        yes=0,
        no=0,
    )
    await store_poll(ctx=ctx, poll_data=poll_data)
    action.poll_id = poll_data.id
    return action, PipelineStep.POLL


async def check_poll_state(ctx, action) -> tuple[ActionData, PipelineStep]:
    poll_data = find_poll_data(ctx, action.poll_id)
    if poll_data is None:
        logger.error(f"Poll data not found: {action.poll_id}")
        return action, PipelineStep.ERROR
    max_vote_count = max([poll_data.yes, poll_data.no])
    if max_vote_count >= action.consensus:
        await ctx.bot.stop_poll(
            chat_id=poll_data.chat_id, message_id=poll_data.message_id
        )
        logger.info("Poll is done, consensus reached")
        return action, PipelineStep.CONSENSUS
    logger.info("Poll is still running, keep current step")
    return action, action.step


async def handle_consensus(ctx, action) -> tuple[ActionData, PipelineStep]:
    poll_data = find_poll_data(ctx, action.poll_id)
    if poll_data is None:
        logger.error(f"Poll data not found: {action.poll_id}")
        return action, PipelineStep.ERROR
    if poll_data.yes > poll_data.no:
        action.poll_decision = True
        return action, PipelineStep.EXECUTE
    else:
        action.poll_decision = False
        return action, PipelineStep.DONE


async def execute_action(ctx, action) -> tuple[ActionData, PipelineStep]:
    match action.action_type:
        case ActionType.PIN:
            await ctx.bot.pin_chat_message(
                action.chat_id,
                action.target_id,
            )
        case ActionType.DELETE:
            await ctx.bot.delete_message(
                action.chat_id,
                action.target_id,
            )
        case ActionType.BAN:
            await ctx.bot.ban_chat_member(
                action.chat_id,
                action.target_id,
                until_date=datetime.now(tz=UTC)
                + timedelta(seconds=action.duration),
            )
        case ActionType.PURGE:
            await ctx.bot.ban_chat_member(
                action.chat_id,
                action.target_id,
                until_date=0,
                revoke_messages=True,
            )
        case ActionType.MUTE:
            await ctx.bot.restrict_chat_member(
                action.chat_id,
                action.target_id,
                until_date=datetime.now(tz=UTC)
                + timedelta(seconds=action.duration),
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            )
        case _:
            logger.warning("Not implemented yet")

    if action.duration:
        action.execute_at = datetime.now(tz=UTC) + timedelta(
            seconds=action.duration
        )
        return action, PipelineStep.REVERT
    return action, PipelineStep.DONE


async def execute_revert(ctx, action) -> tuple[ActionData, PipelineStep]:
    match action.action_type:
        case ActionType.PIN:
            await ctx.bot.unpin_chat_message(
                action.chat_id,
                action.target_id,
            )
        case _:
            logger.warning("Not implemented yet")

    return action, PipelineStep.DONE


async def cleanup(ctx, action) -> None:
    logger.info(f"Cleanup action: {action}")
    poll_data = find_poll_data(ctx, action.poll_id)
    if poll_data:
        await remove_poll(ctx, poll_data)
    await remove_action(ctx, action)


async def process_pipeline_step(
    ctx: CallbackContext, action: ActionData
) -> None:
    now = datetime.now(tz=UTC)
    print(now)
    print(action.execute_at)
    if action.execute_at > now:
        logger.info(f"Action {action.id} is not ready to execute")
        return

    next_step = None
    match action.step:
        case PipelineStep.START:
            action, next_step = await start_poll(ctx, action)
        case PipelineStep.POLL:
            logger.debug("Start the poll")
            action, next_step = await check_poll_state(ctx, action)
        case PipelineStep.CONSENSUS:
            logger.debug(
                "Need to decide if we should execute base on consensus"
            )
            action, next_step = await handle_consensus(ctx, action)
        case PipelineStep.EXECUTE:
            action, next_step = await execute_action(ctx, action)
            logger.debug("Execute action")
        case PipelineStep.REVERT:
            action, next_step = await execute_revert(ctx, action)
        case PipelineStep.DONE:
            await cleanup(ctx, action)

    if next_step:
        action.step = next_step
        await store_action(ctx, action)
        run_pipeline_now(ctx)
    else:
        logger.info("We are done with this action")


async def execute_scheduled_actions(ctx: CallbackContext) -> None:
    logger.info("Execute scheduled actions")
    async with lock:
        logger.info("Got lock")
        await asyncio.sleep(2)
        logger.info("Sleep done")
        for action in iterate_scheduled_actions(ctx.bot_data):
            logger.info(f"Got scheduled jobs: {action}")
            await process_pipeline_step(ctx, action)
        logger.info("Processed tasks")

    logger.info("Lock released")


def run_pipeline_now(ctx: CallbackContext) -> None:
    if not ctx.job_queue:
        raise RuntimeError("Job queue is required to run this bot")
    q = cast(JobQueue, ctx.job_queue)
    q.run_once(execute_scheduled_actions, when=0)
