import pytest
from database.db import init_db, set_feature_flag, get_connection
from utils.feature_gate import (
    check_feature_access,
    is_feature_enabled,
    clear_feature_cache,
)


@pytest.fixture(autouse=True)
def setup_gate_test():
    init_db()
    clear_feature_cache()
    yield
    clear_feature_cache()


def test_missing_database_flag_falls_back_to_registry_default():
    # "task" is defined in registry with default_enabled=True
    # Delete any existing DB override for clean test
    conn = get_connection()
    try:
        conn.execute("DELETE FROM feature_flags WHERE feature_name='task'")
        conn.commit()
    finally:
        conn.close()

    clear_feature_cache()
    result = check_feature_access("task")
    assert result["allowed"] is True
    assert result["feature"] == "task"
    assert result["message"] is None

    assert is_feature_enabled("task") is True


def test_enabled_feature_from_database():
    set_feature_flag(
        feature_name="url_scanner",
        is_enabled=True,
        display_name="اسکنر لینک",
    )
    clear_feature_cache()

    result = check_feature_access("url_scanner")
    assert result["allowed"] is True
    assert result["feature"] == "url_scanner"
    assert result["message"] is None
    assert is_feature_enabled("url_scanner") is True


def test_disabled_feature_returns_disabled_message():
    custom_msg = "اسکنر پیوند در حال حاضر در دست تعمیر است."
    set_feature_flag(
        feature_name="url_scanner",
        is_enabled=False,
        disabled_message=custom_msg,
    )
    clear_feature_cache()

    result = check_feature_access("url_scanner")
    assert result["allowed"] is False
    assert result["feature"] == "url_scanner"
    assert result["message"] == custom_msg
    assert is_feature_enabled("url_scanner") is False


def test_unknown_feature_handling():
    result = check_feature_access("unknown_feature_xyz")
    assert result["allowed"] is False
    assert result["message"] is not None
    assert is_feature_enabled("unknown_feature_xyz") is False

    empty_res = check_feature_access("")
    assert empty_res["allowed"] is False

    none_res = check_feature_access(None)
    assert none_res["allowed"] is False


def test_cache_behavior_and_invalidation():
    # 1. Start enabled
    set_feature_flag("password_tools", is_enabled=True)
    clear_feature_cache()

    assert is_feature_enabled("password_tools") is True

    # 2. Change directly in DB without clearing cache
    set_feature_flag("password_tools", is_enabled=False)

    # Cache should still return previous state before invalidation
    cached_res = check_feature_access("password_tools")
    assert cached_res["allowed"] is True

    # 3. Clear cache -> should reflect updated DB state
    clear_feature_cache()
    fresh_res = check_feature_access("password_tools")
    assert fresh_res["allowed"] is False

