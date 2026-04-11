import pytest
import asyncio
from unittest.mock import MagicMock, patch
from backend.core.orchestrator import YukiOrchestrator

@pytest.fixture
def mock_send_fn():
    return MagicMock()

@pytest.fixture
def orchestrator(mock_send_fn):
    # Mocking external model-heavy components to avoid loading them in unit tests
    with patch("backend.config.cfg", {}), \
         patch("backend.speech.sentinel.VoiceSentinel"), \
         patch("backend.speech.sentinel.VADStreamProcessor"), \
         patch("backend.speech.recognition.AsyncWhisperStreamer"), \
         patch("backend.speech.wake_word.WakeWordDetector"), \
         patch("backend.speech.synthesis_kokoro.HPVoiceSwitcher"), \
         patch("backend.proactive_agent.ProactiveAgent"):
        orchestrator = YukiOrchestrator(mock_send_fn)
        return orchestrator

def test_turn_id_generation(orchestrator):
    """Verify that turn IDs increment correctly."""
    id1 = orchestrator._new_turn_id()
    id2 = orchestrator._new_turn_id()
    
    assert id1 == "turn-000001"
    assert id2 == "turn-000002"
    assert orchestrator._turn_counter == 2

def test_usage_tracking(orchestrator):
    """Verify that session usage starts at zero."""
    assert orchestrator.session_usage["input"] == 0
    assert orchestrator.session_usage["output"] == 0
    assert orchestrator.session_usage["cost"] == 0.0
    assert orchestrator.session_usage["turns"] == 0

@pytest.mark.asyncio
async def test_emit_event(orchestrator, mock_send_fn):
    """Verify that events are emitted through the send function."""
    orchestrator._emit("test_event", payload_data="hello")
    
    # sequence should be 1 after one emit
    mock_send_fn.assert_called_once()
    args = mock_send_fn.call_args[0][0]
    assert args["type"] == "test_event"
    assert args["payload_data"] == "hello"
    assert args["seq"] == 1
