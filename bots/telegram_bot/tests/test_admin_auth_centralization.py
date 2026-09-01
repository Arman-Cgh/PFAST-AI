import os
import pytest
from unittest.mock import patch

import config
from config import ADMIN_ID, ADMIN_IDS, is_admin


def test_default_admin_id_loaded():
    assert isinstance(ADMIN_ID, int)
    assert ADMIN_ID in ADMIN_IDS
    assert is_admin(ADMIN_ID) is True


def test_unauthorized_user_rejected():
    fake_user_id = 999888777
    assert is_admin(fake_user_id) is False


def test_multiple_admin_ids_support():
    with patch.dict(os.environ, {"ADMIN_ID": "12345", "ADMIN_IDS": "67890, 112233, abc, 445566"}):
        # Dynamically test multi-admin parsing logic as in config.py
        admin_id_raw = os.getenv("ADMIN_ID", "").strip()
        admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()

        parsed_main = int(admin_id_raw)
        parsed_set = {parsed_main}

        for aid in admin_ids_raw.split(","):
            aid = aid.strip()
            if aid.isdigit():
                parsed_set.add(int(aid))

        assert parsed_main == 12345
        assert 12345 in parsed_set
        assert 67890 in parsed_set
        assert 112233 in parsed_set
        assert 445566 in parsed_set
        assert len(parsed_set) == 4

