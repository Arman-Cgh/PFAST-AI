import datetime
import logging

from services.ai.memory import MemoryService
from services.ai.profile_manager import ProfileManager
from services.ai.context_optimizer import ContextOptimizer

from database.db import get_history

logger = logging.getLogger(__name__)


BLOCKED_HISTORY_PHRASES = (
    "من PF-AI هستم",
    "من یک دستیار هوشمند هستم",
    "من یک هوش مصنوعی هستم",
    "این را به خاطر دارم",
    "این را به خاطر سپردم",
)


class ContextBuilder:


    def __init__(
        self,
        user_id: int
    ):
        self.user_id = user_id



    def _build_project_context(self):

        return """
پروژه PFAST_AI

نوع پروژه:
دستیار هوشمند تلگرام مبتنی بر هوش مصنوعی


Technology Stack:

- Python
- python-telegram-bot
- Async architecture
- SQLite database
- OpenAI compatible AI providers


ساختار کلی:

handlers/
- مدیریت پیام‌ها و دستورات تلگرام


services/ai/
- AI Engine
- Context Builder
- Prompt Builder
- Memory System
- Provider Manager
- AI Providers


services/tasks/
- Task Manager
- Reminder System
- Background Worker


database/
- Users
- Messages
- Memory
- User State


AI Providers:

- Groq
- OpenRouter
- Tabitoken Claude


قوانین معماری:

- Provider ها مستقل از Engine هستند.
- Context قبل از ارسال به مدل ساخته می‌شود.
- Memory و Profile کاربر ذخیره می‌شوند.
- Task و Reminder سیستم جدا هستند.
"""



    def _build_memory(self):

        try:

            memory = MemoryService.get_memory(
                self.user_id
            )

        except Exception:

            memory = {}


        return memory or {}



    def _build_history(self):

        try:

            history = get_history(
                self.user_id,
                limit=10
            )

        except Exception:

            history = []


        normalized = []


        for item in history:


            if isinstance(item, tuple):

                if len(item) < 2:
                    continue

                role = item[0]
                content = item[1]


            elif isinstance(item, dict):

                role = item.get(
                    "role",
                    ""
                )

                content = item.get(
                    "content",
                    item.get(
                        "message",
                        ""
                    )
                )


            else:

                continue



            if not content:
                continue


            content = str(content)


            if any(
                phrase in content
                for phrase in BLOCKED_HISTORY_PHRASES
            ):
                continue



            normalized.append(
                {
                    "role": str(role),
                    "content": content
                }
            )


        return normalized



    def build(
        self,
        intent="chat",
        user_message=""
    ):

        context = {}



        try:

            profile = ProfileManager.get(
                self.user_id
            )

        except Exception:

            profile = {}



        context["profile"] = (
            profile or {}
        )



        context["memory"] = (
            self._build_memory()
        )



        if intent not in (
            "code",
            "memory"
        ):

            context["history"] = (
                self._build_history()
            )

        else:

            context["history"] = []



        try:

            state = MemoryService.get_state(
                self.user_id
            )

        except Exception:

            state = {}



        context["state"] = (
            state or {}
        )



        # فقط حالت واقعی توسعه پروژه
        # باعث مصرف توکن اضافه نمی‌شود

        if intent in (
            "code",
            "architecture"
        ):

            context["project"] = (
                self._build_project_context()
            )

        else:

            context["project"] = ""



        try:

            context = ContextOptimizer.optimize(
                context,
                intent
            )

        except Exception:
            logger.warning(
                "ContextOptimizer failed for user %s; "
                "using unoptimized context",
                self.user_id,
            )



        context["datetime"] = (
            datetime.datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M"
            )
        )


        return context