import logging

import services.ai.config as ai_config

from services.ai.providers import ProviderManager
from services.ai.cache import AICache
from services.ai.intent_router import IntentRouter

from services.ai.pipeline.task import TaskPipeline
from services.ai.pipeline.memory import MemoryPipeline
from services.ai.pipeline.response import ResponsePipeline


logger = logging.getLogger(__name__)


class AIEngine:

    def __init__(
        self,
        config=None,
    ):
        self.config = (
            config
            or ai_config
        )

        self.provider_manager = (
            ProviderManager()
        )

        self.cache = AICache()

        self.response_pipeline = (
            ResponsePipeline(
                provider_manager=(
                    self.provider_manager
                ),
                cache=self.cache,
            )
        )

        self._initialized = False

    async def initialize(self):

        if self._initialized:
            return

        if hasattr(
            self.provider_manager,
            "initialize",
        ):

            await self.provider_manager.initialize()

        try:
            await MemoryPipeline.start()
        except Exception:
            logger.exception("Failed to start MemoryPipeline worker")

        self._initialized = True

        logger.info(
            "AI Engine initialized"
        )

    async def shutdown(self):

        if not self._initialized:
            return

        try:
            await MemoryPipeline.stop()
        except Exception:
            logger.exception("Failed to stop MemoryPipeline worker")

        if hasattr(
            self.provider_manager,
            "shutdown",
        ):

            await self.provider_manager.shutdown()

        self._initialized = False

        logger.info(
            "AI Engine shutdown"
        )

    async def generate_response(
        self,
        user_id: int,
        message: str,
        intent=None,
        use_cache: bool = True,
        extract_info: bool = True,
    ):

        if not self._initialized:
            await self.initialize()

        message = str(
            message or ""
        ).strip()

        if not message:

            return {
                "response": "",
                "cached": False,
                "intent": {
                    "intent": "chat",
                    "confidence": 0,
                    "source": "empty",
                },
                "provider": "none",
            }

        # ==========================================
        # Intent
        # ==========================================

        if intent is None:

            intent_result = (
                IntentRouter.detect(
                    message
                )
            )

        else:

            intent_result = intent

        if hasattr(
            intent_result,
            "intent",
        ):

            intent_name = (
                intent_result.intent
            )

        elif isinstance(
            intent_result,
            dict,
        ):

            intent_name = (
                intent_result.get(
                    "intent",
                    "chat",
                )
            )

        else:

            intent_name = str(
                intent_result
                or "chat"
            )

        intent_name = (
            str(intent_name)
            .strip()
            .lower()
        )

        # ==========================================
        # Task
        # ==========================================

        if intent_name == "task":

            result = TaskPipeline.execute(
                user_id=user_id,
                message=message,
                intent=intent_result,
            )

            return result

        # ==========================================
        # Image Generation Feature Gate
        # ==========================================

        if intent_name in {"image", "image_generation"}:
            from utils.feature_gate import check_feature_access
            access = check_feature_access("image_generation")
            if not access.get("allowed", False):
                disabled_msg = (
                    access.get("message")
                    or "⚙️ سرویس تولید تصویر هوش مصنوعی موقتاً در دسترس نیست."
                )
                return {
                    "response": disabled_msg,
                    "cached": False,
                    "intent": {
                        "intent": "image_generation",
                        "confidence": 1.0,
                        "source": "feature_gate",
                    },
                    "provider": "none",
                }

        # ==========================================
        # AI Response
        # ==========================================

        result = await (
            self.response_pipeline.generate(
                user_id=user_id,
                message=message,
                intent=intent_name,
                use_cache=use_cache,
            )
        )

        # ==========================================
        # Memory
        # ==========================================

        if (
            extract_info
            and not result.get(
                "cached",
                False,
            )
            and MemoryPipeline.should_extract(
                intent=intent_name,
                message=message,
            )
        ):

            MemoryPipeline.schedule(
                provider_manager=(
                    self.provider_manager
                ),
                provider_name=result.get(
                    "provider",
                    "",
                ),
                user_id=user_id,
                message=message,
                response=result.get(
                    "response",
                    "",
                ),
            )

        # ==========================================
        # Intent Metadata
        # ==========================================

        if hasattr(
            intent_result,
            "to_dict",
        ):

            result["intent"] = (
                intent_result.to_dict()
            )

        elif isinstance(
            intent_result,
            dict,
        ):

            result["intent"] = (
                intent_result
            )

        else:

            result["intent"] = {
                "intent": intent_name,
            }

        return result

    async def ask(
        self,
        user_id: int,
        user_message: str,
        use_cache: bool = True,
        extract_info: bool = True,
    ):
        """
        Backward-compatible API.
        """

        return await self.generate_response(
            user_id=user_id,
            message=user_message,
            use_cache=use_cache,
            extract_info=extract_info,
        )