import pytest
from unittest.mock import MagicMock
from backend.speech.sentinel import VADStreamProcessor

def test_vad_speech_start_trigger():
    """Verify that speech_start is yielded after min_speech_trigger chunks of speech."""
    mock_sentinel = MagicMock()
    # is_speech returns True for every call
    mock_sentinel.is_speech.return_value = True
    
    processor = VADStreamProcessor(mock_sentinel)
    processor.min_speech_trigger = 3
    
    # Chunk 1
    assert processor.process_chunk(b"fake_audio") is None
    assert processor.speech_chunks == 1
    
    # Chunk 2
    assert processor.process_chunk(b"fake_audio") is None
    assert processor.speech_chunks == 2
    
    # Chunk 3 -> Should trigger
    assert processor.process_chunk(b"fake_audio") == "speech_start"
    assert processor.is_speaking is True

def test_vad_speech_end_trigger():
    """Verify that speech_end is yielded after min_silence_trigger chunks of silence."""
    mock_sentinel = MagicMock()
    processor = VADStreamProcessor(mock_sentinel)
    processor.is_speaking = True
    processor.min_silence_trigger = 3
    
    # mock_sentinel.is_speech returns False for silence
    mock_sentinel.is_speech.return_value = False
    
    # Silence 1
    assert processor.process_chunk(b"fake_audio") is None
    assert processor.silence_chunks == 1
    
    # Silence 2
    assert processor.process_chunk(b"fake_audio") is None
    assert processor.silence_chunks == 2
    
    # Silence 3 -> Should trigger
    assert processor.process_chunk(b"fake_audio") == "speech_end"
    assert processor.is_speaking is False

def test_vad_reset_on_interruption():
    """Verify that if silence happens before speech trigger, count resets."""
    mock_sentinel = MagicMock()
    processor = VADStreamProcessor(mock_sentinel)
    processor.min_speech_trigger = 5
    
    # 3 chunks of speech
    mock_sentinel.is_speech.return_value = True
    for _ in range(3):
        processor.process_chunk(b"...")
    assert processor.speech_chunks == 3
    
    # 1 chunk of silence
    mock_sentinel.is_speech.return_value = False
    processor.process_chunk(b"...")
    assert processor.speech_chunks == 0
    assert processor.is_speaking is False
