"""Das Gehirn: wahlweise Ollama (lokal, gratis) oder Claude API – beide mit Werkzeugen und Gedächtnis."""
import json
import re
import urllib.error
import urllib.request

from . import config, memory
from .tools import TOOL_SCHEMAS, get_datetime, run_tool

MAX_STEPS = 10
_SENTENCE_END = re.compile(r"[.!?…:;](?=\s)|\n")


def _strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return text.split("<think>")[0]  # unvollständiger Denk-Block → noch nichts sprechen


def _emit_sentences(content: str, spoken: int, on_sentence, final: bool) -> int:
    """Gibt alle neuen, abgeschlossenen Sätze aus. Rückgabe: wie viele Zeichen bereits gesprochen sind."""
    clean = _strip_think(content)
    rest = clean[spoken:]
    last_end = 0
    for m in _SENTENCE_END.finditer(rest):
        last_end = m.end()
    if final:
        last_end = len(rest)
    chunk = rest[:last_end].strip()
    if chunk and len(chunk) > 1:
        on_sentence(chunk)
    return spoken + last_end


class JarvisError(Exception):
    """Verständliche Fehlermeldung, die Jarvis vorlesen kann."""


class Brain:
    """Gemeinsame Logik: Persönlichkeit, Gedächtnis, Verlauf."""

    web_search = False
    streams = False  # kann Sätze schon während der Generierung ausgeben

    def warmup(self):
        """Optional: Modell vorladen (nur bei Ollama nötig)."""

    def __init__(self):
        self.history = memory.load_history()

    def system_prompt(self) -> str:
        facts = memory.all_facts()
        facts_text = "\n".join(f"- {f}" for f in facts) if facts else "(noch nichts gespeichert)"
        search_rule = ("Bei aktuellen Fakten (News, Preise, Resultate) nutze die Websuche."
                       if self.web_search else
                       "Du hast keinen Internetzugriff. Bei aktuellen Fakten sag das ehrlich und biete search_in_browser an.")
        return f"""Du bist J.A.R.V.I.S., der persönliche KI-Assistent von {config.USER_NAME}, \
inspiriert von Tony Starks Jarvis: höflich, loyal, effizient, mit trockenem britischem Humor.
Du läufst auf seinem MacBook und kannst es mit deinen Werkzeugen steuern.

Regeln:
- Antworte immer auf Deutsch (Hochdeutsch), ausser er spricht eine andere Sprache.
- Deine Antworten werden meist VORGELESEN: kurz halten (1–3 Sätze), kein Markdown, keine Listen mit Sternchen, keine Emojis.
- Nutze Werkzeuge, statt zu raten. Rufe Werkzeuge nur auf, wenn sie wirklich nötig sind.
- {search_rule}
- Wenn er dir etwas Persönliches und Dauerhaftes erzählt (Vorlieben, Personen, Termine), speichere es mit remember_fact.
- Für Erinnerungen «in X Minuten» nutze set_timer und rechne die Zeit in Sekunden um.
- Will er etwas aufs Handy («schick mir», «per Nachricht», «aufs iPhone»), nutze send_imessage bzw. set_timer mit imessage=true.
- Sprich ihn mit «{config.USER_NAME}» an, aber nicht in jedem Satz.

Wohnort: {config.CITY}
(Datum und Uhrzeit stehen in eckigen Klammern vor seiner Nachricht.)

Was du über {config.USER_NAME} weisst:
{facts_text}"""

    def _execute(self, name, args, on_tool):
        """Führt ein Werkzeug aus. Gibt (Ergebnis, reset) zurück."""
        if on_tool:
            on_tool(name, args)
        if name == "clear_conversation":
            return "Gesprächsverlauf wird gelöscht.", True
        return run_tool(name, args), False

    def _run(self, messages, on_tool, on_sentence=None):  # pragma: no cover – in Unterklassen
        raise NotImplementedError

    def ask(self, text: str, on_tool=None, on_sentence=None) -> str:
        """on_sentence(satz) wird – falls unterstützt – für jeden fertigen Satz sofort aufgerufen."""
        if not text.strip():
            return ""
        now = {"role": "user", "content": f"[{get_datetime()}] {text}"}
        messages = [dict(m) for m in self.history] + [now]
        answer, reset = self._run(messages, on_tool, on_sentence)
        answer = answer.strip() or "Erledigt."

        if reset:
            self.history = []
            memory.clear_history()
        else:
            # Nur den reinen Text speichern – hält den Verlauf klein und gültig
            self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": answer}]
            self.history = self.history[-config.MAX_HISTORY:]
            memory.save_history(self.history)
        return answer


