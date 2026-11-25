"""Futuristisches HUD-Fenster für Jarvis (pywebview = natives macOS-Fenster mit WebKit)."""
import json
import threading
import time
from pathlib import Path

from . import config
from .brain import JarvisError, create_brain
from .main import is_exit, strip_wake_word
from .voice import Listener, MicrophoneError, SpeechQueue, speak

UI_FILE = Path(__file__).parent / "ui" / "index.html"
ICON_FILE = Path(__file__).resolve().parent.parent / "assets" / "icon.png"


class JarvisApp:
    def __init__(self, mute=False, use_mic=True, window=None, brain=None):
        self.mute = mute
        self.use_mic = use_mic
        self.window = window
        self.brain = brain
        self.lock = threading.Lock()   # immer nur eine Anfrage gleichzeitig
        self.running = True
        self._last_level = 0.0
        self.speech = None if mute else SpeechQueue(
            on_level=self.level, on_start=lambda: self.call("setState", "speaking"))

    # ---------- Python → HUD ----------
    def js(self, code: str):
        if self.window is None:
            return
        try:
            self.window.evaluate_js(code)
        except Exception:
            pass  # Fenster gerade geschlossen o.ä.

    def call(self, fn: str, *args):
        self.js(f"HUD.{fn}({', '.join(json.dumps(a, ensure_ascii=False) for a in args)})")

    def level(self, value: float):
        now = time.time()
        if now - self._last_level >= 1 / 30:   # höchstens 30 Updates pro Sekunde
            self._last_level = now
            self.js(f"HUD.level({value:.3f})")

    def say(self, text: str):
        self.call("jarvis", text)
        if self.mute:
            return
        self.call("setState", "speaking")
        speak(text, on_level=self.level)

    # ---------- Ablauf ----------
    def handle(self, text: str):
        """Eine Anfrage (getippt oder gesprochen) beantworten."""
        text = text.strip()
        if not text:
            return
        with self.lock:
            self.call("user", text)
            if is_exit(text):
                self.say(f"Bis später, {config.USER_NAME}.")
                self.close()
                return
            self.call("setState", "thinking")
            streaming = self.speech is not None and self.brain.streams
            try:
                answer = self.brain.ask(text, on_tool=lambda name, args: self.call("tool", name),
                                        on_sentence=self.speech.say if streaming else None)
                error, spoken = False, streaming
            except JarvisError as e:
                answer, error, spoken = str(e), True, False
            if error:
                self.call("setState", "error")
            self.call("jarvis", answer)
            if self.speech is not None:
                if not spoken:
                    self.speech.say(answer)
                self.speech.wait()
            self.call("setState", "idle")

    def voice_loop(self):
        try:
            listener = Listener(on_level=self.level)
        except Exception:
            self.call("micOff", "Mikrofon blockiert – Einstellungen → Datenschutz → Mikrofon")
            return
        self.call("info", {"mic": "AKTIV"})
        while self.running:
            if self.lock.locked():          # während Jarvis spricht nicht zuhören (kein Echo)
                time.sleep(0.1)
                continue
            try:
                heard = listener.listen(phrase_limit=12)
            except MicrophoneError:
                self.call("micOff", "Mikrofon getrennt")
                return
            if not heard or self.lock.locked():
                continue
            command = strip_wake_word(heard)
            if command is None:
                continue                     # nicht angesprochen
            if not command:
                self.call("setState", "listening")
                self.say("Ja?")
                self.call("setState", "listening")
                try:
                    command = listener.listen(timeout=6, phrase_limit=12)
                except MicrophoneError:
                    return
                self.call("setState", "idle")
            if command:
                self.handle(command)

    def close(self):
        self.running = False
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass


class Api:
    """Funktionen, die das HUD (JavaScript) aufrufen darf."""

    def __init__(self, app: JarvisApp):
        self._app = app

    def ready(self):
        threading.Thread(target=_on_ready, args=(self._app,), daemon=True).start()

    def send_text(self, text):
        threading.Thread(target=self._app.handle, args=(str(text),), daemon=True).start()


def _on_ready(app: JarvisApp):
    threading.Thread(target=app.brain.warmup, daemon=True).start()  # Modell laden, während Jarvis begrüsst
    engine = f"OLLAMA · {config.OLLAMA_MODEL}" if config.PROVIDER != "claude" else f"CLAUDE · {config.MODEL}"
    voice = config.EDGE_VOICE.replace("Neural", "") if config.TTS == "edge" else config.VOICE
    app.call("info", {"core": engine.upper(), "voice": voice.upper(), "mic": "START…" if app.use_mic else "AUS"})
    with app.lock:
        app.say(f"Willkommen zurück, {config.USER_NAME}. Alle Systeme bereit.")
        app.call("setState", "idle")
    if app.use_mic:
        app.voice_loop()


def _set_dock_icon():
    """Eigenes Symbol im Dock statt der Python-Rakete (nur macOS, optional)."""
    try:
        from AppKit import NSApplication, NSImage
        from PyObjCTools import AppHelper

        def apply():
            image = NSImage.alloc().initWithContentsOfFile_(str(ICON_FILE))
            if image:
                NSApplication.sharedApplication().setApplicationIconImage_(image)

        AppHelper.callAfter(apply)
    except Exception:
        pass


def run_gui(mute=False, use_mic=True):
    try:
        import webview
    except ImportError:
        raise SystemExit("❌ Für das Fenster fehlt pywebview: ~/jarvis/.venv/bin/pip install pywebview")

    app = JarvisApp(mute=mute, use_mic=use_mic, brain=create_brain())
    window = webview.create_window(
        "J.A.R.V.I.S.", str(UI_FILE), js_api=Api(app),
        width=1100, height=760, min_size=(820, 600), background_color="#02060c",
    )
    app.window = window
    window.events.closed += lambda: setattr(app, "running", False)
    webview.start(_set_dock_icon)
