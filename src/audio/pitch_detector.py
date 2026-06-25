"""
Pitch detection and frequency conversion utilities.
"""

import numpy as np
import os

try:
    import librosa
except ImportError as e:
    raise ImportError("librosa is required: pip install librosa") from e

from utils.config import SAMPLE_RATE, HOP_LENGTH, CONFIDENCE_THRESHOLD, REFERENCE_FREQ

# Standard Western note names with flats for accidentals (bassoon convention).
_NOTE_NAMES = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"]


class PitchDetector:
    """Pitch detection and frequency conversion for bassoon audio."""

    def __init__(
        self,
        sr: int = SAMPLE_RATE,
        hop_length: int = HOP_LENGTH,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        reference_freq: float = REFERENCE_FREQ,
    ) -> None:
        self.sr = sr
        self.hop_length = hop_length
        self.confidence_threshold = confidence_threshold
        self.reference_freq = reference_freq

    def detect_pitch(
        self,
        audio: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Detect pitch over time using the configured detector.

        Parameters
        ----------
        audio:
            1-D float32 array of audio samples.

        Returns
        -------
        times : np.ndarray
            Centre time (seconds) of each analysis frame.
        frequencies : np.ndarray
            Fundamental frequency in Hz per frame. Low-confidence frames are NaN.
        confidence : np.ndarray
            Voiced probability in [0, 1] per frame.

        Raises
        ------
        ValueError
            If *audio* is empty or not 1-D.
        """
        if audio.ndim != 1:
            raise ValueError(f"audio must be 1-D, got shape {audio.shape}")
        if audio.size == 0:
            raise ValueError("audio array is empty")

        detector = os.environ.get("PITCH_DETECTOR", "yin").strip().lower()
        if detector == "pyin":
            return self._detect_pitch_pyin(audio)
        return self._detect_pitch_yin(audio)

    def _detect_pitch_pyin(
        self,
        audio: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        # pYIN is more robust on complex bassoon tones, but it is too slow for
        # Render's free-tier request timeout on cold starts.
        f0, voiced_flag, voiced_prob = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("Bb1"),
            fmax=librosa.note_to_hz("Eb5"),
            sr=self.sr,
            hop_length=self.hop_length,
        )

        times = librosa.times_like(f0, sr=self.sr, hop_length=self.hop_length)

        # Use pYIN's HMM-based voiced_flag rather than re-thresholding the raw
        # probability. Bassoon's dense harmonic spectrum keeps voiced_prob low
        # even on well-sustained notes, causing the probability gate to drop
        # entire notes. voiced_flag is the more reliable voicing decision.
        frequencies = f0.copy()
        frequencies[~voiced_flag] = np.nan

        return times, frequencies, voiced_prob

    def _detect_pitch_yin(
        self,
        audio: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Fast hosted pitch detection using YIN plus an RMS voicing gate."""
        frame_length = 2048
        f0 = librosa.yin(
            audio,
            fmin=librosa.note_to_hz("Bb1"),
            fmax=librosa.note_to_hz("Eb5"),
            sr=self.sr,
            hop_length=self.hop_length,
            frame_length=frame_length,
        )
        times = librosa.times_like(f0, sr=self.sr, hop_length=self.hop_length)

        rms = librosa.feature.rms(
            y=audio,
            frame_length=frame_length,
            hop_length=self.hop_length,
            center=True,
        )[0]
        if rms.size < f0.size:
            rms = np.pad(rms, (0, f0.size - rms.size), mode="edge")
        elif rms.size > f0.size:
            rms = rms[:f0.size]

        max_rms = float(np.max(rms)) if rms.size else 0.0
        if max_rms <= 1e-8:
            frequencies = np.full_like(f0, np.nan, dtype=float)
            confidence = np.zeros_like(f0, dtype=float)
            return times, frequencies, confidence

        gate = max(max_rms * 0.02, float(np.percentile(rms, 20)) * 0.5, 1e-5)
        voiced_flag = rms >= gate
        confidence = np.clip(rms / max_rms, 0.0, 1.0)

        frequencies = f0.astype(float, copy=True)
        frequencies[~voiced_flag] = np.nan

        return times, frequencies, confidence

    def hz_to_cents(self, freq: float) -> float:
        """Convert a frequency in Hz to cents relative to ``reference_freq``.

        Returns ``float('nan')`` if *freq* is NaN or <= 0.
        """
        if np.isnan(freq) or freq <= 0:
            return float("nan")
        return 1200.0 * np.log2(freq / self.reference_freq)

    @staticmethod
    def get_note_name(freq: float) -> str:
        """Return the nearest Western note name for a given frequency.

        Returns ``"?"`` if *freq* is NaN, zero, or negative.
        """
        if np.isnan(freq) or freq <= 0:
            return "?"
        midi = 69.0 + 12.0 * np.log2(freq / 440.0)
        midi_rounded = int(round(midi))
        pitch_class = midi_rounded % 12
        octave = (midi_rounded // 12) - 1
        return f"{_NOTE_NAMES[pitch_class]}{octave}"


# ---------------------------------------------------------------------------
# Module-level convenience functions (preserve existing call-sites)
# ---------------------------------------------------------------------------

_default = PitchDetector()


def detect_pitch(
    audio: np.ndarray,
    sr: int = SAMPLE_RATE,
    hop_length: int = HOP_LENGTH,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return PitchDetector(sr=sr, hop_length=hop_length).detect_pitch(audio)


def hz_to_cents(freq: float, reference_freq: float = REFERENCE_FREQ) -> float:
    return PitchDetector(reference_freq=reference_freq).hz_to_cents(freq)


def get_note_name(freq: float) -> str:
    return PitchDetector.get_note_name(freq)
