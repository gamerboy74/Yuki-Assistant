<div align="center">

# 🌸 Yuki — Intelligent Voice Assistant

**Always-on · Offline-first · Windows 11 · Hindi/Hinglish/English**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Electron](https://img.shields.io/badge/Electron-41-47848F?logo=electron&logoColor=white)](https://electronjs.org)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Ollama](https://img.shields.io/badge/Ollama-gemma3%3A4b-white?logo=ollama)](https://ollama.com)
[![Whisper](https://img.shields.io/badge/Whisper-faster--whisper-yellow)](https://github.com/guillaumekln/faster-whisper)

</div>

---

Yuki is a fully offline, always-on desktop voice assistant for Windows 11. She wakes up when you say **"Hey Yuki"**, understands your command using local Whisper STT, processes it through a local Gemma 3 4B brain via Ollama, and speaks back using Microsoft Edge TTS — all without sending anything to the cloud.

**Key features:**
- 🎙️ **Offline STT** — faster-whisper (CUDA + CPU) with Hindi/Hinglish support
- 🧠 **Local AI brain** — Gemma 3 4B via Ollama, fully offline, structured JSON output
- 🔊 **Neural TTS** — Microsoft Edge TTS (NeerjaNeural Indian English voice)
- 🖥️ **Electron shell** — dark glassmorphism UI, system tray, voice visualizer
- ⚡ **OS actions** — open apps, search, WhatsApp, screenshots, volume, brightness, clipboard, weather
- 🌐 **Chat mode** — type in the UI when you don't want to use voice

---

## 📋 Prerequisites

Before you start, install these on your system:

| Tool | Version | Download |
|---|---|---|
| **Python** | 3.10 or 3.11 | [python.org](https://python.org/downloads) |
| **Node.js** | 18+ | [nodejs.org](https://nodejs.org) |
| **Ollama** | Latest | [ollama.com/download](https://ollama.com/download) |
| **Git** | Any | [git-scm.com](https://git-scm.com) |

> **GPU optional but recommended.** Yuki runs fine on CPU. With an NVIDIA GPU + CUDA, Whisper transcription is ~10x faster.

---

## 🚀 Setup (First Time)

### Step 1 — Clone the repo

```powershell
git clone https://github.com/yourname/yuki_assistant.git
cd yuki_assistant
```

### Step 2 — Set up the Python virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> ⚠️ **PyAudio on Windows** can be tricky. If it fails, run:
> ```powershell
> pip install pipwin
> pipwin install pyaudio
> ```

### Step 3 — Pull the AI model via Ollama

```powershell
ollama pull gemma3:4b
```

This downloads a ~3.3 GB model. Only needed once.

### Step 4 — Install Node.js dependencies

```powershell
npm install
```

### Step 5 — Configure your environment

Copy the example env file and fill in your keys:

```powershell
copy .env.example .env
```

Open `.env` and set at minimum:

```env
# Required for OpenAI brain (optional — Yuki uses Ollama by default)
OPENAI_API_KEY=sk-...

# Optional: free key from console.picovoice.ai for offline wake word
# Without this, wake detection uses Google STT (requires internet)
PICOVOICE_KEY=your-key-here
```

> 💡 **No keys needed for basic use.** Yuki defaults to Ollama (offline) for the brain and Google STT (online) for wake word if no Picovoice key is set.

### Step 6 — Set up Playwright (for WhatsApp / YouTube automation)

```powershell
.venv\Scripts\playwright install chromium
```

---

## ▶️ Running Yuki

### Development mode (hot-reload UI)

```powershell
npm run electron:dev
```

This starts:
1. Vite dev server at `http://localhost:5173` (React UI with hot reload)
2. Electron window loading from the dev server
3. Python backend spawned automatically by Electron

### Production mode (no Vite server)

```powershell
npm run electron:launch
```

Builds the React app to `dist/` and launches Electron loading local files. Slower to start but cleaner.

---

## ⚙️ Configuration

All settings live in one file: **`yuki.config.json`**

```json
{
  "assistant": {
    "name": "Yuki",
    "wake_words": ["hey yuki", "ok yuki", "yuki"],
    "greeting": "Hey! I'm Yuki. Ask me anything...",
    "idle_label": "SAY \"HEY YUKI\"",
    "tts_voice": "en-IN-NeerjaNeural"
  },
  "ollama": {
    "model": "gemma3:4b",
    "base_url": "http://localhost:11434"
  },
  "whisper": {
    "model_size": "base",
    "silence_threshold": 300,
    "silence_timeout": 1.2,
    "max_record_secs": 12
  }
}
```

> Both Python and React read this file — change the name once and everything updates.

### Rename the assistant

Edit `yuki.config.json`:
```json
"name": "Nova"
```

Done. No other files need changing.

### Change the TTS voice

Pick any [Edge TTS voice](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support):

```json
"tts_voice": "en-US-JennyNeural"       // US English
"tts_voice": "en-GB-SoniaNeural"       // British English
"tts_voice": "hi-IN-SwaraNeural"       // Hindi
"tts_voice": "en-IN-NeerjaNeural"      // Indian English (default)
```

### Change the AI brain size

```json
"model": "gemma3:4b"    // Fast, 3.3GB (default)
"model": "gemma3:12b"   // Smarter, 8GB (needs good RAM/GPU)
"model": "llama3:latest"  // Alternative, already on your machine
```

Then pull the new model: `ollama pull gemma3:12b`

### Tune Whisper sensitivity

```json
"silence_threshold": 300    // Lower = more sensitive mic (100-1000)
"silence_timeout": 1.2      // Seconds of silence before stopping recording
"model_size": "base"        // tiny / base / small / medium / large-v3
```

---

## 🎙️ What Yuki Can Do

### Voice commands (say after "Hey Yuki")

| What you say | What happens |
|---|---|
| `"Open Chrome"` | Launches Google Chrome |
| `"Open WhatsApp"` | Opens WhatsApp Desktop |
| `"Search for Indian restaurants near me"` | Google search |
| `"Play Arijit Singh on YouTube"` | YouTube autoplay |
| `"Send WhatsApp to Mom: I'm on my way"` | WhatsApp Web message |
| `"Take a screenshot"` | Saves screenshot to Desktop |
| `"What's the weather in Mumbai?"` | Live weather from wttr.in |
| `"Set volume to 60"` | System volume control |
| `"Set brightness to 80"` | Screen brightness |
| `"Copy this to clipboard: Hello world"` | Sets clipboard text |
| `"Remind me in 10 minutes to call the doctor"` | Windows toast reminder |
| `"What time is it?"` | Reads current time |
| `"What's my battery?"` | Reports battery level |

### Hindi / Hinglish works too

```
"Chrome kholo"              → Opens Chrome
"Mujhe time batao"          → Tells you the time
"Volume kam karo"           → Reduces volume
"YouTube pe gaana chalao"   → Plays music on YouTube
```

### Text / chat mode

Type anything in the chat bar (bottom of UI) and press Enter. No voice needed — goes straight to the AI brain.

---

## 🗂️ Project Structure

```
yuki_assistant/
├── yuki.config.json          ← 🔧 Single config for name, model, voice, whisper
├── .env                      ← 🔑 API keys (not committed to git)
├── .env.example              ← Template for .env
├── requirements.txt          ← Python dependencies
├── package.json              ← npm scripts + Node dependencies
│
├── backend/                  ← Python backend
│   ├── assistant.py          ← Main orchestrator loop
│   ├── brain_ollama.py       ← Gemma 3 4B AI brain (offline, default)
│   ├── brain_openai.py       ← GPT-4o brain (online, optional)
│   ├── brain.py              ← Brain router (reads AI_PROVIDER from .env)
│   ├── config.py             ← Reads yuki.config.json for Python
│   ├── executor.py           ← OS action handlers (open, search, volume...)
│   └── speech/
│       ├── recognition.py    ← Whisper STT + audio recording
│       ├── synthesis.py      ← Edge TTS text-to-speech
│       ├── wake_word.py      ← Porcupine wake word (or Google fallback)
│       └── ai_correction.py  ← STT mishear correction via Gemma
│
├── electron/
│   ├── main.cjs              ← Electron main process, spawns Python, IPC
│   └── preload.cjs           ← IPC bridge exposed to React (window.yukiAPI)
│
└── src/                      ← React frontend (Vite + TypeScript)
    ├── App.tsx               ← Root shell, IPC state management
    ├── hooks/
    │   └── useConfig.ts      ← Reads yuki.config.json for React
    ├── pages/
    │   ├── AgentView.tsx     ← Main chat + voice UI
    │   ├── History.tsx       ← Conversation history
    │   └── Settings.tsx      ← Settings page
    └── components/
        ├── layout/
        │   ├── TopNavBar.tsx ← Top nav + window controls
        │   └── SideNavBar.tsx← Side navigation
        └── MiniWidget.tsx    ← System tray mini mode
```

---

## 🔑 Environment Variables (`.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | No | — | OpenAI key (only if using GPT-4o brain) |
| `PICOVOICE_KEY` | No | — | [Free key](https://console.picovoice.ai) for offline wake word |
| `AI_PROVIDER` | No | `ollama` | `ollama` or `openai` — selects which brain to use |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_MODEL` | No | `gemma3:4b` | Overrides `yuki.config.json` model |
| `WHISPER_MODEL_SIZE` | No | `base` | `tiny`/`base`/`small`/`medium`/`large-v3` |

> **Security:** `.env` is in `.gitignore` — never commit it. If you accidentally expose your OpenAI key, rotate it immediately at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

---

## 🐛 Troubleshooting

### "No audio / mic not detected"

1. Check Windows mic permissions: **Settings → Privacy → Microphone → Allow apps**
2. Try a lower threshold: in `yuki.config.json` set `"silence_threshold": 150`
3. Verify PyAudio works: `.venv\Scripts\python -c "import pyaudio; print('OK')"`

### "Gemma isn't responding / brain errors"

1. Check Ollama is running: `ollama list` (should show `gemma3:4b`)
2. Test manually: `ollama run gemma3:4b "say hello"`
3. If model is missing: `ollama pull gemma3:4b`

### "Wake word not detected"

Without a Picovoice key, wake detection uses Google STT and **requires internet**.

- Get a free key at [console.picovoice.ai](https://console.picovoice.ai) (no credit card)
- Add to `.env`: `PICOVOICE_KEY=your-key-here`
- Re-run Yuki — it will use offline Porcupine automatically

### "UI is white / blank"

This usually means Tailwind CSS isn't loading. Run:
```powershell
npm install
npm run electron:dev
```

### "Python backend not starting"

Check the Electron logs in the terminal running `electron:dev`. Common causes:
- `.venv` not activated or missing — re-run `pip install -r requirements.txt`
- Wrong Python path — make sure `.venv/Scripts/python.exe` exists

### PyAudio install fails on Windows

```powershell
pip install pipwin
pipwin install pyaudio
```

---

## 🛠️ Development Tips

### Test the Python brain without UI

```powershell
.venv\Scripts\activate
python -m backend.assistant
```

### Test just the brain (no voice)

```powershell
python tests/test_brain_cli.py
```

### Change AI provider at runtime

In `.env`:
```env
AI_PROVIDER=openai    # Use GPT-4o
AI_PROVIDER=ollama    # Use Gemma 3 4B (default)
```

### Hot-reload

In dev mode (`npm run electron:dev`), React changes hot-reload instantly. Python backend changes require restarting Electron.

---

## 📦 Building for Distribution

```powershell
npm run electron:launch
```

Or to build an installable `.exe`:
```powershell
npx electron-builder --win
```

Output appears in `release/`.

---

## 🔭 Roadmap

- [ ] Offline wake word without Picovoice (local Whisper-based)
- [ ] Streaming token output from Ollama ("thinking..." animation)
- [ ] Weather widget card in UI
- [ ] Volume/brightness sliders in UI
- [ ] Conversation history persistence (SQLite)
- [ ] Plugin system for custom commands

---

## 📄 License

MIT — do whatever you want with it.
