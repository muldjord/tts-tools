# Video and subtitle to piper dataset
This tool can extract a dataset from videos paired with srt files. It is somewhat "smart" in the way it approaches this:
* It will link subtitles together by looking for a capital letter and keep concatenating subtitles until it reaches a sentence-ending character such as `.`, `!` or `?`.
* It will then extract the audio matching the timestamp of the concatenated subtitles.
* It then runs speech-to-text on the audio and compares it to the subtitle. If it matches it keeps the subtitle. If it does not match, it will determine whether the speech-to-text version of the subtitle is better and use that instead. It might also discard the subtitle if the difference is too high (judged by edit distance).

For the tool to work please ensure:
1. Videos must be paired with an srt file named exactly the same as the video file but with the `.srt` extension. For instance, if you have a video file called `my_video.mkv` then the subtitle need to be placed in the same directory and be called `my_video.srt`.
2. It can process several videos in one go. For instance, if you have an entire season of a documentary. Just run it with `*.mkv` if your videos are `mkv` files.
3. It will produce a Piper TTS compatible dataset of `metadata.csv` and wav files in a `wav` folder that can be used directly for training a Piper TTS voice.