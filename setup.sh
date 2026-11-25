#!/usr/bin/env bash
# Einmalige Installation von Jarvis auf macOS
set -e
cd "$(dirname "$0")"

echo "🔧 Jarvis wird installiert..."

if ! command -v brew >/dev/null 2>&1; then
  echo "❌ Homebrew fehlt. Installiere es zuerst: https://brew.sh"
  exit 1
fi

brew list portaudio >/dev/null 2>&1 || brew install portaudio

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "📝 .env erstellt – Namen und Wohnort anpassen mit: open -e .env"
fi

if command -v ollama >/dev/null 2>&1; then
  echo "🧠 Lade das KI-Modell für Ollama (einmalig ca. 5 GB)..."
  ollama pull qwen3:8b || echo "⚠️  Ollama-App öffnen und dann 'ollama pull qwen3:8b' ausführen."
else
  echo "ℹ️  Für die Gratis-Variante Ollama installieren: https://ollama.com/download/mac"
fi

chmod +x jarvis.sh
echo "✅ Fertig! Starten mit:  ./jarvis.sh   (oder ./jarvis.sh --text)"
