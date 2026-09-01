import logging

from services.tasks.service import TaskService


logger = logging.getLogger(
    __name__
)


class TaskPipeline:

    @staticmethod
    def execute(
        user_id: int,
        message: str,
        intent,
    ):

        try:

            result = TaskService.create(
                user_id=user_id,
                message=message,
            )

            due_date = (
                result.get(
                    "due_date"
                )
                or ""
            ).strip()

            response_lines = [
                "✅ یادآوری ثبت شد",
                "",
                (
                    f"📝 "
                    f"{result.get('title', '')}"
                ),
            ]

            if due_date:

                response_lines.append(
                    f"🕐 {due_date}"
                )

            else:

                response_lines.append(
                    "🕐 بدون زمان"
                )

            return {
                "response": "\n".join(
                    response_lines
                ),
                "cached": False,
                "intent": (
                    intent.to_dict()
                    if (
                        intent
                        and hasattr(
                            intent,
                            "to_dict",
                        )
                    )
                    else {}
                ),
                "provider": "task",
            }

        except ValueError as exc:

            logger.warning(
                "Task validation error: %s",
                exc,
            )

            return {
                "response": (
                    f"⚠️ {str(exc)}"
                ),
                "cached": False,
                "intent": (
                    intent.to_dict()
                    if (
                        intent
                        and hasattr(
                            intent,
                            "to_dict",
                        )
                    )
                    else {}
                ),
                "provider": "task",
            }

        except Exception:

            logger.exception(
                "Task pipeline failed"
            )

            return {
                "response": (
                    "❌ خطا در ثبت یادآوری"
                ),
                "cached": False,
                "intent": (
                    intent.to_dict()
                    if (
                        intent
                        and hasattr(
                            intent,
                            "to_dict",
                        )
                    )
                    else {}
                ),
                "provider": "task",
            }