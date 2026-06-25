"""
Full bassoon intonation + embouchure correlation workflow.

Usage:
    python examples/sample_analysis.py [--duration 10] [--save my_note]
                                        [--no-video] [--no-plots]
"""

import argparse
import sys
import os
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np

from audio.recorder import record_audio
from audio.pitch_detector import detect_pitch, get_note_name, hz_to_cents
from analysis.stability import (
    compute_stability_metrics,
    identify_unstable_regions,
    register_analysis,
)
from analysis.correlation import (  # noqa: E402
    correlate_embouchure_intonation,
    correlate_by_register,
)
from visualization.plotter import (
    plot_pitch_contour,
    plot_stability_heatmap,
    plot_register_comparison,
    plot_embouchure_over_time,
    plot_embouchure_intonation_correlation,
    plot_correlation_heatmap,
)
from utils.config import SAMPLE_RATE, STABILITY_THRESHOLD


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Bassoon intonation + embouchure analysis')
    p.add_argument('--duration', type=float, default=10.0,
                   help='Recording duration in seconds (default: 10)')
    p.add_argument('--save', metavar='FILENAME', default=None,
                   help='Base name for saved audio/video files')
    p.add_argument('--no-video', action='store_true',
                   help='Skip webcam recording and embouchure analysis')
    p.add_argument('--no-plots', action='store_true',
                   help='Skip saving plot images')
    return p.parse_args()


def print_section(title: str) -> None:
    print(f'\n{"─" * 60}')
    print(f'  {title}')
    print('─' * 60)


def run(
    duration: float,
    save_as: str | None,
    use_video: bool,
    save_plots: bool,
) -> None:
    # ------------------------------------------------------------------ #
    # 1. Record audio (+ video in parallel if enabled)
    # ------------------------------------------------------------------ #
    print_section('1 / 5  Recording')

    video_path: str | None = None

    if use_video:
        try:
            from video.embouchure_tracker import record_video  # type: ignore[import]
        except ImportError as e:
            print(f'  WARNING: Cannot import video module ({e}). Skipping video.')
            use_video = False

    if use_video:
        video_result: list = []
        video_error: list = []

        def _record_video() -> None:
            try:
                vname = (save_as + "_video") if save_as else None
                video_result.append(record_video(duration=duration, filename=vname))
            except Exception as exc:
                video_error.append(exc)

        video_thread = threading.Thread(target=_record_video, daemon=True)
        video_thread.start()

    audio = record_audio(duration=duration, sample_rate=SAMPLE_RATE, filename=save_as)

    if use_video:
        video_thread.join()
        if video_error:
            print(f'  WARNING: Video recording failed: {video_error[0]}')
            use_video = False
        elif video_result:
            video_path = video_result[0]

    # ------------------------------------------------------------------ #
    # 2. Pitch detection
    # ------------------------------------------------------------------ #
    print_section('2 / 5  Pitch Detection')
    times, frequencies, _ = detect_pitch(audio, sr=SAMPLE_RATE)

    voiced_mask = ~np.isnan(frequencies)
    voiced_pct  = voiced_mask.mean() * 100
    print(f'  Frames analysed : {len(times)}')
    print(f'  Voiced frames   : {voiced_mask.sum()}  ({voiced_pct:.1f}%)')

    if not voiced_mask.any():
        print('\n  No pitched content detected. Check microphone and try again.')
        return

    mean_hz    = float(np.nanmean(frequencies))
    mean_note  = get_note_name(mean_hz)
    mean_cents = hz_to_cents(mean_hz)
    print(f'  Mean pitch      : {mean_hz:.2f} Hz  →  {mean_note}  '
          f'({mean_cents:+.1f} cents from A4)')

    # ------------------------------------------------------------------ #
    # 3. Stability analysis
    # ------------------------------------------------------------------ #
    print_section('3 / 5  Stability Analysis')

    metrics  = compute_stability_metrics(times, frequencies, window_size=1.0)
    regions  = identify_unstable_regions(times, frequencies, threshold=STABILITY_THRESHOLD)
    reg_data = register_analysis(times, frequencies)

    valid_scores  = metrics['stability_score'][~np.isnan(metrics['stability_score'])]
    overall_score = float(np.mean(valid_scores)) if valid_scores.size else 0.0
    print(f'  Overall stability : {overall_score:.3f}  |  Unstable regions: {len(regions)}')

    # ------------------------------------------------------------------ #
    # 4. Embouchure analysis (if video available)
    # ------------------------------------------------------------------ #
    landmarks: dict | None = None
    emb_metrics: dict | None = None
    corr: dict | None = None

    if use_video and video_path:
        print_section('4 / 5  Embouchure Analysis')
        from video.embouchure_tracker import (  # type: ignore[import]
            extract_facial_landmarks,
            compute_embouchure_metrics,
        )

        landmarks   = extract_facial_landmarks(video_path)
        emb_metrics = compute_embouchure_metrics(landmarks)

        print(f'  Face detected    : {emb_metrics["face_detected_pct"]:.1f}% of frames')
        print(f'  Consistency score: {emb_metrics["embouchure_consistency"]:.3f}')
        print(f'  Mean mouth width : {emb_metrics["mean_mouth_width"]:.1f} px  '
              f'(var {emb_metrics["mouth_width_variance"]:.2f})')
        print(f'  Jaw stability    : {emb_metrics["jaw_stability"]:.3f}')
        print(f'  Mean lip tension : {emb_metrics["mean_lip_tension"]:.3f}')

        try:
            corr = correlate_embouchure_intonation(
                landmarks, metrics, times, landmarks["times"]
            )
            _print_correlation_report(corr, emb_metrics, reg_data, landmarks)
        except ValueError as e:
            print(f'  WARNING: Could not compute correlation ({e})')
    else:
        print_section('4 / 5  Embouchure Analysis')
        print('  Skipped (use --no-video to suppress this message, '
              'or remove it to enable webcam recording).')

    # ------------------------------------------------------------------ #
    # 5. Visualizations
    # ------------------------------------------------------------------ #
    print_section('5 / 5  Visualizations')

    if save_plots:
        plot_pitch_contour(times, frequencies, save=True)
        plot_stability_heatmap(times, frequencies, save=True)
        plot_register_comparison(reg_data, save=True)

        if landmarks and corr:
            plot_embouchure_over_time(landmarks, save=True)
            plot_embouchure_intonation_correlation(
                landmarks, times, frequencies, save=True
            )
            plot_correlation_heatmap(corr, save=True)
            print('  All 6 plots saved to data/analysis/')
        else:
            print('  3 intonation plots saved to data/analysis/')
    else:
        print('  Plots skipped (--no-plots).')

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    print_section('Summary')
    rating = (
        'Excellent'  if overall_score >= 0.85 else
        'Good'       if overall_score >= 0.65 else
        'Fair'       if overall_score >= 0.40 else
        'Needs work'
    )
    print(f'  Intonation rating : {rating}  ({overall_score:.3f})')
    print(f'  Dominant pitch    : {mean_note}  ({mean_hz:.2f} Hz,  {mean_cents:+.1f} ¢)')
    if regions:
        worst = max(regions, key=lambda r: r[3])
        print(f'  Most unstable at  : {worst[0]:.1f}s–{worst[1]:.1f}s  '
              f'({worst[2]},  {worst[3]:.0f} cents²)')
    if emb_metrics:
        print(f'  Embouchure score  : {emb_metrics["embouchure_consistency"]:.3f}')
    if corr:
        overall_r = corr.get("overall_correlation", float("nan"))
        print(f'  Overall correlation (|r|): {overall_r:.3f}')
    print()


