"""
Tests for recorder.py — record_audio return type and filename behaviour.

Hardware calls (sd.rec, sd.wait) are mocked so these tests run without a
microphone. The sounddevice query_devices call is also mocked to avoid
PortAudio initialisation on CI machines.
"""

import os
import math
import tempfile
import pytest
import numpy as np
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_rec(frames, samplerate, channels, dtype):
    """Return a silent 2-D array matching what sd.rec would produce."""
    return np.zeros((frames, channels), dtype=dtype)


def _mock_device_info(samplerate: float = 48000.0) -> dict:
    return {"default_samplerate": samplerate, "name": "Mock Microphone"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRecordAudioReturnType:
    """record_audio must return a 1-D float32 numpy array."""

    @patch("audio.recorder.sd.wait")
    @patch("audio.recorder.sd.rec", side_effect=_fake_rec)
    @patch("audio.recorder.sd.query_devices", return_value=_mock_device_info())
    def test_returns_numpy_array(self, mock_query, mock_rec, mock_wait):
        """Return value must be a numpy ndarray."""
        from audio.recorder import record_audio
        result = record_audio(duration=0.1, sample_rate=44100)
        assert isinstance(result, np.ndarray)

    @patch("audio.recorder.sd.wait")
    @patch("audio.recorder.sd.rec", side_effect=_fake_rec)
    @patch("audio.recorder.sd.query_devices", return_value=_mock_device_info())
    def test_returns_1d_array(self, mock_query, mock_rec, mock_wait):
        """Return value must be 1-D (flattened from the 2-D sd.rec output)."""
        from audio.recorder import record_audio
        result = record_audio(duration=0.1, sample_rate=44100)
        assert result.ndim == 1

    @patch("audio.recorder.sd.wait")
    @patch("audio.recorder.sd.rec", side_effect=_fake_rec)
    @patch("audio.recorder.sd.query_devices", return_value=_mock_device_info())
    def test_returns_float32(self, mock_query, mock_rec, mock_wait):
        """Array dtype must be float32."""
        from audio.recorder import record_audio
        result = record_audio(duration=0.1, sample_rate=44100)
        assert result.dtype == np.float32

    @patch("audio.recorder.sd.wait")
    @patch("audio.recorder.sd.rec", side_effect=_fake_rec)
    @patch("audio.recorder.sd.query_devices", return_value=_mock_device_info())
    def test_length_matches_duration(self, mock_query, mock_rec, mock_wait):
        """Array length must equal duration * sample_rate."""
        from audio.recorder import record_audio
        duration = 0.5
        sr = 44100
        result = record_audio(duration=duration, sample_rate=sr)
        assert len(result) == int(duration * sr)


class TestRecordAudioFilename:
    """Tests for the filename parameter of record_audio."""

    @patch("audio.recorder.sd.wait")
    @patch("audio.recorder.sd.rec", side_effect=_fake_rec)
    @patch("audio.recorder.sd.query_devices", return_value=_mock_device_info())
    def test_no_filename_does_not_save(self, mock_query, mock_rec, mock_wait):
        """When filename=None, no file should be written."""
        from audio.recorder import record_audio
        with patch("audio.recorder._save_wav") as mock_save:
            record_audio(duration=0.1, sample_rate=44100, filename=None)
            mock_save.assert_not_called()

    @patch("audio.recorder.sd.wait")
    @patch("audio.recorder.sd.rec", side_effect=_fake_rec)
    @patch("audio.recorder.sd.query_devices", return_value=_mock_device_info())
    def test_filename_triggers_save(self, mock_query, mock_rec, mock_wait):
        """When filename is provided, _save_wav must be called once."""
        from audio.recorder import record_audio
        with patch("audio.recorder._save_wav") as mock_save:
            record_audio(duration=0.1, sample_rate=44100, filename="test_note")
            mock_save.assert_called_once()

    @patch("audio.recorder.sd.wait")
    @patch("audio.recorder.sd.rec", side_effect=_fake_rec)
    @patch("audio.recorder.sd.query_devices", return_value=_mock_device_info())
    def test_filename_passed_to_save(self, mock_query, mock_rec, mock_wait):
        """The exact filename string must be forwarded to _save_wav."""
        from audio.recorder import record_audio
        with patch("audio.recorder._save_wav") as mock_save:
            record_audio(duration=0.1, sample_rate=44100, filename="my_recording")
            args = mock_save.call_args[0]
            assert args[2] == "my_recording"

    @patch("audio.recorder._HAS_SOUNDFILE", True)
    @patch("audio.recorder.sf")
    @patch("audio.recorder.sd.wait")
    @patch("audio.recorder.sd.rec", side_effect=_fake_rec)
    @patch("audio.recorder.sd.query_devices", return_value=_mock_device_info())
    def test_wav_extension_added_automatically(
        self, mock_query, mock_rec, mock_wait, mock_sf
    ):
        """_save_wav must append .wav when the filename has no extension."""
        from audio.recorder import _save_wav
        audio = np.zeros(100, dtype=np.float32)
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("audio.recorder._RECORDINGS_DIR", tmpdir):
                _save_wav(audio, 44100, "no_extension")
                written_path = mock_sf.write.call_args[0][0]
                assert written_path.endswith(".wav")

    @patch("audio.recorder._HAS_SOUNDFILE", True)
    @patch("audio.recorder.sf")
    @patch("audio.recorder.sd.wait")
    @patch("audio.recorder.sd.rec", side_effect=_fake_rec)
    @patch("audio.recorder.sd.query_devices", return_value=_mock_device_info())
    def test_wav_extension_not_doubled(
        self, mock_query, mock_rec, mock_wait, mock_sf
    ):
        """_save_wav must not append .wav when the filename already ends in .wav."""
        from audio.recorder import _save_wav
        audio = np.zeros(100, dtype=np.float32)
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("audio.recorder._RECORDINGS_DIR", tmpdir):
                _save_wav(audio, 44100, "already.wav")
                written_path = mock_sf.write.call_args[0][0]
                assert not written_path.endswith(".wav.wav")


class TestRecordAudioErrorHandling:
    """Tests for error conditions in record_audio."""

    @patch(
        "audio.recorder.sd.query_devices",
        side_effect=__import__("sounddevice").PortAudioError("no device"),
    )
    def test_no_device_raises_runtime_error(self, mock_query):
        """Missing microphone must raise RuntimeError with a helpful message."""
        from audio.recorder import record_audio
        with pytest.raises(RuntimeError, match="No input device"):
            record_audio(duration=0.1)

    @patch("audio.recorder.sd.query_devices", return_value=_mock_device_info(samplerate=8000.0))
    def test_sample_rate_too_high_raises_runtime_error(self, mock_query):
        """Requesting a sample rate above the device maximum must raise RuntimeError."""
        from audio.recorder import record_audio
        with pytest.raises(RuntimeError, match="sample rate"):
            record_audio(duration=0.1, sample_rate=44100)
