"""Tests ohne echte API und ohne Mac – Claude wird simuliert."""
import os
import tempfile
import unittest
from types import SimpleNamespace as NS

os.environ["JARVIS_DATA_DIR"] = tempfile.mkdtemp()
os.environ.setdefault("ANTHROPIC_API_KEY", "test")

from jarvis import memory, main  # noqa: E402
from jarvis.brain import ClaudeBrain as Brain, JarvisError, OllamaBrain  # noqa: E402
from jarvis.tools import TOOL_SCHEMAS, _HANDLERS, run_tool  # noqa: E402
from jarvis import voice  # noqa: E402
from jarvis.voice import clean_for_speech  # noqa: E402
from unittest import mock  # noqa: E402


class FakeClient:
    """Simuliert die Claude API mit vorgegebenen Antworten."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def text(t):
    return NS(type="text", text=t)


def tool_use(name, args, id_="t1"):
    return NS(type="tool_use", name=name, input=args, id=id_)


class TestMemory(unittest.TestCase):
    def setUp(self):
        memory.facts.save([]); memory.notes.save([]); memory.clear_history()

    def test_facts(self):
        memory.remember("Lieblingsauto: BMW M850i")
        self.assertIn("Das weiss ich bereits.", memory.remember("Lieblingsauto: BMW M850i"))
        self.assertEqual(len(memory.all_facts()), 1)
        memory.forget("bmw")
        self.assertEqual(memory.all_facts(), [])

    def test_notes(self):
        memory.add_note("Einkaufen")
        memory.add_note("Lernen")
        self.assertIn("2. Lernen", memory.list_notes())
        memory.delete_note(1)
        self.assertNotIn("Einkaufen", memory.list_notes())
        self.assertIn("gibt es nicht", memory.delete_note(9))


class TestTools(unittest.TestCase):
    def test_every_schema_has_handler(self):
        for schema in TOOL_SCHEMAS:
            if schema["name"] != "clear_conversation":
                self.assertIn(schema["name"], _HANDLERS)

    def test_unknown_and_errors(self):
        self.assertIn("Unbekanntes", run_tool("fliegen", {}))
        self.assertIn("Fehler", run_tool("delete_note", {"number": "x"}))


class TestBrain(unittest.TestCase):
    def setUp(self):
        memory.facts.save([]); memory.notes.save([]); memory.clear_history()

    def test_tool_loop(self):
        client = FakeClient([
            NS(stop_reason="tool_use", content=[tool_use("add_note", {"text": "Wäsche"})]),
            NS(stop_reason="end_turn", content=[text("Notiert, Sir.")]),
        ])
        brain = Brain(client=client)
        self.assertEqual(brain.ask("Notiere Wäsche"), "Notiert, Sir.")
        self.assertIn("Wäsche", memory.list_notes())
        tool_result = client.calls[1]["messages"][-2]["content"][0]  # [-1] ist die spätere Antwort
        self.assertEqual(tool_result["tool_use_id"], "t1")
        # Verlauf gespeichert und neu geladen
        self.assertEqual(len(memory.load_history()), 2)
        self.assertEqual(len(Brain(client=FakeClient([])).history), 2)

    def test_facts_in_system_prompt(self):
        memory.remember("Wohnt in der Schweiz")
        client = FakeClient([NS(stop_reason="end_turn", content=[text("Ok")])])
        Brain(client=client).ask("Hallo")
        self.assertIn("Wohnt in der Schweiz", client.calls[0]["system"])

    def test_clear_conversation(self):
        client = FakeClient([
            NS(stop_reason="end_turn", content=[text("Hallo")]),
            NS(stop_reason="tool_use", content=[tool_use("clear_conversation", {})]),
            NS(stop_reason="end_turn", content=[text("Verlauf gelöscht.")]),
        ])
        brain = Brain(client=client)
        brain.ask("Hi")
        brain.ask("Vergiss unser Gespräch")
        self.assertEqual(memory.load_history(), [])


class FakeOllama:
    """Simuliert die Ollama-API."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.bodies = []

    def __call__(self, path, body):
        self.bodies.append(body)
        return {"message": self.replies.pop(0)}


class TestOllama(unittest.TestCase):
    def setUp(self):
        memory.facts.save([]); memory.notes.save([]); memory.clear_history()

    def test_tool_loop(self):
        fake = FakeOllama([
            {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "add_note", "arguments": {"text": "Einkaufen"}}}]},
            {"role": "assistant", "content": "<think>hmm</think>Notiert."},
        ])
        brain = OllamaBrain(post=fake)
        self.assertEqual(brain.ask("Notiere Einkaufen"), "Notiert.")
        self.assertIn("Einkaufen", memory.list_notes())
        tool_msg = fake.bodies[1]["messages"][-2]  # [-1] ist die spätere Antwort
        self.assertEqual(tool_msg["role"], "tool")
        self.assertEqual(fake.bodies[0]["messages"][0]["role"], "system")
        self.assertEqual(fake.bodies[0]["tools"][0]["type"], "function")

    def test_string_arguments(self):
        memory.add_note("A")
        fake = FakeOllama([
            {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "delete_note", "arguments": '{"number": "1"}'}}]},
            {"role": "assistant", "content": "Gelöscht."},
        ])
        OllamaBrain(post=fake).ask("Lösche Notiz 1")
        self.assertEqual(memory.list_notes(), "Keine Notizen vorhanden.")

    def test_speed_options_and_warmup(self):
        fake = FakeOllama([{"role": "assistant", "content": "x"}, {"role": "assistant", "content": "Hallo."}])
        brain = OllamaBrain(post=fake)
        brain.warmup()
        self.assertEqual(fake.bodies[0]["options"]["num_predict"], 1)
        brain.ask("Hi")
        body = fake.bodies[1]
        self.assertIn("keep_alive", body)
        self.assertEqual(body["options"]["num_ctx"], 4096)

    def test_think_fallback(self):
        calls = []

        def post(path, body):
            calls.append(dict(body))
            if "think" in body:
                raise JarvisError('Ollama-Fehler 400: "model does not support thinking"')
            return {"message": {"role": "assistant", "content": "Hallo."}}

        self.assertEqual(OllamaBrain(post=post).ask("Hi"), "Hallo.")
        self.assertNotIn("think", calls[-1])


