import asyncio
import logging

try:
    from telegram.error import (
        BadRequest,
        Forbidden,
        NetworkError,
        RetryAfter,
        TelegramError,
        TimedOut,
    )
except ImportError:
    class TelegramError(Exception):
        pass

    class BadRequest(TelegramError):
        pass

    class Forbidden(TelegramError):
        pass

    class NetworkError(TelegramError):
        pass

    class RetryAfter(TelegramError):
        retry_after = 5

    class TimedOut(TelegramError):
        pass


from services.tasks.manager import TaskManager

logger = logging.getLogger(__name__)


def is_permanent_chat_error(exc: Exception) -> bool:
    """
    Determines if an exception indicates a permanent unreachable chat condition
    (e.g., chat not found, user blocked bot, user deactivated, invalid ID).
    """
    if isinstance(exc, Forbidden):
        return True

    msg = str(exc).lower()

    if isinstance(exc, BadRequest):
        if any(marker in msg for marker in (
            "chat not found",
            "user not found",
            "peer_id_invalid",
            "chat_id_is_empty",
            "invalid user_id",
            "have no rights",
            "group chat was upgraded",
            "deactivated",
            "bot can't initiate conversation",
            "bot can't send messages to bots",
        )):
            return True

    if any(marker in msg for marker in (
        "chat not found",
        "bot was blocked",
        "user is deactivated",
        "peer_id_invalid",
    )):
        return True

    return False


class TaskWorker:

    def __init__(
        self,
        bot,
    ):
        self.bot = bot
        self.running = True
        self._is_checking = False

    async def start(
        self,
    ):
        logger.info("TaskWorker background daemon started")

        while self.running:
            try:
                await self.check_tasks()
            except Exception as exc:
                logger.exception(
                    "TaskWorker unexpected polling error: %s",
                    exc,
                )

            await asyncio.sleep(
                30
            )

    async def check_tasks(
        self,
    ):
        if self._is_checking:
            logger.debug("TaskWorker: check_tasks already in progress; skipping overlapping run.")
            return False

        self._is_checking = True
        try:
            tasks = await asyncio.to_thread(
                TaskManager.get_due_tasks
            )

            if not tasks:
                return True

            logger.info(
                "Due reminders found: count=%d",
                len(tasks),
            )

            for task in tasks:
                user_id = task.get("user_id")
                task_id = task.get("id")

                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=(
                            "⏰ یادآوری\n\n"
                            f"📌 {task.get('title', '')}\n"
                            f"🕐 {task.get('due_date', '')}"
                        ),
                    )

                    completed = await asyncio.to_thread(
                        TaskManager.complete,
                        task_id,
                        user_id,
                    )

                    if completed:
                        logger.info(
                            "Reminder sent successfully: task_id=%s user_id=%s",
                            task_id,
                            user_id,
                        )

                except Exception as exc:
                    if is_permanent_chat_error(exc):
                        logger.warning(
                            "Unreachable Telegram chat for task_id=%s user_id=%s: %s. Dismissing task.",
                            task_id,
                            user_id,
                            exc,
                        )
                        # Dismiss permanent failure so it does not poison future checks or startup
                        await asyncio.to_thread(
                            TaskManager.complete,
                            task_id,
                            user_id,
                        )

                    elif isinstance(exc, RetryAfter):
                        retry_sec = getattr(exc, "retry_after", 5)
                        logger.warning(
                            "Telegram rate limit hit while sending task_id=%s: retry after %ss",
                            task_id,
                            retry_sec,
                        )
                        await asyncio.sleep(retry_sec)

                    elif isinstance(exc, (TimedOut, NetworkError)):
                        logger.warning(
                            "Transient network error sending reminder task_id=%s to user_id=%s: %s (will retry)",
                            task_id,
                            user_id,
                            exc,
                        )

                    else:
                        logger.exception(
                            "Unexpected error sending reminder for task_id=%s to user_id=%s: %s",
                            task_id,
                            user_id,
                            exc,
                        )

            return True
        finally:
            self._is_checking = False