import pytest

from database.db import init_db, add_user
from services.conversation.handler import ConversationHandler
from services.tasks.manager import TaskManager


@pytest.fixture
def task_user():
    init_db()

    user_id = 666666

    add_user(
        user_id=user_id,
        username="conversation_test",
        first_name="Conversation Test",
    )

    return user_id


@pytest.mark.asyncio
async def test_task_message_routing_and_creation(
    task_user,
):

    handler = ConversationHandler()

    result = await handler.handle(
        user_id=task_user,
        message="یادم بنداز فردا ساعت 9 قبض را پرداخت کنم",
    )

    assert result

    tasks = TaskManager.get_pending(
        task_user
    )

    assert len(tasks) >= 1

    task = next(
        task
        for task in tasks
        if task["title"] == "قبض را پرداخت کنم"
    )

    assert task["due_date"]

    assert task["due_date"].endswith(
        "09:00"
    )


@pytest.mark.asyncio
async def test_task_without_due_date_is_created(
    task_user,
):

    handler = ConversationHandler()

    result = await handler.handle(
        user_id=task_user,
        message="یادم بنداز کتاب بخونم",
    )

    assert result

    tasks = TaskManager.get_pending(
        task_user
    )

    task = next(
        task
        for task in tasks
        if task["title"] == "کتاب بخونم"
    )

    assert task["due_date"] == ""