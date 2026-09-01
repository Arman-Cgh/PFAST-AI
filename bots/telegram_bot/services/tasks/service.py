from datetime import datetime, timedelta

from services.tasks.manager import TaskManager
from services.tasks.parser import TaskParser
from services.tasks.reminder import ReminderEngine


class TaskService:

    # ==========================
    # Create
    # ==========================

    @staticmethod
    def create(
        user_id: int,
        message: str,
    ):

        if not message or not message.strip():

            raise ValueError(
                "متن یادآوری خالی است."
            )

        data = TaskParser.parse(
            message
        )

        if not isinstance(data, dict):

            raise ValueError(
                "اطلاعات یادآوری قابل تشخیص نیست."
            )

        title = data.get(
            "title"
        )

        if (
            not title
            or not isinstance(title, str)
            or not title.strip()
            or len(title.strip()) < 3
        ):

            raise ValueError(
                "عنوان یادآوری معتبر نیست."
            )

        due_date = data.get(
            "due_date"
        )

        due_time = data.get(
            "due_time"
        )

        if due_date and due_time:

            final_due_date = (
                f"{due_date} {due_time}"
            )

        else:

            final_due_date = due_date

        task_id = TaskManager.create(
            user_id=user_id,
            title=title.strip(),
            description="",
            due_date=final_due_date,
        )

        return {
            "id": task_id,
            "title": title.strip(),
            "due_date": final_due_date,
        }

    # ==========================
    # Pending
    # ==========================

    @staticmethod
    def get_pending(
        user_id: int,
    ):

        return TaskManager.get_pending(
            user_id
        )

    # ==========================
    # All
    # ==========================

    @staticmethod
    def get_all(
        user_id: int,
    ):

        return TaskManager.get_all(
            user_id
        )

    # ==========================
    # Get One
    # ==========================

    @staticmethod
    def get(
        task_id: int,
        user_id: int,
    ):

        return TaskManager.get_by_id(
            task_id,
            user_id,
        )

    # ==========================
    # Due
    # ==========================

    @staticmethod
    def get_due(
        user_id: int,
    ):

        return ReminderEngine.get_due_tasks(
            user_id
        )

    # ==========================
    # Complete
    # ==========================

    @staticmethod
    def complete(
        task_id: int,
        user_id: int,
    ):

        return TaskManager.complete(
            task_id,
            user_id,
        )

    # ==========================
    # Delete
    # ==========================

    @staticmethod
    def delete(
        task_id: int,
        user_id: int,
    ):

        return TaskManager.delete(
            task_id,
            user_id,
        )

    # ==========================
    # Repeat
    # ==========================

    @staticmethod
    def repeat(
        task_id: int,
        user_id: int,
        repeat_type: str,
    ):

        task = TaskManager.get_by_id(
            task_id,
            user_id,
        )

        if not task:
            return None

        due_date = (
            task.get("due_date")
            or ""
        ).strip()

        if not due_date:
            return None

        target = None

        # ==========================
        # Parse existing datetime
        # ==========================

        try:

            target = datetime.strptime(
                due_date,
                "%Y-%m-%d %H:%M"
            )

        except ValueError:

            try:

                target = datetime.strptime(
                    due_date,
                    "%Y-%m-%d"
                )

            except ValueError:

                return None

        # ==========================
        # Calculate next occurrence
        # ==========================

        if repeat_type == "tomorrow":

            target += timedelta(
                days=1
            )

        elif repeat_type == "week":

            target += timedelta(
                days=7
            )

        elif repeat_type == "month":

            # Approximation of one month.
            # Calendar-aware recurrence will be
            # implemented later when recurrence
            # becomes a persistent DB feature.
            target += timedelta(
                days=30
            )

        else:

            return None

        # ==========================
        # Preserve datetime format
        # ==========================

        if " " in due_date:

            next_due_date = target.strftime(
                "%Y-%m-%d %H:%M"
            )

        else:

            next_due_date = target.strftime(
                "%Y-%m-%d"
            )

        # ==========================
        # Create next task
        # ==========================

        new_task_id = TaskManager.create(
            user_id=user_id,
            title=task["title"],
            description=task.get(
                "description",
                ""
            ),
            due_date=next_due_date,
        )

        return {
            "id": new_task_id,
            "title": task["title"],
            "due_date": next_due_date,
            "source_id": task["id"],
        }