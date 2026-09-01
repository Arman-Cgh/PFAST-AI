import itertools
import threading
import time


class TabitokenKeyManager:

    def __init__(self, keys: list[str]):

        clean_keys = [
            key.strip()
            for key in keys
            if key.strip()
        ]

        if not clean_keys:
            raise ValueError(
                "No Tabitoken API keys configured"
            )

        self.keys = clean_keys

        self.available_keys = {
            key: {
                "failures": 0,
                "disabled_until": 0,
                "requests": 0,
            }
            for key in clean_keys
        }

        self._cycle = itertools.cycle(
            clean_keys
        )

        self._lock = threading.Lock()


    def get_next_key(self):

        with self._lock:

            now = time.time()

            checked = 0

            while checked < len(self.keys):

                key = next(self._cycle)

                data = self.available_keys[key]

                if data["disabled_until"] <= now:

                    data["requests"] += 1

                    return key

                checked += 1


            # اگر همه موقتاً خراب بودند
            # دوباره اولین را بده
            key = next(self._cycle)

            self.available_keys[key]["requests"] += 1

            return key


    def mark_success(
        self,
        key: str
    ):

        if key in self.available_keys:

            self.available_keys[key]["failures"] = 0


    def mark_failure(
        self,
        key: str,
        cooldown: int = 60
    ):

        if key not in self.available_keys:
            return

        data = self.available_keys[key]

        data["failures"] += 1


        if data["failures"] >= 2:

            data["disabled_until"] = (
                time.time()
                +
                cooldown
            )


    def stats(self):
        """
        Return operational stats keyed by a MASKED key fingerprint
        (first 4 chars + *** + last 4 chars) to prevent raw API key exposure
        in logs, admin endpoints, or debug output.
        """
        masked = {}
        for key, data in self.available_keys.items():
            if len(key) >= 8:
                fingerprint = f"{key[:4]}***{key[-4:]}"
            else:
                fingerprint = "***"
            masked[fingerprint] = dict(data)
        return masked