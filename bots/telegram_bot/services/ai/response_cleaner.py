BLOCKED_PHRASES = (
    "من PF-AI هستم",
    "من یک دستیار هوشمند هستم",
    "من یک مدل هوش مصنوعی هستم",
    "این را به خاطر دارم",
    "این را به خاطر سپردم",
    "من به یاد دارم",
)


def clean_response(
    response: str,
    user_message: str = ""
):

    if not response:
        return response


    identity_question = any(
        word in user_message.lower()
        for word in (
            "اسمت",
            "نامت",
            "کی هستی",
            "هویت",
            "سازنده",
        )
    )


    if identity_question:
        return response.strip()


    for phrase in BLOCKED_PHRASES:

        response = response.replace(
            phrase,
            ""
        )


    return response.strip()