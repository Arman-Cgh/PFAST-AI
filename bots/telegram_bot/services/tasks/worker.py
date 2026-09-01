import asyncio
import logging

from services.tasks.manager import TaskManager

logger = logging.getLogger(__name__)


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
                user_id = task[
                    "user_id"
                ]

                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=(
                            "⏰ یادآوری\n\n"
                            f"📌 {task['title']}\n"
                            f"🕐 {task['due_date']}"
                        ),
                    )

                    completed = await asyncio.to_thread(
                        TaskManager.complete,
                        task["id"],
                        user_id,
                    )

                    if completed:
                        logger.info(
                            "Reminder sent successfully: task_id=%s user_id=%s",
                            task["id"],
                            user_id,
                        )

                except Exception as exc:
                    logger.exception(
                        "Failed to send reminder for task_id=%s to user_id=%s: %s",
                        task.get("id"),
                        user_id,
                        exc,
                    )

            return True
        finally:
            self._is_checking = False