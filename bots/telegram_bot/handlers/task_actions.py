from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

from services.tasks.service import TaskService
from handlers.tasks import send_tasks


def build_delete_confirmation(
    task_id: int,
):

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🗑 بله، حذف شود",
                    callback_data=f"task:delete_confirm:{task_id}",
                ),
                InlineKeyboardButton(
                    "❌ لغو",
                    callback_data="tasks:refresh",
                ),
            ]
        ]
    )


def build_repeat_keyboard(
    task_id: int,
):

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "فردا",
                    callback_data=f"task:repeat_apply:{task_id}:tomorrow",
                ),
                InlineKeyboardButton(
                    "هفته بعد",
                    callback_data=f"task:repeat_apply:{task_id}:week",
                ),
            ],
            [
                InlineKeyboardButton(
                    "ماه بعد",
                    callback_data=f"task:repeat_apply:{task_id}:month",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ لغو",
                    callback_data="tasks:refresh",
                ),
            ],
        ]
    )


async def done_task(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id

    if not context.args:

        await update.message.reply_text(
            "استفاده:\n/done task_id"
        )

        return

    try:

        task_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "شناسه تسک نامعتبر است."
        )

        return

    success = TaskService.complete(
        task_id,
        user_id,
    )

    if success:

        await update.message.reply_text(
            "✅ تسک انجام شد."
        )

    else:

        await update.message.reply_text(
            "❌ تسک پیدا نشد یا قبلاً انجام شده است."
        )


async def delete_task(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id

    if not context.args:

        await update.message.reply_text(
            "استفاده:\n/delete task_id"
        )

        return

    try:

        task_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "شناسه تسک نامعتبر است."
        )

        return

    success = TaskService.delete(
        task_id,
        user_id,
    )

    if success:

        await update.message.reply_text(
            "🗑 تسک حذف شد."
        )

    else:

        await update.message.reply_text(
            "❌ تسک پیدا نشد یا دسترسی ندارید."
        )


async def task_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    if not query.from_user:
        return

    user_id = query.from_user.id
    data = query.data or ""

    # ==========================
    # Refresh
    # ==========================

    if data == "tasks:refresh":

        await send_tasks(
            update,
            context,
        )

        return

    # ==========================
    # Done
    # ==========================

    if data.startswith("task:done:"):

        try:

            task_id = int(
                data.split(":")[2]
            )

        except (ValueError, IndexError):

            await query.answer(
                "شناسه تسک نامعتبر است.",
                show_alert=True,
            )

            return

        success = TaskService.complete(
            task_id,
            user_id,
        )

        if success:

            await query.answer(
                "✅ انجام شد."
            )

        else:

            await query.answer(
                "تسک پیدا نشد.",
                show_alert=True,
            )

        await send_tasks(
            update,
            context,
        )

        return

    # ==========================
    # Delete confirmation
    # ==========================

    if data.startswith("task:delete:"):

        try:

            task_id = int(
                data.split(":")[2]
            )

        except (ValueError, IndexError):

            await query.answer(
                "شناسه تسک نامعتبر است.",
                show_alert=True,
            )

            return

        task = TaskService.get(
            task_id,
            user_id,
        )

        if not task:

            await query.answer(
                "این تسک وجود ندارد.",
                show_alert=True,
            )

            await send_tasks(
                update,
                context,
            )

            return

        await query.edit_message_text(
            (
                "⚠️ حذف تسک\n\n"
                f"#{task['id']}  {task['title']}\n\n"
                "آیا مطمئن هستید که می‌خواهید این تسک حذف شود؟"
            ),
            reply_markup=build_delete_confirmation(
                task_id
            ),
        )

        return

    # ==========================
    # Delete confirmed
    # ==========================

    if data.startswith("task:delete_confirm:"):

        try:

            task_id = int(
                data.split(":")[2]
            )

        except (ValueError, IndexError):

            await query.answer(
                "شناسه تسک نامعتبر است.",
                show_alert=True,
            )

            return

        success = TaskService.delete(
            task_id,
            user_id,
        )

        if success:

            await query.answer(
                "🗑 حذف شد."
            )

        else:

            await query.answer(
                "تسک پیدا نشد.",
                show_alert=True,
            )

        await send_tasks(
            update,
            context,
        )

        return

    # ==========================
    # Repeat menu
    # ==========================

    if data.startswith("task:repeat:"):

        try:

            task_id = int(
                data.split(":")[2]
            )

        except (ValueError, IndexError):

            await query.answer(
                "شناسه تسک نامعتبر است.",
                show_alert=True,
            )

            return

        task = TaskService.get(
            task_id,
            user_id,
        )

        if not task:

            await query.answer(
                "این تسک وجود ندارد.",
                show_alert=True,
            )

            await send_tasks(
                update,
                context,
            )

            return

        await query.edit_message_text(
            (
                "🔁 تکرار تسک\n\n"
                f"#{task['id']}  {task['title']}\n"
                f"🕐 {task.get('due_date') or 'بدون زمان'}\n\n"
                "زمان اجرای بعدی را انتخاب کنید:"
            ),
            reply_markup=build_repeat_keyboard(
                task_id
            ),
        )

        return

    # ==========================
    # Repeat apply
    # ==========================

    if data.startswith("task:repeat_apply:"):

        parts = data.split(":")

        if len(parts) != 4:

            await query.answer(
                "درخواست نامعتبر است.",
                show_alert=True,
            )

            return

        try:

            task_id = int(
                parts[2]
            )

        except ValueError:

            await query.answer(
                "شناسه تسک نامعتبر است.",
                show_alert=True,
            )

            return

        repeat_type = parts[3]

        result = TaskService.repeat(
            task_id,
            user_id,
            repeat_type,
        )

        if not result:

            await query.answer(
                "امکان تکرار این تسک وجود ندارد.",
                show_alert=True,
            )

            await send_tasks(
                update,
                context,
            )

            return

        await query.answer(
            "🔁 تسک برای نوبت بعدی ساخته شد."
        )

        await send_tasks(
            update,
            context,
        )

        return