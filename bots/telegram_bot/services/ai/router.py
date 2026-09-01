from services.ai.config import AI_PROVIDER


class AIRouter:


    COMPLEX_KEYWORDS = [

        # English
        "code",
        "python",
        "javascript",
        "java",
        "debug",
        "error",
        "exception",
        "architecture",
        "database",
        "api",
        "server",
        "docker",
        "linux",
        "deploy",
        "refactor",
        "algorithm",
        "security",


        # Persian
        "کد",
        "برنامه نویسی",
        "برنامه‌نویسی",
        "خطا",
        "ارور",
        "دیباگ",
        "معماری",
        "دیتابیس",
        "پایگاه داده",
        "ای پی آی",
        "سرور",
        "داکر",
        "لینوکس",
        "دیپلوی",
        "ریفکتور",
        "الگوریتم",
        "امنیت",
    ]


    SIMPLE_KEYWORDS = [

        "سلام",
        "خوبی",
        "مرسی",
        "ممنون",
        "خداحافظ",
        "hello",
        "hi",
        "thanks",

    ]


    def select_provider(
        self,
        message: str
    ):


        text = message.lower()


        for keyword in self.COMPLEX_KEYWORDS:

            if keyword in text:

                return "tabitoken"


        for keyword in self.SIMPLE_KEYWORDS:

            if keyword in text:

                return "groq"


        # پیش فرض
        return "groq"