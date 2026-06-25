"""
Flask web interface for the Bassoon Intonation Stability Analyzer.

Run with:
    python app.py

Then open http://localhost:5000 in your browser.
"""

import sys
import os
import io
import base64
import threading
import math
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from flask import Flask, render_template, jsonify, request
import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be set before importing pyplot
import matplotlib.pyplot as plt

from audio.pitch_detector import detect_pitch, get_note_name, hz_to_cents
from analysis.stability import (
    compute_stability_metrics,
    identify_unstable_regions,
    register_analysis,
    compute_note_segmented_metrics,
)
from analysis.stats import cents_deviation_stats, intonation_tendency, compare_registers
from analysis.correlation import correlate_embouchure_intonation, correlate_by_register
from visualization.plotter import (
    plot_pitch_contour,
    plot_stability_heatmap,
    plot_register_comparison,
    plot_embouchure_over_time,
    plot_embouchure_intonation_correlation,
    plot_correlation_heatmap,
)
from utils.config import SAMPLE_RATE, STABILITY_THRESHOLD

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "100")) * 1024 * 1024


@app.after_request
def add_cors_headers(response):
    origin = os.environ.get("CORS_ORIGIN", "*")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

def _clean(obj):
    """Recursively replace NaN/Inf with None so jsonify never sees them."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    try:
        import numpy as np
        if isinstance(obj, np.floating):
            v = float(obj)
            return None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(obj, np.integer):
            return int(obj)
    except ImportError:
        pass
    return obj

_state: dict = {}
_recording_lock = threading.Lock()


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


@app.route("/")
def home():
    return render_template("home.html")

@app.route("/analyzer")
def index():
    return render_template("index.html")

@app.route("/practice")
def practice():
    return render_template("practice.html")

@app.route("/reeds")
def reeds():
    return render_template("reeds.html")

@app.route("/progress")
def progress():
    return render_template("progress.html")


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok"})


@app.route("/api/record", methods=["POST"])
def api_record():
    """Hosted deployments cannot record from a user's microphone server-side."""
    return jsonify({
        "error": (
            "Server-side microphone recording is unavailable on hosted Render. "
            "Record audio in the browser and upload it to /api/analyze_file."
        )
    }), 501


@app.route("/api/analyze_file", methods=["POST"])
def api_analyze_file():
    """Analyze an uploaded WAV file, optionally paired with a video file."""
    import soundfile as sf

    if "file" not in request.files:
        return jsonify({"error": "No audio file uploaded."}), 400

    wav_file = request.files["file"]
    buf = io.BytesIO(wav_file.read())
    try:
        audio, sr = sf.read(buf, dtype="float32")
    except Exception as exc:
        return jsonify({"error": f"Could not read audio file: {exc}"}), 400

    if audio.ndim > 1:
        audio = audio[:, 0]

    video_path = None
    video_warning = None
    if "video" in request.files and request.files["video"].filename:
        try:
            video_file = request.files["video"]
            suffix = os.path.splitext(video_file.filename)[1] or ".mp4"
            tmp = tempfile.NamedTemporaryFile(prefix="upload_", suffix=suffix, delete=False)
            video_path = tmp.name
            tmp.close()
            video_file.save(video_path)
        except Exception as exc:
            video_warning = f"Could not save video: {exc}"

    try:
        result = _run_analysis(audio, sr=int(sr), video_path=video_path)
        if video_warning:
            result["summary"]["video_warning"] = video_warning
        _state.clear()
        _state.update(result)
        return jsonify(_clean({"status": "ok", "summary": result["summary"]}))
    finally:
        if video_path:
            try:
                os.unlink(video_path)
            except OSError:
                pass