# ---------------------------------------------------------------- Ollama (gratis)
class OllamaBrain(Brain):
    """Lokales Modell über Ollama – kostenlos, offline, kein API-Key."""

    def __init__(self, post=None, post_stream=None):
        super().__init__()
        self.post = post or self._http_post
        # Streaming nur mit echtem Server oder explizit übergebener Test-Funktion
        self.post_stream = post_stream or (None if post else self._http_stream)
        self.streams = self.post_stream is not None
        self.think_supported = True
        self.tools = [{"type": "function",
                       "function": {"name": t["name"], "description": t["description"],
                                    "parameters": t["input_schema"]}}
                      for t in TOOL_SCHEMAS]

    @staticmethod
    def _http_post(path, body):
        req = urllib.request.Request(
            config.OLLAMA_URL.rstrip("/") + path, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")
            if e.code == 404 and "not found" in detail:
                raise JarvisError(f"Das Modell {config.OLLAMA_MODEL} fehlt. "
                                  f"Bitte im Terminal 'ollama pull {config.OLLAMA_MODEL}' ausführen.")
            raise JarvisError(f"Ollama-Fehler {e.code}: {detail[:200]}")
        except urllib.error.URLError:
            raise JarvisError("Ollama läuft nicht. Bitte die Ollama-App öffnen.")

    @staticmethod
    def _http_stream(path, body):
        """Liefert die Antwort Stück für Stück (eine JSON-Zeile pro Token-Gruppe)."""
        req = urllib.request.Request(
            config.OLLAMA_URL.rstrip("/") + path, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                for line in resp:
                    if line.strip():
                        data = json.loads(line.decode("utf-8"))
                        if "error" in data:
                            raise JarvisError(f"Ollama-Fehler: {data['error']}")
                        yield data
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")
            if e.code == 404 and "not found" in detail:
                raise JarvisError(f"Das Modell {config.OLLAMA_MODEL} fehlt. "
                                  f"Bitte im Terminal 'ollama pull {config.OLLAMA_MODEL}' ausführen.")
            raise JarvisError(f"Ollama-Fehler {e.code}: {detail[:200]}")
        except urllib.error.URLError:
            raise JarvisError("Ollama läuft nicht. Bitte die Ollama-App öffnen.")

    def _body(self, messages, stream):
        body = {"model": config.OLLAMA_MODEL, "messages": messages, "tools": self.tools,
                "stream": stream, "keep_alive": config.OLLAMA_KEEP_ALIVE,
                "options": {"temperature": 0.6, "num_ctx": config.OLLAMA_CONTEXT, "num_predict": 300}}
        if self.think_supported:
            body["think"] = False  # schneller: kein langes «Nachdenken» vor der Antwort
        return body

    def _chat_streaming(self, messages, on_sentence):
        """Streamt die Antwort und gibt jeden fertigen Satz sofort an on_sentence weiter."""
        content, tool_calls, spoken = "", [], 0
        try:
            for data in self.post_stream("/api/chat", self._body(messages, True)):
                msg = data.get("message") or {}
                if msg.get("tool_calls"):
                    tool_calls.extend(msg["tool_calls"])
                content += msg.get("content") or ""
                if not tool_calls:
                    spoken = _emit_sentences(content, spoken, on_sentence, final=False)
                if data.get("done"):
                    break
        except JarvisError as e:
            if self.think_supported and "think" in str(e).lower() and not content:
                self.think_supported = False
                return self._chat_streaming(messages, on_sentence)
            raise
        if not tool_calls:
            _emit_sentences(content, spoken, on_sentence, final=True)
        return {"role": "assistant", "content": content, "tool_calls": tool_calls}

    def _chat(self, messages):
        try:
            return self.post("/api/chat", self._body(messages, False))
        except JarvisError as e:
            if self.think_supported and "think" in str(e).lower():
                self.think_supported = False
                return self._chat(messages)
            raise

    def warmup(self):
        """Lädt das Modell beim Start schon in den Speicher – die erste Antwort kommt dann viel schneller."""
        try:
            body_messages = [{"role": "system", "content": self.system_prompt()}, {"role": "user", "content": "Hallo"}]
            body = {"model": config.OLLAMA_MODEL, "messages": body_messages, "tools": self.tools,
                    "stream": False, "keep_alive": config.OLLAMA_KEEP_ALIVE,
                    "options": {"num_ctx": config.OLLAMA_CONTEXT, "num_predict": 1}}
            if self.think_supported:
                body["think"] = False
            self.post("/api/chat", body)
        except Exception:
            pass  # Aufwärmen ist optional

    def _run(self, messages, on_tool, on_sentence=None):
        messages = [{"role": "system", "content": self.system_prompt()}] + messages
        reset, content = False, ""
        for _ in range(MAX_STEPS):
            if on_sentence and self.post_stream:
                msg = self._chat_streaming(messages, on_sentence)
            else:
                msg = self._chat(messages)["message"]
            messages.append(msg)
            content = re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S)
            calls = msg.get("tool_calls") or []
            if not calls:
                break
            for call in calls:
                fn = call.get("function", {})
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                output, r = self._execute(fn.get("name", ""), args, on_tool)
                reset = reset or r
                messages.append({"role": "tool", "content": output, "tool_name": fn.get("name", "")})
        return content, reset


# ---------------------------------------------------------------- Claude (API-Key nötig)
class ClaudeBrain(Brain):
    WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}

    def __init__(self, client=None):
        super().__init__()
        import anthropic

        self.anthropic = anthropic
        key = config.ANTHROPIC_API_KEY
        if client is None and (not key or key.startswith("sk-ant-...")):
            raise SystemExit("❌ Kein ANTHROPIC_API_KEY in der .env – oder JARVIS_PROVIDER=ollama setzen.")
        self.client = client or anthropic.Anthropic(api_key=key)
        self.web_search = config.WEB_SEARCH

    def _create(self, messages):
        tools = TOOL_SCHEMAS + ([self.WEB_SEARCH_TOOL] if self.web_search else [])
        try:
            return self.client.messages.create(model=config.MODEL, max_tokens=1024,
                                               system=self.system_prompt(), tools=tools, messages=messages)
        except self.anthropic.BadRequestError as e:
            if self.web_search and "web_search" in str(e):
                self.web_search = False  # Websuche im Account nicht aktiviert → ohne weiter
                return self._create(messages)
            raise JarvisError(f"Claude-Fehler: {e}")
        except self.anthropic.AuthenticationError:
            raise JarvisError("Mein API-Schlüssel ist ungültig. Bitte prüfe die .env-Datei.")
        except self.anthropic.APIConnectionError:
            raise JarvisError("Ich habe gerade keine Verbindung zum Internet.")
        except self.anthropic.APIError as e:
            raise JarvisError(f"Da ist etwas schiefgelaufen: {getattr(e, 'message', e)}")

    def _run(self, messages, on_tool, on_sentence=None):
        reset, response = False, None
        for _ in range(MAX_STEPS):
            response = self._create(messages)
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason == "pause_turn":  # lange Websuche → weitermachen
                continue
            if response.stop_reason != "tool_use":
                break
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output, r = self._execute(block.name, block.input, on_tool)
                    reset = reset or r
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
            messages.append({"role": "user", "content": results})
        text = "".join(b.text for b in response.content if b.type == "text") if response else ""
        return text, reset


def create_brain() -> Brain:
    if config.PROVIDER == "claude":
        return ClaudeBrain()
    return OllamaBrain()
