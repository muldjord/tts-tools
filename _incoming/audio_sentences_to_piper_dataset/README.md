# Audio sentences to Piper TTS dataset
This script takes audio sentence files, transcribes them, and exports them back to disk in the Piper TTS dataset format of `metadata.csv` and a `wav` folder.

## Pre-requisites
The script uses `ffmpeg` for audio conversion. On Debian-derived Linux distros you can install it with:
```
$ sudo apt install ffmpeg
```

The script also uses the Whisper speech-to-text engine for audio transcription. You must create a Python3 venv and install the packages required.
```
$ python3 -m venv _venv
$ source _venv/bin/activate
$ pip install faster_whisper
```

## Commandline parameters
There are no command-line parameters! The parameters are hardcoded. You just run it and it will work as follows:
1. It will look for audio sentences in an `originals` folder. Please make sure they are wav files!
2. It will create a `metadata.csv` file in the same folder it is run from.
3. It will create a `wav` folder with all processed wav files that are references in the `metadata.csv` file.