@app.route("/api/plots")
def api_plots():
    """Return the analysis plots as base64 PNG strings."""
    if not _state:
        return jsonify({"error": "No analysis results yet. Record or upload a file first."}), 404

    times = _state["times"]
    frequencies = _state["frequencies"]
    reg_metrics = _state["register_metrics"]
    landmarks = _state.get("landmarks")
    correlation = _state.get("correlation")

    plots = {
        "pitch_contour":      _fig_to_b64(plot_pitch_contour(times, frequencies, save=False)),
        "stability_heatmap":  _fig_to_b64(plot_stability_heatmap(times, frequencies, save=False)),
        "register_comparison": _fig_to_b64(plot_register_comparison(reg_metrics, save=False)),
    }

    if landmarks is not None:
        plots["embouchure_timeline"] = _fig_to_b64(
            plot_embouchure_over_time(landmarks, save=False)
        )
        plots["embouchure_intonation"] = _fig_to_b64(
            plot_embouchure_intonation_correlation(landmarks, times, frequencies, save=False)
        )
        if correlation is not None:
            plots["correlation_heatmap"] = _fig_to_b64(
                plot_correlation_heatmap(correlation, save=False)
            )

    return jsonify(_clean(plots))


@app.route("/api/results")
def api_results():
    """Return full numeric results as JSON."""
    if not _state:
        return jsonify({"error": "No results available."}), 404
    return jsonify(_clean({
        "summary":                  _state["summary"],
        "unstable_regions":         _state["unstable_regions"],
        "register_stats":           _state["register_stats"],
        "register_unstable_counts": _state["register_unstable_counts"],
        "embouchure":               _state.get("embouchure_summary"),
        "correlation":              _state.get("correlation_summary"),
        "register_correlation":     _state.get("register_correlation"),
        "interpretation":           _state.get("interpretation", []),
        "note_breakdown":           _state.get("note_breakdown", []),
    }))


@app.route("/api/status")
def api_status():
    recording = not _recording_lock.acquire(blocking=False)
    if not recording:
        _recording_lock.release()

    video_available = True
    try:
        import video.embouchure_tracker  # noqa: F401
    except ImportError:
        video_available = False

    return jsonify({
        "recording":       recording,
        "has_results":     bool(_state),
        "video_available": video_available,
    })


