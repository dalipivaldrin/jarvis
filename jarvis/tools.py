"""Werkzeuge, die Jarvis auf dem Mac ausführen kann (Claude Tool Use)."""
import json
import subprocess
import threading
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime

from . import config, memory

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

WEATHER_CODES = {
    0: "klar", 1: "überwiegend klar", 2: "teilweise bewölkt", 3: "bedeckt",
    45: "Nebel", 48: "Reifnebel", 51: "leichter Nieselregen", 53: "Nieselregen",
    55: "starker Nieselregen", 61: "leichter Regen", 63: "Regen", 65: "starker Regen",
    66: "gefrierender Regen", 67: "starker gefrierender Regen", 71: "leichter Schneefall",
    73: "Schneefall", 75: "starker Schneefall", 77: "Schneegriesel", 80: "Regenschauer",
    81: "kräftige Regenschauer", 82: "heftige Regenschauer", 85: "Schneeschauer",
    86: "starke Schneeschauer", 95: "Gewitter", 96: "Gewitter mit Hagel", 99: "starkes Gewitter mit Hagel",
}


# ---------- Hilfsfunktionen ----------
def _esc(text: str) -> str:
    """String sicher in AppleScript einbetten."""
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def _osa(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "AppleScript-Fehler")
    return r.stdout.strip()


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def notify(title: str, message: str, speak: bool = True):
    """macOS-Mitteilung anzeigen und optional vorlesen."""
    try:
        _osa(f'display notification "{_esc(message)}" with title "{_esc(title)}" sound name "Glass"')
    except Exception:
        pass
    print(f"\n🔔 {title}: {message}")
    if speak:
        subprocess.run(["say", "-v", config.VOICE, message], capture_output=True)


# ---------- Mac steuern ----------
def open_app(name: str) -> str:
    r = subprocess.run(["open", "-a", name], capture_output=True, text=True)
    return f"{name} wurde geöffnet." if r.returncode == 0 else f"App '{name}' nicht gefunden."


def quit_app(name: str) -> str:
    _osa(f'tell application "{_esc(name)}" to quit')
    return f"{name} wurde beendet."


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    _osa(f"set volume output volume {level}")
    return f"Lautstärke auf {level} % gesetzt."


def get_volume() -> str:
    return f"Lautstärke: {_osa('output volume of (get volume settings)')} %"


def media_control(action: str, app: str = "Spotify") -> str:
    commands = {"play": "play", "pause": "pause", "toggle": "playpause",
                "next": "next track", "previous": "previous track"}
    if action not in commands:
        return f"Unbekannte Aktion: {action}"
    if action == "play" and app == "Spotify":
        subprocess.run(["open", "-a", "Spotify"], capture_output=True)
    _osa(f'tell application "{_esc(app)}" to {commands[action]}')
    if action in ("next", "previous", "play"):
        try:
            track = _osa(f'tell application "{_esc(app)}" to (name of current track) & " – " & (artist of current track)')
            return f"Läuft jetzt: {track}"
        except Exception:
            pass
    return f"{app}: {action} ausgeführt."


def lock_screen() -> str:
    subprocess.run(["pmset", "displaysleepnow"], capture_output=True)
    return "Bildschirm gesperrt."


def battery_status() -> str:
    out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    lines = [l.strip() for l in out.splitlines() if "%" in l]
    return lines[0] if lines else "Akkustatus nicht verfügbar."


# ---------- Web & Infos ----------
def get_datetime() -> str:
    now = datetime.now()
    return f"{WEEKDAYS[now.weekday()]}, {now.strftime('%d.%m.%Y, %H:%M')} Uhr"


def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"{url} geöffnet."


def search_in_browser(query: str) -> str:
    webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(query))
    return f"Google-Suche nach '{query}' im Browser geöffnet."


def get_weather(city: str = "") -> str:
    city = city or config.CITY
    geo = _get_json("https://geocoding-api.open-meteo.com/v1/search?count=1&language=de&name="
                    + urllib.parse.quote(city))
    if not geo.get("results"):
        return f"Ort '{city}' nicht gefunden."
    place = geo["results"][0]
    data = _get_json(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={place['latitude']}&longitude={place['longitude']}"
        "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
        "&timezone=auto&forecast_days=3"
    )
    cur, daily = data["current"], data["daily"]
    lines = [f"{place['name']} jetzt: {cur['temperature_2m']}°C (gefühlt {cur['apparent_temperature']}°C), "
             f"{WEATHER_CODES.get(cur['weather_code'], 'unbekannt')}, Wind {cur['wind_speed_10m']} km/h."]
    for i, label in enumerate(["Heute", "Morgen", "Übermorgen"]):
        lines.append(f"{label}: {daily['temperature_2m_min'][i]}–{daily['temperature_2m_max'][i]}°C, "
                     f"{WEATHER_CODES.get(daily['weather_code'][i], 'unbekannt')}, "
                     f"Regenrisiko {daily['precipitation_probability_max'][i]}%")
    return "\n".join(lines)


