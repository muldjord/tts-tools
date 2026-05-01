#!/usr/bin/env python3

import argparse
import csv
import glob
import os
import re
import subprocess
import time
import wave
import numpy as np
import math
from difflib import SequenceMatcher, ndiff
from faster_whisper import WhisperModel

# Text output colors
RED = "\033[91m"
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
DIGIT_PATTERN = re.compile(r'\d')

ROMAN_PATTERN = re.compile(
    r'\bM{0,4}(CM|CD|D?C{0,3})'
    r'(XC|XL|L?X{0,3})'
    r'(IX|IV|V?I{1,3})\b'
)

def contains_number(text: str) -> bool:
    if DIGIT_PATTERN.search(text):
        return True

    if ROMAN_PATTERN.search(text):
        # Ensure the match length is at least 2 characters
        return any(len(m.group(0)) >= 2 for m in ROMAN_PATTERN.finditer(text))

    return False

def first_last_words_match(a: str, b: str) -> bool:
    def get_words(s):
        # Extract word tokens and normalize casing
        return re.findall(r'\b\w+\b', s.lower())

    wa = get_words(a)
    wb = get_words(b)

    if not wa or not wb:
        return False

    return wa[0] == wb[0] and wa[-1] == wb[-1]

def clear_path_or_quit(path, suffix):
    old_files = os.listdir(path)
            
    remove_old = "n"
    
    for item in old_files:
        if item.endswith(f".{suffix}"):
            remove_old = input(f"'{suffix}' files found in folder '{path}'. Would you like to remove them (y/N)? ")
            if remove_old.lower() != "y":
                print(f"{RED}Can't continue with '{suffix}' files in '{path}' directory. Quitting...{RESET}")
                return False
            break

    for item in old_files:
        if item.endswith(f".{suffix}"):
            os.remove(os.path.join(path, item))
    return True

def format_time(seconds):

    seconds = int(seconds)

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    return f"{h:02d}:{m:02d}:{s:02d}"

def levenshtein_distance(a, b):
    m, n = len(a), len(b)

    dp = [[0]*(n+1) for _ in range(m+1)]

    for i in range(m+1):
        dp[i][0] = i
    for j in range(n+1):
        dp[0][j] = j

    for i in range(1, m+1):
        for j in range(1, n+1):
            cost = 0 if a[i-1] == b[j-1] else 1

            dp[i][j] = min(
                dp[i-1][j] + 1,
                dp[i][j-1] + 1,
                dp[i-1][j-1] + cost
            )

    return dp[m][n]

def count_contractions(text: str) -> int:
    # A set of common English contractions
    contractions = {
        "aren't", "can't", "couldn't", "didn't", "doesn't", "don't",
        "hadn't", "hasn't", "haven't", "he'd", "he'll", "he's",
        "i'd", "i'll", "i'm", "i've",
        "isn't", "it'd", "it'll", "it's",
        "let's",
        "mightn't", "mustn't",
        "shan't", "she'd", "she'll", "she's",
        "shouldn't",
        "that's", "there's", "they'd", "they'll", "they're", "they've",
        "wasn't", "we'd", "we'll", "we're", "we've",
        "weren't",
        "what's", "where's", "who's", "why's",
        "won't", "wouldn't",
        "you'd", "you'll", "you're", "you've"
    }

    # Normalize text to lowercase
    text = text.lower()

    # Extract words with optional apostrophes
    tokens = re.findall(r"\b[\w']+\b", text)

    # Count matches
    return sum(1 for token in tokens if token in contractions)

# Return two colored strings showing inline differences.
def color_diff(a, b):
    diff = list(ndiff(a, b))

    out1 = []
    out2 = []

    for d in diff:
        code = d[0]
        char = d[2:]

        if code == " ":
            out1.append(char)
            out2.append(char)

        elif code == "-":
            out1.append(f"{RED}{char}{RESET}")

        elif code == "+":
            out2.append(f"{GREEN}{char}{RESET}")

    return "".join(out1), "".join(out2)

def run(cmd):
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def time_to_seconds(t):
    h, m, s = t.split(":")
    s, ms = s.split(",")
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000

def normalize_text(text: str): 
    if text.strip().startswith("-"):
        text = text.lstrip("- ")
    # Remove xml tags
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("|", "")
    return text.strip()

