"""
Descriptive and inferential statistics for intonation analysis.
"""

from __future__ import annotations

import numpy as np
from scipy import stats as scipy_stats


class IntonationStats:
    """Descriptive statistics and intonation tendency analysis."""

    def __init__(self, reference_freq: float = 440.0) -> None:
        self.reference_freq = reference_freq

    def summary_stats(self, values: np.ndarray) -> dict[str, float]:
        """Compute descriptive statistics for a 1-D array of measurements.

        NaN values are excluded. Returns keys: ``mean``, ``median``, ``std``,
        ``min``, ``max``, ``q25``, ``q75``, ``iqr``, ``n``.
        """
        clean = values[~np.isnan(values)]
        if clean.size == 0:
            nan = float("nan")
            return dict(mean=nan, median=nan, std=nan, min=nan, max=nan,
                        q25=nan, q75=nan, iqr=nan, n=0)

        q25, q75 = float(np.percentile(clean, 25)), float(np.percentile(clean, 75))
        return {
            "mean":   float(np.mean(clean)),
            "median": float(np.median(clean)),
            "std":    float(np.std(clean)),
            "min":    float(np.min(clean)),
            "max":    float(np.max(clean)),
            "q25":    q25,
            "q75":    q75,
            "iqr":    q75 - q25,
            "n":      int(clean.size),
        }

    def cents_deviation_stats(self, frequencies: np.ndarray) -> dict[str, float]:
        """Compute statistics on pitch deviation in cents from ``reference_freq``.

        Returns summary stats plus ``"mean_bias"`` (positive = sharp, negative = flat).
        """
        voiced = frequencies[~np.isnan(frequencies)]
        if voiced.size == 0:
            return self.summary_stats(np.array([]))

        cents = 1200.0 * np.log2(voiced / self.reference_freq)
        result = self.summary_stats(cents)
        result["mean_bias"] = result["mean"]
        return result

    def intonation_tendency(
        self,
        frequencies: np.ndarray,
        threshold_cents: float = 5.0,
    ) -> str:
        """Classify the overall intonation tendency.

        Returns one of ``"sharp"``, ``"flat"``, or ``"centred"``.
        """
        s = self.cents_deviation_stats(frequencies)
        bias = s.get("mean_bias", float("nan"))
        if np.isnan(bias):
            return "centred"
        if bias > threshold_cents:
            return "sharp"
        if bias < -threshold_cents:
            return "flat"
        return "centred"

    def compare_registers(
        self,
        register_metrics: dict[str, dict],
    ) -> dict[str, dict[str, float]]:
        """Compare stability statistics across bassoon registers.

        Args:
            register_metrics: Output of ``StabilityAnalyzer.register_analysis``.

        Returns:
            Dict keyed by register name with summary stats plus
            ``"mean_variance"`` and ``"time_fraction"``.
        """
        result: dict[str, dict[str, float]] = {}
        for reg, data in register_metrics.items():
            m    = data.get("metrics")
            frac = data.get("time_fraction", 0.0)
            if m is None:
                entry = self.summary_stats(np.array([]))
            else:
                entry = self.summary_stats(m["stability_score"])
                valid_var = m["variance"][~np.isnan(m["variance"])]
                entry["mean_variance"] = float(np.mean(valid_var)) if valid_var.size else float("nan")
            entry["time_fraction"] = float(frac)
            result[reg] = entry
        return result

    @staticmethod
    def pitch_histogram(
        frequencies: np.ndarray,
        n_bins: int = 48,
        freq_min: float = 58.27,
        freq_max: float = 698.46,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build a histogram of voiced pitch frames across the bassoon range.

        Returns ``(counts, bin_edges)`` as from ``np.histogram``.
        """
        voiced = frequencies[~np.isnan(frequencies)]
        voiced = voiced[(voiced >= freq_min) & (voiced <= freq_max)]
        return np.histogram(voiced, bins=n_bins, range=(freq_min, freq_max))


# ---------------------------------------------------------------------------
# Module-level convenience functions (preserve existing call-sites)
# ---------------------------------------------------------------------------

_default = IntonationStats()


def summary_stats(values: np.ndarray) -> dict[str, float]:
    return _default.summary_stats(values)


def cents_deviation_stats(
    frequencies: np.ndarray,
    reference_freq: float = 440.0,
) -> dict[str, float]:
    return IntonationStats(reference_freq=reference_freq).cents_deviation_stats(frequencies)


def intonation_tendency(
    frequencies: np.ndarray,
    reference_freq: float = 440.0,
    threshold_cents: float = 5.0,
) -> str:
    return IntonationStats(reference_freq=reference_freq).intonation_tendency(
        frequencies, threshold_cents=threshold_cents
    )


def compare_registers(register_metrics: dict[str, dict]) -> dict[str, dict[str, float]]:
    return _default.compare_registers(register_metrics)


def pitch_histogram(
    frequencies: np.ndarray,
    n_bins: int = 48,
    freq_min: float = 58.27,
    freq_max: float = 698.46,
) -> tuple[np.ndarray, np.ndarray]:
    return IntonationStats.pitch_histogram(frequencies, n_bins, freq_min, freq_max)
