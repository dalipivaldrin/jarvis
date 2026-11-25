"""Das Gehirn: Claude API mit Werkzeugen, Websuche und Gedächtnis."""
import anthropic

from . import config, memory
from .tools import TOOL_SCHEMAS, get_datetime, run_tool

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
MAX_STEPS = 10


class Brain:
    def __init__(self, client=None):
        if client is None and not config.ANTHROPIC_API_KEY:
            raise SystemExit("❌ Kein ANTHROPIC_API_KEY gefunden. Trage ihn in die .env-Datei ein.")
        self.client = client or anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.history = memory.load_history()
        self.web_search = config.WEB_SEARCH

    def _system_prompt(self) -> str:
        facts = memory.all_facts()
        facts_text = "\n".join(f"- {f}" for f in facts) if facts else "(noch nichts gespeichert)"
        return f"""Du bist J.A.R.V.I.S., der persönliche KI-Assistent von {config.USER_NAME}, \
inspiriert von Tony Starks Jarvis: höflich, loyal, effizient, mit trockenem britischem Humor.
Du läufst auf seinem MacBook und kannst es mit deinen Werkzeugen steuern.

Regeln:
- Antworte auf Deutsch (Hochdeutsch), ausser er spricht eine andere Sprache.
- Deine Antworten werden meist VORGELESEN: kurz halten (1–3 Sätze), kein Markdown, keine Listen mit Sternchen, keine Emojis.
- Nutze Werkzeuge, statt zu raten. Bei aktuellen Fakten (News, Preise, Resultate) nutze die Websuche.
- Wenn er dir etwas Persönliches und Dauerhaftes erzählt (Vorlieben, Personen, Termine), speichere es mit remember_fact.
- Für Erinnerungen «in X Minuten» nutze set_timer und rechne die Zeit in Sekunden um.
- Sprich ihn mit «{config.USER_NAME}» an, aber nicht in jedem Satz.

Wohnort: {config.CITY}
Jetzt: {get_datetime()}

Was du über {config.USER_NAME} weisst:
{facts_text}"""

    def _tools(self):
        return TOOL_SCHEMAS + ([WEB_SEARCH_TOOL] if self.web_search else [])

    def _create(self, messages):
        try:
            return self.client.messages.create(
                model=config.MODEL, max_tokens=1024, system=self._system_prompt(),
                tools=self._tools(), messages=messages,
            )
        except anthropic.BadRequestError as e:
            if self.web_search and "web_search" in str(e):
                self.web_search = False  # Websuche im Account nicht aktiviert → ohne weiter
                return self._create(messages)
            raise

    def ask(self, text: str, on_tool=None) -> str:
        if not text.strip():
            return ""
        messages = list(self.history) + [{"role": "user", "content": text}]
        reset = False
        response = None

        for _ in range(MAX_STEPS):
            response = self._create(messages)
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "pause_turn":  # lange Websuche → einfach weitermachen
                continue
            if response.stop_reason != "tool_use":
                break

            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if on_tool:
                    on_tool(block.name, block.input)
                if block.name == "clear_conversation":
                    reset = True
                    output = "Gesprächsverlauf wird gelöscht."
                else:
                    output = run_tool(block.name, block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
            messages.append({"role": "user", "content": results})

        answer = "".join(b.text for b in response.content if b.type == "text").strip() if response else ""
        answer = answer or "Erledigt."

        if reset:
            self.history = []
            memory.clear_history()
        else:
            # Nur den reinen Text speichern – hält den Verlauf klein und gültig
            self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": answer}]
            self.history = self.history[-config.MAX_HISTORY:]
            memory.save_history(self.history)
        return answer
