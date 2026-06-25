"""
Webcam recording and MediaPipe facial landmark extraction for embouchure tracking.
"""

from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError as e:
    raise ImportError("opencv-python is required: pip install opencv-python") from e

try:
    import mediapipe as mp
except ImportError as e:
    raise ImportError("mediapipe is required: pip install mediapipe") from e

_RECORDINGS_DIR = Path(__file__).parent.parent.parent / "data" / "recordings"
_MODEL_DIR  = Path(__file__).parent.parent.parent / "data"
_MODEL_PATH = _MODEL_DIR / "face_landmarker.task"
_MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

# MediaPipe Face Mesh landmark indices used to track bassoon embouchure.
# mouth_left/right measure horizontal lip spread (embouchure width).
# mouth_top/bottom measure vertical aperture (how open the embouchure is).
# chin tracks jaw drop — the primary pitch-correction mechanism on bassoon,
# where lowering the jaw relaxes reed pressure and lowers pitch.
_LM = {
    "mouth_left":   61,
    "mouth_right":  291,
    "mouth_top":    13,
    "mouth_bottom": 14,
    "chin":         152,
}


def _ensure_model() -> str:
    if not _MODEL_PATH.exists():
        _MODEL_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Downloading face landmarker model (~30 MB) to {_MODEL_PATH}…")
        urllib.request.urlretrieve(_MODEL_URL, str(_MODEL_PATH))
        print("Model downloaded.")
    return str(_MODEL_PATH)


