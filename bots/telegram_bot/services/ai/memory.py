from database.db import (
    get_memories,
    save_memory,
    get_history,
)


class MemoryService:


    @staticmethod
    def apply(
        user_id,
        memory,
        state=None,
    ):

        for key, value in memory.items():

            save_memory(
                user_id,
                key,
                value,
            )


    @staticmethod
    def get_memory(
        user_id
    ):

        rows = get_memories(
            user_id
        )

        result = {}

        for key, value in rows:

            result[key] = value


        return result



    @staticmethod
    def get_state(
        user_id
    ):

        return {}



class MemoryEngine:


    def __init__(
        self,
        user_id
    ):

        self.user_id = user_id



    def get_short_memory(
        self,
        limit=20
    ):

        history = get_history(
            self.user_id,
            limit,
        )

        return history



    def get_long_memory(
        self
    ):

        return MemoryService.get_memory(
            self.user_id
        )


    def build(self):

        return {
            "short_memory": self.get_short_memory(),
            "long_memory": self.get_long_memory(),
        }