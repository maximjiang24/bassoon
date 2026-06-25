"""
Visualization utilities for bassoon intonation analysis.
"""

from __future__ import annotations

import os

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from audio.pitch_detector import hz_to_cents
from analysis.stability import compute_stability_metrics
from utils.config import REFERENCE_FREQ, STABILITY_THRESHOLD

_OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "analysis")
)


class IntonationPlotter:
    """Generates and saves intonation and embouchure analysis plots."""

    def __init__(self, output_dir: str = _OUTPUT_DIR) -> None:
        self.output_dir = output_dir

    def plot_pitch_contour(
        self,
        times: np.ndarray,
        frequencies: np.ndarray,
        title: str = "Pitch Contour",
        save: bool = True,
    ) -> plt.Figure:
        """Plot pitch deviation in cents over time."""
        cents = np.array([hz_to_cents(f, REFERENCE_FREQ) for f in frequencies])

        fig, ax = plt.subplots(figsize=(12, 4))
        _plot_segmented_line(ax, times, cents)
        ax.axhline(0, color="gray", linewidth=0.8, linestyle="--", label="A4 reference")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Cents (relative to A4)")
        ax.set_title(title)
        ax.legend(loc="upper right", fontsize=8)
        fig.tight_layout()

        if save:
            self._save_figure(fig, "pitch_contour.png")
        return fig

    def plot_stability_heatmap(
        self,
        times: np.ndarray,
        frequencies: np.ndarray,
        window_size: float = 1.0,
        save: bool = True,
    ) -> plt.Figure:
        """Heatmap of pitch stability across time windows (green=stable, red=unstable)."""
        metrics    = compute_stability_metrics(times, frequencies, window_size)
        scores     = metrics["stability_score"]
        starts     = metrics["window_starts"]
        note_names = metrics["note_names"]

        data   = scores[np.newaxis, :]
        masked = np.ma.masked_invalid(data)

        cmap = plt.cm.RdYlGn
        cmap.set_bad(color="#3D3020")

        fig, ax = plt.subplots(figsize=(max(8, len(scores) * 0.4), 2.5))
        im = ax.imshow(
            masked,
            aspect="auto",
            cmap=cmap,
            vmin=0,
            vmax=1,
            extent=[float(starts[0]), float(starts[-1] + window_size), 0, 1],
        )

        tick_positions = starts + window_size / 2
        ax.set_xticks(tick_positions[::max(1, len(tick_positions) // 20)])
        ax.set_xticklabels(
            note_names[::max(1, len(note_names) // 20)],
            rotation=45, ha="right", fontsize=7,
        )
        ax.set_yticks([])
        ax.set_xlabel("Time (s) / Note")
        ax.set_title("Pitch Stability Heatmap  (green = stable, red = unstable)")

        cbar = fig.colorbar(im, ax=ax, orientation="vertical", fraction=0.02, pad=0.02)
        cbar.set_label("Stability score")
        fig.tight_layout()

        if save:
            self._save_figure(fig, "stability_heatmap.png")
        return fig

    def plot_register_comparison(
        self,
        register_metrics: dict[str, dict],
        save: bool = True,
    ) -> plt.Figure:
        """Bar chart comparing mean stability score across bassoon registers."""
        labels:         list[str]   = []
        mean_scores:    list[float] = []
        time_fractions: list[float] = []
        colors:         list[str]   = []

        register_colors = {"low": "#5C2E1A", "tenor": "#C8874A", "high": "#8A7A60"}

        for register in ("low", "tenor", "high"):
            entry   = register_metrics.get(register, {})
            metrics = entry.get("metrics")
            frac    = entry.get("time_fraction", 0.0)

            if metrics is None or metrics["stability_score"].size == 0:
                score = 0.0
            else:
                valid = metrics["stability_score"][~np.isnan(metrics["stability_score"])]
                score = float(np.mean(valid)) if valid.size > 0 else 0.0

            labels.append(register.capitalize())
            mean_scores.append(score)
            time_fractions.append(frac)
            colors.append(register_colors[register])

        x   = np.arange(len(labels))
        fig, ax1 = plt.subplots(figsize=(7, 4))

        bars = ax1.bar(x, mean_scores, color=colors, width=0.5, zorder=2)
        ax1.set_ylim(0, 1.05)
        ax1.set_ylabel("Mean stability score (0–1)")
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels)
        ax1.set_title("Intonation Stability by Register")
        # The dashed line at 1/e (~0.37) marks the natural knee of the exponential
        # stability formula — scores above this are considered acceptable intonation
        # for a bassoon player (variance within STABILITY_THRESHOLD cents²).
        ax1.axhline(
            np.exp(-1),
            color="red", linewidth=0.8, linestyle="--",
            label=f"Threshold knee ({np.exp(-1):.2f})",
        )
        ax1.legend(fontsize=8)
        ax1.grid(axis="y", linewidth=0.4, zorder=1)

        for bar, frac in zip(bars, time_fractions):
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.02,
                f"{frac:.0%} of time",
                ha="center", va="bottom", fontsize=8,
            )

        fig.tight_layout()
        if save:
            self._save_figure(fig, "register_comparison.png")
        return fig

    def plot_embouchure_over_time(
        self,
        embouchure_landmarks: dict,
        save: bool = True,
    ) -> plt.Figure:
        """Multi-line plot of embouchure metrics over time."""
        times = np.array(embouchure_landmarks["times"])
        mw    = np.array(embouchure_landmarks["mouth_width"],  dtype=float)
        mh    = np.array(embouchure_landmarks["mouth_height"], dtype=float)
        jaw   = np.array(embouchure_landmarks["jaw_position"], dtype=float)
        lt    = np.array(embouchure_landmarks["lip_tension"],  dtype=float)

        fig, axes = plt.subplots(4, 1, figsize=(12, 8), sharex=True)

        _plot_segmented_line(axes[0], times, mw)
        axes[0].set_ylabel("Mouth width (px)")
        axes[0].set_title("Embouchure Metrics Over Time")

        _plot_segmented_line(axes[1], times, mh)
        axes[1].set_ylabel("Mouth height (px)")

        _plot_segmented_line(axes[2], times, jaw)
        axes[2].set_ylabel("Jaw position (px)")
        axes[2].invert_yaxis()

        _plot_segmented_line(axes[3], times, lt)
        axes[3].set_ylabel("Lip tension (0–1)")
        axes[3].set_ylim(0, 1.05)
        axes[3].set_xlabel("Time (s)")

        for ax in axes:
            ax.grid(axis="y", linewidth=0.3, alpha=0.5)

        fig.tight_layout()
        if save:
            self._save_figure(fig, "embouchure_timeline.png")
        return fig

    def plot_embouchure_intonation_correlation(
        self,
        embouchure_landmarks: dict,
        audio_times: np.ndarray,
        frequencies: np.ndarray,
        save: bool = True,
    ) -> plt.Figure:
        """Dual-axis plot overlaying jaw position and pitch deviation."""
        v_times = np.array(embouchure_landmarks["times"], dtype=float)
        jaw     = np.array(embouchure_landmarks["jaw_position"], dtype=float)
        cents   = np.array([hz_to_cents(f, REFERENCE_FREQ) for f in frequencies])

        color_jaw   = "#C8874A"
        color_pitch = "#5C2E1A"

        fig, ax1 = plt.subplots(figsize=(12, 4))
        ax2 = ax1.twinx()

        _plot_segmented_line(ax1, v_times, jaw)
        ax1.set_ylabel("Jaw position (px)", color=color_jaw)
        ax1.tick_params(axis="y", labelcolor=color_jaw)
        ax1.invert_yaxis()

        _plot_segmented_line(ax2, audio_times, cents)
        ax2.set_ylabel("Pitch deviation (cents)", color=color_pitch)
        ax2.tick_params(axis="y", labelcolor=color_pitch)
        ax2.axhline(0, color="gray", linewidth=0.6, linestyle="--")

        ax1.set_xlabel("Time (s)")
        ax1.set_title("Jaw Position vs Pitch Deviation")

        legend = [
            Line2D([0], [0], color=color_jaw,   label="Jaw position"),
            Line2D([0], [0], color=color_pitch, label="Pitch (cents)"),
        ]
        ax1.legend(handles=legend, fontsize=8, loc="upper right")

        fig.tight_layout()
        if save:
            self._save_figure(fig, "embouchure_intonation_correlation.png")
        return fig

    def plot_correlation_heatmap(
        self,
        correlation_dict: dict,
        save: bool = True,
    ) -> plt.Figure:
        """Heatmap of Pearson r values between embouchure and intonation metrics."""
        pair_keys = [k for k in correlation_dict if k != "overall_correlation"]
        labels    = [k.replace("_vs_", "\nvs\n").replace("_", " ") for k in pair_keys]
        r_vals    = np.array([
            correlation_dict[k]["r"] if isinstance(correlation_dict[k], dict)
            else float("nan")
            for k in pair_keys
        ], dtype=float)

        masked = np.ma.masked_invalid(r_vals[np.newaxis, :])
        cmap   = plt.cm.RdBu_r
        cmap.set_bad(color="#3D3020")

        fig, ax = plt.subplots(figsize=(max(6, len(pair_keys) * 1.8), 2.5))
        im = ax.imshow(masked, aspect="auto", cmap=cmap, vmin=-1, vmax=1)

        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_yticks([])
        ax.set_title("Embouchure–Intonation Correlation (Pearson r)")

        for i, r in enumerate(r_vals):
            if not np.isnan(r):
                ax.text(i, 0, f"{r:+.2f}", ha="center", va="center",
                        fontsize=9, fontweight="bold",
                        color="white" if abs(r) > 0.5 else "black")

        cbar = fig.colorbar(im, ax=ax, orientation="vertical", fraction=0.02, pad=0.02)
        cbar.set_label("r")
        fig.tight_layout()

        if save:
            self._save_figure(fig, "correlation_heatmap.png")
        return fig

    def _save_figure(self, fig: plt.Figure, filename: str) -> None:
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, filename)
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#F5F0E8")
        print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _plot_segmented_line(ax: plt.Axes, times: np.ndarray, values: np.ndarray) -> None:
    """Draw a line that breaks at NaN values."""
    valid = ~np.isnan(values)
    if not np.any(valid):
        return

    segment_times: list[float] = []
    segment_vals:  list[float] = []

    for t, v, ok in zip(times, values, valid):
        if ok:
            segment_times.append(float(t))
            segment_vals.append(float(v))
        else:
            if segment_times:
                ax.plot(segment_times, segment_vals, color="#5C2E1A", linewidth=1.0)
                segment_times, segment_vals = [], []

    if segment_times:
        ax.plot(segment_times, segment_vals, color="#5C2E1A", linewidth=1.0)


# ---------------------------------------------------------------------------
# Module-level convenience functions (preserve existing call-sites)
# ---------------------------------------------------------------------------

_default = IntonationPlotter()


def plot_pitch_contour(times, frequencies, title="Pitch Contour", save=True):
    return _default.plot_pitch_contour(times, frequencies, title=title, save=save)


def plot_stability_heatmap(times, frequencies, window_size=1.0, save=True):
    return _default.plot_stability_heatmap(times, frequencies, window_size=window_size, save=save)


def plot_register_comparison(register_metrics, save=True):
    return _default.plot_register_comparison(register_metrics, save=save)


def plot_embouchure_over_time(embouchure_landmarks, save=True):
    return _default.plot_embouchure_over_time(embouchure_landmarks, save=save)


def plot_embouchure_intonation_correlation(embouchure_landmarks, audio_times, frequencies, save=True):
    return _default.plot_embouchure_intonation_correlation(
        embouchure_landmarks, audio_times, frequencies, save=save
    )


def plot_correlation_heatmap(correlation_dict, save=True):
    return _default.plot_correlation_heatmap(correlation_dict, save=save)


def _save_figure(fig, filename):
    _default._save_figure(fig, filename)
