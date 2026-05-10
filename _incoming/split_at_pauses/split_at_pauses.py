#!/usr/bin/env python3

"""
Split a WAV file into segments based on detected pauses.

Behavior:
- Loads a WAV file into a NumPy array
- Detects pauses longer than X milliseconds
- Uses a moving RMS average over 10 ms windows to estimate signal level
- Detects a dynamic noise floor from the RMS distribution
- Finds the midpoint of each detected pause
- Exports audio from:
      midpoint(previous pause)
  to:
      midpoint(current pause)

Output:
- WAV files written into ./output/

Requirements:
    pip install numpy scipy soundfile

Usage:
    python split_on_pauses.py input.wav --pause-ms 700

Optional:
    --threshold-multiplier 2.0
"""

import os
import argparse
import numpy as np
import soundfile as sf

from scipy.ndimage import uniform_filter1d


# ------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------

def to_mono(audio: np.ndarray) -> np.ndarray:
    """Convert stereo/multi-channel audio to mono."""
    if audio.ndim == 1:
        return audio
    return np.mean(audio, axis=1)


def moving_rms(signal: np.ndarray, window_size: int) -> np.ndarray:
    """
    Compute moving RMS using a sliding window.

    window_size is in samples.
    """
    squared = signal.astype(np.float64) ** 2
    mean_squared = uniform_filter1d(squared, size=window_size)
    return np.sqrt(mean_squared + 1e-12)


def detect_noise_floor(rms: np.ndarray) -> float:
    """
    Estimate noise floor from lower percentile RMS values.

    This works reasonably well for dialogue/music recordings
    with pauses/background noise.
    """
    lower = np.percentile(rms, 20)
    return lower


def find_pauses(
    rms: np.ndarray,
    sample_rate: int,
    silence_threshold: float,
    min_pause_ms: float
):
    """
    Detect pauses longer than min_pause_ms.

    Returns:
        list of tuples:
            (start_sample, end_sample, midpoint_sample)
    """

    silent = rms < silence_threshold

    pauses = []

    in_pause = False
    start = 0

    min_pause_samples = int(sample_rate * min_pause_ms / 1000)

    for i, is_silent in enumerate(silent):

        if is_silent and not in_pause:
            in_pause = True
            start = i

        elif not is_silent and in_pause:
            end = i
            in_pause = False

            duration = end - start

            if duration >= min_pause_samples:
                midpoint = (start + end) // 2
                pauses.append((start, end, midpoint))

    # Handle pause continuing to EOF
    if in_pause:
        end = len(silent)
        duration = end - start

        if duration >= min_pause_samples:
            midpoint = (start + end) // 2
            pauses.append((start, end, midpoint))

    return pauses


def save_segments(
    audio: np.ndarray,
    sample_rate: int,
    pauses,
    output_dir="output"
):
    """
    Save audio between pause midpoints.
    """

    os.makedirs(output_dir, exist_ok=True)

    if len(pauses) < 2:
        print("Not enough pauses detected to create segments.")
        return

    segment_count = 0

    for i in range(1, len(pauses)):

        prev_mid = pauses[i - 1][2]
        curr_mid = pauses[i][2]

        segment = audio[prev_mid:curr_mid]

        if len(segment) == 0:
            continue

        while True:
            segment_count += 1
            out_path = os.path.join(
                output_dir,
                f"segment_{segment_count:04d}.wav"
            )
            if not os.path.isfile(out_path):
                break

        sf.write(out_path, segment, sample_rate)

        duration_sec = len(segment) / sample_rate
        if duration_sec > 12.0:
            print(
                f"Discarded due to length: {duration_sec:.2f} sec)"
            )
            continue

        print(
            f"Saved: {out_path} "
            f"({duration_sec:.2f} sec)"
        )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "input_wav",
        help="Input WAV file"
    )

    parser.add_argument(
        "--pause-ms",
        type=float,
        default=700,
        help="Minimum pause length in milliseconds"
    )

    parser.add_argument(
        "--threshold-multiplier",
        type=float,
        default=2.0,
        help=(
            "Silence threshold multiplier above detected noise floor"
        )
    )

    args = parser.parse_args()

    print("Loading audio...")

    audio, sample_rate = sf.read(args.input_wav)

    mono = to_mono(audio)

    # --------------------------------------------------------
    # Moving RMS over 10 ms
    # --------------------------------------------------------

    rms_window_ms = 10.0

    rms_window_samples = max(
        1,
        int(sample_rate * rms_window_ms / 1000)
    )

    print(
        f"Computing moving RMS "
        f"({rms_window_ms} ms window)..."
    )

    rms = moving_rms(mono, rms_window_samples)

    # --------------------------------------------------------
    # Noise floor detection
    # --------------------------------------------------------

    noise_floor = detect_noise_floor(rms)

    silence_threshold = (
        noise_floor * args.threshold_multiplier
    )

    print(f"Detected noise floor: {noise_floor:.6f}")
    print(f"Silence threshold:   {silence_threshold:.6f}")

    # --------------------------------------------------------
    # Pause detection
    # --------------------------------------------------------

    pauses = find_pauses(
        rms=rms,
        sample_rate=sample_rate,
        silence_threshold=silence_threshold,
        min_pause_ms=args.pause_ms
    )

    print(f"Detected {len(pauses)} pauses.")

    if len(pauses) < 2:
        print("Need at least two pauses to create segments.")
        return

    # --------------------------------------------------------
    # Save segments
    # --------------------------------------------------------

    save_segments(
        audio=audio,
        sample_rate=sample_rate,
        pauses=pauses,
        output_dir="output"
    )

    print("Done.")


if __name__ == "__main__":
    main()
