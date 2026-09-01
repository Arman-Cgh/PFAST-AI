import pytest
from datetime import datetime, timedelta

from database.db import add_user, init_db, get_connection
from services.tasks.manager import TaskManager
from services.tasks.worker import TaskWorker


class MockBot:

    def __init__(self):

        self.messages = []


    async def send_message(
        self,
        chat_id,
        text,
    ):

        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
            }
        )


@pytest.fixture
def test_user():

    init_db()

    user_id = 777777

    add_user(
        user_id=user_id,
        username="worker_test_user",
        first_name="Worker Test",
    )

    conn = get_connection()

    conn.execute(
        "DELETE FROM tasks WHERE user_id=?",
        (user_id,),
    )

    conn.commit()
    conn.close()

    return user_id


@pytest.mark.asyncio
async def test_worker_sends_reminder(
    test_user
):

    past_time = (
        datetime.now() - timedelta(minutes=5)
    ).strftime(
        "%Y-%m-%d %H:%M"
    )


    task_id = TaskManager.create(
        user_id=test_user,
        title="Worker Reminder Test",
        description="",
        due_date=past_time,
    )


    bot = MockBot()

    worker = TaskWorker(
        bot
    )


    await worker.check_tasks()


    assert len(
        bot.messages
    ) > 0


    user_messages = [
        message
        for message in bot.messages
        if message["chat_id"] == test_user
    ]


    assert len(
        user_messages
    ) > 0


    assert "Worker Reminder Test" in user_messages[0]["text"]


def test_worker_init():

    bot = MockBot()

    worker = TaskWorker(
        bot
    )

    assert worker.running is True