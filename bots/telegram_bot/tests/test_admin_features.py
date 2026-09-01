import pytest
from unittest.mock import AsyncMock, MagicMock

from database.db import init_db, get_feature_flag
from utils.feature_gate import is_feature_enabled, clear_feature_cache
from services.features.service import (
    list_features_with_status,
    toggle_feature,
    set_feature_status,
)
from handlers.admin.features import (
    handle_features_callback,
    build_features_keyboard,
    build_features_text,
)


@pytest.fixture(autouse=True)
def setup_admin_feature_tests():
    init_db()
    clear_feature_cache()
    yield
    clear_feature_cache()


def test_list_features_with_status():
    features = list_features_with_status()
    assert isinstance(features, list)
    assert len(features) >= 7

    names = [f["name"] for f in features]
    assert "task" in names
    assert "memory" in names
    assert "security_tools" in names

    for f in features:
        assert "is_enabled" in f
        assert "display_name" in f
        assert "disabled_message" in f


def test_toggle_feature_flow_and_cache_invalidation():
    # 1. Ensure starts enabled
    set_feature_status("security_tools", True)
    assert is_feature_enabled("security_tools") is True

    # 2. Toggle to False
    new_state = toggle_feature("security_tools")
    assert new_state is False
    assert is_feature_enabled("security_tools") is False

    db_flag = get_feature_flag("security_tools")
    assert db_flag is not None
    assert db_flag["is_enabled"] is False

    # 3. Toggle back to True
    new_state_2 = toggle_feature("security_tools")
    assert new_state_2 is True
    assert is_feature_enabled("security_tools") is True

    db_flag_2 = get_feature_flag("security_tools")
    assert db_flag_2 is not None
    assert db_flag_2["is_enabled"] is True


def test_toggle_nonexistent_feature():
    assert toggle_feature("non_existent_123") is False
    assert set_feature_status("non_existent_123", True) is False


def test_build_features_ui_elements():
    text = build_features_text()
    assert "مدیریت قابلیت‌های سیستم" in text

    keyboard = build_features_keyboard()
    assert keyboard is not None
    assert len(keyboard.inline_keyboard) >= 8  # features + back button


@pytest.mark.asyncio
async def test_handle_features_callback_listing():
    update = MagicMock()
    query = MagicMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    context = MagicMock()

    handled = await handle_features_callback(update, context, "features")
    assert handled is True
    query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_handle_features_callback_toggle():
    update = MagicMock()
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    context = MagicMock()

    handled = await handle_features_callback(update, context, "toggle_feature:url_scanner")
    assert handled is True
    query.answer.assert_called_once()
    query.edit_message_text.assert_called_once()