def _run_analysis(audio: np.ndarray, sr: int = SAMPLE_RATE, video_path: str | None = None) -> dict:
    times, frequencies, _ = detect_pitch(audio, sr=sr)

    voiced_mask = ~np.isnan(frequencies)
    voiced_pct  = float(voiced_mask.mean() * 100)
    mean_hz     = float(np.nanmean(frequencies)) if voiced_mask.any() else float("nan")

    metrics      = compute_stability_metrics(times, frequencies)
    regions      = identify_unstable_regions(times, frequencies, threshold=STABILITY_THRESHOLD)
    reg_metrics  = register_analysis(times, frequencies)
    dev_stats    = cents_deviation_stats(frequencies)
    tendency     = intonation_tendency(frequencies)
    reg_stats    = compare_registers(reg_metrics)

    # Note-segmented scoring — scores only sustained notes, ignores transitions
    note_segments = compute_note_segmented_metrics(times, frequencies)
    if note_segments:
        # Fix 5: duration-weighted mean so longer notes count more than short ones,
        # making the aggregate stable even when segment count varies between trials.
        durations = np.array([seg["duration"] for seg in note_segments])
        scores    = np.array([seg["stability_score"] for seg in note_segments])
        overall   = float(np.average(scores, weights=durations))
    else:
        valid_scores = metrics["stability_score"][~np.isnan(metrics["stability_score"])]
        overall      = float(np.mean(valid_scores)) if valid_scores.size else 0.0
    rating = (
        "Excellent"  if overall >= 0.85 else
        "Good"       if overall >= 0.65 else
        "Fair"       if overall >= 0.40 else
        "Needs work"
    )

    summary = {
        "duration_s":       float(times[-1]) if times.size else 0.0,
        "voiced_pct":       round(voiced_pct, 1),
        "mean_hz":          round(mean_hz, 2)     if not np.isnan(mean_hz) else None,
        "mean_note":        get_note_name(mean_hz) if not np.isnan(mean_hz) else "—",
        "mean_cents":       round(hz_to_cents(mean_hz), 1) if not np.isnan(mean_hz) else None,
        "tendency":         tendency,
        "overall_score":    round(overall, 3),
        "rating":           rating,
        "unstable_count":   len(regions),
        "mean_bias_cents":  round(dev_stats.get("mean_bias", 0.0), 1),
        "has_video":        False,
    }

    serialised_regions = [
        {"start": round(s, 2), "end": round(e, 2), "note": n, "variance": round(v, 1)}
        for s, e, n, v in regions
    ]

    serialised_reg = {}
    for reg, st in reg_stats.items():
        serialised_reg[reg] = {k: (round(v, 3) if isinstance(v, float) and not np.isnan(v) else None)
                               for k, v in st.items()}

    register_unstable_counts = {
        reg: len(data["unstable_regions"])
        for reg, data in reg_metrics.items()
    }

    result = {
        "times":                    times,
        "frequencies":              frequencies,
        "register_metrics":         reg_metrics,
        "summary":                  summary,
        "unstable_regions":         serialised_regions,
        "register_stats":           serialised_reg,
        "register_unstable_counts": register_unstable_counts,
        "note_breakdown":           [
            {
                "note":            seg["note"],
                "register":        seg["register"],
                "start":           round(seg["start"], 2),
                "end":             round(seg["end"], 2),
                "duration":        round(seg["duration"], 2),
                "mean_cents":      round(seg["mean_cents"], 1),
                "cents_deviation": round(seg["cents_deviation"], 1),
                "variance":        round(seg["variance"], 1),
                "stability_score": round(seg["stability_score"], 3),
            }
            for seg in note_segments
        ],
    }

    if video_path:
        try:
            from video.embouchure_tracker import (  # type: ignore[import]
                extract_facial_landmarks,
                compute_embouchure_metrics,
            )
            landmarks = extract_facial_landmarks(video_path)
            emb = compute_embouchure_metrics(landmarks)
            corr = correlate_embouchure_intonation(landmarks, metrics, times, landmarks["times"])
            reg_corr = {
                r: correlate_by_register(landmarks, reg_metrics, r)
                for r in ("low", "tenor", "high")
            }
            result["landmarks"] = landmarks
            result["correlation"] = corr
            result["embouchure_summary"] = _serialise_embouchure(emb)
            result["correlation_summary"] = _serialise_correlation(corr)
            result["register_correlation"] = {
                r: rc.get("overall_correlation") for r, rc in reg_corr.items()
            }
            result["interpretation"] = _interpret(emb, corr)
            summary["has_video"] = True
            summary["embouchure_score"] = round(emb["embouchure_consistency"], 3)
            summary["face_detected_pct"] = round(emb["face_detected_pct"], 1)
            overall_r = corr.get("overall_correlation")
            if overall_r is not None and not (overall_r != overall_r):
                summary["overall_correlation"] = round(float(overall_r), 3)
        except Exception as exc:
            summary["video_warning"] = f"Video analysis failed: {exc}"

    return result


def _serialise_embouchure(emb: dict) -> dict:
    out = {}
    for k, v in emb.items():
        if isinstance(v, float):
            out[k] = None if np.isnan(v) else round(v, 4)
        else:
            out[k] = v
    return out


def _serialise_correlation(corr: dict) -> dict:
    out = {}
    for k, v in corr.items():
        if isinstance(v, dict):
            out[k] = {
                "r": None if np.isnan(v["r"]) else round(float(v["r"]), 3),
                "p": None if np.isnan(v["p"]) else round(float(v["p"]), 3),
            }
        else:
            out[k] = None if (isinstance(v, float) and np.isnan(v)) else round(float(v), 3)
    return out


