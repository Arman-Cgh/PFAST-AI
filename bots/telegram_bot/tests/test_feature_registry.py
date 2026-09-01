import pytest
from services.features.registry import (
    FEATURE_DEFINITIONS,
    get_feature_definition,
    get_all_features,
    validate_feature_exists,
)


REQUIRED_FEATURES = [
    "task",
    "memory",
    "image_generation",
    "security_tools",
    "password_tools",
    "url_scanner",
    "admin_tools",
]


def test_registry_loads_and_contains_required_features():
    all_features = get_all_features()
    assert isinstance(all_features, dict)
    assert len(all_features) >= len(REQUIRED_FEATURES)

    for feature_name in REQUIRED_FEATURES:
        assert feature_name in all_features
        assert validate_feature_exists(feature_name) is True


def test_feature_definition_structure_and_defaults():
    for feature_name in REQUIRED_FEATURES:
        defn = get_feature_definition(feature_name)
        assert defn is not None
        assert defn["name"] == feature_name
        assert isinstance(defn["category"], str) and len(defn["category"]) > 0
        assert isinstance(defn["display_name"], str) and len(defn["display_name"]) > 0
        assert isinstance(defn["disabled_message"], str) and len(defn["disabled_message"]) > 0
        assert defn["default_enabled"] is True


def test_unknown_feature_handling():
    assert get_feature_definition("non_existent_feature_123") is None
    assert get_feature_definition("") is None
    assert get_feature_definition(None) is None

    assert validate_feature_exists("non_existent_feature_123") is False
    assert validate_feature_exists("") is False
    assert validate_feature_exists(None) is False


def test_case_insensitivity_and_whitespace_trimming():
    assert validate_feature_exists("  TASK  ") is True
    assert validate_feature_exists("URL_SCANNER") is True

    defn = get_feature_definition("  Password_Tools  ")
    assert defn is not None
    assert defn["name"] == "password_tools"


def test_registry_immutability():
    defn = get_feature_definition("task")
    assert defn is not None
    defn["default_enabled"] = False

    original = get_feature_definition("task")
    assert original["default_enabled"] is True