def clean_text(text):

    lines = text.splitlines()
    cleaned = []

    for line in lines:

        line = normalize_text(line)

        cleaned.append(line.strip())

    text = " ".join(cleaned)
    text = re.sub(r"\s+", " ", text)

    return text.strip()

# ------------------------------------------------------------
# Subtitle parsing
# ------------------------------------------------------------

def parse_srt(path):

    with open(path, encoding="utf8") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content.strip())

    subs = []

    for block in blocks:

        lines = block.splitlines()

        if len(lines) < 2:
            continue

        start, end = lines[1].split(" --> ")

        text = "\n".join(lines[2:])

        subs.append({
            "start": time_to_seconds(start),
            "end": time_to_seconds(end),
            "text": clean_text(text)
        })

    return subs

# ------------------------------------------------------------
# Audio loading (Loads into RAM)
# ------------------------------------------------------------

def load_full_audio(video):

    # 32bit floats for internal use
    cmd = [
        "ffmpeg",
        "-i", video,
        "-ac", "1",
        "-ar", "22050",
        "-f", "f32le",
        "-"
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    raw = proc.stdout.read()

    audio = np.frombuffer(raw, dtype=np.float32)

    sr = 22050

    return audio, sr


def write_wav(path, audio, sr):

    audio = np.clip(audio, -1, 1)
    # 16 bit ints for saved wavs
    audio = (audio * 32767).astype(np.int16)

    with wave.open(path,"w") as wf:

        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())


# ------------------------------------------------------------
# Audio processing
# ------------------------------------------------------------

def apply_fades(audio, sr, start_fade, end_fade):

    if start_fade > 0:

        n = int(sr*start_fade)

        if n < len(audio):

            ramp = np.linspace(0,1,n)
            audio[:n] *= ramp

    if end_fade > 0:

        n = int(sr*end_fade)

        if n < len(audio):

            ramp = np.linspace(1,0,n)
            audio[-n:] *= ramp

    return audio

def loudness_normalize(audio, target_rms=0.1, eps=1e-8, peak_limit=0.99):
    rms = np.sqrt(np.mean(audio**2) + eps)

    gain = target_rms / rms

    normalized = audio * gain

    peak = np.max(np.abs(normalized))

    if peak > peak_limit:
        normalized = normalized * (peak_limit / peak)

    return normalized

