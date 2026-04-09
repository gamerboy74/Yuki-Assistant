import { useState, useEffect } from 'react';
import { useConfig } from '../hooks/useConfig';

// Real edge-tts neural voices (free, no API key needed)
const TTS_VOICES = [
  { id: 'en-IN-NeerjaNeural',   label: 'Neerja',   desc: 'Indian English · Female' },
  { id: 'en-US-JennyNeural',    label: 'Jenny',    desc: 'US English · Female · Warm' },
  { id: 'en-US-GuyNeural',      label: 'Guy',      desc: 'US English · Male · JARVIS feel' },
  { id: 'en-GB-SoniaNeural',    label: 'Sonia',    desc: 'British English · Female' },
  { id: 'hi-IN-SwaraNeural',    label: 'Swara',    desc: 'Hindi · Female' },
];

const WHISPER_MODELS = [
  { id: 'tiny',   label: 'Tiny',   desc: 'Fastest · Less accurate' },
  { id: 'base',   label: 'Base',   desc: 'Fast · Good accuracy (default)' },
  { id: 'small',  label: 'Small',  desc: 'Balanced · Better Hindi/Hinglish' },
  { id: 'medium', label: 'Medium', desc: 'Slower · Best accuracy' },
];

export default function Settings() {
  const config = useConfig();

  const [ttsVoice,     setTtsVoice]     = useState(config.ttsVoice || 'en-IN-NeerjaNeural');
  const [whisperModel, setWhisperModel] = useState('base');
  const [silenceThold, setSilenceThold] = useState(300);
  const [silenceTime,  setSilenceTime]  = useState(1.2);
  const [ollamaUrl,    setOllamaUrl]    = useState('http://localhost:11434');
  const [saved,        setSaved]        = useState(false);
  const [routerOn,     setRouterOn]     = useState(true);
  const [purgeConfirm, setPurgeConfirm] = useState(false);

  // Prefill from config on mount
  useEffect(() => {
    if (config.ttsVoice)     setTtsVoice(config.ttsVoice);
  }, [config]);

  function handleSave() {
    // Send new settings to Python backend via IPC
    const payload = {
      tts_voice:         ttsVoice,
      whisper_model:     whisperModel,
      silence_threshold: silenceThold,
      silence_timeout:   silenceTime,
      ollama_url:        ollamaUrl,
      router_enabled:    routerOn,
    };
    window.yukiAPI?.sendMessage?.(`__settings__:${JSON.stringify(payload)}`);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  function handlePurgeMemory() {
    if (!purgeConfirm) { setPurgeConfirm(true); return; }
    window.yukiAPI?.sendMessage?.('forget everything');
    setPurgeConfirm(false);
  }

  return (
    <div className="absolute inset-0 overflow-y-auto px-8 md:px-12 pt-12 pb-32">
      <header className="mb-12">
        <h1 className="font-headline text-5xl font-light tracking-tight text-on-surface mb-2">
          Voice <span className="text-primary font-medium">Settings</span>
        </h1>
        <p className="text-on-surface-variant font-body tracking-wider text-sm max-w-xl">
          Configure Yuki's voice, recognition model, and behaviour. Changes take effect immediately.
        </p>
      </header>

      <div className="grid grid-cols-12 gap-8 max-w-6xl">
        {/* Left column */}
        <section className="col-span-12 lg:col-span-8 space-y-8">

          {/* TTS Voice Selection */}
          <div className="bg-surface-container-low rounded-xl p-8 hover:bg-surface-container transition-all duration-300">
            <div className="flex justify-between items-center mb-8">
              <h2 className="font-headline text-2xl">TTS Voice</h2>
              <span className="text-xs uppercase tracking-widest text-primary font-bold">{TTS_VOICES.length} Voices</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {TTS_VOICES.map(v => {
                const active = ttsVoice === v.id;
                return (
                  <div
                    key={v.id}
                    onClick={() => setTtsVoice(v.id)}
                    className={`p-5 rounded-lg cursor-pointer transition-all group border-2 ${
                      active
                        ? 'bg-surface-container-high border-primary/30 shadow-[0_0_20px_rgba(143,245,255,0.07)]'
                        : 'bg-surface-container-high border-transparent hover:border-outline-variant/40'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <div>
                        <h3 className={`font-headline text-lg ${active ? 'text-primary' : 'text-on-surface'}`}>{v.label}</h3>
                        <p className="text-xs text-on-surface-variant">{v.desc}</p>
                      </div>
                      <span className={`material-symbols-outlined text-lg ${active ? 'text-primary' : 'text-on-surface-variant'}`}
                            style={active ? { fontVariationSettings: "'FILL' 1" } : {}}>
                        {active ? 'check_circle' : 'radio_button_unchecked'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Whisper Model */}
          <div className="bg-surface-container-low rounded-xl p-8 hover:bg-surface-container transition-all duration-300">
            <h2 className="font-headline text-2xl mb-6">Speech Recognition Model</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {WHISPER_MODELS.map(m => {
                const active = whisperModel === m.id;
                return (
                  <div key={m.id} onClick={() => setWhisperModel(m.id)}
                    className={`p-4 rounded-lg cursor-pointer border-2 transition-all text-center ${
                      active ? 'border-primary/30 bg-surface-container-high' : 'border-transparent bg-surface-container-high hover:border-outline-variant/30'
                    }`}>
                    <p className={`font-headline text-lg ${active ? 'text-primary' : ''}`}>{m.label}</p>
                    <p className="text-[10px] text-on-surface-variant mt-1">{m.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Sensitivity Sliders */}
          <div className="bg-surface-container-low rounded-xl p-8 hover:bg-surface-container transition-all duration-300">
            <h2 className="font-headline text-2xl mb-6">Microphone Sensitivity</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
              <div>
                <div className="flex justify-between mb-3">
                  <label className="text-xs uppercase tracking-[0.2em] font-bold text-on-surface-variant">Silence Threshold</label>
                  <span className="text-xs text-primary font-mono">{silenceThold}</span>
                </div>
                <input type="range" min="100" max="800" value={silenceThold}
                  onChange={e => setSilenceThold(Number(e.target.value))}
                  className="w-full accent-primary" />
                <p className="text-[10px] text-on-surface-variant mt-2">Lower = more sensitive (picks up soft voices). Higher = less noise.</p>
              </div>
              <div>
                <div className="flex justify-between mb-3">
                  <label className="text-xs uppercase tracking-[0.2em] font-bold text-on-surface-variant">Silence Timeout (s)</label>
                  <span className="text-xs text-primary font-mono">{silenceTime.toFixed(1)}s</span>
                </div>
                <input type="range" min="0.5" max="3.0" step="0.1" value={silenceTime}
                  onChange={e => setSilenceTime(Number(e.target.value))}
                  className="w-full accent-primary" />
                <p className="text-[10px] text-on-surface-variant mt-2">How long to wait after you stop speaking before processing.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Right sidebar */}
        <section className="col-span-12 lg:col-span-4 space-y-8">

          {/* Ollama / AI */}
          <div className="bg-surface-container-high rounded-xl p-6 border-l-4 border-primary/40">
            <h2 className="font-headline text-xl mb-4">AI Backend</h2>
            <div className="space-y-4">
              <div>
                <label className="text-xs uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Ollama URL</label>
                <input
                  type="text" value={ollamaUrl} onChange={e => setOllamaUrl(e.target.value)}
                  className="w-full bg-surface-container-highest rounded-lg px-4 py-2.5 text-sm font-mono text-on-surface border border-outline-variant/20 focus:border-primary/40 focus:outline-none"
                />
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-container-highest transition-colors cursor-pointer"
                   onClick={() => setRouterOn(!routerOn)}>
                <div>
                  <p className="text-sm font-medium">Fast Path Router</p>
                  <p className="text-[10px] text-on-surface-variant">Resolve simple commands instantly without AI</p>
                </div>
                <div className={`w-10 h-5 rounded-full relative flex items-center px-1 transition-colors ${routerOn ? 'bg-primary/20' : 'bg-outline-variant'}`}>
                  <div className={`w-3.5 h-3.5 rounded-full transition-transform ${routerOn ? 'bg-primary translate-x-4 shadow-[0_0_8px_rgba(143,245,255,0.6)]' : 'bg-surface-variant translate-x-0'}`} />
                </div>
              </div>
            </div>
          </div>

          {/* Wake Word Info */}
          <div className="bg-surface-container-low rounded-xl p-6 hover:bg-surface-container transition-all duration-300">
            <h2 className="font-headline text-xl mb-4">Wake Word</h2>
            <div className="bg-surface-container-highest rounded-lg p-4 flex items-center gap-3 border border-outline-variant/20 mb-4">
              <span className="material-symbols-outlined text-primary">record_voice_over</span>
              <span className="text-sm font-medium">"Hey Yuki" / "Yuki"</span>
              <span className="ml-auto text-[10px] text-on-surface-variant uppercase tracking-wider">
                {window.yukiAPI ? 'Active' : 'Browser Mode'}
              </span>
            </div>
            <p className="text-[11px] text-on-surface-variant leading-relaxed">
              For offline wake word, add <code className="text-primary font-mono">PICOVOICE_KEY</code> to your <code className="text-primary">.env</code> file. Without it, STT-based detection via Google is used.
            </p>
          </div>

          {/* Privacy */}
          <div className="glass-panel rounded-xl p-6 border border-outline-variant/10">
            <div className="flex items-center gap-3 mb-6">
              <span className="material-symbols-outlined text-error">security</span>
              <h2 className="font-headline text-xl">Privacy</h2>
            </div>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-on-surface-variant">Local AI Processing</span>
                <span className="text-primary font-mono text-xs">ENABLED</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-on-surface-variant">Cloud Voice History</span>
                <span className="text-on-surface/40 font-mono text-xs">OFFLINE</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-on-surface-variant">Memory File</span>
                <span className="text-primary font-mono text-xs">LOCAL ONLY</span>
              </div>
              <button
                onClick={handlePurgeMemory}
                className={`w-full mt-2 py-2.5 rounded-full text-xs font-bold uppercase tracking-widest transition-colors ${
                  purgeConfirm
                    ? 'bg-error text-on-error'
                    : 'bg-secondary-container text-on-secondary-container hover:bg-secondary-fixed-dim'
                }`}
              >
                {purgeConfirm ? 'Confirm — Erase All Memories?' : 'Purge Yuki\'s Memory'}
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* Sticky Footer */}
      <div className="fixed bottom-8 right-8 flex items-center gap-4 z-50">
        <span className={`text-xs text-primary transition-opacity duration-500 ${saved ? 'opacity-100' : 'opacity-0'}`}>
          ✓ Settings saved — restart Yuki to apply
        </span>
        <button
          onClick={handleSave}
          className="px-10 py-3 rounded-full text-on-primary-fixed font-bold text-sm tracking-widest active:scale-95 transition-all duration-300"
          style={{ background: 'linear-gradient(135deg, #8ff5ff 0%, #00eefc 100%)', boxShadow: '0 4px 20px rgba(0,238,252,0.3)' }}
        >
          Save Settings
        </button>
      </div>
    </div>
  );
}
