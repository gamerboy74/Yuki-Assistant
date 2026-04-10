from backend.utils.permissions import is_confirmed, requires_explicit_confirmation
from backend.tools.dispatcher import _looks_unsafe_app_target


def test_permissions_require_confirmation_for_power_actions():
    assert requires_explicit_confirmation("shutdown") is True
    assert requires_explicit_confirmation("restart") is True
    assert requires_explicit_confirmation("sleep") is True
    assert requires_explicit_confirmation("lock") is False


def test_permissions_confirm_flag_parsing():
    assert is_confirmed({"confirm": True}) is True
    assert is_confirmed({"confirm": False}) is False
    assert is_confirmed({}) is False


def test_dispatcher_blocks_shell_control_chars():
    assert _looks_unsafe_app_target("chrome & calc") is True
    assert _looks_unsafe_app_target("notepad") is False
