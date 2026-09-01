import asyncio
import logging
from typing import Optional, Set

from services.ai.extractor import extract_memory
from services.ai.memory import MemoryService


logger = logging.getLogger(__name__)


class MemoryPipeline:

    MAX_QUEUE_SIZE = 50

    SKIP_INTENTS = {
        "task",
        "code",
        "search",
        "image",
        "vision",
    }

    MEMORY_KEYWORDS = (
        "اسمم",
        "نامم",
        "من هستم",
        "شغلم",
        "کارم",
        "علاقه دارم",
        "یادت باشه",
        "یادت بمونه",
        "ذخیره کن",
        "به خاطر بسپار",
        "فراموش نکن",
        "remember",
        "save",
    )

    _queue: Optional[asyncio.Queue] = None
    _worker_task: Optional[asyncio.Task] = None
    _pending_users: Set[int] = set()
    _running: bool = False

    @classmethod
    def should_extract(
        cls,
        intent: str,
        message: str,
    ) -> bool:
        if intent == "memory":
            return True

        if intent in cls.SKIP_INTENTS:
            return False

        text = (
            message or ""
        ).lower()

        return any(
            keyword.lower() in text
            for keyword in cls.MEMORY_KEYWORDS
        )

    @classmethod
    def get_status(cls) -> dict:
        """
        Safe, read-only operational status of the memory pipeline.
        """
        is_active = bool(
            cls._running
            and cls._worker_task is not None
            and not cls._worker_task.done()
        )
        qsize = cls._queue.qsize() if cls._queue is not None else 0
        return {
            "running": is_active,
            "queue_size": qsize,
            "max_queue_size": cls.MAX_QUEUE_SIZE,
            "pending_users": len(cls._pending_users) if cls._pending_users else 0,
        }

    @classmethod
    async def start(cls):
        """
        Initialize queue and start background worker loop.
        """
        if cls._running and cls._worker_task and not cls._worker_task.done():
            return

        cls._queue = asyncio.Queue(maxsize=cls.MAX_QUEUE_SIZE)
        cls._pending_users = set()
        cls._running = True
        cls._worker_task = asyncio.create_task(
            cls._worker_loop(),
            name="memory_extraction_worker",
        )
        logger.info("Memory extraction pipeline worker started")

    @classmethod
    async def stop(cls):
        """
        Gracefully stop the background worker loop.
        """
        cls._running = False

        if cls._worker_task:
            cls._worker_task.cancel()
            try:
                await cls._worker_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Error stopping memory extraction worker")
            finally:
                cls._worker_task = None

        cls._queue = None
        cls._pending_users.clear()
        logger.info("Memory extraction pipeline worker stopped")

    @classmethod
    async def _worker_loop(cls):
        while cls._running:
            try:
                if cls._queue is None:
                    break

                item = await cls._queue.get()

                user_id = item["user_id"]

                try:
                    await cls.extract(
                        provider_manager=item["provider_manager"],
                        provider_name=item["provider_name"],
                        user_id=user_id,
                        message=item["message"],
                        response=item["response"],
                    )
                except Exception as exc:
                    logger.exception(
                        "Memory extraction worker job failed for user %s: %s",
                        user_id,
                        exc,
                    )
                finally:
                    cls._pending_users.discard(user_id)
                    if cls._queue is not None:
                        cls._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Unexpected error in memory worker loop")
                await asyncio.sleep(0.5)

    @staticmethod
    async def extract(
        provider_manager,
        provider_name,
        user_id,
        message,
        response,
    ):
        try:
            result = await extract_memory(
                provider=provider_manager,
                provider_name=provider_name,
                user_id=user_id,
                user_message=message,
                assistant_response=response,
            )

            if not result:
                return

            MemoryService.apply(
                user_id=user_id,
                memory=result.get(
                    "memory",
                    {},
                ),
                state=result.get(
                    "state",
                    {},
                ),
            )

        except Exception as e:
            logger.exception(
                "Memory extraction failed: %s",
                e,
            )

    @classmethod
    def schedule(
        cls,
        provider_manager,
        provider_name,
        user_id,
        message,
        response,
    ) -> bool:
        """
        Non-blocking memory extraction queue scheduling.
        Deduplicates pending user extraction and drops safely on overflow.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("No running event loop for memory extraction")
            return False

        # Lazy initialization if worker is not yet started in this loop
        if not cls._running or cls._queue is None or cls._worker_task is None or cls._worker_task.done():
            cls._queue = asyncio.Queue(maxsize=cls.MAX_QUEUE_SIZE)
            cls._pending_users = set()
            cls._running = True
            cls._worker_task = loop.create_task(
                cls._worker_loop(),
                name="memory_extraction_worker",
            )

        # Deduplicate: Skip if an extraction for this user is already queued
        if user_id in cls._pending_users:
            logger.debug(
                "Skipping memory extraction: job already queued for user %s",
                user_id,
            )
            return False

        item = {
            "provider_manager": provider_manager,
            "provider_name": provider_name,
            "user_id": user_id,
            "message": message,
            "response": response,
        }

        try:
            cls._queue.put_nowait(item)
            cls._pending_users.add(user_id)
            return True
        except asyncio.QueueFull:
            logger.warning(
                "Memory extraction queue is full (%s items). Dropping extraction for user %s.",
                cls.MAX_QUEUE_SIZE,
                user_id,
            )
            return False