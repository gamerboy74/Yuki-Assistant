"""Permission helpers for high-impact assistant actions."""

from __future__ import annotations


_CONFIRM_REQUIRED_ACTIONS = {"shutdown", "restart", "sleep"}


def requires_explicit_confirmation(action: str) -> bool:
	"""Return True if this system action should require a confirmation flag."""
	return action.lower().strip() in _CONFIRM_REQUIRED_ACTIONS


def is_confirmed(params: dict | None) -> bool:
	"""Return True only when caller explicitly confirms destructive intent."""
	if not params:
		return False
	return bool(params.get("confirm") is True)
