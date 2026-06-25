"""
Correlation analysis between embouchure metrics and intonation stability.
"""

from __future__ import annotations

import numpy as np
from scipy import stats as scipy_stats


class CorrelationAnalyzer:
    """Computes correlations between embouchure metrics and intonation stability."""

    # These four pairs capture the physical mechanics of bassoon embouchure:
    # - mouth_width: wider embouchure generally relaxes reed pressure, affecting pitch
    # - mouth_height: vertical aperture controls air column speed and tone center
    # - jaw_position: jaw drop is the primary mechanism for lowering pitch on bassoon
    # - lip_tension: reed pinch directly raises pitch; over-tensing causes sharp intonation
    _PAIRS: dict[str, str] = {
        "mouth_width_vs_stability":    "mouth_width",
        "mouth_height_vs_stability":   "mouth_height",
        "jaw_stability_vs_intonation": "jaw_position",
        "lip_tension_vs_stability":    "lip_tension",
    }

    _METRICS: list[str] = ["mouth_width", "mouth_height", "jaw_position", "lip_tension"]

    def correlate_embouchure_intonation(
        self,
        embouchure_landmarks: dict,
        stability_metrics: dict,
        audio_times: np.ndarray,
        video_times: list[float],
    ) -> dict:
        """Pearson correlations between embouchure metrics and intonation stability.

        Both time series are resampled onto a common time grid before correlation.
        Frames where either series is NaN are excluded pairwise.

        Args:
            embouchure_landmarks: Output of
                :func:`video.embouchure_tracker.extract_facial_landmarks`.
                Must contain ``times``, ``mouth_width``, ``mouth_height``,
                ``jaw_position``, and ``lip_tension`` keys.
            stability_metrics: Output of
                :func:`analysis.stability.compute_stability_metrics`.
                Must contain ``window_starts`` and ``stability_score`` keys.
            audio_times: 1-D array of audio frame times (seconds).
            video_times: List of video frame times (seconds).

        Returns:
            Dict with Pearson *r* values (−1 to +1) and p-values:

            - ``mouth_width_vs_stability``     – r and p
            - ``mouth_height_vs_stability``    – r and p
            - ``jaw_stability_vs_intonation``  – r and p
            - ``lip_tension_vs_stability``     – r and p
            - ``overall_correlation``          – mean |r| across all four pairs
        """
        stab_times  = stability_metrics["window_starts"] + 0.5
        stab_scores = stability_metrics["stability_score"]

        t_start = max(float(audio_times[0]),  float(video_times[0]))
        t_end   = min(float(audio_times[-1]), float(video_times[-1]))
        grid    = np.arange(t_start, t_end, 1.0)

        if grid.size < 3:
            return self._empty_correlation()

        stab_on_grid = np.interp(grid, stab_times, stab_scores)
        v_times      = np.array(video_times, dtype=float)

        return self._correlate_pairs(grid, v_times, embouchure_landmarks, stab_on_grid)

    def identify_embouchure_changes(
        self,
        embouchure_landmarks: dict,
        threshold: float = 5.0,
    ) -> list[tuple[float, str, float]]:
        """Detect moments of significant embouchure change.

        A change event is recorded when the frame-to-frame delta of any tracked
        metric exceeds *threshold* (in the metric's native units).

        Args:
            embouchure_landmarks: Output of
                :func:`video.embouchure_tracker.extract_facial_landmarks`.
            threshold: Minimum frame-to-frame change magnitude to flag as an event.
                Units are pixels for spatial metrics, 0–1 scale for lip_tension.

        Returns:
            List of ``(time, metric_name, change_magnitude)`` tuples, sorted by time.
        """
        times  = np.array(embouchure_landmarks["times"], dtype=float)
        events: list[tuple[float, str, float]] = []

        for name in self._METRICS:
            raw = np.array(embouchure_landmarks[name], dtype=float)
            # Scale threshold for lip_tension (0-1 range vs pixel metrics)
            eff_threshold = threshold * 0.01 if name == "lip_tension" else threshold

            for i in range(1, len(raw)):
                if np.isnan(raw[i]) or np.isnan(raw[i - 1]):
                    continue
                delta = abs(float(raw[i] - raw[i - 1]))
                if delta >= eff_threshold:
                    events.append((float(times[i]), name, round(delta, 3)))

        events.sort(key=lambda e: e[0])
        return events

    def correlate_by_register(
        self,
        embouchure_landmarks: dict,
        intonation_data: dict,
        register_type: str,
    ) -> dict:
        """Compute embouchure–intonation correlation for a single register.

        Args:
            embouchure_landmarks: Output of
                :func:`video.embouchure_tracker.extract_facial_landmarks`.
            intonation_data: Output of
                :func:`analysis.stability.register_analysis`. Must have a key
                matching *register_type* with a ``"metrics"`` sub-dict.
            register_type: One of ``"low"``, ``"tenor"``, ``"high"``.

        Returns:
            Same structure as :meth:`correlate_embouchure_intonation` but
            computed only on frames belonging to *register_type*.  Returns
            an empty correlation dict if the register had no data.
        """
        reg     = intonation_data.get(register_type, {})
        metrics = reg.get("metrics")
        if metrics is None or metrics["stability_score"].size == 0:
            return self._empty_correlation()

        stab_times  = metrics["window_starts"] + 0.5
        stab_scores = metrics["stability_score"]

        v_times = np.array(embouchure_landmarks["times"], dtype=float)
        t_start = max(float(stab_times[0]),  float(v_times[0]))
        t_end   = min(float(stab_times[-1]), float(v_times[-1]))
        grid    = np.arange(t_start, t_end, 1.0)

        if grid.size < 3:
            return self._empty_correlation()

        stab_on_grid = np.interp(grid, stab_times, stab_scores)
        return self._correlate_pairs(grid, v_times, embouchure_landmarks, stab_on_grid)

    def _correlate_pairs(
        self,
        grid: np.ndarray,
        v_times: np.ndarray,
        embouchure_landmarks: dict,
        stab_on_grid: np.ndarray,
    ) -> dict:
        result: dict = {}
        r_vals: list[float] = []

        for key, name in self._PAIRS.items():
            raw       = np.array(embouchure_landmarks[name], dtype=float)
            x_on_grid = np.interp(grid, v_times, raw)
            valid     = ~(np.isnan(x_on_grid) | np.isnan(stab_on_grid))

            if valid.sum() < 3:
                result[key] = {"r": float("nan"), "p": float("nan")}
                continue

            r, p = scipy_stats.pearsonr(x_on_grid[valid], stab_on_grid[valid])
            result[key] = {"r": round(float(r), 4), "p": round(float(p), 4)}
            r_vals.append(abs(float(r)))

        result["overall_correlation"] = round(float(np.mean(r_vals)), 4) if r_vals else float("nan")
        return result

    @staticmethod
    def _empty_correlation() -> dict:
        nan = float("nan")
        return {
            "mouth_width_vs_stability":    {"r": nan, "p": nan},
            "mouth_height_vs_stability":   {"r": nan, "p": nan},
            "jaw_stability_vs_intonation": {"r": nan, "p": nan},
            "lip_tension_vs_stability":    {"r": nan, "p": nan},
            "overall_correlation":         nan,
        }


# ---------------------------------------------------------------------------
# Module-level convenience functions (preserve existing call-sites)
# ---------------------------------------------------------------------------

_default = CorrelationAnalyzer()


def correlate_embouchure_intonation(
    embouchure_landmarks: dict,
    stability_metrics: dict,
    audio_times: np.ndarray,
    video_times: list[float],
) -> dict:
    return _default.correlate_embouchure_intonation(
        embouchure_landmarks, stability_metrics, audio_times, video_times
    )


def identify_embouchure_changes(
    embouchure_landmarks: dict,
    threshold: float = 5.0,
) -> list[tuple[float, str, float]]:
    return _default.identify_embouchure_changes(embouchure_landmarks, threshold)


def correlate_by_register(
    embouchure_landmarks: dict,
    intonation_data: dict,
    register_type: str,
) -> dict:
    return _default.correlate_by_register(embouchure_landmarks, intonation_data, register_type)


def _empty_correlation() -> dict:
    return CorrelationAnalyzer._empty_correlation()
