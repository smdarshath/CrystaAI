"""Backend (OS-level) speech: text-to-speech through the operating system's own engine, and optional offline
speech-to-text through Vosk. Both report honestly when unavailable. Browser speech is handled in the web UI."""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import threading
from pathlib import Path

from ..errors import ToolUnavailable

SYS = platform.system()
_proc = None
_lock = threading.Lock()


def tts_engine():
    if SYS == "Darwin" and shutil.which("say"):
        return "say"
    if SYS == "Windows" and shutil.which("powershell"):
        return "powershell"
    for e in ("espeak-ng", "espeak", "spd-say"):
        if shutil.which(e):
            return e
    return None


def _clean(text):
    return re.sub(r"[`*_#\[\]]|https?://\S+", " ", text)[:800].strip()


def speak(text, lang="en", rate=1.0):
    global _proc
    eng = tts_engine()
    if not eng:
        raise ToolUnavailable("No operating-system speech engine found. On Linux install one: sudo apt install espeak-ng")
    text, lang2 = _clean(text), (lang or "en").split("-")[0]
    if not text:
        return {"ok": False, "message": "Nothing to say."}
    wpm = str(int(160 * max(.5, min(2, rate))))
    if eng in ("espeak-ng", "espeak"):
        argv = [eng, "-v", lang2, "-s", wpm, "--", text]
    elif eng == "spd-say":
        argv = ["spd-say", "-l", lang2, "-r", str(int((rate - 1) * 100)), "--", text]
    elif eng == "say":
        argv = ["say", "-r", wpm, text]
    else:
        safe = text.replace("'", "''")
        argv = ["powershell", "-NoProfile", "-Command", f"Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate={int((rate - 1) * 5)}; $s.Speak('{safe}')"]
    stop()
    with _lock:
        _proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "engine": eng, "message": f"Speaking with {eng}."}


def stop():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            _proc.terminate()
        _proc = None


def stt_status(models_dir):
    try:
        import vosk  # noqa: F401
        import sounddevice  # noqa: F401
    except Exception:
        return {"available": False, "reason": "Offline speech-to-text needs: pip install vosk sounddevice, plus a model folder in models/ (e.g. vosk-model-small-en-in-0.4)."}
    models = [d for d in Path(models_dir).glob("vosk-model*") if d.is_dir()]
    if not models:
        return {"available": False, "reason": "Vosk is installed but no model folder named vosk-model* was found in models/."}
    return {"available": True, "model": models[0].name}


def listen_once(models_dir, seconds=6):
    st = stt_status(models_dir)
    if not st["available"]:
        raise ToolUnavailable(st["reason"])
    import json
    import queue
    import sounddevice as sd
    import vosk
    model = vosk.Model(str(next(Path(models_dir).glob("vosk-model*"))))
    rec, q = vosk.KaldiRecognizer(model, 16000), queue.Queue()
    with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype="int16", channels=1, callback=lambda d, f, t, s: q.put(bytes(d))):
        for _ in range(int(seconds * 4)):
            rec.AcceptWaveform(q.get())
    return {"text": json.loads(rec.FinalResult()).get("text", ""), "engine": "vosk"}
