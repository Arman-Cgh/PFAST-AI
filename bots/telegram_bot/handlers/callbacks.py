from telegram import Update
from telegram.ext import ContextTypes

from config import is_admin
from handlers.admin_callbacks import admin_callback
from handlers.user_callbacks import user_callback


async def callback_dispatcher(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.callback_query.from_user.id

    if is_admin(user_id):
        await admin_callback(update, context)
        return

    await user_callback(update, context)
