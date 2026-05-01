#!/usr/bin/env python3

import os
import re
import math
import wave
import subprocess
import time
from faster_whisper import WhisperModel

# -------------------------
# Prerequisites
# -------------------------

# $ pip install faster-whisper ctranslate2
# $ apt install ffmpeg

# -------------------------
# Configuration
# -------------------------

ORIGINALS_DIR = "originals"
WAV_DIR = "wav"
OUTPUT_FILE = "metadata.csv"

MODEL_SIZE = "large-v3"
DEVICE = "cpu"

LANGUAGE = "en"

# 0.50 permissive
# 0.60 balanced
# 0.65–0.70 strict
MIN_CONFIDENCE = 0.65

MIN_DURATION = 1.2
MAX_DURATION = 12.0

TARGET_SR = 22050

# -------------------------
# Text normalization
# -------------------------

def normalize_text(text: str):
#   text = text.strip().lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace('"', "")
#   text = text.replace('"', "").replace("'", "")
    text = re.sub(r"[:;()\|\[\]]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# -------------------------
# Check WAV format
# -------------------------

def wav_is_correct_format(path):
    try:
        with wave.open(path, "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            comp = wf.getcomptype()
            if sr == TARGET_SR and ch == 1 and sw == 2 and comp == "NONE":
                return True
    except wave.Error:
        pass
    return False

# -------------------------
# Convert WAV
# -------------------------

def convert_wav(source_path, target_path):
    if os.path.exists(target_path):
        print("Converted file already exists, skipping conversion")
        return
    if wav_is_correct_format(source_path):
        # just copy if format already correct
        subprocess.run(["cp", source_path, target_path])
        return
    # convert using ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-i", source_path,
        "-ac", "1",
        "-ar", str(TARGET_SR),
        "-sample_fmt", "s16",
        target_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# -------------------------
# Get duration
# -------------------------

def get_wav_duration(path):
    with wave.open(path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)

# -------------------------
# Confidence calculation
# -------------------------

def compute_confidence(segments):
    probs = []
    for s in segments:
        if s.avg_logprob is not None:
            probs.append(math.exp(s.avg_logprob))
    if not probs:
        return 0.0
    return sum(probs) / len(probs)

# -------------------------
# Format seconds HH:MM:SS
# -------------------------

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# -------------------------
# Main pipeline
# -------------------------

def main():

    os.makedirs(WAV_DIR, exist_ok=True)

    model = WhisperModel(MODEL_SIZE, device=DEVICE)

    wav_files = sorted(
        f for f in os.listdir(ORIGINALS_DIR)
        if f.lower().endswith(".wav")
    )

    total_files = len(wav_files)
    kept = 0
    skipped = 0

    start_time = time.time()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:

        for idx, wav_file in enumerate(wav_files, 1):

            wav_source = os.path.join(ORIGINALS_DIR, wav_file)
            wav_target = os.path.join(WAV_DIR, wav_file)
            basename = os.path.splitext(wav_file)[0]

            print(f"\nProcessing {wav_file} ({idx}/{total_files})")

            # -------------------------
            # Convert audio
            # -------------------------
            convert_wav(wav_source, wav_target)

            # -------------------------
            # Duration filter
            # -------------------------
            duration = get_wav_duration(wav_target)
            if duration < MIN_DURATION:
                print(f"Skipping (too short: {duration:.2f}s)")
                skipped += 1
                os.remove(wav_target)
                continue

            if duration > MAX_DURATION:
                print(f"Skipping (too long: {duration:.2f}s)")
                skipped += 1
                os.remove(wav_target)
                continue

            # -------------------------
            # Transcription
            # -------------------------
            segments, info = model.transcribe(
                wav_target,
                language=LANGUAGE
            )

            segments = list(segments)
            text = " ".join(s.text.strip() for s in segments)
            text = normalize_text(text)
            confidence = compute_confidence(segments)

            if confidence < MIN_CONFIDENCE:
                print(f"Skipping (low confidence: {confidence:.2f})")
                skipped += 1
                os.remove(wav_target)
                continue

            out.write(f"{basename}|{text}\n")
            print(f"Accepted (conf: {confidence:.2f})")
            kept += 1

            # -------------------------
            # ETA estimation
            # -------------------------
            elapsed = time.time() - start_time
            avg_per_file = elapsed / idx
            remaining = total_files - idx
            eta = remaining * avg_per_file
            print("Accepted so far: ", kept)
            print("Skipped so far: ", skipped)
            print(f"Estimated time remaining: {format_time(eta)}")

    print("\nFinished")
    print("Accepted in total:", kept)
    print("Skipped in total:", skipped)

if __name__ == "__main__":
    main()
