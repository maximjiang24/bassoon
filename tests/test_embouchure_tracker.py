"""
Unit tests for video.embouchure_tracker.

These tests focus on the pure-Python helpers that don't require a webcam or
actual video file. The full extraction pipeline is exercised lightly via a
synthetic landmark dict.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("cv2", reason="opencv-python not installed")
pytest.importorskip("mediapipe", reason="mediapipe not installed")

from video.embouchure_tracker import (  # noqa: E402
    compute_embouchure_metrics,
    align_audio_video,
)


def _make_landmarks(n: int = 60, fps: float = 30.0, jitter: float = 0.0) -> dict:
    rng = np.random.default_rng(0)
    times = [i / fps for i in range(n)]
    base_w  = 80.0
    base_h  = 12.0
    base_jaw = 320.0
    base_lt = 0.5

    if jitter > 0:
        mw = (base_w + rng.normal(0, jitter, n)).tolist()
        mh = (base_h + rng.normal(0, jitter * 0.4, n)).tolist()
        jaw = (base_jaw + rng.normal(0, jitter, n)).tolist()
        lt = np.clip(base_lt + rng.normal(0, jitter * 0.01, n), 0, 1).tolist()
    else:
        mw = [base_w] * n
        mh = [base_h] * n
        jaw = [base_jaw] * n
        lt = [base_lt] * n

    return {
        "times":        times,
        "mouth_width":  mw,
        "mouth_height": mh,
        "jaw_position": jaw,
        "lip_tension":  lt,
    }


class TestComputeEmbouchureMetrics:
    def test_returns_required_keys(self):
        result = compute_embouchure_metrics(_make_landmarks())
        required = {
            "mean_mouth_width", "mouth_width_variance",
            "mean_mouth_height", "mouth_height_variance",
            "mean_jaw_position", "jaw_position_variance",
            "jaw_stability",
            "mean_lip_tension", "lip_tension_variance",
            "embouchure_consistency", "face_detected_pct",
        }
        assert required.issubset(result.keys())

    def test_perfect_stability_for_constant_landmarks(self):
        result = compute_embouchure_metrics(_make_landmarks(jitter=0.0))
        assert result["jaw_stability"] == pytest.approx(1.0, abs=1e-6)
        assert result["embouchure_consistency"] == pytest.approx(1.0, abs=1e-6)
        assert result["mouth_width_variance"] == pytest.approx(0.0, abs=1e-6)

    def test_variability_lowers_consistency(self):
        stable  = compute_embouchure_metrics(_make_landmarks(jitter=0.0))
        jittery = compute_embouchure_metrics(_make_landmarks(jitter=5.0))
        assert jittery["embouchure_consistency"] < stable["embouchure_consistency"]
        assert jittery["jaw_stability"] < stable["jaw_stability"]

    def test_face_detected_pct_with_nans(self):
        lm = _make_landmarks(n=10)
        for k in ("mouth_width", "mouth_height", "jaw_position", "lip_tension"):
            lm[k][:5] = [float("nan")] * 5
        result = compute_embouchure_metrics(lm)
        assert result["face_detected_pct"] == pytest.approx(50.0)

    def test_all_nan_input_yields_nan_means(self):
        n = 10
        nan = float("nan")
        lm = {
            "times":        list(range(n)),
            "mouth_width":  [nan] * n,
            "mouth_height": [nan] * n,
            "jaw_position": [nan] * n,
            "lip_tension":  [nan] * n,
        }
        result = compute_embouchure_metrics(lm)
        assert math.isnan(result["mean_mouth_width"])
        assert result["face_detected_pct"] == pytest.approx(0.0)

    def test_consistency_score_in_range(self):
        result = compute_embouchure_metrics(_make_landmarks(jitter=2.0))
        assert 0.0 <= result["embouchure_consistency"] <= 1.0
        assert 0.0 <= result["jaw_stability"] <= 1.0


class TestAlignAudioVideo:
    def test_overlap_grid_uses_audio_step(self):
        audio_t = np.linspace(0.0, 5.0, 1001)  # 5 ms step
        video_t = list(np.linspace(1.0, 4.0, 91))
        grid = align_audio_video(audio_t, video_t)
        assert grid[0] == pytest.approx(1.0)
        assert grid[-1] < 4.0
        step = grid[1] - grid[0]
        assert step == pytest.approx(audio_t[1] - audio_t[0], rel=1e-3)

    def test_video_starts_later_uses_video_start(self):
        audio_t = np.linspace(0.0, 10.0, 101)
        video_t = list(np.linspace(2.0, 8.0, 60))
        grid = align_audio_video(audio_t, video_t)
        assert grid[0] >= 2.0
        assert grid[-1] <= 8.0

    def test_no_overlap_raises(self):
        audio_t = np.linspace(0.0, 1.0, 11)
        video_t = list(np.linspace(2.0, 3.0, 11))
        with pytest.raises(ValueError, match="overlapping"):
            align_audio_video(audio_t, video_t)