# | result   | meaning           |
# | -------- | ----------------- |
# | < 5 dB   | silence / noise   |
# | 5–10 dB  | weak speech       |
# | 10–20 dB | normal speech     |
# | > 20 dB  | very clean speech |
def speech_noise_ratio(audio, frame=1024):
    audio = np.abs(audio)
    frames = audio[:len(audio)//frame*frame].reshape(-1, frame)
    energy = frames.mean(axis=1)
    noise = np.percentile(energy, 20)
    speech = np.percentile(energy, 90)

    return 20*np.log10((speech+1e-8)/(noise+1e-8))

# | value   | meaning           |
# | ------- | ----------------- |
# | 0.0     | silence           |
# | 0.1–0.3 | little speech     |
# | 0.4–0.7 | normal speech     |
# | >0.7    | continuous speech |
def speech_presence(audio):
    audio = np.abs(audio)
    noise = np.percentile(audio,20)
    speech = audio > noise * 3

    return speech.mean()

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("-i", required=True)

    # Subtitle sentence min/max in characters
    parser.add_argument("--min-length", type=int, default=10)
    parser.add_argument("--max-length", type=int, default=200)

    # Max edit distance threshold between subtitle and related transcribed audio
    parser.add_argument("--max-edit-threshold", type=int, default=3)

    # Padding to add at start and end of audio snippets
    parser.add_argument("--start-padding", type=float, default=0.15)
    parser.add_argument("--end-padding", type=float, default=0.05)

    # Fade start and end of audio snippets
    parser.add_argument("--start-fade", type=float, default=0.15)
    parser.add_argument("--end-fade", type=float, default=0.05)

    parser.add_argument("--speech-noise-threshold", type=float, default=10.0)
    parser.add_argument("--speech-presence-threshold", type=float, default=0.3)

    parser.add_argument("--whisper-model", default="large-v3")
    parser.add_argument("--whisper-device", default="cpu")
    parser.add_argument("--whisper-lang", default="en")

    parser.add_argument("--discard-mismatches", action='store_true')
    
    args = parser.parse_args()

    # Set whether to discard sentences / subtitles that mismatches the transcription
    discard_mismatches = args.discard_mismatches

    videos = sorted(glob.glob(args.i))

    max_edit_threshold = args.max_edit_threshold

    whisper_lang = args.whisper_lang
    
    if not videos:
        print(f"{RED}No videos found!{RESET}")
        return

    output_path = "wav"
    skipped_path = "skipped"

    print(f"{GREEN}Output path:{RESET} '{output_path}'")
    os.makedirs(output_path, exist_ok=True)
    if not clear_path_or_quit(output_path, "wav"):
        return

    if not discard_mismatches:
        print(f"{GREEN}Skipped path:{RESET} '{skipped_path}'")
        os.makedirs(skipped_path, exist_ok=True)
        if not clear_path_or_quit(skipped_path, "wav"):
            return

    csv_file = "metadata.csv"

    print(f"{GREEN}Output file:{RESET} '{csv_file}'")

    if os.path.exists(csv_file):
        remove_old_csv = input("Output file already exists. Would you like to remove it (y/N)? ")
        if remove_old_csv.lower() != "y":
            print(f"{RED}Can't continue with existing output file. Quitting...{RESET}")
            return
        os.remove(csv_file)

    whisper = WhisperModel(args.whisper_model, device=args.whisper_device)

    clip_id = 1
    accepted = 0
    skipped = 0
    mismatches = 0 # Bad subtitle and transcription match, these are saved but needs manual editing

    total_videos = len(videos)
    current_video = 0
    
    for video in videos:

        print(f"{GREEN}Processing:{RESET} {video}")

        audio_full, sr = load_full_audio(video)

        srt = os.path.splitext(video)[0] + ".srt"

        print(f"{BLUE}Expected subtitle file:{RESET} {srt}")

        if not os.path.exists(srt):
            print(f"{YELLOW}  Subtitle file not found, skipping video!{RESET}")
            continue

        subs = parse_srt(srt)

        current_video += 1

        idx = 0

        start_time = time.time()
        total_subtitles = len(subs)

        while idx < len(subs):

            print(f"\n{GREEN}Processing: '{RESET}{video}{GREEN}' (id: {RESET}{clip_id:06d}{GREEN}, subtitle: {RESET}{idx}{GREEN}/{RESET}{total_subtitles}{GREEN}, video: {RESET}{current_video}{GREEN}/{RESET}{total_videos}{GREEN}):{RESET}")
            subtitle = subs[idx]["text"]

            if not subtitle or not subtitle[0].isupper():
                print(f"{YELLOW}  Subtitle doesn't begin with uppercase letter or is empty, skipping...{RESET}")
                idx += 1
                continue

            start = subs[idx]["start"]
            end = subs[idx]["end"]

            while not subtitle.endswith((".", "!", "?", ".\"", "!\"", "?\"", )) and idx+1 < len(subs):
                idx += 1
                subtitle += " " + subs[idx]["text"]
                end = subs[idx]["end"]

            subtitle = subtitle.strip()
 
            basename = f"{clip_id:06d}"

            if len(subtitle) < args.min_length or len(subtitle) > args.max_length:
                print(f"{YELLOW}  Skipping! Subtitle is either too short or too long!{RESET}")
                idx += 1
                skipped += 1
                continue

            start -= args.start_padding
            end += args.end_padding

            start = max(0, start)

            start_sample = int(start * sr)
            end_sample = int(end * sr)

            audio = audio_full[max(start_sample, 0):min(end_sample, len(audio_full))].copy()

            if len(audio) == 0:
                print(f"{YELLOW}  Skipping, audio empty!{RESET}")
                idx += 1
                skipped += 1
                continue

            audio = loudness_normalize(audio)

            if speech_noise_ratio(audio) < args.speech_noise_threshold:
                print(f"{YELLOW}  Skipping, bad speech to noise threshold!{RESET}")
                idx += 1
                skipped += 1
                if not discard_mismatches:
                    write_wav(os.path.join(skipped_path, f"{skipped:06d}_noisy.wav"), audio, sr)
                continue

            if speech_presence(audio) < args.speech_presence_threshold:
                print(f"{YELLOW}  Skipping, contains too many pauses!{RESET}")
                idx += 1
                skipped += 1
                if not discard_mismatches:
                    write_wav(os.path.join(skipped_path, f"{skipped:06d}_pausy.wav"), audio, sr)
                continue

            audio = apply_fades(audio, sr, args.start_fade, args.end_fade)

            segments, info = whisper.transcribe(
                audio,
                language=whisper_lang
            )
            segments = list(segments)
            transcription = " ".join(s.text.strip() for s in segments)
            transcription = normalize_text(transcription)

            dist = levenshtein_distance(subtitle, transcription)

            keeper = True

            s1, s2 = color_diff(subtitle, transcription)

            # Check if first or last word is mismatched
            if not first_last_words_match(subtitle, transcription):
                if discard_mismatches:
                    print(f"{YELLOW}  Discarded, beginning or end is mismatched!{RESET}")
                    skipped += 1
                    keeper = False
                else:
                    mismatches += 1
                    print(f"{YELLOW}  Accepted, but beginning or end is mismatched!{RESET}")
                    # Audio is badly matched to subtitle, add padding to enable fixing manually
                    start_sample -= int(2.0 * sr)
                    end_sample += int(2.0 * sr)
                    audio = audio_full[max(start_sample, 0):min(end_sample, len(audio_full))].copy()
                    audio = loudness_normalize(audio)
                    basename += "_fix_ends"

            # Check if number of contractions are mismatched or if edit distance exceeds threshold
            elif count_contractions(subtitle) != count_contractions(transcription):
                print(f"{YELLOW}  Contractions mismatch, using transcription!{RESET}")
                subtitle = transcription
                    
            elif dist > max_edit_threshold:
                if contains_number(subtitle):
                    print(f"{YELLOW}  Edit distance too high, but detected number(s), keeping subtitle as is!{RESET}")
                else:
                    print(f"{YELLOW}  Edit distance too high, using transcription!{RESET}")
                    subtitle = transcription

            print(f"{BLUE}Edit distance:{RESET} {dist}")
            print(f"{BLUE}Subtitle     :{RESET} {s1}")
            print(f"{BLUE}Transcription:{RESET} {s2}")

            if keeper:
                write_wav(os.path.join(output_path, f"{basename}.wav"), audio, sr)

                with open(csv_file, 'a', encoding="utf8") as output_file:
                    output_file.write(f"{clip_id:06d}|{subtitle}\n")
                clip_id += 1
                accepted += 1

            idx += 1
            
            elapsed = time.time() - start_time
            avg_per_file = elapsed / idx
            remaining = total_subtitles - idx
            eta = remaining * avg_per_file
            print(f"\n{BLUE}Estimated time remaining for this video: {format_time(eta)}{RESET}")
            print(f"{GREEN}Accepted  :{RESET}", accepted)
            if not discard_mismatches:
                print(f"{YELLOW}Mismatches:{RESET}", mismatches)
            print(f"{YELLOW}Skipped   :{RESET}", skipped)

    print(f"\n{BLUE}All done (total time: {format_time(elapsed)})!{RESET}")
    print(f"{GREEN}Accepted  :{RESET}", accepted)
    if not discard_mismatches:
        print(f"{YELLOW}Mismatches:{RESET}", mismatches)
    print(f"{YELLOW}Skipped   :{RESET}", skipped)

    if mismatches > 0 and not discard_mismatches:
        print(f"\n{mismatches} {YELLOW}number of subtitles were mismatched with their transcribed counterpart in a problematic way. You need to fix these manually! Mismatched wav files are located in the '{RESET}{output_path}{YELLOW}' folder. There are two types you need to fix:{RESET}")
        print(f"\n1. Wav files with '_fix_middle' appended: {YELLOW}These files mismatch in the middle of the sentence. Play the audio file and edit the sentence in '{RESET}{csv_file}{YELLOW}' so it matches the audio completely! Then remove the '_fix_middle' appended to the file in the '{RESET}{output_path}{YELLOW}' path.{RESET}")

        print(f"\n2. Wav files with '_fix_beginning' appended: {YELLOW}These files mismatch in the beginning of the sentence. This most often means the subtitle timings were a bit off and a word is missing from the audio at the beginning of the wav file. You need to open this in your preferred audio editor and cut the beginning and end so the spoken audio completely matches the entry in '{RESET}{csv_file}{YELLOW}'. Then save it back to the '{RESET}{output_path}{YELLOW}' folder. Remember to remove the '{RESET}_fix_beginning{YELLOW}' part of the filename after fixing it!{RESET}")

if __name__ == "__main__":
    main()
