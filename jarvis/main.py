"""Startpunkt: python -m jarvis  [--text] [--mute]"""
import argparse
import re
import sys

from . import config
from .brain import JarvisError, create_brain
from .voice import speak

CYAN, GREEN, GREY, RESET = "\033[96m", "\033[92m", "\033[90m", "\033[0m"
EXIT_WORDS = {"tschüss", "tschüs", "ciao", "beenden", "exit", "quit", "auf wiedersehen", "gute nacht"}

BANNER = f"""{CYAN}
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝{RESET}
   Just A Rather Very Intelligent System
"""


def show_tool(name, args):
    print(f"{GREY}  ⚙  {name} {args if args else ''}{RESET}")


def respond(brain, text, mute):
    try:
        answer = brain.ask(text, on_tool=show_tool)
    except JarvisError as e:
        answer = str(e)
    print(f"{CYAN}Jarvis:{RESET} {answer}\n")
    if not mute:
        speak(answer)


def is_exit(text):
    return text.lower().strip(" .!?") in EXIT_WORDS


def text_loop(brain, mute):
    print(f"{GREY}Textmodus – schreib einfach los. 'exit' zum Beenden.{RESET}\n")
    while True:
        try:
            text = input(f"{GREEN}Du:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if is_exit(text):
            break
        respond(brain, text, mute)


def strip_wake_word(text):
    """Gibt den Befehl nach dem Wake-Word zurück, oder None wenn kein Wake-Word gesagt wurde."""
    match = re.search(rf"\b{re.escape(config.WAKE_WORD)}\b[\s,.!?]*(.*)", text, flags=re.I)
    return match.group(1).strip() if match else None


def voice_loop(brain, mute):
    from .voice import Listener

    try:
        listener = Listener()
    except Exception as e:
        print(f"⚠️  Mikrofon nicht verfügbar ({e}). Wechsle in den Textmodus.")
        return text_loop(brain, mute)

    print(f"{GREY}Sprachmodus – sag «{config.WAKE_WORD.capitalize()}, ...». Ctrl+C zum Beenden.{RESET}\n")
    try:
        while True:
            heard = listener.listen(phrase_limit=12)
            if not heard:
                continue
            command = strip_wake_word(heard)
            if command is None:
                continue  # nicht angesprochen
            print(f"{GREEN}Du:{RESET} {heard}")
            if not command:
                speak("Ja?")
                command = listener.listen(timeout=6)
                if not command:
                    continue
                print(f"{GREEN}Du:{RESET} {command}")
            if is_exit(command):
                break
            respond(brain, command, mute)
    except KeyboardInterrupt:
        print()


def main():
    parser = argparse.ArgumentParser(description="Jarvis – dein persönlicher KI-Assistent")
    parser.add_argument("--text", action="store_true", help="Nur Texteingabe (kein Mikrofon)")
    parser.add_argument("--mute", action="store_true", help="Antworten nicht vorlesen")
    args = parser.parse_args()

    print(BANNER)
    brain = create_brain()
    engine = f"Ollama ({config.OLLAMA_MODEL})" if config.PROVIDER != "claude" else f"Claude ({config.MODEL})"
    print(f"{GREY}Gehirn: {engine}{RESET}")
    greeting = f"Willkommen zurück, {config.USER_NAME}. Alle Systeme bereit."
    print(f"{CYAN}Jarvis:{RESET} {greeting}\n")
    if not args.mute:
        speak(greeting)

    if args.text:
        text_loop(brain, args.mute)
    else:
        voice_loop(brain, args.mute)

    goodbye = f"Bis später, {config.USER_NAME}."
    print(f"{CYAN}Jarvis:{RESET} {goodbye}")
    if not args.mute:
        speak(goodbye)
    sys.exit(0)


if __name__ == "__main__":
    main()
