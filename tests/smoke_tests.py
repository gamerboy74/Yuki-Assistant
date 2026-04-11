import pytest
import asyncio
from backend.brain import process_stream
from backend.plugins import get_plugin, execute_plugin

@pytest.mark.asyncio
async def test_brain_cascade_logic():
    """Verify that the brain router correctly identifies conversational vs agentic paths."""
    from backend.brain.shared import is_conversational
    
    assert is_conversational("hi yuki") == True
    assert is_conversational("open chrome and search for weather") == False
    assert is_conversational("kaise ho yuki") == True

@pytest.mark.asyncio
async def test_plugin_modular_discovery():
    """Verify that the refactored recursive plugin discovery works for system domain."""
    # These were previously in a flat structure, now in system/ subpackage
    p_open = get_plugin("open_app")
    p_power = get_plugin("system_control")
    p_info = get_plugin("system_info")
    
    assert p_open is not None
    assert p_power is not None
    assert p_info is not None
    assert "Open a Windows application" in p_open.description

@pytest.mark.asyncio
async def test_executor_routing():
    """Verify that execute_plugin routes correctly to the new modular system."""
    res = execute_plugin("system_info", {"query": "time"})
    assert "The time is" in res or "I couldn't" in res

@pytest.mark.asyncio
async def test_history_integrity():
    """Verify that shared history tracks messages correctly."""
    from backend.brain import shared
    shared.clear_history()
    
    shared.add_user_message("Hello")
    shared.add_assistant_message("Hi Sir")
    
    history = shared.get_history()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["content"] == "Hi Sir"

if __name__ == "__main__":
    pytest.main([__file__])
