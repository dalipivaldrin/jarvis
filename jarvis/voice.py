"""Sprachausgabe (Microsoft-Neural-Stimme oder macOS 'say') und Spracherkennung (Mikrofon).

Beide Richtungen können einen Lautstärke-Pegel (0..1) melden – damit pulsiert das HUD.
"""
import asyncio
import math
import os
import random
import re
import subprocess
import tempfile
import threading
import time

from . import config

_edge_failed = False  # nach einem Fehler nur einmal warnen


class MicrophoneError(Exception):
    """Mikrofon blockiert oder nicht verfügbar."""


def clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " Code siehe Bildschirm. ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)      # Markdown-Links
    text = re.sub(r"https?://\S+", "", text)                    # URLs nicht vorlesen
    text = re.sub(r"[*_#`>|]", "", text)                         # Markdown-Zeichen
    return re.sub(r"\s+", " ", text).strip()


def word_level(t: float, words) -> float:
    """Pegel zum Zeitpunkt t (Sekunden), abgeleitet aus Wortgrenzen [(start, dauer), ...]."""
    for start, dur in words:
        if start <= t <= start + dur:
            phase = (t - start) / max(dur, 0.05)
            return 0.55 + 0.45 * math.sin(math.pi * phase)  # Wort an- und abschwellen lassen
    return 0.08


def _play(path_or_cmd, on_level=None, words=None):
    """Spielt Audio ab und meldet währenddessen den Pegel ans HUD."""
    proc = subprocess.Popen(path_or_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if on_level:
        start = time.time()
        while proc.poll() is None:
            t = time.time() - start
            level = word_level(t, words) if words else 0.35 + random.random() * 0.55
            on_level(level)
            time.sleep(1 / 30)
        on_level(0)
    return proc.wait() == 0


def _speak_edge(text: str, on_level=None) -> bool:
    """Menschlich klingende Neural-Stimme von Microsoft (gratis, braucht Internet)."""
    import edge_tts

    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    words = []

    async def synth():
        communicate = edge_tts.Communicate(text, config.EDGE_VOICE, rate=config.EDGE_RATE,
                                           pitch=config.EDGE_PITCH, boundary="WordBoundary")
        with open(path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":  # Zeiten in 100-ns-Einheiten
                    words.append((chunk["offset"] / 1e7, chunk["duration"] / 1e7))

    try:
        asyncio.run(synth())
        if os.path.getsize(path) == 0:
            return False
        return _play(["afplay", path], on_level, words)
    finally:
        os.remove(path)


def _speak_mac(text: str, on_level=None):
    if not _play(["say", "-v", config.VOICE, text], on_level):  # Stimme fehlt → Standardstimme
        _play(["say", text], on_level)


def speak(text: str, on_level=None):
    global _edge_failed
    text = clean_for_speech(text)
    if not text:
        return
    if config.TTS == "edge":
        try:
            if _speak_edge(text, on_level):
                return
        except Exception as e:  # kein Internet, Dienst gestört, Paket fehlt …
            if not _edge_failed:
                print(f"⚠️  Neural-Stimme nicht verfügbar ({type(e).__name__}) – nutze Mac-Stimme.")
            _edge_failed = True
    _speak_mac(text, on_level)


def rms_level(data: bytes, sample_width: int = 2) -> float:
    """Lautstärke eines Audio-Blocks als Wert 0..1."""
    if not data:
        return 0.0
    try:
        import audioop  # Python ≤3.12 eingebaut, ab 3.13 über audioop-lts
        rms = audioop.rms(data, sample_width)
    except ImportError:
        import array
        samples = array.array("h", data[: len(data) // 2 * 2])
        rms = math.sqrt(sum(s * s for s in samples) / max(len(samples), 1))
    return min(1.0, (rms / 32768) * 12)


class Listener:
    """Hört übers Mikrofon zu und wandelt Sprache in Text um (Google Speech, gratis)."""

    def __init__(self, on_level=None):
        import speech_recognition as sr  # erst hier importieren, damit Textmodus ohne Mikrofon läuft

        self.sr = sr
        self.on_level = on_level
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        self.mic = sr.Microphone()
        try:
            with self.mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except (AttributeError, AssertionError, OSError) as e:
            raise MicrophoneError(str(e))

    def _tap(self, source):
        """Liest beim Zuhören den Pegel mit, ohne die Erkennung zu stören."""
        if not self.on_level or source.stream is None:
            return
        original = source.stream.read
        width = getattr(source, "SAMPLE_WIDTH", 2)

        def read(size):
            data = original(size)
            self.on_level(rms_level(data, width))
            return data

        source.stream.read = read

    def listen(self, timeout=None, phrase_limit=15) -> str:
        try:
            with self.mic as source:
                self._tap(source)
                try:
                    audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
                except self.sr.WaitTimeoutError:
                    return ""
        except (AttributeError, AssertionError, OSError) as e:
            raise MicrophoneError(str(e))
        try:
            return self.recognizer.recognize_google(audio, language=config.LANGUAGE)
        except self.sr.UnknownValueError:
            return ""
        except self.sr.RequestError as e:
            print(f"⚠️  Spracherkennung nicht erreichbar: {e}")
            return ""
