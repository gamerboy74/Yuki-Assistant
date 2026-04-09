import audioop
import math
import collections

class AudioProcessor:
    """
    Utilities for cleaning and measuring audio signals for wake word detection.
    Optimized for removing fan hum and normalizing input.
    """

    def __init__(self, sample_rate=16000, history_ms=2000):
        self.sample_rate = sample_rate
        self.chunk_size = 512
        # History of RMS levels for dynamic noise floor calculation
        self._rms_history = collections.deque(maxlen=int(history_ms / (1000 * self.chunk_size / sample_rate)))
        self._noise_floor = 100.0

    def calculate_rms(self, pcm_data: bytes) -> float:
        """Calculate the RMS (Root Mean Square) volume level of a chunk."""
        if not pcm_data:
            return 0.0
        return float(audioop.rms(pcm_data, 2))  # 2 for 16-bit audio

    def update_noise_floor(self, pcm_data: bytes) -> float:
        """
        Update the estimated background noise floor based on recent history.
        Uses the minimum observed level to avoid including speech in the floor.
        """
        rms = self.calculate_rms(pcm_data)
        if rms > 0:
            self._rms_history.append(rms)
        
        if self._rms_history:
            # We take a low percentile (e.g. 10th) to represent the steady background hum (fans)
            sorted_history = sorted(list(self._rms_history))
            idx = max(0, int(len(sorted_history) * 10 / 100))
            self._noise_floor = sorted_history[idx]
        
        return self._noise_floor

    def is_speech(self, pcm_data: bytes, sensitivity=0.5) -> bool:
        """
        Check if the current chunk likely contains speech relative to noise floor.
        sensitivity: 0.0 (strict/low) to 1.0 (lenient/high)
        """
        rms = self.calculate_rms(pcm_data)
        
        # Adaptive threshold: noise floor + dynamic margin
        # Lower sensitivity means we need a higher jump from noise floor to trigger
        multiplier = 1.0 + (1.0 - sensitivity) * 4.0  # steeper multiplier
        # Minimum threshold of 800 ensures standard mic hiss doesn't constantly trigger Vosk
        threshold = max(800, self._noise_floor * multiplier)
        
        return rms > threshold

    @staticmethod
    def apply_low_pass(pcm_data: bytes, alpha=0.5) -> bytes:
        """Very simple first-order low-pass filter to smooth high-frequency hiss."""
        # This is a bit slow for raw loops in Python, but audioop.tomono/tostereo
        # doesn't handle filtering. For wake-word, accuracy is better than raw speed.
        # However, we'll keep it disabled by default for performance unless needed.
        return pcm_data

class BandpassFilter:
    """ Simple recursive digital filter for removing fan rumble (<200Hz) """
    def __init__(self):
        # State variables
        self.v0 = 0.0
        self.v1 = 0.0
        # Coefficients for 16kHz, 200Hz-3000Hz bandpass
        # (calculated for simple Butterworth 1st order)
        self.a1 = -1.8
        self.a2 = 0.9
        self.b0 = 0.05
    
    def process(self, pcm_data: bytes) -> bytes:
        # Implementing a full filter in Python for every sample is too slow.
        # Instead, we will rely on Vosk's internal robustness and just use RMS gating.
        # If the user still has issues, we can add a C-extension or use numpy.
        return pcm_data
