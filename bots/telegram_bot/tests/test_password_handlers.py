import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.db import init_db, set_feature_flag
from utils.feature_gate import clear_feature_cache
from handlers.security.password import (
    handle_password_callback,
    handle_password_analysis_text,
    get_password_menu_text,
    get_password_menu_keyboard,
    get_generator_text,
    get_generator_keyboard,
    format_strength_report,
)
from handlers.user_callbacks import user_callback, get_main_keyboard


@pytest.fixture(autouse=True)
def setup_password_handler_tests():
    init_db()
    clear_feature_cache()
    yield
    clear_feature_cache()


def test_password_menu_ui_elements():
    text = get_password_menu_text()
    assert "مرکز ابزارهای رمز عبور امن" in text

    kb = get_password_menu_keyboard()
    assert len(kb.inline_keyboard) == 3


def test_generator_keyboard_and_options():
    opts = {"length": 16, "upper": True, "lower": True, "digits": True, "symbols": True}
    kb = get_generator_keyboard(opts)
    assert len(kb.inline_keyboard) == 5

    text = get_generator_text(generated_password="test_password_123")
    assert "`test_password_123`" in text


@pytest.mark.asyncio
async def test_feature_disabled_behavior():
    set_feature_flag("password_tools", is_enabled=False, disabled_message="ابزار رمز عبور موقتاً غیرفعال است.")
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    context = MagicMock()
    context.user_data = {}

    handled = await handle_password_callback(update, context, "password:menu")
    assert handled is True
    query.edit_message_text.assert_called_once()
    args, kwargs = query.edit_message_text.call_args
    assert "ابزار رمز عبور موقتاً غیرفعال است" in args[0]


@pytest.mark.asyncio
async def test_password_menu_callback():
    set_feature_flag("password_tools", is_enabled=True)
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    context = MagicMock()
    context.user_data = {"pending_action": "old_action"}

    handled = await handle_password_callback(update, context, "password:menu")
    assert handled is True
    assert "pending_action" not in context.user_data
    query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_password_generator_callbacks():
    set_feature_flag("password_tools", is_enabled=True)
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    context = MagicMock()
    context.user_data = {}

    # 1. Open Generator Menu
    handled = await handle_password_callback(update, context, "password:gen_menu")
    assert handled is True

    # 2. Set Length to 24
    handled = await handle_password_callback(update, context, "password:set_len:24")
    assert handled is True
    assert context.user_data["pwd_gen_opts"]["length"] == 24

    # 3. Toggle group
    handled = await handle_password_callback(update, context, "password:toggle:symbols")
    assert handled is True
    assert context.user_data["pwd_gen_opts"]["symbols"] is False

    # 4. Generate password
    handled = await handle_password_callback(update, context, "password:gen")
    assert handled is True
    query.edit_message_text.assert_called()
    last_text = query.edit_message_text.call_args[0][0]
    assert "رمز عبور تولید شده:" in last_text


@pytest.mark.asyncio
async def test_password_check_state_prompt():
    set_feature_flag("password_tools", is_enabled=True)
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    context = MagicMock()
    context.user_data = {}

    handled = await handle_password_callback(update, context, "password:check_menu")
    assert handled is True
    assert context.user_data.get("pending_action") == "check_password"
    query.edit_message_text.assert_called_once()
    call_text = query.edit_message_text.call_args[0][0]
    assert "تست و ارزیابی قدرت رمز عبور" in call_text
    assert "حریم خصوصی" in call_text


@pytest.mark.asyncio
async def test_handle_password_analysis_text_local_and_no_ai():
    update = MagicMock()
    message = MagicMock()
    message.reply_text = AsyncMock()
    update.message = message
    context = MagicMock()
    context.user_data = {"pending_action": "check_password"}

    # Run analysis on a password
    handled = await handle_password_analysis_text(update, context, "xK9#mQ2$vL8@pZ4!")
    assert handled is True
    assert "pending_action" not in context.user_data
    message.reply_text.assert_called_once()

    reply_content = message.reply_text.call_args[0][0]
    assert "گزارش ارزیابی قدرت رمز عبور" in reply_content
    assert "سطح امنیت" in reply_content
    assert "100" in reply_content


@pytest.mark.asyncio
async def test_user_callbacks_routes_password_tools():
    set_feature_flag("password_tools", is_enabled=True)
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user = MagicMock()
    query.from_user.id = 12345
    query.data = "password:menu"
    update.callback_query = query
    context = MagicMock()
    context.user_data = {}

    await user_callback(update, context)
    query.edit_message_text.assert_called_once()