def _interpret(emb: dict, corr: dict) -> list[str]:
    notes: list[str] = []
    consistency = emb.get("embouchure_consistency", 0.0)
    if consistency >= 0.85:
        notes.append(f"Embouchure is very consistent ({consistency:.2f}).")
    elif consistency >= 0.65:
        notes.append(f"Embouchure is reasonably consistent ({consistency:.2f}).")
    else:
        notes.append(f"Embouchure varies notably ({consistency:.2f}); aim for steadier mouth shape.")

    jaw_r = corr.get("jaw_stability_vs_intonation", {}).get("r", float("nan"))
    if not np.isnan(jaw_r) and abs(jaw_r) > 0.4:
        direction = "more stable" if jaw_r > 0 else "less stable"
        notes.append(f"Jaw position correlates with intonation (r = {jaw_r:+.2f}); "
                     f"higher jaw → {direction} pitch.")

    lt_r = corr.get("lip_tension_vs_stability", {}).get("r", float("nan"))
    if not np.isnan(lt_r) and abs(lt_r) > 0.4:
        direction = "better" if lt_r > 0 else "worse"
        notes.append(f"Lip tension correlates with stability (r = {lt_r:+.2f}); "
                     f"higher tension → {direction} stability.")

    mw_r = corr.get("mouth_width_vs_stability", {}).get("r", float("nan"))
    if not np.isnan(mw_r) and abs(mw_r) > 0.4:
        direction = "more" if mw_r > 0 else "less"
        notes.append(f"Mouth width correlates with stability (r = {mw_r:+.2f}); "
                     f"wider mouth → {direction} stability.")

    return notes


