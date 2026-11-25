# 🤖 J.A.R.V.I.S. – Persönlicher KI-Assistent für macOS

*Just A Rather Very Intelligent System* – ein Sprachassistent im Stil von Tony Starks Jarvis, der den Mac steuert. Als Gehirn dient wahlweise **Ollama** (gratis, lokal, offline) oder die **Claude API**.

> «Jarvis, mach die Musik lauter und sag mir, wie das Wetter morgen wird.»

## Funktionen

| Bereich | Was Jarvis kann |
|---|---|
| 🎙️ **Sprache** | Wake-Word «Jarvis», Spracherkennung (Schweizerdeutsch/Deutsch), menschlich klingende Neural-Stimme (Microsoft Edge TTS, gratis) |
| ⌨️ **Text** | Chat im Terminal, falls kein Mikrofon gewünscht |
| 💻 **Mac steuern** | Apps öffnen/beenden, Lautstärke, Spotify/Apple Music, Bildschirm sperren, Akkustand |
| 🧠 **Zwei Gehirne** | Ollama (kostenlos, privat, offline) oder Claude API (stärker, mit Websuche) |
| 🌐 **Web & Infos** | Websuche (nur Claude), Wetter (Open-Meteo), Websites öffnen, Datum/Uhrzeit |
| ⏰ **Erinnerungen** | Timer mit Mitteilung und Sprachausgabe, Einträge in der Apple-Erinnerungen-App |
| 📝 **Notizen** | Notizen speichern, auflisten, löschen |
| 🧠 **Gedächtnis** | Merkt sich Fakten über dich und den Gesprächsverlauf – auch nach einem Neustart |

## Architektur

```
Mikrofon ──► Spracherkennung ──► Wake-Word-Filter
                                       │
                                       ▼
                            ┌─────────────────────┐
     Gedächtnis (JSON) ◄──► │ Brain: Ollama/Claude│ ◄──► Websuche
                            └─────────┬───────────┘
                                      │ Tool Use
                                      ▼
                     Mac-Werkzeuge (AppleScript, open, pmset, …)
                                      │
                                      ▼
                         Antwort ──► Neural-Stimme (edge-tts) / say
```

| Datei | Aufgabe |
|---|---|
| `jarvis/brain.py` | Ollama- und Claude-Gehirn, Tool-Use-Schleife, System-Prompt mit Persönlichkeit |
| `jarvis/tools.py` | Alle Werkzeuge und ihre JSON-Schemas |
| `jarvis/memory.py` | Fakten, Notizen und Verlauf in `~/.jarvis/` |
| `jarvis/voice.py` | Spracherkennung und Sprachausgabe |
| `jarvis/main.py` | Start, Sprach- und Textmodus |
| `jarvis/gui.py` + `jarvis/ui/index.html` | HUD-Fenster (pywebview + animiertes Canvas) |
| `install_app.sh` | Baut die macOS-App mit Symbol und Mikrofon-Berechtigung |

## Installation

