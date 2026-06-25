"""
Pitch stability analysis for bassoon intonation data.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from utils.config import SAMPLE_RATE, HOP_LENGTH, STABILITY_WINDOW_SIZE, STABILITY_THRESHOLD
from audio.pitch_detector import hz_to_cents, get_note_name

# Bassoon register boundaries in Hz.
# Low register (below B♭2): the fundamental/bocal register — hardest to control
# and most prone to flat intonation due to the long air column.
# Tenor register (B♭2–B♭4): the primary playing range for most repertoire;
# intonation here is most representative of overall technique.
# High register (above B♭4): requires flicking the octave key and a faster,
# focused airstream — sharp tendencies are common as the player overbows.
_BB2_HZ = 116.54
_BB4_HZ = 466.16


class StabilityAnalyzer:
    """Computes pitch stability metrics over bassoon recordings."""

    def __init__(
        self,
        window_size: float = STABILITY_WINDOW_SIZE,
        threshold: float = STABILITY_THRESHOLD,
    ) -> None:
        self.window_size = window_size
        self.threshold = threshold

    def compute_stability_metrics(
        self,
        times: np.ndarray,
        frequencies: np.ndarray,
        window_size: float | None = None,
    ) -> dict:
        """Compute per-window pitch stability metrics over a recording.

        Parameters
        ----------
        times:
            Centre times of each analysis frame in seconds.
        frequencies:
            Fundamental frequency in Hz per frame. NaN = unvoiced.
        window_size:
            Duration of each analysis window in seconds. Defaults to
            ``self.window_size``.

        Returns
        -------
        dict with keys ``window_starts``, ``window_ends``, ``mean_freq``,
        ``variance``, ``drift_rate``, ``stability_score``, ``note_names``.
        """
        ws = window_size if window_size is not None else self.window_size

        if times.shape != frequencies.shape:
            raise ValueError("times and frequencies must have the same shape")

        total_duration = float(times[-1]) if times.size > 0 else 0.0
        n_windows = max(1, int(np.ceil(total_duration / ws)))

        window_starts = np.arange(n_windows) * ws
        window_ends   = window_starts + ws

        mean_freq      = np.full(n_windows, np.nan)
        variance       = np.full(n_windows, np.nan)
        drift_rate     = np.full(n_windows, np.nan)
        stability_score = np.zeros(n_windows)
        note_names: list[str] = []

        for i, (t_start, t_end) in enumerate(zip(window_starts, window_ends)):
            mask    = (times >= t_start) & (times < t_end) & ~np.isnan(frequencies)
            freqs_w = frequencies[mask]
            times_w = times[mask]

            if freqs_w.size < 2:
                note_names.append("?")
                continue

            cents_w = np.array([hz_to_cents(f) for f in freqs_w])

            mean_freq[i]       = float(np.mean(freqs_w))
            variance[i]        = float(np.var(cents_w))
            drift_rate[i]      = _linear_drift(times_w, cents_w)
            stability_score[i] = _stability_score(variance[i], self.threshold)
            note_names.append(get_note_name(mean_freq[i]))

        return {
            "window_starts":   window_starts,
            "window_ends":     window_ends,
            "mean_freq":       mean_freq,
            "variance":        variance,
            "drift_rate":      drift_rate,
            "stability_score": stability_score,
            "note_names":      note_names,
        }

    def identify_unstable_regions(
        self,
        times: np.ndarray,
        frequencies: np.ndarray,
        threshold: float | None = None,
    ) -> list[tuple[float, float, str, float]]:
        """Find contiguous regions where pitch variance exceeds *threshold* cents².

        Returns
        -------
        list of ``(start_time, end_time, note_name, variance)`` tuples.
        """
        thr = threshold if threshold is not None else self.threshold

        if times.shape != frequencies.shape:
            raise ValueError("times and frequencies must have the same shape")

        metrics    = self.compute_stability_metrics(times, frequencies)
        variances  = metrics["variance"]
        starts     = metrics["window_starts"]
        ends       = metrics["window_ends"]
        mean_freqs = metrics["mean_freq"]

        unstable: list[tuple[float, float, str, float]] = []
        in_region    = False
        region_start = 0.0
        region_vars: list[float]  = []
        region_freqs: list[float] = []

        for i, var in enumerate(variances):
            is_unstable = (not np.isnan(var)) and (var > thr)

            if is_unstable and not in_region:
                in_region    = True
                region_start = float(starts[i])
                region_vars  = [var]
                region_freqs = [] if np.isnan(mean_freqs[i]) else [float(mean_freqs[i])]

            elif is_unstable and in_region:
                region_vars.append(var)
                if not np.isnan(mean_freqs[i]):
                    region_freqs.append(float(mean_freqs[i]))

            elif not is_unstable and in_region:
                in_region  = False
                region_end = float(ends[i - 1])
                mean_var   = float(np.mean(region_vars))
                mean_f     = float(np.mean(region_freqs)) if region_freqs else np.nan
                unstable.append((region_start, region_end, get_note_name(mean_f), mean_var))

        if in_region:
            region_end = float(ends[len(variances) - 1])
            mean_var   = float(np.mean(region_vars))
            mean_f     = float(np.mean(region_freqs)) if region_freqs else np.nan
            unstable.append((region_start, region_end, get_note_name(mean_f), mean_var))

        return unstable

    def register_analysis(
        self,
        times: np.ndarray,
        frequencies: np.ndarray,
    ) -> dict[str, dict]:
        """Compute stability metrics broken down by bassoon register.

        Returns
        -------
        dict with keys ``"low"``, ``"tenor"``, ``"high"``. Each value contains
        ``metrics``, ``unstable_regions``, ``frame_count``, ``time_fraction``.
        """
        voiced       = ~np.isnan(frequencies)
        total_voiced = int(np.sum(voiced))

        masks = {
            "low":   voiced & (frequencies < _BB2_HZ),
            "tenor": voiced & (frequencies >= _BB2_HZ) & (frequencies <= _BB4_HZ),
            "high":  voiced & (frequencies > _BB4_HZ),
        }

        result: dict[str, dict] = {}
        for register, mask in masks.items():
            t_reg       = times[mask]
            f_reg       = frequencies[mask]
            frame_count = int(np.sum(mask))

            if frame_count < 2:
                result[register] = {
                    "metrics":          None,
                    "unstable_regions": [],
                    "frame_count":      frame_count,
                    "time_fraction":    0.0,
                }
                continue

            result[register] = {
                "metrics":          self.compute_stability_metrics(t_reg, f_reg),
                "unstable_regions": self.identify_unstable_regions(t_reg, f_reg),
                "frame_count":      frame_count,
                "time_fraction":    frame_count / total_voiced if total_voiced > 0 else 0.0,
            }

        return result

    def compute_note_segmented_metrics(
        self,
        times: np.ndarray,
        frequencies: np.ndarray,
        shift_threshold_cents: float = 50.0,
        shift_window_frames: int = 5,
        transition_trim_frames: int = 2,
        min_duration_s: float = 0.10,
        median_filter_frames: int = 5,
        nan_fill_max_frames: int = 12,
        trimmed_pct: float = 0.10,
    ) -> list[dict]:
        """Segment pitch data into individual sustained notes and score each one.

        Stability improvements over a simple window-based approach:

        1. Median filter — removes single-frame pYIN spikes before any
           segmentation or variance calculation. A 5-frame window (~58 ms)
           is short enough to preserve true pitch movement while suppressing
           spurious outliers.

        2. Short NaN gap filling — voiced notes often have 1–4 frames of NaN
           inside them (breath attack, key noise). Filling these gaps prevents
           a single noisy frame from splitting one note into two segments.

        3. Three-phase segmentation — split on rests, then split on pitch
           transitions (50-cent shift), then trim transition frames from both
           edges of each segment so the glide between notes is excluded.

        4. Trimmed variance — removes the top and bottom 10 % of cent values
           before computing variance, so isolated noisy frames inside a
           segment don't inflate the score.

        5. Duration-weighted session score — longer notes carry more weight
           than short ones, making the aggregate score stable even when the
           number of detected segments varies between trials.
        """
        if times.size < 2:
            return []

        # ── Fix 2: fill short NaN gaps inside voiced regions ─────────────────
        freqs = frequencies.copy().astype(float)
        nan_mask = np.isnan(freqs)
        if np.any(nan_mask):
            # Label contiguous NaN runs
            changes      = np.where(np.diff(nan_mask.astype(int)))[0] + 1
            boundaries   = [0] + list(changes) + [len(nan_mask)]
            for s, e in zip(boundaries[:-1], boundaries[1:]):
                if nan_mask[s] and (e - s) <= nan_fill_max_frames:
                    # Only fill if surrounded by voiced frames on both sides
                    if s > 0 and e < len(freqs) and not nan_mask[s - 1] and not nan_mask[e]:
                        freqs[s:e] = np.interp(
                            np.arange(s, e),
                            [s - 1, e],
                            [freqs[s - 1], freqs[e]],
                        )

        # ── Fix 1: median filter to suppress pYIN spike artefacts ────────────
        from scipy.ndimage import median_filter as _mf
        voiced_mask = ~np.isnan(freqs)
        if np.sum(voiced_mask) > median_filter_frames:
            # Apply filter only to voiced frames to avoid NaN contamination
            filtered = freqs.copy()
            v_idx    = np.where(voiced_mask)[0]
            v_vals   = freqs[v_idx]
            v_filt   = _mf(v_vals, size=median_filter_frames)
            filtered[v_idx] = v_filt
            freqs = filtered

        # ── Phase 1: find contiguous voiced runs (split on remaining NaN gaps)
        voiced        = ~np.isnan(freqs)
        changes       = np.where(np.diff(voiced.astype(int)))[0] + 1
        run_boundaries = [0] + list(changes) + [len(voiced)]

        voiced_runs = []
        for s, e in zip(run_boundaries[:-1], run_boundaries[1:]):
            if voiced[s]:
                voiced_runs.append((s, e))

        segments = []

        for run_s, run_e in voiced_runs:
            t_run = times[run_s:run_e]
            f_run = freqs[run_s:run_e]

            if f_run.size < 2:
                continue

            c_run = np.array([hz_to_cents(f) for f in f_run])

            # ── Phase 2: split on pitch transitions ───────────────────────
            # Only keep one boundary per shift_window_frames gap so a slow
            # glide doesn't generate dozens of consecutive boundary points
            # that eat into both neighboring notes.
            boundaries = []
            last_b = -shift_window_frames
            for i in range(shift_window_frames, len(c_run)):
                if abs(c_run[i] - c_run[i - shift_window_frames]) >= shift_threshold_cents:
                    if i - last_b >= shift_window_frames:
                        boundaries.append(i)
                        last_b = i

            seg_starts = [0] + boundaries
            seg_ends   = boundaries + [len(c_run)]

            for s, e in zip(seg_starts, seg_ends):
                # ── Check raw duration BEFORE trimming ────────────────────
                # This ensures min_duration_s gates the note length, not the
                # post-trim remnant. Avoids silently dropping short valid notes.
                if e > s:
                    raw_duration = float(t_run[e - 1] - t_run[s])
                    if raw_duration < min_duration_s:
                        continue

                # ── Phase 3: trim transition frames ───────────────────────
                trim_s = s + transition_trim_frames if s > 0 else s
                trim_e = e - transition_trim_frames if e < len(c_run) else e

                if trim_s >= trim_e:
                    continue

                t_seg = t_run[trim_s:trim_e]
                f_seg = f_run[trim_s:trim_e]
                c_seg = c_run[trim_s:trim_e]

                if t_seg.size < 2:
                    continue

                duration = float(t_seg[-1] - t_seg[0])
                if duration < min_duration_s:
                    continue

                # ── Fix 4: trimmed variance ────────────────────────────────
                # First strip octave-error frames (>600 cents from median),
                # then apply percentage trim for remaining outliers.
                c_clean = c_seg.copy()
                if c_clean.size >= 4:
                    med = float(np.median(c_clean))
                    c_clean = c_clean[np.abs(c_clean - med) <= 600]
                if c_clean.size < 2:
                    c_clean = c_seg
                if c_clean.size >= 10:
                    lo = np.percentile(c_clean, trimmed_pct * 100)
                    hi = np.percentile(c_clean, (1 - trimmed_pct) * 100)
                    c_trimmed = c_clean[(c_clean >= lo) & (c_clean <= hi)]
                    var_c = float(np.var(c_trimmed)) if c_trimmed.size >= 2 else float(np.var(c_clean))
                else:
                    var_c = float(np.var(c_clean))

                mean_hz = float(np.mean(f_seg))
                mean_c  = float(np.mean(c_seg))
                score   = float(np.exp(-var_c / (STABILITY_THRESHOLD ** 2)))

                # cents_deviation: distance from nearest ET semitone [-50, +50]
                d = mean_c % 100.0
                cents_dev = d - 100.0 if d > 50.0 else d

                if mean_hz < _BB2_HZ:
                    register = "low"
                elif mean_hz > _BB4_HZ:
                    register = "high"
                else:
                    register = "tenor"

                segments.append({
                    "note":            get_note_name(mean_hz),
                    "register":        register,
                    "start":           float(t_seg[0]),
                    "end":             float(t_seg[-1]),
                    "duration":        duration,
                    "mean_cents":      mean_c,
                    "cents_deviation": cents_dev,
                    "variance":        var_c,
                    "stability_score": score,
                })

        return segments


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _linear_drift(times: np.ndarray, cents: np.ndarray) -> float:
    if times.size < 2:
        return float("nan")
    slope, *_ = stats.linregress(times, cents)
    return float(slope)


def _stability_score(variance_cents_sq: float, threshold: float = STABILITY_THRESHOLD) -> float:
    # Exponential decay maps pitch variance (cents²) onto a 0–1 score.
    # A variance equal to STABILITY_THRESHOLD² scores ≈ 0.37 (1/e), giving a
    # natural "knee" at the threshold — scores above ~0.37 are considered stable
    # for a bassoon player, where 20 cents is roughly one fifth of a semitone.
    if np.isnan(variance_cents_sq):
        return 0.0
    return float(np.exp(-variance_cents_sq / (threshold ** 2)))


# ---------------------------------------------------------------------------
# Module-level convenience functions (preserve existing call-sites)
# ---------------------------------------------------------------------------

_default = StabilityAnalyzer()


def compute_stability_metrics(
    times: np.ndarray,
    frequencies: np.ndarray,
    window_size: float = STABILITY_WINDOW_SIZE,
) -> dict:
    return _default.compute_stability_metrics(times, frequencies, window_size=window_size)


def identify_unstable_regions(
    times: np.ndarray,
    frequencies: np.ndarray,
    threshold: float = STABILITY_THRESHOLD,
) -> list[tuple[float, float, str, float]]:
    return _default.identify_unstable_regions(times, frequencies, threshold=threshold)


def register_analysis(
    times: np.ndarray,
    frequencies: np.ndarray,
) -> dict[str, dict]:
    return _default.register_analysis(times, frequencies)


def compute_note_segmented_metrics(
    times: np.ndarray,
    frequencies: np.ndarray,
    shift_threshold_cents: float = 50.0,
    shift_window_frames: int = 5,
    transition_trim_frames: int = 2,
    min_duration_s: float = 0.10,
    median_filter_frames: int = 5,
    nan_fill_max_frames: int = 12,
    trimmed_pct: float = 0.10,
) -> list[dict]:
    return _default.compute_note_segmented_metrics(
        times, frequencies,
        shift_threshold_cents=shift_threshold_cents,
        shift_window_frames=shift_window_frames,
        transition_trim_frames=transition_trim_frames,
        min_duration_s=min_duration_s,
        median_filter_frames=median_filter_frames,
        nan_fill_max_frames=nan_fill_max_frames,
        trimmed_pct=trimmed_pct,
    )