# ---------- Timer & Erinnerungen ----------
_timers = []


def set_timer(seconds: int, message: str = "Dein Timer ist abgelaufen.") -> str:
    seconds = int(seconds)
    if seconds <= 0:
        return "Die Dauer muss positiv sein."
    t = threading.Timer(seconds, notify, args=("Jarvis", message))
    t.daemon = True
    t.start()
    _timers.append(t)
    mins, secs = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    parts = [f"{hrs} h" if hrs else "", f"{mins} min" if mins else "", f"{secs} s" if secs else ""]
    return f"Timer gestellt: {' '.join(p for p in parts if p)} – «{message}»"


def add_apple_reminder(title: str) -> str:
    """Eintrag in der Apple-Erinnerungen-App (synchronisiert aufs iPhone)."""
    _osa(f'tell application "Reminders" to make new reminder with properties {{name:"{_esc(title)}"}}')
    return f"Erinnerung in der Erinnerungen-App erstellt: {title}"


# ---------- Tool-Definitionen für Claude ----------
def _tool(name, description, props=None, required=None):
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": props or {}, "required": required or []}}


TOOL_SCHEMAS = [
    _tool("open_app", "Öffnet eine Mac-App, z.B. 'Safari', 'Spotify', 'Visual Studio Code'.",
          {"name": {"type": "string", "description": "Exakter App-Name"}}, ["name"]),
    _tool("quit_app", "Beendet eine laufende Mac-App.",
          {"name": {"type": "string"}}, ["name"]),
    _tool("set_volume", "Setzt die Systemlautstärke (0–100).",
          {"level": {"type": "integer", "minimum": 0, "maximum": 100}}, ["level"]),
    _tool("get_volume", "Liest die aktuelle Systemlautstärke."),
    _tool("media_control", "Steuert die Musik in Spotify oder Apple Music.",
          {"action": {"type": "string", "enum": ["play", "pause", "toggle", "next", "previous"]},
           "app": {"type": "string", "enum": ["Spotify", "Music"], "default": "Spotify"}}, ["action"]),
    _tool("lock_screen", "Sperrt den Bildschirm / schaltet ihn aus."),
    _tool("battery_status", "Zeigt Akkustand und Ladestatus des MacBooks."),
    _tool("get_datetime", "Aktuelles Datum, Wochentag und Uhrzeit."),
    _tool("open_url", "Öffnet eine Website im Standardbrowser.",
          {"url": {"type": "string"}}, ["url"]),
    _tool("search_in_browser", "Öffnet eine Google-Suche im Browser, wenn der Nutzer selbst Ergebnisse sehen will.",
          {"query": {"type": "string"}}, ["query"]),
    _tool("get_weather", "Aktuelles Wetter und 3-Tage-Prognose. Ohne Ort wird der Wohnort genommen.",
          {"city": {"type": "string"}}),
    _tool("set_timer", "Stellt einen Timer bzw. eine Erinnerung in X Sekunden (Mitteilung + Sprachausgabe).",
          {"seconds": {"type": "integer"}, "message": {"type": "string"}}, ["seconds"]),
    _tool("add_apple_reminder", "Legt einen Eintrag in der Apple-Erinnerungen-App an (To-do ohne Uhrzeit).",
          {"title": {"type": "string"}}, ["title"]),
    _tool("add_note", "Speichert eine Notiz.", {"text": {"type": "string"}}, ["text"]),
    _tool("list_notes", "Listet alle gespeicherten Notizen auf."),
    _tool("delete_note", "Löscht eine Notiz anhand ihrer Nummer.",
          {"number": {"type": "integer"}}, ["number"]),
    _tool("remember_fact", "Speichert dauerhaft einen Fakt über den Nutzer (Vorlieben, Personen, Pläne).",
          {"fact": {"type": "string"}}, ["fact"]),
    _tool("forget_fact", "Löscht gespeicherte Fakten, die ein Stichwort enthalten.",
          {"keyword": {"type": "string"}}, ["keyword"]),
    _tool("clear_conversation", "Löscht den bisherigen Gesprächsverlauf (Neustart des Gesprächs)."),
]

_HANDLERS = {
    "open_app": open_app, "quit_app": quit_app, "set_volume": set_volume, "get_volume": get_volume,
    "media_control": media_control, "lock_screen": lock_screen, "battery_status": battery_status,
    "get_datetime": get_datetime, "open_url": open_url, "search_in_browser": search_in_browser,
    "get_weather": get_weather, "set_timer": set_timer, "add_apple_reminder": add_apple_reminder,
    "add_note": memory.add_note, "list_notes": memory.list_notes, "delete_note": memory.delete_note,
    "remember_fact": memory.remember, "forget_fact": memory.forget,
}


def run_tool(name: str, args: dict) -> str:
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"Unbekanntes Werkzeug: {name}"
    try:
        return str(handler(**(args or {})))
    except Exception as e:  # Fehler an Claude zurückgeben statt abzustürzen
        return f"Fehler bei {name}: {e}"
