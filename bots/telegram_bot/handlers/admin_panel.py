from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID, is_admin
from handlers.admin.menu import get_admin_menu


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message

    if not user or not message:
        return

    if not is_admin(user.id):
        await message.reply_text("⛔ دسترسی ندارید.")
        return

    await message.reply_text(
        "🛠 پنل مدیریت PFAST_AI",
        reply_markup=get_admin_menu(),
    )
