class Personality:

    def __init__(
        self,
        profile: dict = None,
        memory=None,
        state: dict = None,
    ):

        self.profile = (
            profile
            if isinstance(profile, dict)
            else {}
        )

        self.memory = self.format_memory(
            memory
        )

        self.state = (
            state
            if isinstance(state, dict)
            else {}
        )


    def format_memory(
        self,
        memory
    ):

        if isinstance(memory, dict):

            lines = []

            for key, value in memory.items():

                if value is not None:

                    lines.append(
                        f"- {key}: {value}"
                    )

            return "\n".join(lines)


        return str(
            memory or ""
        )


    def build(self):

        name = self.extract_memory(
            "name"
        )

        if not name:

            name = self.profile.get(
                "first_name",
                ""
            )


        job = self.extract_memory(
            "job"
        )


        interests = self.extract_memory(
            "interests"
        )


        lines = [
            "اطلاعات کاربر:"
        ]


        if name:

            lines.append(
                f"نام: {name}"
            )


        if job:

            lines.append(
                f"شغل: {job}"
            )


        if interests:

            lines.append(
                f"علاقه‌مندی‌ها: {interests}"
            )


        return "\n".join(
            lines
        )


    def extract_memory(
        self,
        key,
    ):

        key = str(
            key
        ).lower().strip()


        for line in self.memory.split("\n"):

            clean = (
                line
                .replace("-", "")
                .strip()
            )


            if ":" not in clean:
                continue


            current_key, value = clean.split(
                ":",
                1
            )


            if (
                current_key.strip().lower()
                ==
                key
            ):

                return value.strip()


        return ""