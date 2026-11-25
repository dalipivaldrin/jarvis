# 🤖 J.A.R.V.I.S. – Persönlicher KI-Assistent für macOS

*Just A Rather Very Intelligent System* – ein Sprachassistent im Stil von Tony Starks Jarvis, der mit der **Claude API** denkt und den Mac steuert.

> «Jarvis, mach die Musik lauter und sag mir, wie das Wetter morgen wird.»

## Funktionen

| Bereich | Was Jarvis kann |
|---|---|
| 🎙️ **Sprache** | Wake-Word «Jarvis», Spracherkennung (Schweizerdeutsch/Deutsch), Antworten per Sprachausgabe |
| ⌨️ **Text** | Chat im Terminal, falls kein Mikrofon gewünscht |
| 💻 **Mac steuern** | Apps öffnen/beenden, Lautstärke, Spotify/Apple Music, Bildschirm sperren, Akkustand |
| 🌐 **Web & Infos** | Websuche (aktuelle News, Resultate), Wetter (Open-Meteo), Websites öffnen, Datum/Uhrzeit |
| ⏰ **Erinnerungen** | Timer mit Mitteilung und Sprachausgabe, Einträge in der Apple-Erinnerungen-App |
| 📝 **Notizen** | Notizen speichern, auflisten, löschen |
| 🧠 **Gedächtnis** | Merkt sich Fakten über dich und den Gesprächsverlauf – auch nach einem Neustart |

## Architektur

```
Mikrofon ──► Spracherkennung ──► Wake-Word-Filter
                                       │
                                       ▼
                            ┌─────────────────────┐
     Gedächtnis (JSON) ◄──► │  Brain (Claude API) │ ◄──► Websuche
                            └─────────┬───────────┘
                                      │ Tool Use
                                      ▼
                     Mac-Werkzeuge (AppleScript, open, pmset, …)
                                      │
                                      ▼
                         Antwort ──► Sprachausgabe (say)
```

| Datei | Aufgabe |
|---|---|
| `jarvis/brain.py` | Gespräch mit Claude, Tool-Use-Schleife, System-Prompt mit Persönlichkeit |
| `jarvis/tools.py` | Alle Werkzeuge und ihre JSON-Schemas |
| `jarvis/memory.py` | Fakten, Notizen und Verlauf in `~/.jarvis/` |
| `jarvis/voice.py` | Spracherkennung und Sprachausgabe |
| `jarvis/main.py` | Start, Sprach- und Textmodus |

## Installation

Voraussetzungen: macOS, Python 3.10+, [Homebrew](https://brew.sh), ein [Anthropic API-Key](https://console.anthropic.com/settings/keys).

```bash
git clone https://github.com/dalipivaldrin/jarvis.git
cd jarvis
bash setup.sh
open -e .env          # API-Key eintragen
./jarvis.sh           # Sprachmodus
./jarvis.sh --text    # Textmodus
```

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
| `ANTHROPIC_API_KEY` | – | Dein API-Key (Pflicht) |
| `JARVIS_USER_NAME` | `Sir` | Wie Jarvis dich anspricht |
| `JARVIS_CITY` | `Zürich` | Ort für das Wetter |
| `JARVIS_MODEL` | `claude-sonnet-5-5` | Claude-Modell |
| `JARVIS_LANGUAGE` | `de-CH` | Sprache der Spracherkennung |
| `JARVIS_VOICE` | `Anna` | macOS-Stimme (Liste: `say -v '?'`) |
| `JARVIS_WAKE_WORD` | `jarvis` | Aktivierungswort |
| `JARVIS_WEB_SEARCH` | `true` | Websuche über die Claude API |

## Tests

```bash
source .venv/bin/activate
python -m unittest discover tests
```

## Eigene Werkzeuge hinzufügen

1. Funktion in `jarvis/tools.py` schreiben, die einen Text zurückgibt
2. Schema mit `_tool(...)` in `TOOL_SCHEMAS` eintragen
3. Funktion in `_HANDLERS` registrieren

Claude entscheidet danach selbst, wann das Werkzeug benutzt wird.

## Datenschutz

Gedächtnis und Notizen bleiben lokal in `~/.jarvis/`. Gesprochene Befehle werden zur Erkennung an Google Speech und der Text an die Claude API geschickt. Der API-Key steht in `.env` und wird nie hochgeladen.

---
Gebaut von [Valdrin Dalipi](https://github.com/dalipivaldrin) · MIT-Lizenz
