import asyncio

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from core.logger import logger

from database.db import init_db

from handlers.about import about
from handlers.admin_panel import admin_panel
from handlers.callbacks import callback_dispatcher
from handlers.clear import clear_memory
from handlers.help import help_command
from handlers.message import handle_message
from handlers.plan import plan_command
from handlers.profile import profile
from handlers.start import start
from handlers.tasks import tasks_command
from handlers.task_actions import (
    delete_task,
    done_task,
    task_callback,
)
from handlers.tech import tech_command

from handlers.user_callbacks import (
    buy_command,
    referral_command,
)

from services.ai.config import TELEGRAM_TOKEN
from services.ai.engine import AIEngine
from services.ai.pipeline.memory import MemoryPipeline
from services.tasks.worker import TaskWorker


async def configure_commands(
    application,
):
    commands = [
        BotCommand(
            "start",
            "شروع و منوی اصلی",
        ),
        BotCommand(
            "help",
            "راهنمای ربات",
        ),
        BotCommand(
            "tasks",
            "مشاهده تسک‌ها",
        ),
        BotCommand(
            "profile",
            "پروفایل من",
        ),
        BotCommand(
            "plan",
            "پلن و اشتراک",
        ),
        BotCommand(
            "buy",
            "خرید اشتراک",
        ),
        BotCommand(
            "referral",
            "دعوت از دوستان",
        ),
        BotCommand(
            "tech",
            "دستیار فنی",
        ),
        BotCommand(
            "clear",
            "پاک کردن حافظه گفتگو",
        ),
        BotCommand(
            "about",
            "درباره ربات",
        ),
    ]

    await application.bot.set_my_commands(
        commands
    )


async def telegram_error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    error = context.error

    if error is None:
        logger.error(
            "Telegram update failed without an exception. update=%r",
            update,
        )
        return

    logger.error(
        "Unhandled Telegram application error: %s",
        error,
        exc_info=(
            type(error),
            error,
            error.__traceback__,
        ),
    )

    if not isinstance(
        update,
        Update,
    ):
        return

    try:
        effective_message = (
            update.effective_message
        )

        if effective_message:
            await effective_message.reply_text(
                "⚠️ یک خطای موقت رخ داد. دوباره تلاش کنید."
            )

    except Exception:
        logger.exception(
            "Failed to send user-facing error message"
        )


async def post_init(
    application,
):
    await configure_commands(
        application
    )

    ai_engine = AIEngine()

    await ai_engine.initialize()

    application.bot_data[
        "ai_engine"
    ] = ai_engine

    worker = TaskWorker(
        application.bot
    )

    application.bot_data[
        "task_worker"
    ] = worker

    application.bot_data[
        "task_worker_task"
    ] = asyncio.create_task(
        worker.start()
    )

    logger.info(
        "Shared AI Engine and Task Worker started"
    )


async def post_shutdown(
    application,
):
    ai_engine = application.bot_data.get(
        "ai_engine"
    )

    if ai_engine:
        try:
            await ai_engine.shutdown()
        except Exception:
            logger.exception(
                "AI Engine shutdown failed"
            )

    try:
        await MemoryPipeline.stop()
    except Exception:
        logger.exception(
            "Memory Pipeline shutdown failed"
        )

    worker = application.bot_data.get(
        "task_worker"
    )

    if worker:
        try:
            worker.running = False
        except Exception:
            logger.exception(
                "Failed to stop Task Worker"
            )

    worker_task = application.bot_data.get(
        "task_worker_task"
    )

    if worker_task:
        try:
            worker_task.cancel()
            await worker_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception(
                "Task Worker shutdown failed"
            )

    logger.info(
        "PFAST_AI shutdown completed"
    )


def build_application():
    token = str(
        TELEGRAM_TOKEN or ""
    ).strip()

    if not token:
        raise RuntimeError(
            "TELEGRAM_TOKEN is not configured."
        )

    application = (
        Application
        .builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_error_handler(
        telegram_error_handler
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "admin",
            admin_panel,
        )
    )

    application.add_handler(
        CommandHandler(
            "plan",
            plan_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "tech",
            tech_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "profile",
            profile,
        )
    )

    application.add_handler(
        CommandHandler(
            "clear",
            clear_memory,
        )
    )

    application.add_handler(
        CommandHandler(
            "buy",
            buy_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "referral",
            referral_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "about",
            about,
        )
    )

    application.add_handler(
        CommandHandler(
            "tasks",
            tasks_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "done",
            done_task,
        )
    )

    application.add_handler(
        CommandHandler(
            "delete",
            delete_task,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            task_callback,
            pattern=r"^(task:|tasks:)",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            callback_dispatcher
        )
    )

    application.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_message,
        )
    )

    return application


def main():
    init_db()

    # ========================================================
    # 🛡 Pre-flight Startup Gate
    # ========================================================
    logger.info("Running startup pre-flight validation...")
    from services.system.preflight import StartupPreflight
    StartupPreflight.run_all(fail_fast=True)
    logger.info("Startup pre-flight validation PASSED.")

    application = build_application()

    logger.info(
        "Starting PFAST_AI Telegram Bot..."
    )

    application.run_polling()


if __name__ == "__main__":
    main()