@app.route("/api/embouchure_feedback", methods=["POST"])
def api_embouchure_feedback():
    """Generate AI-powered embouchure feedback using Claude."""
    try:
        import anthropic
    except ImportError:
        return jsonify({"error": "anthropic package not installed. Run: pip install anthropic"}), 500

    data = request.get_json(silent=True) or {}

    # Pull all available metrics from the request
    emb        = data.get("embouchure", {})
    corr       = data.get("correlation", {})
    summary    = data.get("summary", {})
    reg_corr   = data.get("register_correlation", {})

    consistency  = emb.get("embouchure_consistency")
    jaw_stab     = emb.get("jaw_stability")
    lip_tension  = emb.get("mean_lip_tension")
    lip_var      = emb.get("lip_tension_variance")
    mw_var       = emb.get("mouth_width_variance")
    face_pct     = emb.get("face_detected_pct")
    tendency     = summary.get("tendency", "centred")
    mean_note    = summary.get("mean_note", "unknown")
    mean_hz      = summary.get("mean_hz")
    overall      = summary.get("overall_score")
    mean_bias    = summary.get("mean_bias_cents", 0)

    # Determine register from mean Hz
    if mean_hz:
        if mean_hz < 116.54:
            register = "low (below B♭2)"
        elif mean_hz <= 466.16:
            register = "tenor (B♭2–B♭4)"
        else:
            register = "high (above B♭4)"
    else:
        register = "unknown"

    jaw_r  = (corr.get("jaw_stability_vs_intonation") or {}).get("r")
    lt_r   = (corr.get("lip_tension_vs_stability")    or {}).get("r")
    mw_r   = (corr.get("mouth_width_vs_stability")    or {}).get("r")
    mh_r   = (corr.get("mouth_height_vs_stability")   or {}).get("r")

    # Build a structured prompt with all measurable data
    prompt = f"""You are an expert bassoon pedagogue giving real-time embouchure feedback to a student.

Here is the data from their most recent recording session. Use your knowledge of bassoon technique to give specific, actionable feedback. Be direct but encouraging. Write in plain language a student can understand — no jargon without explanation.

## Session Data

**Mean note played**: {mean_note} ({mean_hz} Hz if available)
**Register**: {register}
**Intonation tendency**: {tendency} ({mean_bias:+.1f} cents mean bias)
**Overall stability score**: {overall if overall is not None else 'unavailable'} / 1.0

## Embouchure Metrics (0–1 scale)

- Embouchure consistency: {consistency if consistency is not None else 'N/A'}
- Jaw stability: {jaw_stab if jaw_stab is not None else 'N/A'} (1.0 = perfectly still jaw)
- Mean lip tension: {lip_tension if lip_tension is not None else 'N/A'} (0 = no tension, 1 = maximum)
- Lip tension variance: {lip_var if lip_var is not None else 'N/A'} (lower = more consistent)
- Mouth width variance: {mw_var if mw_var is not None else 'N/A'} px² (lower = more stable opening)
- Face detected: {face_pct if face_pct is not None else 'N/A'}% of frames

## Correlation: Embouchure vs Intonation (Pearson r)

- Jaw position vs intonation: {jaw_r if jaw_r is not None else 'N/A'}
- Lip tension vs stability: {lt_r if lt_r is not None else 'N/A'}
- Mouth width vs stability: {mw_r if mw_r is not None else 'N/A'}
- Mouth height vs stability: {mh_r if mh_r is not None else 'N/A'}

## Register correlations (|r| overall per register)

- Low register: {reg_corr.get('low')}
- Tenor register: {reg_corr.get('tenor')}
- High register: {reg_corr.get('high')}

## Bassoon pedagogy context (use this to ground your feedback)

**Register-specific embouchure rules:**
- Low register: minimal lip tension, open "O" mouth, relaxed jaw, warm slow air. Over-tightening kills low-note response.
- Tenor register: moderate tension, active corner engagement, flexible "O" shape, stable jaw.
- High register: firm but flexible lip pressure, more reed in mouth, faster cooler air, absolutely stable jaw. Over-squeezing causes sharp pitch and collapsed tone.

**Problem notes and tendencies:**
- F3/G3: tend flat — cause is under-support + soft reed. Fix: firmer lip seal, more air, maintain open mouth width.
- B♭4: tends sharp — cause is over-tightening in register change. Fix: loosen lip grip, voice lower ("ooh"), increase air speed.
- C5: unstable — can go either way. Sharp = over-tight. Flat = under-support. Diagnose from bias direction.
- Tenor octave (C#4–F#4): D4 tends flat, Eb4 sharp, F4 most demanding, F#4 sharp.

**Jaw stability rules:**
- Jaw should NEVER move during articulation ("gobbling"). This is universally condemned in published pedagogy.
- Jaw stability below 0.7 = significant problem. Below 0.4 = severe.
- Moving jaw → slowed articulation + pitch fluctuation + tone disruption.

**Lip tension interpretation:**
- Too low (0.0–0.3): under-support → airy tone, flat pitch, air leaks.
- Correct for register: low=0.3–0.5, tenor=0.5–0.7, high=0.7–0.9.
- Too high (>0.9): over-pinching → thin tone, sharp pitch, restricted dynamics.

**Correlation interpretation:**
- Strong positive jaw r (>0.4): jaw movement directly affecting pitch — priority fix.
- Strong lip tension r: lip changes are causing intonation instability.
- Strong mouth width r: embouchure collapse affecting pitch consistency.

## Your task

Write 3–5 paragraphs of specific, actionable feedback for this student. Structure it as:
1. One sentence summarising what went well.
2. The single most important embouchure problem to fix (be specific — name the metric, what it means, and exactly what to do).
3. One or two secondary issues if they are significant.
4. One specific exercise to practise this week targeting the identified problem.
5. One encouraging closing sentence.

Keep the total response under 300 words. Do not use bullet points — write in flowing paragraphs."""

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        feedback_text = message.content[0].text
        return jsonify({"feedback": feedback_text})
    except Exception as exc:
        return jsonify({"error": f"AI feedback failed: {exc}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
