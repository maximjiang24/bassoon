"""
Audio recording utilities for bassoon intonation capture.
"""

import os
import time
import threading
import numpy as np

try:
    import sounddevice as sd
except ImportError as e:
    raise ImportError("sounddevice is required: pip install sounddevice") from e

try:
    import soundfile as sf
    _HAS_SOUNDFILE = True
except ImportError:
    _HAS_SOUNDFILE = False

from utils.config import SAMPLE_RATE, RECORDING_DURATION

_RECORDINGS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "recordings"
)


class AudioRecorder:
    """Records audio from the default microphone and optionally saves to WAV."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        duration: float = RECORDING_DURATION,
    ) -> None:
        self.sample_rate = sample_rate
        self.duration = duration

    def record(
        self,
        duration: float | None = None,
        filename: str | None = None,
    ) -> np.ndarray:
        """Record audio from the default microphone.

        Parameters
        ----------
        duration:
            Length of the recording in seconds. Defaults to ``self.duration``.
        filename:
            If provided, the recording is saved to
            ``data/recordings/<filename>.wav``. The ``.wav`` extension is added
            automatically if omitted.

        Returns
        -------
        np.ndarray
            1-D float32 array of audio samples.

        Raises
        ------
        RuntimeError
            If no input device is available or the device rejects the requested
            sample rate.
        OSError
            If the output file cannot be written.
        """
        dur = duration if duration is not None else self.duration
        self._check_input_device()

        print(f"Recording for {dur:.1f} seconds — play now...")
        stop_event = threading.Event()
        self._start_progress_thread(dur, stop_event)

        try:
            audio: np.ndarray = sd.rec(
                frames=int(dur * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
            )
            sd.wait()
        except sd.PortAudioError as exc:
            raise RuntimeError(f"Recording failed: {exc}") from exc
        finally:
            stop_event.set()

        audio = audio.flatten()
        print("\nRecording complete.")

        if filename is not None:
            _save_wav(audio, self.sample_rate, filename)

        return audio

    def _check_input_device(self) -> None:
        try:
            device_info = sd.query_devices(kind="input")
        except sd.PortAudioError as exc:
            raise RuntimeError(
                "No input device found. Check that a microphone is connected."
            ) from exc

        max_rate = device_info.get("default_samplerate", self.sample_rate)
        if self.sample_rate > int(max_rate * 1.05):
            raise RuntimeError(
                f"Requested sample rate {self.sample_rate} Hz exceeds device maximum "
                f"{int(max_rate)} Hz."
            )

    def _start_progress_thread(self, duration: float, stop_event: threading.Event) -> None:
        def _run() -> None:
            start = time.monotonic()
            while not stop_event.is_set():
                elapsed = time.monotonic() - start
                remaining = max(0.0, duration - elapsed)
                print(f"\r  {elapsed:5.1f}s / {duration:.1f}s  ({remaining:.1f}s left) ",
                      end="", flush=True)
                time.sleep(0.1)

        t = threading.Thread(target=_run, daemon=True)
        t.start()


# ---------------------------------------------------------------------------
# Module-level helpers (preserve existing call-sites in tests and app.py)
# ---------------------------------------------------------------------------

def _check_input_device(sample_rate: int) -> None:
    AudioRecorder(sample_rate=sample_rate)._check_input_device()


def _start_progress_thread(duration: float, stop_event: threading.Event) -> None:
    AudioRecorder()._start_progress_thread(duration, stop_event)


def _save_wav(audio: np.ndarray, sample_rate: int, filename: str) -> None:
    if not _HAS_SOUNDFILE:
        raise OSError(
            "soundfile is required to save recordings: pip install soundfile"
        )
    if not filename.endswith(".wav"):
        filename = filename + ".wav"
    recordings_dir = os.path.abspath(_RECORDINGS_DIR)
    os.makedirs(recordings_dir, exist_ok=True)
    path = os.path.join(recordings_dir, filename)
    sf.write(path, audio, sample_rate, subtype="PCM_16")
    print(f"Saved to: {path}")


def record_audio(
    duration: float = RECORDING_DURATION,
    sample_rate: int = SAMPLE_RATE,
    filename: str | None = None,
) -> np.ndarray:
    return AudioRecorder(sample_rate=sample_rate, duration=duration).record(
        duration=duration, filename=filename
    )
