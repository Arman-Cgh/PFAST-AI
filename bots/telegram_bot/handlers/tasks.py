from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

from services.tasks.service import TaskService


def build_tasks_keyboard(
    tasks,
):

    keyboard = []

    for task in tasks:

        task_id = task["id"]

        keyboard.append(
            [
                InlineKeyboardButton(
                    "✅ انجام شد",
                    callback_data=(
                        f"task:done:{task_id}"
                    ),
                ),
                InlineKeyboardButton(
                    "🔁 تکرار",
                    callback_data=(
                        f"task:repeat:{task_id}"
                    ),
                ),
                InlineKeyboardButton(
                    "🗑 حذف",
                    callback_data=(
                        f"task:delete:{task_id}"
                    ),
                ),
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔄 بروزرسانی",
                callback_data=(
                    "tasks:refresh"
                ),
            )
        ]
    )

    return InlineKeyboardMarkup(
        keyboard
    )


def format_due_date(
    due_date,
):

    if not due_date:
        return "بدون زمان"

    due_date = str(
        due_date
    ).strip()

    if not due_date:
        return "بدون زمان"

    try:

        if len(due_date) == 16:

            target = datetime.strptime(
                due_date,
                "%Y-%m-%d %H:%M",
            )

            return target.strftime(
                "%Y/%m/%d - %H:%M"
            )

        if len(due_date) == 10:

            target = datetime.strptime(
                due_date,
                "%Y-%m-%d",
            )

            return target.strftime(
                "%Y/%m/%d"
            )

    except ValueError:

        pass

    return due_date


def build_tasks_text(
    tasks,
):

    if not tasks:

        return (
            "📋 تسک‌های فعال شما\n\n"
            "در حال حاضر هیچ تسک فعالی ندارید.\n\n"
            "برای ساخت یادآوری کافی است مثلاً بنویسید:\n"
            "«یادم بنداز فردا ساعت ۱۰ "
            "با علی تماس بگیر»"
        )

    lines = [
        "📋 تسک‌های فعال شما",
        "",
    ]

    for index, task in enumerate(
        tasks,
        start=1,
    ):

        title = str(
            task.get(
                "title",
                "",
            )
        ).strip()

        due_date = format_due_date(
            task.get(
                "due_date"
            )
        )

        lines.append(
            f"{index}. {title}"
        )

        lines.append(
            f"🕐 {due_date}"
        )

        lines.append("")

    lines.append(
        "برای هر تسک از دکمه‌های زیر استفاده کنید."
    )

    return "\n".join(
        lines
    )


async def send_tasks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return

    user_id = (
        update.effective_user.id
    )

    tasks = TaskService.get_pending(
        user_id
    )

    text = build_tasks_text(
        tasks
    )

    keyboard = (
        build_tasks_keyboard(
            tasks
        )
        if tasks
        else None
    )

    if update.callback_query:

        await update.callback_query.edit_message_text(
            text,
            reply_markup=keyboard,
        )

    elif update.message:

        await update.message.reply_text(
            text,
            reply_markup=keyboard,
        )


async def tasks_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await send_tasks(
        update,
        context,
    )