# Yuki Assistant Architecture

Yuki follows a modular, reactive architecture designed for low-latency, agentic interactions.

## High-Level Data Flow

1.  **Ingestion (Audio/Text)**: 
    *   Audio is captured via `pyaudio` and processed by the Silero VAD state machine in `backend/speech/vad.py`.
    *   Transcription is performed locally via `faster-whisper`.
    *   State changes are emitted over the Electron IPC bridge to the React frontend.

2.  **Orchestration**:
    *   The `BrainOrchestrator` (`backend/brain/orchestrator.py`) handles conversation history, context management, and turn-locking.
    *   It determines if a request requires tool execution (agentic mode) or a direct response.

3.  **Plugin Dispatch System**:
    *   Commands are routed to `backend/executor.py`, which acts as a thin dispatcher.
    *   The dispatcher utilizes the `backend/plugins/` registry to dynamically discover and execute "hard" logic (filesystem, browser, OS controls).
    *   This registry (see `backend/plugins/__init__.py`) allows Yuki to scale without a monolithic executor.

4.  **Presentation (HUD)**:
    *   The React frontend uses a centralized Zustand store (`src/store/settingsStore.ts`) for high-performance, reactive configuration management.
    *   The HUD provides real-time visualization of the "Sentient Orb," token usage, and system health.

## Core Modules

*   **`backend/plugins/`**: The home for all assistant capabilities (Vision, Computer Hands, Weather, etc.).
*   **`backend/brain/`**: Logic for LLM interaction and agentic decision making.
*   **`backend/speech/`**: Audio pipeline, VAD, and TTS providers.
*   **`electron/`**: The host layer bridging the Python kernel with the React interface.
*   **`src/`**: The Vite-powered React HUD.

## Design Philosophy

*   **Local First**: STT, VAD, and many tool logic layers run locally to minimize latency.
*   **Thin Dispatcher**: Core backend modules should remain thin, delegating complex logic to specialized plugins.
*   **Reactive State**: All UI elements must react instantly to backend state changes via the IPC channel and Zustand store.
