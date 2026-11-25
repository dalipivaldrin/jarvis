"""Langzeitgedächtnis: Fakten, Notizen und Gesprächsverlauf als JSON in ~/.jarvis."""
import copy
import json
import threading
from datetime import datetime

from . import config


class Store:
    def __init__(self, name, default):
        self.path = config.DATA_DIR / f"{name}.json"
        self.default = default
        self.lock = threading.Lock()

    def load(self):
        if not self.path.exists():
            return copy.deepcopy(self.default)
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return copy.deepcopy(self.default)

    def save(self, data):
        with self.lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)


facts = Store("facts", [])
notes = Store("notes", [])
history = Store("history", [])


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------- Fakten über den Nutzer ----------
def remember(fact: str) -> str:
    data = facts.load()
    if fact in data:
        return "Das weiss ich bereits."
    data.append(fact)
    facts.save(data)
    return f"Gemerkt: {fact}"


def forget(keyword: str) -> str:
    data = facts.load()
    kept = [f for f in data if keyword.lower() not in f.lower()]
    removed = len(data) - len(kept)
    facts.save(kept)
    return f"{removed} Eintrag/Einträge vergessen." if removed else "Dazu habe ich nichts gespeichert."


def all_facts() -> list:
    return facts.load()


# ---------- Notizen ----------
def add_note(text: str) -> str:
    data = notes.load()
    data.append({"text": text, "created": _now()})
    notes.save(data)
    return f"Notiz Nr. {len(data)} gespeichert."


def list_notes() -> str:
    data = notes.load()
    if not data:
        return "Keine Notizen vorhanden."
    return "\n".join(f"{i}. {n['text']} ({n['created']})" for i, n in enumerate(data, 1))


def delete_note(number: int) -> str:
    data = notes.load()
    if not 1 <= number <= len(data):
        return f"Notiz Nr. {number} gibt es nicht."
    removed = data.pop(number - 1)
    notes.save(data)
    return f"Notiz gelöscht: {removed['text']}"


# ---------- Gesprächsverlauf ----------
def load_history() -> list:
    return history.load()


def save_history(messages: list):
    trimmed = messages[-config.MAX_HISTORY:]
    # Verlauf muss immer mit einer Nutzer-Nachricht beginnen
    while trimmed and trimmed[0]["role"] != "user":
        trimmed.pop(0)
    history.save(trimmed)


def clear_history():
    history.save([])
