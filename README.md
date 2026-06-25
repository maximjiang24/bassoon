# Bassoon Intonation

A Python toolkit for recording, analyzing, and visualizing bassoon intonation.
It uses the pYIN pitch-detection algorithm to track fundamental frequency
frame-by-frame, then computes stability metrics across time windows and
bassoon registers, and produces publication-ready plots.

---

## Features

- Live microphone recording via `sounddevice`
- Probabilistic pitch detection (pYIN) tuned to the bassoon's sounding range (B♭1–E♭5)
- Per-window stability metrics: variance, drift rate, stability score
- Automatic detection of unstable pitch regions
- Register-level breakdown (low / tenor / high)
- Three matplotlib visualizations: pitch contour, stability heatmap, register comparison
- Jupyter notebooks for interactive exploration
- pytest test suite with no hardware dependencies

---

## Project Structure

```
bassoon-intonation/
├── data/
│   ├── recordings/     # WAV files saved by the recorder
│   └── analysis/       # PNG plots saved by the visualizer
├── examples/
│   └── sample_analysis.py   # End-to-end CLI workflow
├── notebooks/
│   ├── 01_test_pitch_detection.ipynb
│   ├── 02_analyze_recording.ipynb
│   └── 03_stability_metrics.ipynb
├── src/
│   ├── audio/
│   │   ├── recorder.py        # Microphone capture
│   │   └── pitch_detector.py  # pYIN wrapper + Hz/cents/note helpers
│   ├── analysis/
│   │   └── stability.py       # Window metrics, region detection, register split
│   ├── visualization/
│   │   └── plotter.py         # Pitch contour, heatmap, register bar chart
│   └── utils/
│       └── config.py          # Shared constants
└── tests/
    ├── test_pitch_detector.py
    ├── test_stability.py
    └── test_recorder.py
```

---

## Installation

**Requirements:** Python 3.10+

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd bassoon-intonation

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install the package in editable mode
pip install -e .
```

> **Note:** `soundfile` is also required for saving WAV files.
> Add it to your environment with `pip install soundfile` if it is not
> pulled in automatically.

---

## Quick Start

### Record and analyze from the command line

```bash
cd examples
python sample_analysis.py --duration 10 --save my_bb3
```

This records 10 seconds, saves the WAV to `data/recordings/my_bb3.wav`,
runs the full analysis pipeline, prints a summary report, and writes three
plots to `data/analysis/`.

### Run the interactive notebooks

```bash
jupyter notebook notebooks/
```

| Notebook | Purpose |
|----------|---------|
| `01_test_pitch_detection` | Verify the detector on a file or synthetic tone |
| `02_analyze_recording`    | Full pipeline with live recording |
| `03_stability_metrics`    | Explore metrics on synthetic data; tune the threshold |

### Use the API directly

```python
import sys
sys.path.insert(0, 'src')

import soundfile as sf
from audio.pitch_detector import detect_pitch, get_note_name, hz_to_cents
from analysis.stability import compute_stability_metrics, identify_unstable_regions
from visualization.plotter import plot_pitch_contour

# Load a WAV file
audio, sr = sf.read('data/recordings/my_bb3.wav', dtype='float32')

# Detect pitch
times, frequencies, confidence = detect_pitch(audio, sr=sr)

# Stability metrics
metrics = compute_stability_metrics(times, frequencies, window_size=1.0)
regions = identify_unstable_regions(times, frequencies, threshold=20)

# Plot
fig = plot_pitch_contour(times, frequencies, title='B♭3 Long Tone', save=True)
```

---

## Configuration

All tunable constants live in `src/utils/config.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `SAMPLE_RATE` | `44100` | Recording sample rate (Hz) |
| `HOP_LENGTH` | `512` | Frames between pitch analysis windows |
| `RECORDING_DURATION` | `30` | Default recording length (s) |
| `STABILITY_WINDOW_SIZE` | `1.0` | Analysis window size (s) |
| `STABILITY_THRESHOLD` | `20` | Variance threshold for unstable regions (cents) |
| `CONFIDENCE_THRESHOLD` | `0.1` | Minimum pYIN voiced probability |
| `REFERENCE_FREQ` | `440` | A4 reference for cent calculations (Hz) |

Change `REFERENCE_FREQ` to `442` for orchestral pitch or `415` for period instruments.

---

## Running Tests

```bash
pytest tests/ -v
```

The test suite mocks all hardware calls (`sounddevice`, `soundfile`) so it
runs without a microphone on any machine.

---

## Roadmap

- [ ] Long-tone tracking across a full scale (chromatic B♭1–E♭5)
- [ ] Intonation tendency report per note (e.g. "F3 consistently 15 cents flat")
- [ ] Comparison mode: overlay two recordings on the same pitch contour
- [ ] Export to CSV / JSON for external analysis
- [ ] Real-time pitch display during recording
- [ ] Support for alternate tuning systems (just intonation, Pythagorean)
