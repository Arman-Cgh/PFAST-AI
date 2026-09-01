import pytest
from database.db import (
    init_db,
    get_connection,
    get_feature_flag,
    get_all_feature_flags,
    set_feature_flag,
)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_feature_flag_table_exists():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feature_flags'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "feature_flags"
    finally:
        conn.close()


def test_get_nonexistent_feature_flag():
    flag = get_feature_flag("non_existent_feature_xyz")
    assert flag is None

    assert get_feature_flag("") is None
    assert get_feature_flag(None) is None


def test_set_and_get_feature_flag():
    feature_name = "test_password_check"
    success = set_feature_flag(
        feature_name=feature_name,
        is_enabled=True,
        disabled_message="این ابزار موقتاً غیرفعال است",
        category="security",
        display_name="بررسی رمز عبور",
    )
    assert success is True

    flag = get_feature_flag(feature_name)
    assert flag is not None
    assert flag["feature_name"] == feature_name
    assert flag["is_enabled"] is True
    assert flag["category"] == "security"
    assert flag["display_name"] == "بررسی رمز عبور"
    assert flag["disabled_message"] == "این ابزار موقتاً غیرفعال است"
    assert flag["updated_at"] != ""


def test_update_existing_feature_flag():
    feature_name = "test_url_scanner"
    
    # 1. Create enabled
    set_feature_flag(
        feature_name=feature_name,
        is_enabled=True,
        disabled_message="اسکنر لینک غیرفعال است",
        category="security",
        display_name="اسکنر لینک",
    )
    
    flag = get_feature_flag(feature_name)
    assert flag["is_enabled"] is True

    # 2. Toggle to disabled
    success = set_feature_flag(
        feature_name=feature_name,
        is_enabled=False,
    )
    assert success is True

    updated_flag = get_feature_flag(feature_name)
    assert updated_flag["is_enabled"] is False
    # Preserves other fields
    assert updated_flag["category"] == "security"
    assert updated_flag["display_name"] == "اسکنر لینک"
    assert updated_flag["disabled_message"] == "اسکنر لینک غیرفعال است"


def test_get_all_feature_flags():
    set_feature_flag("test_feature_a", True, category="cat_a", display_name="A")
    set_feature_flag("test_feature_b", False, category="cat_b", display_name="B")

    all_flags = get_all_feature_flags()
    assert isinstance(all_flags, dict)
    assert "test_feature_a" in all_flags
    assert "test_feature_b" in all_flags
    assert all_flags["test_feature_a"]["is_enabled"] is True
    assert all_flags["test_feature_b"]["is_enabled"] is False

