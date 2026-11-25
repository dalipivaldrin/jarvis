"""Sprachausgabe (Microsoft-Neural-Stimme oder macOS 'say') und Spracherkennung (Mikrofon)."""
import asyncio
import os
import re
import subprocess
import tempfile

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


def _speak_edge(text: str) -> bool:
    """Menschlich klingende Neural-Stimme von Microsoft (gratis, braucht Internet)."""
    import edge_tts

    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        communicate = edge_tts.Communicate(text, config.EDGE_VOICE, rate=config.EDGE_RATE, pitch=config.EDGE_PITCH)
        asyncio.run(communicate.save(path))
        if os.path.getsize(path) == 0:
            return False
        return subprocess.run(["afplay", path], capture_output=True).returncode == 0
    finally:
        os.remove(path)


def _speak_mac(text: str):
    r = subprocess.run(["say", "-v", config.VOICE, text], capture_output=True)
    if r.returncode != 0:  # Stimme nicht installiert → Standardstimme
        subprocess.run(["say", text], capture_output=True)


def speak(text: str):
    global _edge_failed
    text = clean_for_speech(text)
    if not text:
        return
    if config.TTS == "edge":
        try:
            if _speak_edge(text):
                return
        except Exception as e:  # kein Internet, Dienst gestört, Paket fehlt …
            if not _edge_failed:
                print(f"⚠️  Neural-Stimme nicht verfügbar ({type(e).__name__}) – nutze Mac-Stimme.")
            _edge_failed = True
    _speak_mac(text)


class Listener:
    """Hört übers Mikrofon zu und wandelt Sprache in Text um (Google Speech, gratis)."""

    def __init__(self):
        import speech_recognition as sr  # erst hier importieren, damit Textmodus ohne Mikrofon läuft

        self.sr = sr
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        self.mic = sr.Microphone()
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)

    def listen(self, timeout=None, phrase_limit=15) -> str:
        try:
            with self.mic as source:
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
