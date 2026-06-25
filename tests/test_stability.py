"""
Tests for stability.py — compute_stability_metrics, identify_unstable_regions,
and register_analysis.

All tests use synthetic numpy arrays so no audio hardware or librosa is needed.
"""

import math
import pytest
import numpy as np

from analysis.stability import (
    compute_stability_metrics,
    identify_unstable_regions,
    register_analysis,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_steady(freq_hz: float, duration: float = 3.0, sr: int = 44100, hop: int = 512) -> tuple:
    """Return (times, frequencies) for a perfectly steady tone."""
    n_frames = int(duration * sr / hop)
    times = np.arange(n_frames) * hop / sr
    frequencies = np.full(n_frames, freq_hz)
    return times, frequencies


def _make_noisy(freq_hz: float, noise_cents: float, duration: float = 3.0,
                sr: int = 44100, hop: int = 512, seed: int = 0) -> tuple:
    """Return (times, frequencies) with Gaussian pitch noise in cents."""
    rng = np.random.default_rng(seed)
    n_frames = int(duration * sr / hop)
    times = np.arange(n_frames) * hop / sr
    offsets_hz = freq_hz * (2 ** (rng.normal(0, noise_cents / 1200, n_frames)) - 1)
    frequencies = freq_hz + offsets_hz
    return times, frequencies


# ---------------------------------------------------------------------------
# compute_stability_metrics
# ---------------------------------------------------------------------------

class TestComputeStabilityMetrics:
    """Tests for compute_stability_metrics()."""

    def test_returns_expected_keys(self):
        """Result dict must contain all documented keys."""
        times, freqs = _make_steady(440.0)
        result = compute_stability_metrics(times, freqs)
        for key in ("window_starts", "window_ends", "mean_freq", "variance",
                    "drift_rate", "stability_score", "note_names"):
            assert key in result, f"Missing key: {key}"

    def test_steady_tone_has_near_zero_variance(self):
        """A perfectly steady tone should have variance ≈ 0 cents²."""
        times, freqs = _make_steady(440.0, duration=5.0)
        result = compute_stability_metrics(times, freqs)
        valid = result["variance"][~np.isnan(result["variance"])]
        assert np.all(valid < 1e-6)

    def test_steady_tone_stability_score_near_one(self):
        """A perfectly steady tone should have stability score ≈ 1."""
        times, freqs = _make_steady(440.0, duration=5.0)
        result = compute_stability_metrics(times, freqs)
        scores = result["stability_score"]
        assert np.all(scores > 0.99)

    def test_noisy_tone_has_higher_variance(self):
        """A noisy tone should have higher variance than a steady one."""
        times_s, freqs_s = _make_steady(440.0, duration=5.0)
        times_n, freqs_n = _make_noisy(440.0, noise_cents=50.0, duration=5.0)
        var_steady = np.nanmean(compute_stability_metrics(times_s, freqs_s)["variance"])
        var_noisy = np.nanmean(compute_stability_metrics(times_n, freqs_n)["variance"])
        assert var_noisy > var_steady

    def test_window_count_matches_duration(self):
        """Number of windows should equal ceil(duration / window_size)."""
        import math as _math
        duration = 5.0
        window_size = 1.0
        times, freqs = _make_steady(440.0, duration=duration)
        result = compute_stability_metrics(times, freqs, window_size=window_size)
        expected = _math.ceil(times[-1] / window_size)
        assert len(result["window_starts"]) == expected

    def test_mean_freq_close_to_input(self):
        """Mean frequency per window should be close to the input frequency."""
        times, freqs = _make_steady(330.0, duration=4.0)
        result = compute_stability_metrics(times, freqs)
        valid = result["mean_freq"][~np.isnan(result["mean_freq"])]
        assert np.allclose(valid, 330.0, atol=0.1)

    def test_note_names_length_matches_windows(self):
        """note_names list length must equal number of windows."""
        times, freqs = _make_steady(440.0, duration=3.0)
        result = compute_stability_metrics(times, freqs)
        assert len(result["note_names"]) == len(result["window_starts"])

    def test_all_nan_frequencies_returns_nan_metrics(self):
        """All-NaN input should produce NaN metrics without raising."""
        times = np.linspace(0, 3, 100)
        freqs = np.full(100, np.nan)
        result = compute_stability_metrics(times, freqs)
        assert np.all(np.isnan(result["mean_freq"]))

    def test_shape_mismatch_raises(self):
        """Mismatched times/frequencies shapes must raise ValueError."""
        times = np.linspace(0, 1, 50)
        freqs = np.linspace(440, 440, 60)
        with pytest.raises(ValueError):
            compute_stability_metrics(times, freqs)

    def test_custom_window_size(self):
        """Passing a custom window_size should change the number of windows."""
        times, freqs = _make_steady(440.0, duration=6.0)
        r1 = compute_stability_metrics(times, freqs, window_size=1.0)
        r2 = compute_stability_metrics(times, freqs, window_size=2.0)
        assert len(r1["window_starts"]) > len(r2["window_starts"])


# ---------------------------------------------------------------------------
# identify_unstable_regions
# ---------------------------------------------------------------------------

class TestIdentifyUnstableRegions:
    """Tests for identify_unstable_regions()."""

    def test_steady_tone_has_no_unstable_regions(self):
        """A perfectly steady tone should produce no unstable regions."""
        times, freqs = _make_steady(440.0, duration=5.0)
        regions = identify_unstable_regions(times, freqs, threshold=20)
        assert regions == []

    def test_noisy_tone_has_unstable_regions(self):
        """A highly noisy tone should produce at least one unstable region."""
        times, freqs = _make_noisy(440.0, noise_cents=100.0, duration=5.0)
        regions = identify_unstable_regions(times, freqs, threshold=20)
        assert len(regions) > 0

    def test_region_tuple_structure(self):
        """Each region must be a 4-tuple (start, end, note_name, variance)."""
        times, freqs = _make_noisy(440.0, noise_cents=100.0, duration=5.0)
        regions = identify_unstable_regions(times, freqs, threshold=20)
        for region in regions:
            assert len(region) == 4
            start, end, note, var = region
            assert isinstance(start, float)
            assert isinstance(end, float)
            assert isinstance(note, str)
            assert isinstance(var, float)

    def test_region_start_before_end(self):
        """Every region must have start_time < end_time."""
        times, freqs = _make_noisy(440.0, noise_cents=100.0, duration=5.0)
        regions = identify_unstable_regions(times, freqs, threshold=20)
        for start, end, _, _ in regions:
            assert start < end

    def test_high_threshold_suppresses_regions(self):
        """A very high threshold should suppress all unstable regions."""
        times, freqs = _make_noisy(440.0, noise_cents=10.0, duration=5.0)
        regions = identify_unstable_regions(times, freqs, threshold=1_000_000)
        assert regions == []

    def test_shape_mismatch_raises(self):
        """Mismatched array shapes must raise ValueError."""
        times = np.linspace(0, 1, 50)
        freqs = np.linspace(440, 440, 60)
        with pytest.raises(ValueError):
            identify_unstable_regions(times, freqs)


# ---------------------------------------------------------------------------
# register_analysis
# ---------------------------------------------------------------------------

class TestRegisterAnalysis:
    """Tests for register_analysis()."""

    def test_returns_three_registers(self):
        """Result must contain exactly the keys 'low', 'tenor', 'high'."""
        times, freqs = _make_steady(440.0, duration=3.0)
        result = register_analysis(times, freqs)
        assert set(result.keys()) == {"low", "tenor", "high"}

    def test_tenor_register_populated_for_a4(self):
        """A4 (440 Hz) falls in the tenor register; low and high should be empty."""
        times, freqs = _make_steady(440.0, duration=3.0)
        result = register_analysis(times, freqs)
        assert result["tenor"]["frame_count"] > 0
        assert result["low"]["frame_count"] == 0
        assert result["high"]["frame_count"] == 0

    def test_low_register_populated_for_bb1(self):
        """B♭1 (~58.27 Hz) falls in the low register."""
        bb1 = 440.0 * 2 ** (-39 / 12)
        times, freqs = _make_steady(bb1, duration=3.0)
        result = register_analysis(times, freqs)
        assert result["low"]["frame_count"] > 0
        assert result["tenor"]["frame_count"] == 0

    def test_high_register_populated_for_eb5(self):
        """E♭5 (~622 Hz) falls in the high register."""
        eb5 = 440.0 * 2 ** (6 / 12)
        times, freqs = _make_steady(eb5, duration=3.0)
        result = register_analysis(times, freqs)
        assert result["high"]["frame_count"] > 0
        assert result["tenor"]["frame_count"] == 0

    def test_time_fractions_sum_to_one(self):
        """time_fraction values across all registers must sum to 1.0."""
        # Mix of registers: low + tenor + high
        n = 300
        times = np.arange(n) * 512 / 44100
        freqs = np.concatenate([
            np.full(100, 58.27),   # low
            np.full(100, 440.0),   # tenor
            np.full(100, 622.25),  # high
        ])
        result = register_analysis(times, freqs)
        total = sum(result[r]["time_fraction"] for r in ("low", "tenor", "high"))
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_empty_register_has_none_metrics(self):
        """A register with no frames must have metrics=None."""
        times, freqs = _make_steady(440.0, duration=3.0)
        result = register_analysis(times, freqs)
        assert result["low"]["metrics"] is None
        assert result["high"]["metrics"] is None

    def test_all_nan_input_returns_zero_frame_counts(self):
        """All-NaN frequencies should produce zero frame counts in all registers."""
        times = np.linspace(0, 3, 100)
        freqs = np.full(100, np.nan)
        result = register_analysis(times, freqs)
        for reg in ("low", "tenor", "high"):
            assert result[reg]["frame_count"] == 0
