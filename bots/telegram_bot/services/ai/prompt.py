from .config import SYSTEM_PROMPT
from .personality import Personality

import json


MAX_HISTORY_MESSAGES = 10


BLOCKED_HISTORY_PHRASES = (
    "من PF-AI هستم",
    "من یک دستیار هوشمند هستم",
    "من یک هوش مصنوعی هستم",
    "این را به خاطر دارم",
    "این را به خاطر سپردم",
    "من به یاد دارم",
    "AetherAI",
)


CODE_MODE_RULES = """
قوانین حالت کدنویسی:

- مثل یک برنامه‌نویس حرفه‌ای پاسخ بده.
- اگر کد خواسته شد، کد کامل و قابل اجرا بده.
- برای کد از Markdown استفاده کن.
- اگر خطا وجود دارد ابتدا علت را مشخص کن.
- اطلاعات فنی را حدس نزن.
- اگر اطلاعات کافی نیست فقط سوال ضروری بپرس.
"""


def clean_history(history):

    result = []

    for item in history or []:

        if not isinstance(item, dict):
            continue


        content = item.get(
            "content",
            ""
        )


        if not content:
            continue


        content = str(content)


        if any(
            phrase in content
            for phrase in BLOCKED_HISTORY_PHRASES
        ):
            continue


        result.append(
            {
                "role": str(
                    item.get(
                        "role",
                        "user"
                    )
                ),
                "content": content,
            }
        )


    return result



def build_prompt(
    user_id=None,
    user_message="",
    profile=None,
    history=None,
    memory="",
    state=None,
    current_time="",
    context=None,
    datetime=None,
    intent="chat",
):


    project = ""


    if context:

        project = context.get(
            "project",
            ""
        )


        profile = context.get(
            "profile",
            profile
        )


        history = context.get(
            "history",
            history
        )


        memory = context.get(
            "memory",
            memory
        )


        state = context.get(
            "state",
            state
        )


        current_time = context.get(
            "datetime",
            current_time
        )



    if datetime:
        current_time = datetime



    intent = str(
        intent or "chat"
    ).lower().strip()



    personality = Personality(
        profile=profile,
        memory=memory,
        state=state
    ).build()



    if isinstance(memory, dict):

        memory_text = "\n".join(
            [
                f"- {k}: {v}"
                for k, v in memory.items()
                if v
            ]
        )

    else:

        memory_text = (
            str(memory)
            if memory
            else
            "حافظه‌ای ثبت نشده است."
        )



    profile_text = json.dumps(
        profile or {},
        ensure_ascii=False
    )


    state_text = json.dumps(
        state or {},
        ensure_ascii=False
    )



    history = clean_history(
        history
    )


    if intent == "code":

        history = history[-3:]

    elif intent == "task":

        history = history[-2:]

    elif intent == "memory":

        history = []

    else:

        history = history[-MAX_HISTORY_MESSAGES:]



    history_text = "\n".join(
        [
            f"{x['role']}: {x['content']}"
            for x in history
        ]
    )


    if not history_text:
        history_text = "تاریخچه‌ای وجود ندارد."



    mode_rules = (
        CODE_MODE_RULES
        if intent == "code"
        else ""
    )



    system_message = f"""

{SYSTEM_PROMPT}


حالت:
{intent}


{mode_rules}


اطلاعات کاربر:
{profile_text}


شخصیت:
{personality}


وضعیت:
{state_text}


حافظه:
{memory_text}


اطلاعات پروژه:
{project}
اگر اطلاعات پروژه در بخش بالا وجود دارد، آن را به عنوان مرجع معتبر استفاده کن و درباره نداشتن دسترسی به پروژه صحبت نکن.


زمان:
{current_time}


تاریخچه:
{history_text}

"""


    return [
        {
            "role": "system",
            "content": system_message.strip()
        },
        {
            "role": "user",
            "content": user_message
        }
    ]