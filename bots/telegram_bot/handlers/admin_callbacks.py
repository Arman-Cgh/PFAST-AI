from telegram import Update
from telegram.ext import ContextTypes

from handlers.admin.actions import handle_actions_callback
from handlers.admin.ban import handle_ban_callback
from handlers.admin.broadcast import handle_broadcast_callback
from handlers.admin.features import handle_features_callback
from handlers.admin.mandatory_join import handle_mandatory_join_callback
from handlers.admin.payments import handle_payments_callback
from handlers.admin.plans import handle_plans_callback
from handlers.admin.settings import handle_settings_callback
from handlers.admin.stats import handle_stats_callback
from handlers.admin.subscriptions import handle_subscriptions_callback
from handlers.admin.users import handle_users_callback
from config import ADMIN_ID, is_admin
from handlers.admin.menu import get_admin_menu


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی ندارید.")
        return

    data = query.data or ""

    if data == "admin":
        await query.edit_message_text(
            "🛠 پنل مدیریت PFAST_AI",
            reply_markup=get_admin_menu(),
        )
        return

    handlers = (
        handle_subscriptions_callback,
        handle_users_callback,
        handle_plans_callback,
        handle_payments_callback,
        handle_settings_callback,
        handle_mandatory_join_callback,
        handle_broadcast_callback,
        handle_ban_callback,
        handle_actions_callback,
        handle_stats_callback,
        handle_features_callback,
    )

    for handler in handlers:
        if await handler(update, context, data):
            return

    await query.edit_message_text(
        "❓ دستور مدیریتی ناشناخته است.",
        reply_markup=get_admin_menu(),
    )
