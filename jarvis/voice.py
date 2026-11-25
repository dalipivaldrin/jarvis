"""Sprachausgabe (macOS 'say') und Spracherkennung (Mikrofon)."""
import re
import subprocess

from . import config


def clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " Code siehe Bildschirm. ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)      # Markdown-Links
    text = re.sub(r"https?://\S+", "", text)                    # URLs nicht vorlesen
    text = re.sub(r"[*_#`>|]", "", text)                         # Markdown-Zeichen
    return re.sub(r"\s+", " ", text).strip()


def speak(text: str):
    text = clean_for_speech(text)
    if not text:
        return
    r = subprocess.run(["say", "-v", config.VOICE, text], capture_output=True)
    if r.returncode != 0:  # Stimme nicht installiert → Standardstimme
        subprocess.run(["say", text], capture_output=True)


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
        with self.mic as source:
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            except self.sr.WaitTimeoutError:
                return ""
        try:
            return self.recognizer.recognize_google(audio, language=config.LANGUAGE)
        except self.sr.UnknownValueError:
            return ""
        except self.sr.RequestError as e:
            print(f"⚠️  Spracherkennung nicht erreichbar: {e}")
            return ""
