import re

from services.tasks.constants import (
    TASK_TRIGGER_WORDS,
)


class TaskRouter:

    @staticmethod
    def _normalize(
        text: str,
    ) -> str:

        text = str(
            text or ""
        ).strip().lower()

        replacements = {
            "ي": "ی",
            "ى": "ی",
            "ك": "ک",
            "ۀ": "ه",
            "ة": "ه",
            "ؤ": "و",
            "إ": "ا",
            "أ": "ا",
            "ٱ": "ا",
        }

        for source, target in (
            replacements.items()
        ):

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
    def _detect_explicit(
        text: str,
    ):

        for keyword in (
            TASK_TRIGGER_WORDS
        ):

            if keyword.lower() in text:

                return {
                    "intent": "task",
                    "confidence": 0.95,
                    "source": "keyword",
                }

        return None

    @staticmethod
    def _detect_semantic(
        text: str,
    ):

        temporal_patterns = (
            r"\bامروز\b",
            r"\bفردا\b",
            r"\bپس\s*فردا\b",
            r"\bپسفردا\b",
            (
                r"\b\d+\s*دقیقه\s*"
                r"(?:دیگه|دیگر|بعد)"
            ),
            (
                r"\b\d+\s*ساعت\s*"
                r"(?:دیگه|دیگر|بعد)"
            ),
            (
                r"\b(?:یک|یه|دو|سه|چهار|پنج|شش|"
                r"هفت|هشت|نه|ده)\s+دقیقه\s+"
                r"(?:دیگه|دیگر|بعد)"
            ),
            (
                r"\b(?:یک|یه|دو|سه|چهار|پنج|شش|"
                r"هفت|هشت|نه|ده)\s+ساعت\s+"
                r"(?:دیگه|دیگر|بعد)"
            ),
            r"\bساعت\s+\d{1,2}",
        )

        has_time = any(
            re.search(
                pattern,
                text,
            )
            for pattern in temporal_patterns
        )

        if not has_time:
            return None

        action_patterns = (
            r"\bیادم\s+بنداز\b",
            r"\bیادم\s+بیار\b",
            r"\bیادآوری\s+کن\b",
            r"\bیادآوریم\s+کن\b",
            r"\bزنگ\s+بزن\b",
            r"\bتماس\s+بگیر\b",
            r"\bپیام\s+بده\b",
            r"\bپیام\s+بفرست\b",
            r"\bبررسی\s+کن\b",
            r"\bانجام\s+بده\b",
            r"\bپیگیری\s+کن\b",
            r"\bremind\b",
            r"\bcall\b",
            r"\bsend\b",
        )

        has_action = any(
            re.search(
                pattern,
                text,
            )
            for pattern in action_patterns
        )

        if not has_action:
            return None

        return {
            "intent": "task",
            "confidence": 0.90,
            "source": "semantic",
        }

    @staticmethod
    def detect(
        message: str,
    ):

        if not message:
            return None

        text = TaskRouter._normalize(
            message
        )

        if not text:
            return None

        result = (
            TaskRouter._detect_explicit(
                text
            )
        )

        if result:
            return result

        return (
            TaskRouter._detect_semantic(
                text
            )
        )