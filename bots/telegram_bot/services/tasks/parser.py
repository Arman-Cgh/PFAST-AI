import re

from datetime import datetime, timedelta

from services.tasks.constants import (
    DATE_KEYWORDS,
    EMPTY_TITLE,
    PERSIAN_DIGITS,
    RELATIVE_HOUR_PATTERNS,
    RELATIVE_MINUTE_PATTERNS,
    TASK_REMOVE_WORDS,
)


class TaskParser:

    NUMBER_WORDS = {
        "یک": 1,
        "یه": 1,
        "دو": 2,
        "سه": 3,
        "چهار": 4,
        "پنج": 5,
        "شش": 6,
        "هفت": 7,
        "هشت": 8,
        "نه": 9,
        "ده": 10,
        "یازده": 11,
        "دوازده": 12,
        "سیزده": 13,
        "چهارده": 14,
        "پانزده": 15,
        "شانزده": 16,
        "هفده": 17,
        "هجده": 18,
        "نوزده": 19,
        "بیست": 20,
    }

    @staticmethod
    def normalize_text(
        text: str,
    ) -> str:

        text = str(text or "")

        replacements = {
            "ي": "ی",
            "ى": "ی",
            "ك": "ک",
        }

        for source, target in replacements.items():
            text = text.replace(
                source,
                target,
            )

        for source, target in PERSIAN_DIGITS.items():
            text = text.replace(
                source,
                target,
            )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    @staticmethod
    def remove_trigger(
        text: str,
    ) -> str:

        result = text.strip()

        for word in sorted(
            TASK_REMOVE_WORDS,
            key=len,
            reverse=True,
        ):

            pattern = (
                rf"^{re.escape(word)}"
                r"(?:\s+|$)"
            )

            cleaned = re.sub(
                pattern,
                "",
                result,
                count=1,
                flags=re.IGNORECASE,
            )

            if cleaned != result:
                return cleaned.strip()

        return result

    @classmethod
    def _parse_relative(
        cls,
        text: str,
        now: datetime,
        unit: str,
    ):

        if unit == "minutes":
            numeric_patterns = RELATIVE_MINUTE_PATTERNS
            word = "دقیقه"
            delta_factory = lambda value: timedelta(
                minutes=value
            )

        else:
            numeric_patterns = RELATIVE_HOUR_PATTERNS
            word = "ساعت"
            delta_factory = lambda value: timedelta(
                hours=value
            )

        for pattern in numeric_patterns:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            value = int(
                match.group(1)
            )

            target = now + delta_factory(
                value
            )

            cleaned = re.sub(
                pattern,
                "",
                text,
                count=1,
                flags=re.IGNORECASE,
            )

            return (
                target.strftime(
                    "%Y-%m-%d"
                ),
                target.strftime(
                    "%H:%M"
                ),
                cleaned,
            )

        for number_word, value in (
            cls.NUMBER_WORDS.items()
        ):

            pattern = (
                rf"(?<!\S)"
                rf"{re.escape(number_word)}"
                rf"\s+{word}\s+"
                r"(?:دیگه|دیگر|بعد)"
                r"(?!\S)"
            )

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            target = now + delta_factory(
                value
            )

            cleaned = re.sub(
                pattern,
                "",
                text,
                count=1,
                flags=re.IGNORECASE,
            )

            return (
                target.strftime(
                    "%Y-%m-%d"
                ),
                target.strftime(
                    "%H:%M"
                ),
                cleaned,
            )

        return "", "", text

    @classmethod
    def parse_relative_minutes(
        cls,
        text: str,
        now: datetime,
    ):

        return cls._parse_relative(
            text,
            now,
            "minutes",
        )

    @classmethod
    def parse_relative_hours(
        cls,
        text: str,
        now: datetime,
    ):

        return cls._parse_relative(
            text,
            now,
            "hours",
        )

    @staticmethod
    def parse_date(
        text: str,
        now: datetime,
    ):

        for keyword, days in sorted(
            DATE_KEYWORDS.items(),
            key=lambda item: len(
                item[0]
            ),
            reverse=True,
        ):

            pattern = (
                rf"(?<!\S)"
                rf"{re.escape(keyword)}"
                r"(?!\S)"
            )

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            target = now + timedelta(
                days=days
            )

            cleaned = re.sub(
                pattern,
                "",
                text,
                count=1,
                flags=re.IGNORECASE,
            )

            return (
                target.strftime(
                    "%Y-%m-%d"
                ),
                cleaned,
            )

        return "", text

    @staticmethod
    def parse_time(
        text: str,
        now: datetime,
        existing_date: str,
    ):

        match = re.search(
            r"(?:ساعت\s*)?(\d{1,2}):(\d{2})",
            text,
            flags=re.IGNORECASE,
        )

        if match:

            hour = int(
                match.group(1)
            )

            minute = int(
                match.group(2)
            )

            if not (
                0 <= hour <= 23
                and 0 <= minute <= 59
            ):

                return (
                    existing_date,
                    "",
                    text,
                )

            due_date = existing_date

            if not due_date:

                candidate = now.replace(
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )

                if candidate <= now:
                    candidate += timedelta(
                        days=1
                    )

                due_date = candidate.strftime(
                    "%Y-%m-%d"
                )

            cleaned = re.sub(
                re.escape(
                    match.group(0)
                ),
                "",
                text,
                count=1,
                flags=re.IGNORECASE,
            )

            return (
                due_date,
                f"{hour:02d}:{minute:02d}",
                cleaned,
            )

        match = re.search(
            r"ساعت\s+(\d{1,2})(?!\d)",
            text,
            flags=re.IGNORECASE,
        )

        if not match:

            return (
                existing_date,
                "",
                text,
            )

        hour = int(
            match.group(1)
        )

        if not 0 <= hour <= 23:

            return (
                existing_date,
                "",
                text,
            )

        due_date = existing_date

        if not due_date:

            candidate = now.replace(
                hour=hour,
                minute=0,
                second=0,
                microsecond=0,
            )

            if candidate <= now:
                candidate += timedelta(
                    days=1
                )

            due_date = candidate.strftime(
                "%Y-%m-%d"
            )

        cleaned = re.sub(
            re.escape(
                match.group(0)
            ),
            "",
            text,
            count=1,
            flags=re.IGNORECASE,
        )

        return (
            due_date,
            f"{hour:02d}:00",
            cleaned,
        )

    @staticmethod
    def cleanup_title(
        title: str,
    ) -> str:

        title = re.sub(
            r"\s+",
            " ",
            title,
        ).strip()

        for keyword in sorted(
            DATE_KEYWORDS,
            key=len,
            reverse=True,
        ):

            title = re.sub(
                (
                    rf"(?<!\S)"
                    rf"{re.escape(keyword)}"
                    r"(?!\S)"
                ),
                "",
                title,
                flags=re.IGNORECASE,
            )

        title = re.sub(
            r"(?<!\S)ساعت(?!\S)",
            "",
            title,
            flags=re.IGNORECASE,
        )

        title = re.sub(
            r"\s+",
            " ",
            title,
        ).strip()

        return title or EMPTY_TITLE

    @classmethod
    def parse(
        cls,
        message: str,
    ):

        now = datetime.now()

        text = cls.normalize_text(
            message
        )

        text = cls.remove_trigger(
            text
        )

        title = text

        due_date = ""
        due_time = ""

        (
            due_date,
            due_time,
            title,
        ) = cls.parse_relative_minutes(
            title,
            now,
        )

        if not due_date:

            (
                due_date,
                due_time,
                title,
            ) = cls.parse_relative_hours(
                title,
                now,
            )

        if not due_date:

            due_date, title = cls.parse_date(
                title,
                now,
            )

        (
            due_date,
            parsed_time,
            title,
        ) = cls.parse_time(
            title,
            now,
            due_date,
        )

        if parsed_time:
            due_time = parsed_time

        title = cls.cleanup_title(
            title
        )

        return {
            "title": title,
            "due_date": due_date,
            "due_time": due_time,
        }