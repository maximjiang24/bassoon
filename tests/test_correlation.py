"""
Unit tests for analysis.correlation.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from analysis.correlation import (
    correlate_embouchure_intonation,
    identify_embouchure_changes,
    correlate_by_register,
    _empty_correlation,
)


def _make_landmarks(times: list[float], jaw_signal=None) -> dict:
    n = len(times)
    if jaw_signal is None:
        jaw_signal = [320.0] * n
    return {
        "times":        list(times),
        "mouth_width":  [80.0] * n,
        "mouth_height": [12.0] * n,
        "jaw_position": list(jaw_signal),
        "lip_tension":  [0.5] * n,
    }


def _make_stability(starts: np.ndarray, scores: np.ndarray) -> dict:
    return {
        "window_starts":   starts,
        "window_ends":     starts + 1.0,
        "mean_freq":       np.full_like(scores, 220.0, dtype=float),
        "variance":        np.zeros_like(scores, dtype=float),
        "drift_rate":      np.zeros_like(scores, dtype=float),
        "stability_score": scores,
        "note_names":      ["A3"] * len(scores),
    }


class TestCorrelateEmbouchureIntonation:
    def test_returns_required_keys(self):
        v_t = list(np.linspace(0.0, 10.0, 100))
        a_t = np.linspace(0.0, 10.0, 1000)
        landmarks = _make_landmarks(v_t)
        stab = _make_stability(np.arange(0.0, 10.0, 1.0), np.full(10, 0.8))
        result = correlate_embouchure_intonation(landmarks, stab, a_t, v_t)
        for key in ("mouth_width_vs_stability", "mouth_height_vs_stability",
                    "jaw_stability_vs_intonation", "lip_tension_vs_stability",
                    "overall_correlation"):
            assert key in result

    def test_short_overlap_returns_empty(self):
        v_t = [0.0, 0.5]
        a_t = np.array([0.0, 0.4])
        result = correlate_embouchure_intonation(
            _make_landmarks(v_t), _make_stability(np.array([0.0]), np.array([0.5])), a_t, v_t
        )
        for key in ("mouth_width_vs_stability", "mouth_height_vs_stability",
                    "jaw_stability_vs_intonation", "lip_tension_vs_stability"):
            assert math.isnan(result[key]["r"])
        assert math.isnan(result["overall_correlation"])

    def test_perfect_correlation_recovered(self):
        a_t = np.linspace(0.0, 20.0, 2000)
        starts = np.arange(0.0, 20.0, 1.0)
        scores = np.linspace(0.0, 1.0, len(starts))
        stab = _make_stability(starts, scores)

        v_t = list(np.linspace(0.0, 20.0, 600))
        jaw = [300.0 + 50.0 * (t / 20.0) for t in v_t]
        landmarks = _make_landmarks(v_t, jaw_signal=jaw)

        result = correlate_embouchure_intonation(landmarks, stab, a_t, v_t)
        r = result["jaw_stability_vs_intonation"]["r"]
        assert r == pytest.approx(1.0, abs=0.05)

    def test_pearson_r_in_valid_range(self):
        rng = np.random.default_rng(42)
        a_t = np.linspace(0.0, 15.0, 1500)
        starts = np.arange(0.0, 15.0, 1.0)
        scores = rng.uniform(0, 1, len(starts))
        stab = _make_stability(starts, scores)

        v_t = list(np.linspace(0.0, 15.0, 450))
        jaw = list(rng.normal(320, 5, len(v_t)))
        landmarks = _make_landmarks(v_t, jaw_signal=jaw)

        result = correlate_embouchure_intonation(landmarks, stab, a_t, v_t)
        for key in ("mouth_width_vs_stability", "jaw_stability_vs_intonation",
                    "lip_tension_vs_stability"):
            r = result[key]["r"]
            if not math.isnan(r):
                assert -1.0 <= r <= 1.0


class TestIdentifyEmbouchureChanges:
    def test_no_change_yields_empty_list(self):
        landmarks = _make_landmarks(list(np.linspace(0, 5, 50)))
        events = identify_embouchure_changes(landmarks, threshold=2.0)
        assert events == []

    def test_detects_jump(self):
        n = 50
        times = list(np.linspace(0, 5, n))
        jaw = [320.0] * n
        jaw[25] = 340.0  # 20 px jump
        landmarks = _make_landmarks(times, jaw_signal=jaw)
        events = identify_embouchure_changes(landmarks, threshold=10.0)
        names = [e[1] for e in events]
        assert "jaw_position" in names
        assert any(e[2] >= 10.0 for e in events)

    def test_returns_sorted_by_time(self):
        n = 40
        times = list(np.linspace(0, 4, n))
        jaw = [320.0] * n
        mw = [80.0] * n
        jaw[10] = 350.0
        mw[20] = 100.0
        jaw[30] = 290.0
        landmarks = _make_landmarks(times, jaw_signal=jaw)
        landmarks["mouth_width"] = mw
        events = identify_embouchure_changes(landmarks, threshold=10.0)
        times_only = [e[0] for e in events]
        assert times_only == sorted(times_only)

    def test_lip_tension_threshold_scaled(self):
        n = 30
        times = list(np.linspace(0, 3, n))
        lt = [0.5] * n
        lt[15] = 0.62  # 0.12 jump on a 0–1 scale
        landmarks = _make_landmarks(times)
        landmarks["lip_tension"] = lt
        # threshold=10 → effective threshold for lip_tension is 0.10
        events = identify_embouchure_changes(landmarks, threshold=10.0)
        assert any(e[1] == "lip_tension" for e in events)


class TestCorrelateByRegister:
    def test_empty_register_returns_empty_correlation(self):
        intonation = {"low": {"metrics": None}}
        landmarks = _make_landmarks(list(np.linspace(0, 5, 50)))
        result = correlate_by_register(landmarks, intonation, "low")
        assert math.isnan(result["overall_correlation"])

    def test_returns_required_keys(self):
        starts = np.arange(0.0, 10.0, 1.0)
        scores = np.linspace(0.0, 1.0, len(starts))
        intonation = {
            "tenor": {"metrics": _make_stability(starts, scores)},
        }
        landmarks = _make_landmarks(list(np.linspace(0, 10, 300)))
        result = correlate_by_register(landmarks, intonation, "tenor")
        for key in ("mouth_width_vs_stability", "jaw_stability_vs_intonation",
                    "overall_correlation"):
            assert key in result


def test_empty_correlation_helper():
    result = _empty_correlation()
    assert math.isnan(result["overall_correlation"])
    for key in ("mouth_width_vs_stability", "mouth_height_vs_stability",
                "jaw_stability_vs_intonation", "lip_tension_vs_stability"):
        assert math.isnan(result[key]["r"])
        assert math.isnan(result[key]["p"])
