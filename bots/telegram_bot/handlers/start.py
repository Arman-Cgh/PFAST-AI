import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from config import (
    BOT_NAME,
    BOT_CREATOR,
)

from database.db import (
    add_user,
    create_referral,
    get_referral_settings,
    get_user_referral_stats,
)

from handlers.user_callbacks import (
    get_main_keyboard,
)

from handlers.mandatory_join import (
    require_mandatory_join,
)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    # ==========================================
    # User registration / update
    # ==========================================

    try:
        await asyncio.to_thread(
            add_user,
            user.id,
            user.username or "",
            user.first_name or "",
        )
    except Exception:
        # Registration failure must not crash Telegram update handling.
        pass

    # ==========================================
    # Mandatory join gate
    #
    # Referral is registered only after the user
    # passes the mandatory-join requirement.
    # ==========================================

    if not await require_mandatory_join(
        update,
        context,
    ):
        return

    # ==========================================
    # Referral registration
    # ==========================================

    if context.args:
        payload = str(
            context.args[0]
        ).strip()

        if payload.startswith("ref_"):
            raw_inviter_id = payload.split(
                "_",
                1,
            )[1].strip()

            try:
                inviter_id = int(
                    raw_inviter_id
                )
            except (
                ValueError,
                TypeError,
            ):
                inviter_id = None

            if (
                inviter_id
                and inviter_id != user.id
            ):
                try:
                    before_stats = (
                        get_user_referral_stats(
                            inviter_id
                        )
                    )

                    created = create_referral(
                        inviter_id,
                        user.id,
                    )

                except Exception:
                    # Invalid/missing inviter or DB issue must never
                    # break the invited user's /start flow.
                    created = False
                    before_stats = {}

                if created:
                    try:
                        settings = (
                            get_referral_settings()
                        )

                        stats = (
                            get_user_referral_stats(
                                inviter_id
                            )
                        )

                        total_invites = int(
                            stats.get(
                                "invites",
                                0,
                            )
                            or 0
                        )

                        required_invites = int(
                            settings.get(
                                "required_invites",
                                3,
                            )
                            or 3
                        )

                        previous_reward_count = int(
                            before_stats.get(
                                "rewarded",
                                before_stats.get(
                                    "rewards",
                                    0,
                                ),
                            )
                            or 0
                        )

                        current_reward_count = int(
                            stats.get(
                                "rewarded",
                                stats.get(
                                    "rewards",
                                    0,
                                ),
                            )
                            or 0
                        )

                        # Prevent division/modulo problems if
                        # bad referral settings exist.
                        if required_invites <= 0:
                            required_invites = 1

                        reward_just_activated = (
                            current_reward_count
                            > previous_reward_count
                        )

                        # ==========================================
                        # Reward activated
                        # ==========================================

                        if reward_just_activated:
                            await context.bot.send_message(
                                chat_id=inviter_id,
                                text=(
                                    "🎉 تبریک!\n\n"
                                    "یک دعوت موفق جدید ثبت شد "
                                    "و جایزه شما فعال شد.\n\n"
                                    f"👥 دعوت‌های موفق: "
                                    f"{total_invites}\n"
                                    f"🎁 پلن جایزه: "
                                    f"{str(settings.get('reward_plan', 'pro')).upper()}\n"
                                    f"⏳ مدت جایزه: "
                                    f"{int(settings.get('reward_days', 3) or 3)} روز"
                                ),
                            )

                        # ==========================================
                        # Normal successful referral
                        # ==========================================

                        else:
                            remainder = (
                                total_invites
                                % required_invites
                            )

                            if remainder == 0:
                                remaining = 0
                            else:
                                remaining = (
                                    required_invites
                                    - remainder
                                )

                            await context.bot.send_message(
                                chat_id=inviter_id,
                                text=(
                                    "🎉 یک دعوت موفق جدید!\n\n"
                                    f"👥 دعوت‌های موفق: "
                                    f"{total_invites}\n"
                                    f"🎯 هر {required_invites} دعوت "
                                    "یک جایزه دریافت می‌کنی.\n"
                                    f"🎁 {remaining} دعوت دیگر "
                                    "تا جایزه بعدی مانده."
                                ),
                            )

                    except Exception:
                        # Notification/reporting failure must never
                        # break the invited user's /start flow.
                        pass

    # ==========================================
    # Welcome
    # ==========================================

    text = (
        f"👋 سلام {user.first_name or 'دوست من'}!\n\n"
        f"🤖 به {BOT_NAME} خوش اومدی.\n\n"
        "من دستیار هوشمند شخصی تو هستم.\n\n"
        f"Made by: {BOT_CREATOR}"
    )

    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(),
    )