class TestVoice(unittest.TestCase):
    def test_edge_used_when_available(self):
        with mock.patch.object(voice.config, "TTS", "edge"), \
                mock.patch.object(voice, "_speak_edge", return_value=True) as edge, \
                mock.patch.object(voice, "_speak_mac") as mac:
            voice.speak("Hallo")
        edge.assert_called_once_with("Hallo", None)
        mac.assert_not_called()

    def test_fallback_to_mac(self):
        with mock.patch.object(voice.config, "TTS", "edge"), \
                mock.patch.object(voice, "_speak_edge", side_effect=OSError("offline")), \
                mock.patch.object(voice, "_speak_mac") as mac:
            voice.speak("Hallo")
        mac.assert_called_once_with("Hallo", None)

    def test_mac_mode(self):
        with mock.patch.object(voice.config, "TTS", "mac"), \
                mock.patch.object(voice, "_speak_edge") as edge, \
                mock.patch.object(voice, "_speak_mac") as mac:
            voice.speak("Hallo")
        edge.assert_not_called()
        mac.assert_called_once()


class FakeWindow:
    def __init__(self):
        self.calls = []

    def evaluate_js(self, code):
        self.calls.append(code)


class TestGui(unittest.TestCase):
    def setUp(self):
        memory.facts.save([]); memory.notes.save([]); memory.clear_history()

    def make_app(self, replies):
        from jarvis.gui import JarvisApp
        win = FakeWindow()
        app = JarvisApp(mute=True, use_mic=False, window=win, brain=OllamaBrain(post=FakeOllama(replies)))
        return app, win

    def test_text_request_updates_hud(self):
        app, win = self.make_app([
            {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "add_note", "arguments": {"text": "Test"}}}]},
            {"role": "assistant", "content": "Notiert, Sir."},
        ])
        app.handle("Notiere Test")
        js = "\n".join(win.calls)
        self.assertIn('HUD.user("Notiere Test")', js)
        self.assertIn('HUD.setState("thinking")', js)
        self.assertIn('HUD.tool("add_note")', js)
        self.assertIn('HUD.jarvis("Notiert, Sir.")', js)
        self.assertTrue(win.calls[-1].endswith('HUD.setState("idle")'))

    def test_error_state(self):
        from jarvis.gui import JarvisApp

        def broken(path, body):
            raise JarvisError("Ollama läuft nicht.")
        win = FakeWindow()
        app = JarvisApp(mute=True, use_mic=False, window=win, brain=OllamaBrain(post=broken))
        app.handle("Hallo")
        self.assertIn('HUD.setState("error")', "\n".join(win.calls))

    def test_level_throttled(self):
        app, win = self.make_app([])
        for _ in range(50):
            app.level(0.5)
        self.assertLess(len(win.calls), 5)


class TestIMessage(unittest.TestCase):
    def test_requires_phone(self):
        from jarvis import tools
        with mock.patch.object(tools.config, "PHONE", ""):
            self.assertIn("JARVIS_PHONE", tools.send_imessage("Hallo"))

    def test_sends_only_to_own_number(self):
        from jarvis import tools
        with mock.patch.object(tools.config, "PHONE", "+41790000000"), \
                mock.patch.object(tools, "_osa") as osa:
            result = tools.send_imessage('Sag "Hallo"')
        script = osa.call_args[0][0]
        self.assertIn('participant "+41790000000"', script)
        self.assertIn('Sag \\"Hallo\\"', script)   # Anführungszeichen sicher maskiert
        self.assertIn("gesendet", result)

    def test_timer_with_imessage(self):
        from jarvis import tools
        with mock.patch.object(tools, "notify"), mock.patch.object(tools, "send_imessage") as send:
            tools._timer_done("Wäsche", True)
        send.assert_called_once()
        self.assertIn("(kommt auch per iMessage)", tools.set_timer(3600, "Test", "true"))
        tools._timers[-1].cancel()


class TestLevels(unittest.TestCase):
    def test_word_level(self):
        words = [(0.0, 0.4), (0.6, 0.3)]
        self.assertGreater(voice.word_level(0.2, words), 0.9)
        self.assertLess(voice.word_level(0.5, words), 0.2)

    def test_rms_level(self):
        import struct
        silent = struct.pack("<100h", *([0] * 100))
        loud = struct.pack("<100h", *([12000, -12000] * 50))
        self.assertEqual(voice.rms_level(silent), 0.0)
        self.assertGreater(voice.rms_level(loud), 0.9)


class TestHelpers(unittest.TestCase):
    def test_wake_word(self):
        self.assertEqual(main.strip_wake_word("Jarvis, öffne Safari"), "öffne Safari")
        self.assertEqual(main.strip_wake_word("hey jarvis"), "")
        self.assertIsNone(main.strip_wake_word("öffne Safari"))

    def test_speech_cleanup(self):
        self.assertEqual(clean_for_speech("**Hallo** [Link](https://x.ch)"), "Hallo Link")

    def test_exit(self):
        self.assertTrue(main.is_exit("Tschüss!"))
        self.assertFalse(main.is_exit("öffne Spotify"))


if __name__ == "__main__":
    unittest.main()