Voraussetzungen: macOS, Python 3.10+, [Homebrew](https://brew.sh) und [Ollama](https://ollama.com/download/mac) (gratis).

```bash
git clone https://github.com/dalipivaldrin/jarvis.git
cd jarvis
bash setup.sh
```

Dann starten – im Textmodus oder mit Sprache:

```bash
./jarvis.sh --text
./jarvis.sh
```

Namen und Wohnort passt du in der Datei `.env` an (`open -e .env`).

### Als App mit futuristischem HUD starten

![Jarvis HUD](assets/screenshot.png)

```bash
bash install_app.sh              # erstellt ~/Applications/Jarvis.app mit HUD-Fenster und eigenem Symbol
bash install_app.sh --autostart  # zusätzlich: startet bei jeder Anmeldung
bash install_app.sh --terminal   # alternativ: App startet Jarvis im Terminal
```

Danach Jarvis per Spotlight (Cmd+Leertaste → «Jarvis») oder über das Dock starten.
Das HUD reagiert live: Ringe und Strahlen pulsieren mit deiner Stimme (Mikrofonpegel) und
synchron zu Jarvis' Wörtern (Wortgrenzen der Neural-Stimme). Farben zeigen den Zustand:
Cyan = bereit/spricht, Bernstein = verarbeitet, Rot = Fehler.

Direkt aus dem Terminal: `./jarvis.sh --gui`

### Optional: Claude statt Ollama

Für stärkere Antworten und Websuche in `.env` setzen: `JARVIS_PROVIDER=claude` und einen
[Anthropic API-Key](https://console.anthropic.com/settings/keys) (Guthaben nötig) bei `ANTHROPIC_API_KEY` eintragen.

Beim ersten Start fragt macOS nach dem Mikrofonzugriff für das Terminal – bitte erlauben.
Für die Musik- und Erinnerungen-Steuerung fragt macOS ebenfalls einmal nach Erlaubnis.

## Beispiele

- «Jarvis, öffne Visual Studio Code»
- «Jarvis, stell die Lautstärke auf 30»
- «Jarvis, nächster Song»
- «Jarvis, wie wird das Wetter morgen in Zürich?»
- «Jarvis, erinnere mich in 20 Minuten an die Wäsche»
- «Jarvis, notiere: Präsentation für Montag vorbereiten»
- «Jarvis, merk dir, dass ich am liebsten Hip-Hop höre»
- «Jarvis, was gibt es Neues in der Schweiz?»
- «Jarvis, tschüss»

## Einstellungen (`.env`)

| Variable | Standard | Beschreibung |
|---|---|---|
| `JARVIS_USER_NAME` | `Sir` | Wie Jarvis dich anspricht |
| `JARVIS_CITY` | `Zürich` | Ort für das Wetter |
| `JARVIS_PROVIDER` | `ollama` | `ollama` (gratis) oder `claude` |
| `JARVIS_OLLAMA_MODEL` | `qwen3:8b` | Ollama-Modell (muss Tool-Calling können); schneller: `qwen3:4b` |
| `JARVIS_OLLAMA_KEEP_ALIVE` | `60m` | So lange bleibt das Modell geladen (schnelle Antworten) |
| `ANTHROPIC_API_KEY` | – | Nur für Claude |
| `JARVIS_MODEL` | `claude-sonnet-5-5` | Claude-Modell |
| `JARVIS_LANGUAGE` | `de-CH` | Sprache der Spracherkennung |
| `JARVIS_TTS` | `edge` | `edge` (menschliche Neural-Stimme, Internet) oder `mac` (offline) |
| `JARVIS_EDGE_VOICE` | `de-CH-JanNeural` | Neural-Stimme, z.B. `de-DE-ConradNeural`, `de-DE-KillianNeural`, `de-CH-LeniNeural` |
| `JARVIS_EDGE_RATE` | `+0%` | Sprechtempo, z.B. `+10%` |
| `JARVIS_VOICE` | `Anna` | macOS-Stimme als Ersatz ohne Internet (Liste: `say -v '?'`) |
| `JARVIS_WAKE_WORD` | `jarvis` | Aktivierungswort |
| `JARVIS_WEB_SEARCH` | `true` | Websuche (nur Claude) |

## Tests

```bash
source .venv/bin/activate
python -m unittest discover tests
```

## Eigene Werkzeuge hinzufügen

1. Funktion in `jarvis/tools.py` schreiben, die einen Text zurückgibt
2. Schema mit `_tool(...)` in `TOOL_SCHEMAS` eintragen
3. Funktion in `_HANDLERS` registrieren

Das Gehirn entscheidet danach selbst, wann das Werkzeug benutzt wird.

## Datenschutz

Gedächtnis und Notizen bleiben lokal in `~/.jarvis/`. Mit Ollama bleibt das Denken komplett auf deinem Mac. Gesprochene Befehle werden zur Erkennung an Google Speech geschickt; mit Claude geht der Text zusätzlich an die Claude API. Die `.env` mit Schlüsseln wird nie hochgeladen.

---
Gebaut von [Valdrin Dalipi](https://github.com/dalipivaldrin) · MIT-Lizenz
