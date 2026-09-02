from services.ai.intents import IntentResult
from services.tasks.router import TaskRouter


class IntentRouter:

    MEMORY_KEYWORDS = (
        "یادت باشه",
        "یادت بمونه",
        "ذخیره کن",
        "به خاطر بسپار",
        "فراموش نکن",
        "remember this",
        "remember",
        "save this",
        "save",
    )

    CODE_KEYWORDS = (
        "python",
        "پایتون",
        "code",
        "کد",
        "برنامه نویسی",
        "برنامه‌نویسی",
        "programming",
        "function",
        "تابع",
        "class",
        "کلاس",
        "bug",
        "باگ",
        "debug",
        "دیباگ",
        "error",
        "ارور",
        "خطا",
        "exception",
        "استثنا",
        "api",
        "کتابخانه",
        "library",
        "framework",
        "فریمورک",
        "syntax",
        "سینتکس",
    )


    IMAGE_KEYWORDS = (
        "عکس بساز",
        "تصویر بساز",
        "عکس تولید کن",
        "تصویر تولید کن",
        "یک عکس از",
        "یک تصویر از",
        "تولید عکس",
        "تولید تصویر",
        "ساخت عکس",
        "ساخت تصویر",
        "generate image",
        "create image",
        "draw a",
        "draw an",
        "/image",
    )


    @staticmethod
    def detect(message: str):

        if not message:

            return IntentResult(
                intent="chat",
                confidence=0,
                source="default",
            )


        text = message.lower().strip()


        # ==========================
        # Task
        # ==========================

        task = TaskRouter.detect(
            message
        )

        if task:

            return IntentResult(
                intent="task",
                confidence=0.95,
                source="task_router",
            )


        # ==========================
        # Image
        # ==========================

        for keyword in IntentRouter.IMAGE_KEYWORDS:

            if keyword in text:

                return IntentResult(
                    intent="image_generation",
                    confidence=0.9,
                    source="keyword",
                )


        # ==========================
        # Memory
        # ==========================

        for keyword in IntentRouter.MEMORY_KEYWORDS:

            if keyword in text:

                return IntentResult(
                    intent="memory",
                    confidence=0.9,
                    source="keyword",
                )


        # ==========================
        # Code
        # ==========================

        for keyword in IntentRouter.CODE_KEYWORDS:

            if keyword in text:

                return IntentResult(
                    intent="code",
                    confidence=0.85,
                    source="keyword",
                )


        # ==========================
        # Default Chat
        # ==========================

        return IntentResult(
            intent="chat",
            confidence=0.5,
            source="default",
        )