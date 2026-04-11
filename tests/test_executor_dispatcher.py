import pytest
from unittest.mock import MagicMock, patch
from backend.executor import execute

def test_execute_none():
    """Verify that action type 'none' returns None."""
    action = {"type": "none", "params": {}}
    assert execute(action) is None

@patch("backend.plugins.execute_plugin")
def test_execute_youtube_dispatch(mock_execute):
    """Verify that 'play_youtube' routes to the correct plugin."""
    action = {"type": "play_youtube", "params": {"query": "Lo-fi beats"}}
    execute(action)
    mock_execute.assert_called_once_with("play_youtube", {"query": "Lo-fi beats"})

@patch("backend.plugins.execute_plugin")
def test_execute_spotify_dispatch(mock_execute):
    """Verify that 'play_spotify' routes to the correct plugin."""
    action = {"type": "play_spotify", "params": {"query": "After Hours"}}
    execute(action)
    mock_execute.assert_called_once_with("play_spotify", {"query": "After Hours"})

def test_execute_unknown_type():
    """Verify that an unknown action type returns a graceful error/None."""
    # Depending on implementation, it might log an error and return None
    action = {"type": "non_existent_command", "params": {}}
    # Just checking it doesn't crash for now
    execute(action)
