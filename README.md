<div align="center">

<img src="public/yuki_logo.png" alt="Yuki Logo" width="120" />

# 🌸 Yuki Neural HUD
### **The F.R.I.D.A.Y.-Class Desktop Neural Assistant**

**Next-Gen HUD · Multi-Source Brains · Deep Windows Integration · 100% Reactive**

[![Reliability](https://img.shields.io/badge/Neural_Link-Stable-00f2ff.svg?style=for-the-badge&logoColor=white)](https://ai.google.dev/)
[![UI Style](https://img.shields.io/badge/Aesthetic-Neural_Terminal-ff00ff.svg?style=for-the-badge)](https://react.dev)
[![Local AI](https://img.shields.io/badge/Local_Brain-Ollama-white.svg?style=for-the-badge&logo=ollama)](https://ollama.com)

---

**Yuki** is not just a voice assistant; she is a high-fidelity **Neural HUD** for your desktop. Built with an elite "Senior Designer" aesthetic, she transforms your Windows experience with a professional terminal-driven interface, reactive frequency waveforms, and a multi-brain cascade that ensures she never stops thinking.

[**Get Started**](#-quick-start) • [**Commands**](#-neural-commands) • [**Architecture**](#-neural-architecture) • [**Stability**](#-stability--fallbacks)

</div>

---

## ✨ Elite Features

### 🖥️ Neural Terminal HUD
*   **Command Line Interaction**: A monospaced terminal prompt (`>_`) for lightning-fast text and voice commands.
*   **HUD Segments**: Information is delivered in structured protocol blocks featuring asymmetric glowing borders and metadata headers.
*   **Real-time Streaming**: No waiting. Responses crawl onto the screen as Yuki thinks, providing a "living" interface experience.
31. 
32. ### 🌐 Observant Browser Research
33. *   **Self-Sensing Navigation**: Yuki doesn't just open links; she reads them. She can scrape live web content, parse DOM snippets, and provide summaries directly in the HUD.
34. *   **Nexus Bridge (CDP)**: Direct browser communication over Chrome DevTools Protocol for low-latency element interaction.
35. *   **Isolated Profiles**: Yuki maintains her own `.yuki_profile` to keep her agentic sessions separate from your personal browsing.

### 🌊 Local Neural Voice (Kokoro-82M)
*   **Zero-Latency Synthesis**: Yuki uses high-performance local TTS powered by **Kokoro-82M**, allowing her to respond instantly even without an internet connection.
*   **Hinglish Optimized**: Specially tuned to handle Hindi-English hybrid sentences with natural prosody.
*   **Reactive Waveform**: A 5-bar vertical visualizer reflects her speech patterns in real-time, shifting rhythms between **Listening**, **Thinking**, and **Speaking**.

### 🧠 Multi-Link Brain Cascade
*   **Primary Link**: **Gemini 2.0 Flash** for state-of-the-art reasoning and tool dispatching.
*   **Neural Economy**: Real-time monitoring of tokens and session cost via an integrated dashboard widget.
*   **Total Reliability**: Implemented circuit-breaker logic prevents "blackouts" by switching to **OpenAI GPT-4o** or **Local Ollama (Gemma 3)** in under 500ms.

---

## 🚀 Quick Start

### Prerequisites
- **Node.js 18+** & **Python 3.10+**
- **espeak-ng**: Required for local Kokoro-82M voice synthesis.
- **Ollama** (for local stability): `ollama pull gemma3:4b`
- **NVIDIA GPU** (Optional): Recommended for sub-second Whisper transcription and neural synthesis.

### Installation
1.  **Clone & Install**:
    ```powershell
    git clone https://github.com/gamerboy74/Yuki-Assistant.git
    cd yuki_assistant
    npm install
    pip install -r requirements.txt
    ```
2.  **Launch**:
    ```powershell
    npm run electron:dev
    ```
3.  **Link Your Brain**:
    Once the HUD boots, click the **Settings (Cog)** icon. Paste your API keys (Google, OpenAI, or ElevenLabs) directly into the interface. 
    
    > [!TIP]
    > Yuki automatically generates and manages your `yuki.config.json` file. You can also reference `yuki.config.json.example` for manual setup.

---

## 🛠️ Neural Commands

Yuki supports deep OS automation out of the box.

| Command | Protocol Action |
| :--- | :--- |
| `Open YouTube` | Launches YouTube in default browser via Link Map |
| `Search cricbuzz for scores` | **Observant Research**: Navigates, scrapes, and reports live data |
| `Pause the song` | Triggers Global Media Control Protocol |
| `Set volume to 50` | Hardware sound modulation |
| `Send file to Mom` | Automated WhatsApp File Dispatcher |
| `Take a screenshot` | Captures Desktop to `%USERPROFILE%\Desktop` |
| `Weather in Tokyo` | Real-time weather segment fetching |

---

## 🛡️ Stability & Fallbacks

> [!IMPORTANT]
> **Neural Recharge (429 Handling)**: 
> If you hit the Gemini Free Tier limit, Yuki will automatically detect the "Resource Exhausted" signal and rewire her brain to **Ollama** (Local). Ensure Ollama is running (`ollama serve`) to maintain 100% uptime.

### Config Syncing
All settings are stored in `yuki.config.json`.
*   **Proactive Agent**: An autonomous background layer monitors neural link health, API quotas, and system thermal levels, providing audible alerts if maintenance is required.
*   **Persistence Guard**: Yuki includes a hydration check to prevent UI restarts from resetting your custom ElevenLabs or Edge TTS settings.
*   **Auto-Healing**: Missing configuration blocks are automatically restored using system defaults during boot.

---

## 🏗️ Neural Architecture

```mermaid
graph TD
    UI[Electron/React HUD] -->|Transcript| ORC[Python Orchestrator]
    ORC -->|VAD| MIC[Sentinel Voice Activity]
    ORC -->|Health| PRO[Proactive Agent]
    ORC -->|Brain Cascade| LINK{Neural Link}
    LINK -->|Cloud| GEM[Gemini 2.0 / OpenAI]
    LINK -->|Local| OLL[Ollama / Gemma 3]
    LINK -->|Tools| EX[Executor Service]
    EX -->|Apps| WIN[Windows OS]
    EX -->|Web| BRO[Browser Automation]
```

---

## 🎨 Aesthetic Guidelines

Yuki follows the **"Neural Terminal"** design language:
- **Typography**: JetBrains Mono / Inter.
- **Color Space**: Deep Obsidian backgrounds with #00f2ff (Cyan) and #ff00ff (Magenta) accents.
- **FX**: Glassmorphism (Backdrop blur 12px), Asymmetric glow borders, and real-time frequency pulses.

---

<p align="center">
  Generated by <b>Antigravity AI</b> for <b>Yuki Assistant</b>.
</p>
