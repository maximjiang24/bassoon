"""
Configuration constants for bassoon intonation analysis.
"""

# Audio sample rate in Hz. 44100 is CD quality and sufficient for
# capturing all harmonics relevant to bassoon analysis.
SAMPLE_RATE = 44100

# Number of audio samples between successive pitch analysis frames.
# Smaller values give finer time resolution at the cost of more computation.
HOP_LENGTH = 512

# Default recording duration in seconds for a single note capture session.
RECORDING_DURATION = 30

# Length of the sliding window (in seconds) used to assess pitch stability.
# A note is considered stable if pitch deviation stays within STABILITY_THRESHOLD
# over this window.
STABILITY_WINDOW_SIZE = 1.0  # seconds

# Maximum pitch deviation in cents allowed within STABILITY_WINDOW_SIZE for a
# note to be classified as stable. 20 cents is roughly one fifth of a semitone.
STABILITY_THRESHOLD = 20  # cents

# Minimum confidence score (0–1) returned by the pitch detector for a frame
# to be included in analysis. Frames below this are treated as unvoiced/noise.
CONFIDENCE_THRESHOLD = 0.1

# Reference frequency in Hz for A4, used as the anchor for all cent calculations.
# Standard concert pitch; adjust to 442 or 415 for period-instrument contexts.
REFERENCE_FREQ = 440  # Hz, A4
