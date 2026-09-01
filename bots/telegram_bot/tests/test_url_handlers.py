import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.db import init_db, set_feature_flag
from utils.feature_gate import clear_feature_cache
from handlers.security.url import (
    handle_url_callback,
    handle_url_scan_text,
    get_url_menu_text,
    get_url_menu_keyboard,
    get_scan_prompt_text,
    get_scan_prompt_keyboard,
    format_url_report,
    get_url_result_keyboard,
)
from handlers.user_callbacks import user_callback, get_main_keyboard


@pytest.fixture(autouse=True)
def setup_url_handler_tests():
    init_db()
    clear_feature_cache()
    yield
    clear_feature_cache()


def test_url_menu_ui_elements():
    text = get_url_menu_text()
    assert "مرکز اسکن و امنیت پیوندها" in text

    kb = get_url_menu_keyboard()
    assert len(kb.inline_keyboard) == 2


def test_scan_prompt_ui_elements():
    prompt = get_scan_prompt_text()
    assert "اسکن و بررسی پیوند اینترنتی" in prompt
    assert "حریم خصوصی" in prompt

    kb = get_scan_prompt_keyboard()
    assert len(kb.inline_keyboard) == 1


@pytest.mark.asyncio
async def test_feature_disabled_behavior():
    set_feature_flag("url_scanner", is_enabled=False, disabled_message="اسکنر پیوند موقتاً غیرفعال است.")
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    context = MagicMock()
    context.user_data = {}

    handled = await handle_url_callback(update, context, "url:menu")
    assert handled is True
    query.edit_message_text.assert_called_once()
    args, kwargs = query.edit_message_text.call_args
    assert "اسکنر پیوند موقتاً غیرفعال است" in args[0]


@pytest.mark.asyncio
async def test_url_menu_callback_and_state_clear():
    set_feature_flag("url_scanner", is_enabled=True)
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    context = MagicMock()
    context.user_data = {"pending_action": "old_action"}

    handled = await handle_url_callback(update, context, "url:menu")
    assert handled is True
    assert "pending_action" not in context.user_data
    query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_scan_prompt_callback_creates_pending_action():
    set_feature_flag("url_scanner", is_enabled=True)
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    context = MagicMock()
    context.user_data = {}

    handled = await handle_url_callback(update, context, "url:scan_prompt")
    assert handled is True
    assert context.user_data.get("pending_action") == "scan_url"
    query.edit_message_text.assert_called_once()
    prompt_text = query.edit_message_text.call_args[0][0]
    assert "اسکن و بررسی پیوند" in prompt_text


@pytest.mark.asyncio
async def test_handle_url_scan_text_safe():
    update = MagicMock()
    message = MagicMock()
    message.reply_text = AsyncMock()
    update.message = message
    context = MagicMock()
    context.user_data = {"pending_action": "scan_url"}

    handled = await handle_url_scan_text(update, context, "https://google.com")
    assert handled is True
    assert "pending_action" not in context.user_data
    message.reply_text.assert_called_once()

    reply = message.reply_text.call_args[0][0]
    assert "گزارش ارزیابی امنیت پیوند" in reply
    assert "امن و بدون ریسک" in reply


@pytest.mark.asyncio
async def test_handle_url_scan_text_suspicious():
    update = MagicMock()
    message = MagicMock()
    message.reply_text = AsyncMock()
    update.message = message
    context = MagicMock()
    context.user_data = {"pending_action": "scan_url"}

    handled = await handle_url_scan_text(update, context, "https://bit.ly/3xSecret")
    assert handled is True
    reply = message.reply_text.call_args[0][0]
    assert "مشکوک و نیازمند احتیاط" in reply
    assert "لینک کوتاه‌شده" in reply


@pytest.mark.asyncio
async def test_handle_url_scan_text_dangerous_and_offline():
    update = MagicMock()
    message = MagicMock()
    message.reply_text = AsyncMock()
    update.message = message
    context = MagicMock()
    context.user_data = {"pending_action": "scan_url"}

    with patch("socket.socket") as mock_socket:
        handled = await handle_url_scan_text(update, context, "http://127.0.0.1:8000/admin")
        assert handled is True
        mock_socket.assert_not_called()

    reply = message.reply_text.call_args[0][0]
    assert "خطرناک و با ریسک بالا" in reply
    assert "SSRF" in reply


@pytest.mark.asyncio
async def test_user_callbacks_routes_url_scanner():
    set_feature_flag("url_scanner", is_enabled=True)
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user = MagicMock()
    query.from_user.id = 12345
    query.data = "url:menu"
    update.callback_query = query
    context = MagicMock()
    context.user_data = {}

    await user_callback(update, context)
    query.edit_message_text.assert_called_once()
    assert "مرکز اسکن و امنیت پیوندها" in query.edit_message_text.call_args[0][0]


def test_main_keyboard_includes_url_scanner():
    kb = get_main_keyboard()
    found = False
    for row in kb.inline_keyboard:
        for btn in row:
            if btn.callback_data == "url:menu":
                found = True
                assert "اسکنر پیوندها" in btn.text
    assert found is True

