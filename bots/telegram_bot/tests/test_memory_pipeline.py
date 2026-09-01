import asyncio
import pytest

from services.ai.pipeline.memory import MemoryPipeline


def test_memory_keyword_detection():

    assert MemoryPipeline.should_extract(
        intent="chat",
        message="یادت باشه اسم من یونس است"
    )


def test_memory_skip_code():

    assert not MemoryPipeline.should_extract(
        intent="code",
        message="یادت باشه این کد را ذخیره کن"
    )


def test_memory_skip_normal_chat():

    assert not MemoryPipeline.should_extract(
        intent="chat",
        message="امروز هوا چطوره؟"
    )


@pytest.mark.asyncio
async def test_memory_pipeline_non_blocking_schedule(monkeypatch):
    extracted_records = []

    async def fake_extract(provider_manager, provider_name, user_id, message, response):
        await asyncio.sleep(0.01)
        extracted_records.append((user_id, message))

    monkeypatch.setattr(MemoryPipeline, "extract", staticmethod(fake_extract))

    await MemoryPipeline.start()
    try:
        scheduled = MemoryPipeline.schedule(
            provider_manager=None,
            provider_name="fake",
            user_id=1001,
            message="اسم من تست است",
            response="سلام",
        )
        assert scheduled is True

        # Wait briefly for background worker to process
        await asyncio.sleep(0.05)
        assert (1001, "اسم من تست است") in extracted_records
    finally:
        await MemoryPipeline.stop()


@pytest.mark.asyncio
async def test_memory_pipeline_deduplication(monkeypatch):
    processing_event = asyncio.Event()

    async def fake_extract(provider_manager, provider_name, user_id, message, response):
        await processing_event.wait()

    monkeypatch.setattr(MemoryPipeline, "extract", staticmethod(fake_extract))

    await MemoryPipeline.start()
    try:
        # First schedule succeeds
        first = MemoryPipeline.schedule(
            provider_manager=None,
            provider_name="fake",
            user_id=2001,
            message="پیام اول",
            response="پاسخ",
        )
        assert first is True

        # Second schedule for the SAME user while pending should be skipped
        second = MemoryPipeline.schedule(
            provider_manager=None,
            provider_name="fake",
            user_id=2001,
            message="پیام دوم",
            response="پاسخ",
        )
        assert second is False
    finally:
        processing_event.set()
        await MemoryPipeline.stop()


@pytest.mark.asyncio
async def test_memory_pipeline_queue_overflow(monkeypatch):
    async def fake_extract(*args, **kwargs):
        await asyncio.sleep(0.1)

    monkeypatch.setattr(MemoryPipeline, "extract", staticmethod(fake_extract))

    await MemoryPipeline.start()
    try:
        # Fill queue to maximum capacity
        for i in range(MemoryPipeline.MAX_QUEUE_SIZE):
            queued = MemoryPipeline.schedule(
                provider_manager=None,
                provider_name="fake",
                user_id=3000 + i,
                message=f"msg {i}",
                response="resp",
            )
            assert queued is True

        # Next one over capacity should be safely dropped without raising error
        overflow_queued = MemoryPipeline.schedule(
            provider_manager=None,
            provider_name="fake",
            user_id=9999,
            message="overflow msg",
            response="resp",
        )
        assert overflow_queued is False
    finally:
        await MemoryPipeline.stop()


@pytest.mark.asyncio
async def test_memory_pipeline_worker_error_resilience(monkeypatch):
    processed = []

    async def fake_extract(provider_manager, provider_name, user_id, message, response):
        if user_id == 4001:
            raise RuntimeError("Extraction crashed intentionally")
        processed.append(user_id)

    monkeypatch.setattr(MemoryPipeline, "extract", staticmethod(fake_extract))

    await MemoryPipeline.start()
    try:
        MemoryPipeline.schedule(None, "fake", 4001, "msg 1", "resp 1")
        MemoryPipeline.schedule(None, "fake", 4002, "msg 2", "resp 2")

        await asyncio.sleep(0.05)
        # Even though 4001 raised an error, worker should continue and process 4002
        assert 4002 in processed
    finally:
        await MemoryPipeline.stop()


@pytest.mark.asyncio
async def test_memory_pipeline_lifecycle_start_stop():
    await MemoryPipeline.start()
    assert MemoryPipeline._running is True
    assert MemoryPipeline._worker_task is not None
    assert not MemoryPipeline._worker_task.done()

    await MemoryPipeline.stop()
    assert MemoryPipeline._running is False
    assert MemoryPipeline._worker_task is None
    assert MemoryPipeline._queue is None