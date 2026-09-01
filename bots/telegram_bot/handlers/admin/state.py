from typing import Dict, Optional


_admin_states: Dict[int, str] = {}


def set_state(
    user_id: int,
    state: str
):
    _admin_states[user_id] = state


def get_state(
    user_id: int
) -> Optional[str]:
    return _admin_states.get(user_id)


def clear_state(
    user_id: int
):
    _admin_states.pop(
        user_id,
        None
    )