import asyncio
import pytest

from services.ai.pipeline.response import ResponsePipeline
from services.ai.cache import AICache
from services.tasks.worker import TaskWorker
from database.db import add_user, save_message


class FakeProviderManager:
    async def generate(self, messages, intent=None, model=None):
        return {
            "text": "پاسخ تست",
            "provider": "fake",
        }


@pytest.mark.asyncio
async def test_async_build_messages_non_blocking():
    pipeline = ResponsePipeline(
        provider_manager=FakeProviderManager(),
        cache=AICache(),
    )

    user_id = 991100

    add_user(user_id, "test_async_user", "Async")
    save_message(user_id, "user", "پیام تستی قبل")
    save_message(user_id, "assistant", "پاسخ تستی قبل")

    messages = await pipeline.build_messages(
        user_id=user_id,
        message="پیام جدید",
        intent="chat",
    )

    assert isinstance(messages, list)
    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "پیام جدید"


@pytest.mark.asyncio
async def test_async_ai_cache_get_set():
    cache = AICache()
    user_id = 991101
    add_user(user_id, "test_cache_user", "CacheUser")

    cache_key = "test_cache_key_async_safety"
    value = "cached_test_answer_content"

    saved = await cache.set(user_id, cache_key, value)
    assert saved is True

    retrieved = await cache.get(user_id, cache_key)
    assert retrieved == value


@pytest.mark.asyncio
async def test_async_task_worker_check_tasks():
    class FakeBot:
        def __init__(self):
            self.sent_messages = []

        async def send_message(self, chat_id, text):
            self.sent_messages.append((chat_id, text))

    bot = FakeBot()
    worker = TaskWorker(bot)

    await worker.check_tasks()
    assert isinstance(bot.sent_messages, list)