class EmbouchureTracker:
    """Records video and extracts embouchure metrics via MediaPipe."""

    def __init__(
        self,
        recordings_dir: Path = _RECORDINGS_DIR,
        model_path: str | None = None,
    ) -> None:
        self.recordings_dir = recordings_dir
        self._model_path = model_path

    def _get_model_path(self) -> str:
        return self._model_path if self._model_path else _ensure_model()

    def record_video(
        self,
        duration: float = 30.0,
        filename: str | None = None,
        fps: int = 30,
    ) -> str:
        """Record video from the default webcam.

        Returns the absolute path to the saved MP4 file.

        Raises
        ------
        RuntimeError
            If no webcam is accessible.
        """
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError(
                "No webcam found. Check that a camera is connected and not in use."
            )

        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if filename is None:
            filename = f"recording_{int(time.time())}"
        if not filename.endswith(".mp4"):
            filename += ".mp4"

        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(self.recordings_dir / filename)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_path, fourcc, fps, (frame_w, frame_h))

        print(f"Recording video for {duration:.1f}s — make sure your face is visible…")
        start = time.monotonic()

        try:
            while True:
                elapsed = time.monotonic() - start
                if elapsed >= duration:
                    break
                ret, frame = cap.read()
                if not ret:
                    break
                writer.write(frame)
                print(
                    f"\r  {elapsed:5.1f}s / {duration:.1f}s  ({duration - elapsed:.1f}s left) ",
                    end="", flush=True,
                )
        finally:
            cap.release()
            writer.release()

        print(f"\nVideo saved to: {out_path}")
        return out_path

    def extract_facial_landmarks(self, video_path: str) -> dict:
        """Extract mouth and jaw landmarks from every frame of a video.

        Uses MediaPipe FaceLandmarker (Tasks API, mediapipe >= 0.10).
        Frames where no face is detected are represented as NaN.

        Returns
        -------
        Dict with keys ``times``, ``mouth_width``, ``mouth_height``,
        ``jaw_position``, ``lip_tension``.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        result: dict[str, list] = {
            "times":        [],
            "mouth_width":  [],
            "mouth_height": [],
            "jaw_position": [],
            "lip_tension":  [],
        }

        from mediapipe.tasks import python as _mp_tasks
        from mediapipe.tasks.python import vision as _mp_vision

        base_opts = _mp_tasks.BaseOptions(model_asset_path=self._get_model_path())
        opts = _mp_vision.FaceLandmarkerOptions(
            base_options=base_opts,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            min_face_presence_confidence=0.5,
        )

        nan       = float("nan")
        frame_idx = 0

        with _mp_vision.FaceLandmarker.create_from_options(opts) as landmarker:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                t       = frame_idx / video_fps
                rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                detection = landmarker.detect(mp_img)

                result["times"].append(t)

                if detection.face_landmarks:
                    lm = detection.face_landmarks[0]

                    def px(idx: int) -> tuple[float, float]:
                        return lm[idx].x * frame_w, lm[idx].y * frame_h

                    ml_x, _    = px(_LM["mouth_left"])
                    mr_x, _    = px(_LM["mouth_right"])
                    mt_x, mt_y = px(_LM["mouth_top"])
                    mb_x, mb_y = px(_LM["mouth_bottom"])
                    _,    chin_y = px(_LM["chin"])

                    mouth_w = float(abs(mr_x - ml_x))
                    mouth_h = float(np.hypot(mb_x - mt_x, mb_y - mt_y))
                    tension = mouth_w / mouth_h if mouth_h > 1e-6 else nan

                    result["mouth_width"].append(mouth_w)
                    result["mouth_height"].append(mouth_h)
                    result["jaw_position"].append(float(chin_y))
                    result["lip_tension"].append(float(np.clip(tension / 10.0, 0.0, 1.0)))
                else:
                    result["mouth_width"].append(nan)
                    result["mouth_height"].append(nan)
                    result["jaw_position"].append(nan)
                    result["lip_tension"].append(nan)

                frame_idx += 1

        cap.release()
        return result

    @staticmethod
    def compute_embouchure_metrics(landmarks: dict) -> dict:
        """Compute summary stability metrics from per-frame landmark data."""

        def _arr(key: str) -> np.ndarray:
            a = np.array(landmarks[key], dtype=float)
            return a[~np.isnan(a)]

        mw  = _arr("mouth_width")
        mh  = _arr("mouth_height")
        jaw = _arr("jaw_position")
        lt  = _arr("lip_tension")

        total    = len(landmarks["times"])
        detected = int(np.sum(~np.isnan(landmarks["mouth_width"])))

        def _stability(arr: np.ndarray, scale: float) -> float:
            if arr.size < 2:
                return 0.0
            return float(np.exp(-np.var(arr) / (scale ** 2)))

        # Scale values are tuned to typical pixel magnitudes at 720p/1080p for a
        # player seated ~1 m from the camera.
        # jaw scale=5 px: small jaw movements have outsized intonation impact on bassoon
        # mw  scale=3 px: embouchure width varies less than jaw during normal playing
        # mh  scale=2 px: vertical aperture is tightly controlled; large changes flag issues
        # lt  scale=0.05: lip tension is normalised 0–1, so the scale is proportionally small
        jaw_stab    = _stability(jaw, scale=5.0)
        mw_stab     = _stability(mw,  scale=3.0)
        mh_stab     = _stability(mh,  scale=2.0)
        lt_stab     = _stability(lt,  scale=0.05)
        consistency = float(np.mean([jaw_stab, mw_stab, mh_stab, lt_stab]))

        return {
            "mean_mouth_width":       float(np.mean(mw))  if mw.size  else float("nan"),
            "mouth_width_variance":   float(np.var(mw))   if mw.size  else float("nan"),
            "mean_mouth_height":      float(np.mean(mh))  if mh.size  else float("nan"),
            "mouth_height_variance":  float(np.var(mh))   if mh.size  else float("nan"),
            "mean_jaw_position":      float(np.mean(jaw)) if jaw.size else float("nan"),
            "jaw_position_variance":  float(np.var(jaw))  if jaw.size else float("nan"),
            "jaw_stability":          jaw_stab,
            "mean_lip_tension":       float(np.mean(lt))  if lt.size  else float("nan"),
            "lip_tension_variance":   float(np.var(lt))   if lt.size  else float("nan"),
            "embouchure_consistency": consistency,
            "face_detected_pct":      round(100.0 * detected / total, 1) if total else 0.0,
        }

    @staticmethod
    def align_audio_video(
        audio_times: np.ndarray,
        video_times: list[float],
    ) -> np.ndarray:
        """Return a common time grid covering the overlap of audio and video."""
        t_start = max(float(audio_times[0]),  float(video_times[0]))
        t_end   = min(float(audio_times[-1]), float(video_times[-1]))

        if t_end <= t_start:
            raise ValueError(
                f"Audio and video have no overlapping time range "
                f"(audio: {audio_times[0]:.2f}–{audio_times[-1]:.2f}s, "
                f"video: {video_times[0]:.2f}–{video_times[-1]:.2f}s)"
            )

        dt = float(audio_times[1] - audio_times[0]) if len(audio_times) > 1 else 1 / 30
        return np.arange(t_start, t_end, dt)


# ---------------------------------------------------------------------------
# Module-level convenience functions (preserve existing call-sites)
# ---------------------------------------------------------------------------

_default = EmbouchureTracker()


def record_video(duration: float = 30.0, filename: str | None = None, fps: int = 30) -> str:
    return _default.record_video(duration=duration, filename=filename, fps=fps)


def extract_facial_landmarks(video_path: str) -> dict:
    return _default.extract_facial_landmarks(video_path)


def compute_embouchure_metrics(landmarks: dict) -> dict:
    return EmbouchureTracker.compute_embouchure_metrics(landmarks)


def align_audio_video(audio_times: np.ndarray, video_times: list[float]) -> np.ndarray:
    return EmbouchureTracker.align_audio_video(audio_times, video_times)
