from services.ai.intent_router import IntentRouter


class IntentRouterService:

    @staticmethod
    def detect(message: str):
        return IntentRouter.detect(message)