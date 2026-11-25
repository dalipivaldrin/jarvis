"""Zentrale Einstellungen – werden aus der .env-Datei geladen."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# KI-Gehirn: "ollama" (gratis, lokal) oder "claude" (API-Key mit Guthaben nötig)
PROVIDER = os.getenv("JARVIS_PROVIDER", "ollama").strip().lower()

OLLAMA_MODEL = os.getenv("JARVIS_OLLAMA_MODEL", "qwen3:8b")
OLLAMA_URL = os.getenv("JARVIS_OLLAMA_URL", "http://localhost:11434")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL = os.getenv("JARVIS_MODEL", "claude-sonnet-5-5")

USER_NAME = os.getenv("JARVIS_USER_NAME", "Sir")
CITY = os.getenv("JARVIS_CITY", "Zürich")

LANGUAGE = os.getenv("JARVIS_LANGUAGE", "de-CH")   # Spracherkennung
VOICE = os.getenv("JARVIS_VOICE", "Anna")          # macOS-Stimme (say -v '?'), auch Ersatz ohne Internet

# Sprachausgabe: "edge" (menschliche Neural-Stimme, gratis, Internet nötig) oder "mac" (offline)
TTS = os.getenv("JARVIS_TTS", "edge").strip().lower()
EDGE_VOICE = os.getenv("JARVIS_EDGE_VOICE", "de-CH-JanNeural")
EDGE_RATE = os.getenv("JARVIS_EDGE_RATE", "+0%")    # Tempo, z.B. +10% oder -10%
EDGE_PITCH = os.getenv("JARVIS_EDGE_PITCH", "+0Hz")  # Tonhöhe, z.B. -5Hz für tiefer
WAKE_WORD = os.getenv("JARVIS_WAKE_WORD", "jarvis").lower()

WEB_SEARCH = os.getenv("JARVIS_WEB_SEARCH", "true").lower() == "true"
MAX_HISTORY = int(os.getenv("JARVIS_MAX_HISTORY", "20"))  # Nachrichten im Kurzzeitgedächtnis

DATA_DIR = Path(os.getenv("JARVIS_DATA_DIR", str(Path.home() / ".jarvis"))).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)