def _print_correlation_report(
    corr: dict,
    emb_metrics: dict,
    reg_data: dict,
    landmarks: dict,
) -> None:
    print('\n  ═══ EMBOUCHURE-INTONATION CORRELATION REPORT ═══')

    consistency = emb_metrics['embouchure_consistency']
    grade = 'Excellent' if consistency >= 0.85 else 'Good' if consistency >= 0.65 else 'Fair'
    print(f'\n  Embouchure Consistency: {consistency:.2f}/1.0  ({grade})')
    print(f'    Mouth width variance : {emb_metrics["mouth_width_variance"]:.2f} px²')
    print(f'    Jaw position variance: {emb_metrics["jaw_position_variance"]:.2f} px²')
    print(f'    Lip tension variance : {emb_metrics["lip_tension_variance"]:.4f}')

    print('\n  Correlation Analysis:')
    labels = {
        'mouth_width_vs_stability':    'Mouth width    vs Intonation Stability',
        'mouth_height_vs_stability':   'Mouth height   vs Intonation Stability',
        'jaw_stability_vs_intonation': 'Jaw position   vs Intonation Stability',
        'lip_tension_vs_stability':    'Lip tension    vs Intonation Stability',
    }
    for key, label in labels.items():
        entry = corr.get(key, {})
        r = entry.get('r', float('nan'))
        p = entry.get('p', float('nan'))
        if not (r != r):  # not NaN
            strength = _r_label(r)
            sig = '  *' if p < 0.05 else ''
            print(f'    {label}: r = {r:+.3f}  ({strength}){sig}')

    print('\n  Per-Register Correlations:')
    for reg in ('low', 'tenor', 'high'):
        rc = correlate_by_register(landmarks, reg_data, reg)
        ov = rc.get('overall_correlation', float('nan'))
        if ov == ov:
            print(f'    {reg.capitalize():6} register: |r| = {ov:.3f}')

    print('\n  Interpretation:')
    jaw_r = corr.get('jaw_stability_vs_intonation', {}).get('r', float('nan'))
    lt_r  = corr.get('lip_tension_vs_stability', {}).get('r', float('nan'))
    if jaw_r == jaw_r and abs(jaw_r) > 0.4:
        direction = 'stable' if jaw_r > 0 else 'unstable'
        print(f'    Jaw position correlates with intonation (r={jaw_r:+.2f}): '
              f'higher jaw position → {direction} intonation.')
    if lt_r == lt_r and abs(lt_r) > 0.4:
        direction = 'better' if lt_r > 0 else 'worse'
        print(f'    Lip tension correlates with stability (r={lt_r:+.2f}): '
              f'higher tension → {direction} stability.')


def _r_label(r: float) -> str:
    a = abs(r)
    if a >= 0.7:
        return 'strong'
    if a >= 0.4:
        return 'moderate'
    return 'weak'


if __name__ == '__main__':
    args = parse_args()
    run(
        duration  = args.duration,
        save_as   = args.save,
        use_video = not args.no_video,
        save_plots = not args.no_plots,
    )
