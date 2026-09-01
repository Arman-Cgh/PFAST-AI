from telegram import Update
from telegram.ext import ContextTypes

from database.db import set_admin_action


def activate_image_mode(
    admin_id: int
):

    set_admin_action(
        admin_id,
        "image"
    )

    return (
        "🖼 ساخت عکس فعال شد.\n\n"
        "لطفاً متن یا توضیح تصویر را ارسال کنید."
    )


def activate_technical_mode(
    admin_id: int
):

    set_admin_action(
        admin_id,
        "technical"
    )

    return (
        "🧠 حالت دانش فنی فعال شد.\n\n"
        "حالا سوال یا مسئله فنی را ارسال کنید."
    )


async def handle_actions_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
):

    query = update.callback_query

    user_id = query.from_user.id


    if data == "image":

        message = activate_image_mode(
            user_id
        )

        await query.edit_message_text(
            message
        )

        return True


    if data == "technical":

        message = activate_technical_mode(
            user_id
        )

        await query.edit_message_text(
            message
        )

        return True


    return False