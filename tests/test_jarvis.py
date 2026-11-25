"""Tests ohne echte API und ohne Mac – Claude wird simuliert."""
import os
import tempfile
import unittest
from types import SimpleNamespace as NS

os.environ["JARVIS_DATA_DIR"] = tempfile.mkdtemp()
os.environ.setdefault("ANTHROPIC_API_KEY", "test")

from jarvis import memory, main  # noqa: E402
from jarvis.brain import Brain  # noqa: E402
from jarvis.tools import TOOL_SCHEMAS, _HANDLERS, run_tool  # noqa: E402
from jarvis.voice import clean_for_speech  # noqa: E402


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
