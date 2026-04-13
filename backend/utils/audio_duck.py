"""
Audio Ducking — dims all system audio when Yuki speaks.
Uses Windows Core Audio API via pycaw with a reference counter.
"""
import os
import threading
from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

# Thread-safe reference counter to prevent nested duck calls from overwriting snapshots
_lock = threading.Lock()
_duck_count = 0
_original_volumes: dict = {}

def duck():
    """Dim system audio if not already ducked."""
    global _duck_count
    with _lock:
        _duck_count += 1
        if _duck_count > 1:
            logger.debug(f"[DUCK] Already ducked (count: {_duck_count}). Skipping snapshot.")
            return

        try:
            from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
            
            # Read volume from config at call time for real-time responsiveness
            duck_vol = cfg.get("audio", {}).get("duck_volume", 0.15)
            
            sessions = AudioUtilities.GetAllSessions()
            current_pid = os.getpid()
            
            for s in sessions:
                if s.Process and s.Process.pid != current_pid:
                    try:
                        vol = s._ctl.QueryInterface(ISimpleAudioVolume)
                        _original_volumes[s.Process.pid] = vol.GetMasterVolume()
                        vol.SetMasterVolume(duck_vol, None)
                    except Exception:
                        continue # Some sessions may be transient or inaccessible
                        
            logger.debug(f"[DUCK] Audio dimmed to {duck_vol*100:.0f}%.")
        except Exception as e:
            logger.warning(f"[DUCK] Failed to duck audio: {e}")

def unduck():
    """Restore system audio when the last active duck call finishes."""
    global _duck_count
    with _lock:
        _duck_count = max(0, _duck_count - 1)
        if _duck_count > 0:
            logger.debug(f"[DUCK] Still ducked (count: {_duck_count}). Waiting for last speaker.")
            return

        try:
            from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
            
            sessions = AudioUtilities.GetAllSessions()
            for s in sessions:
                if s.Process and s.Process.pid in _original_volumes:
                    try:
                        vol = s._ctl.QueryInterface(ISimpleAudioVolume)
                        orig_vol = _original_volumes[s.Process.pid]
                        vol.SetMasterVolume(orig_vol, None)
                    except Exception:
                        continue
                        
            _original_volumes.clear()
            logger.debug("[DUCK] Audio restored.")
        except Exception as e:
            logger.warning(f"[DUCK] Failed to restore audio: {e}")


def force_restore():
    """
    Emergency restore — hard-resets counter and restores ALL ducked sessions.
    Call this on process exit to guarantee audio is never left dimmed.
    """
    global _duck_count
    with _lock:
        _duck_count = 0  # Hard reset regardless of current count
        if not _original_volumes:
            return  # Nothing was ducked, nothing to do

        try:
            from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
            sessions = AudioUtilities.GetAllSessions()
            for s in sessions:
                if s.Process and s.Process.pid in _original_volumes:
                    try:
                        vol = s._ctl.QueryInterface(ISimpleAudioVolume)
                        vol.SetMasterVolume(_original_volumes[s.Process.pid], None)
                    except Exception:
                        continue
            _original_volumes.clear()
            logger.info("[DUCK] Emergency audio restore complete.")
        except Exception as e:
            logger.warning(f"[DUCK] Emergency restore failed: {e}")

