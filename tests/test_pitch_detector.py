"""
Tests for pitch_detector.py — hz_to_cents and get_note_name.

These tests are pure-math and require no audio hardware or librosa pyin call.
"""

import math
import pytest
import numpy as np

from audio.pitch_detector import hz_to_cents, get_note_name


class TestHzToCents:
    """Tests for hz_to_cents()."""

    def test_reference_frequency_is_zero_cents(self):
        """A4 (440 Hz) relative to itself must be exactly 0 cents."""
        assert hz_to_cents(440.0) == pytest.approx(0.0)

    def test_one_octave_up_is_1200_cents(self):
        """A5 (880 Hz) is exactly 1200 cents above A4."""
        assert hz_to_cents(880.0) == pytest.approx(1200.0)

    def test_one_octave_down_is_minus_1200_cents(self):
        """A3 (220 Hz) is exactly -1200 cents below A4."""
        assert hz_to_cents(220.0) == pytest.approx(-1200.0)

    def test_one_semitone_up_is_100_cents(self):
        """B♭4 (~466.16 Hz) is 100 cents above A4."""
        bb4 = 440.0 * 2 ** (1 / 12)
        assert hz_to_cents(bb4) == pytest.approx(100.0, abs=0.01)

    def test_custom_reference_frequency(self):
        """Cents relative to a non-default reference."""
        # 880 Hz relative to 880 Hz = 0 cents
        assert hz_to_cents(880.0, reference_freq=880.0) == pytest.approx(0.0)
        # 440 Hz relative to 880 Hz = -1200 cents
        assert hz_to_cents(440.0, reference_freq=880.0) == pytest.approx(-1200.0)

    def test_zero_frequency_returns_nan(self):
        """Zero Hz is not a valid frequency; result must be NaN."""
        assert math.isnan(hz_to_cents(0.0))

    def test_negative_frequency_returns_nan(self):
        """Negative Hz is not physical; result must be NaN."""
        assert math.isnan(hz_to_cents(-100.0))

    def test_nan_input_returns_nan(self):
        """NaN input must propagate as NaN output."""
        assert math.isnan(hz_to_cents(float("nan")))

    def test_bassoon_low_bb1(self):
        """B♭1 (~58.27 Hz) should be well below 0 cents (A4)."""
        bb1 = 440.0 * 2 ** (-39 / 12)  # 39 semitones below A4
        cents = hz_to_cents(bb1)
        assert cents == pytest.approx(-3900.0, abs=1.0)


class TestGetNoteName:
    """Tests for get_note_name()."""

    def test_a4(self):
        """440 Hz is A4."""
        assert get_note_name(440.0) == "A4"

    def test_a3(self):
        """220 Hz is A3."""
        assert get_note_name(220.0) == "A3"

    def test_a5(self):
        """880 Hz is A5."""
        assert get_note_name(880.0) == "A5"

    def test_middle_c(self):
        """C4 is MIDI 60, ~261.63 Hz."""
        c4 = 440.0 * 2 ** (-9 / 12)
        assert get_note_name(c4) == "C4"

    def test_bb3(self):
        """B♭3 is 3 semitones below middle C, ~233.08 Hz."""
        bb3 = 440.0 * 2 ** (-12 / 12)  # A3
        bb3 = 440.0 * 2 ** (-11 / 12)  # B♭3 = 1 semitone above A3
        assert get_note_name(bb3) == "B♭3"

    def test_bb4(self):
        """B♭4 is 1 semitone above A4."""
        bb4 = 440.0 * 2 ** (1 / 12)
        assert get_note_name(bb4) == "B♭4"

    def test_eb5(self):
        """E♭5 is 6 semitones above B♭4 (top of bassoon range)."""
        eb5 = 440.0 * 2 ** (6 / 12)
        assert get_note_name(eb5) == "E♭5"

    def test_c_sharp(self):
        """C♯4 is 1 semitone above C4."""
        cs4 = 440.0 * 2 ** (-8 / 12)
        assert get_note_name(cs4) == "C♯4"

    def test_zero_returns_question_mark(self):
        """Zero Hz has no note name."""
        assert get_note_name(0.0) == "?"

    def test_negative_returns_question_mark(self):
        """Negative Hz has no note name."""
        assert get_note_name(-440.0) == "?"

    def test_nan_returns_question_mark(self):
        """NaN has no note name."""
        assert get_note_name(float("nan")) == "?"

    def test_slightly_sharp_rounds_to_nearest(self):
        """A frequency 30 cents sharp of A4 still rounds to A4."""
        slightly_sharp = 440.0 * 2 ** (30 / 1200)
        assert get_note_name(slightly_sharp) == "A4"

    def test_slightly_flat_rounds_to_nearest(self):
        """A frequency 30 cents flat of A4 still rounds to A4."""
        slightly_flat = 440.0 * 2 ** (-30 / 1200)
        assert get_note_name(slightly_flat) == "A4"
