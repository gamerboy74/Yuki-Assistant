import React, { useState, useEffect, useRef } from 'react';
import { useConfig } from '../hooks/useConfig';

type Tab = 'identity' | 'intelligence' | 'voices' | 'listener' | 'nexus';

const WHISPER_MODELS = [
  { id: 'tiny', label: 'Tiny', desc: 'Fastest, lower accuracy' },
  { id: 'base', label: 'Base', desc: 'Balanced speed/accuracy' },
  { id: 'small', label: 'Small', desc: 'Better accuracy, slower' },
  { id: 'medium', label: 'Medium', desc: 'High accuracy, requires more RAM' },
];

export default function Settings() {
  const config = useConfig();

  const [activeTab, setActiveTab] = useState<Tab>('identity');
  const [saved, setSaved] = useState(false);

  // -- State variables mapped from config --
  // Core
  const [assistantName, setAssistantName] = useState(config.name);
  const [idleLabel, setIdleLabel] = useState(config.idleLabel);
  const [greeting, setGreeting] = useState(config.greeting);
  const [wakeWords, setWakeWords] = useState(config.wakeWords.join(', '));

  // Threads (Whisper)
  const [whisperModel, setWhisperModel] = useState('base');
  const [silenceThold, setSilenceThold] = useState(300);
  const [silenceTime, setSilenceTime] = useState(1.2);

  // Neural (AI)
  const [geminiModel, setGeminiModel] = useState('gemini-2.0-flash');
  const [geminiFallback, setGeminiFallback] = useState('gemini-2.5-flash-lite');
  const [openaiModel, setOpenaiModel] = useState('gpt-4o-mini');
  const [ollamaModel, setOllamaModel] = useState('gemma3:4b');
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [routerOn, setRouterOn] = useState(true);
  const [brainProvider, setBrainProvider] = useState('auto');

  // Config (Synthesis)
  const [ttsProvider, setTtsProvider] = useState('edge-tts');
  const [ttsVoice, setTtsVoice] = useState('en-US-AvaMultilingualNeural');
  const [elBudget, setElBudget] = useState(2000);
  const [speechThold, setSpeechThold] = useState(0.65);
  const [gainDb, setGainDb] = useState(1.0);
  const [spatialAudio, setSpatialAudio] = useState(false);
  const [resamplingHq, setResamplingHq] = useState(true);

  // Neural Secrets
  const [googleApiKey, setGoogleApiKey] = useState('');
  const [openaiApiKey, setOpenaiApiKey] = useState('');
  const [elApiKey, setElApiKey] = useState('');
  const [elVoiceId, setElVoiceId] = useState('');

  // UI States (Show/Hide)
  const [showGoogle, setShowGoogle] = useState(false);
  const [showOpenai, setShowOpenai] = useState(false);
  const [showEl, setShowEl] = useState(false);

  // Advanced Tuning
  const [maxRecordSecs, setMaxRecordSecs] = useState(12);
  const [fuzzyThold, setFuzzyThold] = useState(0.72);
  const [logFastPath, setLogFastPath] = useState(true);
  const [correctionModel, setCorrectionModel] = useState('gemma3:4b');
  const [useLiteFallback, setUseLiteFallback] = useState(true);
  
  // Interface Nexus (Chrome/Browser)
  const [browserPreferred, setBrowserPreferred] = useState('chrome');
  const [browserFallback, setBrowserFallback] = useState('brave');
  const [browserAutoLaunch, setBrowserAutoLaunch] = useState(true);
  const [browserCdpPort, setBrowserCdpPort] = useState(9222);

  // Persistence Guard
  const isHydrated = useRef(false);

  // Dynamic Data
  const [availableVoices, setAvailableVoices] = useState<any[]>([]);
  const [voiceSearch, setVoiceSearch] = useState('');
  const [genderFilter, setGenderFilter] = useState<'female' | 'male'>('female');

  const carouselRef = useRef<HTMLDivElement>(null);

  // Vault
  const [purgeConfirm, setPurgeConfirm] = useState(false);
  const [previewing, setPreviewing] = useState<string | null>(null);

  // Use a ref to prevent auto-save on initial mount (which would overwrite fetched config with defaults)
  const isInitialMount = React.useRef(true);

  // 1. Initialize state from native Electron config source
  useEffect(() => {
    const loadConfig = async () => {
      try {
        let data;
        if (window.yukiAPI?.getSettings) {
          data = await window.yukiAPI.getSettings();
        } else {
          // Fallback for browser-only mode (testing)
          const resp = await fetch('/yuki.config.json');
          data = await resp.json();
        }

        if (!data) return;

        setAssistantName(data.assistant?.name || 'Yuki');
        setIdleLabel(data.assistant?.idle_label || 'SAY "HEY YUKI"');
        setGreeting(data.assistant?.greeting || '');
        setWakeWords(data.assistant?.wake_words?.join(', ') || 'hey yuki');

        setWhisperModel(data.whisper?.model_size || 'base');
        setSilenceThold(data.whisper?.silence_threshold || 300);
        setSilenceTime(data.whisper?.silence_timeout || 1.2);

        setGeminiModel(data.gemini?.model || 'gemini-2.0-flash');
        setGeminiFallback(data.gemini?.fallback_model || 'gemini-2.5-flash-lite');
        setOpenaiModel(data.openai?.model || 'gpt-4o-mini');
        setOllamaModel(data.ollama?.model || 'gemma3:4b');
        setOllamaUrl(data.ollama?.base_url || 'http://localhost:11434');
        setRouterOn(data.router?.enabled ?? true);

        setTtsProvider(data.tts?.provider || 'elevenlabs');
        setTtsVoice(data.assistant?.tts_voice || 'en-IN-NeerjaNeural');
        setElBudget(data.tts?.elevenlabs_char_budget || 300);
        setSpeechThold(data.vad?.speech_threshold || 0.65);
        setGainDb(data.tts?.gain_db ?? 1.0);
        setSpatialAudio(data.tts?.spatial_audio ?? false);
        setResamplingHq(data.tts?.resampling_hq ?? true);
        
        // Advanced
        setMaxRecordSecs(data.whisper?.max_record_secs ?? 12);
        setFuzzyThold(data.router?.fuzzy_threshold ?? 0.72);
        setLogFastPath(data.router?.log_fast_path ?? true);
        setCorrectionModel(data.ai_correction?.model ?? 'gemma3:4b');
        setUseLiteFallback(data.gemini?.use_lite_fallback ?? true);
        setBrainProvider(data.brain?.provider || 'auto');

        setBrowserPreferred(data.chrome?.preferred || 'chrome');
        setBrowserFallback(data.chrome?.fallback || 'brave');
        setBrowserAutoLaunch(data.chrome?.auto_launch ?? true);
        setBrowserCdpPort(data.chrome?.cdp_port ?? 9222);

        // Secrets (Ensures they load even if empty in default)
        setGoogleApiKey(data.gemini?.google_api_key || '');
        setOpenaiApiKey(data.openai?.openai_api_key || '');
        setElApiKey(data.tts?.elevenlabs_api_key || '');
        setElVoiceId(data.tts?.elevenlabs_voice_id || '');

        // Mark as hydrated - safe to save from now on
        setTimeout(() => { isHydrated.current = true; }, 100);
      } catch (err) {
        console.error("Critical: Could not load configuration", err);
      }
    };

    loadConfig();

    // Listen for dynamic voices list
    if (window.yukiAPI?.onState) {
      window.yukiAPI.onState((msg: any) => {
        if (msg.type === 'voices') {
          // If first chunk arrives, reset list. Subsequent chunks append.
          if (!msg.chunk || msg.chunk === 1) {
            setAvailableVoices(msg.data);
          } else {
            setAvailableVoices(prev => {
              // Deduplicate just in case 
              const existingIds = new Set(prev.map(v => v.id));
              const newVoices = msg.data.filter((v: any) => !existingIds.has(v.id));
              return [...prev, ...newVoices];
            });
          }
        }
      });
    }

    // Request voices immediately
    window.yukiAPI?.sendCommand?.({ type: 'get_voices' });

    return () => window.yukiAPI?.removeStateListener?.();
  }, []);

  // 2. Auto-save logic (Debounced)
  useEffect(() => {
    if (!isHydrated.current) return;

    const timer = setTimeout(() => {
      handleSave();
    }, 1500); // 1.5s debounce to prevent saving during fast typing

    return () => clearTimeout(timer);
  }, [
    assistantName, idleLabel, greeting, wakeWords,
    whisperModel, silenceThold, silenceTime, maxRecordSecs,
    geminiModel, geminiFallback, openaiModel, ollamaModel, ollamaUrl, routerOn, brainProvider,
    ttsProvider, ttsVoice, elBudget, speechThold, gainDb, spatialAudio, resamplingHq,
    googleApiKey, openaiApiKey, elApiKey, elVoiceId, useLiteFallback, correctionModel, fuzzyThold, logFastPath,
    browserPreferred, browserFallback, browserAutoLaunch, browserCdpPort
  ]);
  const handleVoiceSelect = (voiceId: string, provider: string) => {
    setTtsVoice(voiceId);
    if (provider === 'elevenlabs' || ttsProvider === 'elevenlabs') {
      setElVoiceId(voiceId);
    }
  };

  const handlePreviewVoice = (voiceId: string, provider: string) => {
    setPreviewing(voiceId);
    window.yukiAPI?.sendCommand?.({ 
      type: 'preview_voice', 
      voiceId, 
      provider 
    });
    // Visual feedback reset
    setTimeout(() => setPreviewing(null), 6000);
  };

  const handleSave = async () => {
    try {
      const payload = {
        assistant: {
          name: assistantName,
          wake_words: wakeWords.split(',').map((w: string) => w.trim()),
          greeting: greeting,
          idle_label: idleLabel,
          tts_voice: ttsVoice
        },
        gemini: { 
          model: geminiModel,
          fallback_model: geminiFallback,
          use_lite_fallback: useLiteFallback,
          google_api_key: googleApiKey
        },
        openai: { 
          model: openaiModel,
          openai_api_key: openaiApiKey
        },
        ollama: { model: ollamaModel, base_url: ollamaUrl },
        ai_correction: { model: correctionModel },
        router: { 
          enabled: routerOn,
          fuzzy_threshold: fuzzyThold,
          log_fast_path: logFastPath
        },
        vad: { speech_threshold: speechThold },
        whisper: {
          model_size: whisperModel,
          silence_threshold: silenceThold,
          silence_timeout: silenceTime,
          max_record_secs: maxRecordSecs
        },
        tts: { 
          provider: ttsProvider,
          elevenlabs_char_budget: elBudget,
          elevenlabs_api_key: elApiKey,
          elevenlabs_voice_id: elVoiceId,
          gain_db: gainDb,
          spatial_audio: spatialAudio,
          resampling_hq: resamplingHq
        },
        brain: {
          provider: brainProvider
        },
        chrome: {
          preferred: browserPreferred,
          fallback: browserFallback,
          auto_launch: browserAutoLaunch,
          cdp_port: browserCdpPort
        }
      };

      if (window.yukiAPI?.saveSettings) {
        window.yukiAPI.saveSettings(payload);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error(e);
    }
  };

  const handlePurgeMemory = () => {
    if (!purgeConfirm) {
      setPurgeConfirm(true);
      setTimeout(() => setPurgeConfirm(false), 3000);
    } else {
      window.yukiAPI?.purgeMemory?.();
      setPurgeConfirm(false);
    }
  };

  const scrollCarousel = (direction: 'left' | 'right') => {
    if (carouselRef.current) {
      const scrollAmount = 400;
      carouselRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth'
      });
    }
  };

  // ----------------------------------------------------
  // SUB-PANELS
  // ----------------------------------------------------

  const renderCore = () => (
    <div className="space-y-8 animate-in fade-in duration-700">
      {/* Premium Identity Header */}
      <div className="relative h-48 bg-surface-container-low border border-outline-variant/10 overflow-hidden group">
        <div className="absolute inset-0 dot-grid opacity-10"></div>
        <div className="absolute inset-0 bg-gradient-to-t from-surface-container-low via-transparent to-transparent"></div>
        
        {/* The Intelligence Orb (HUD Style) */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="relative w-24 h-24">
            <div className={`absolute inset-0 rounded-full border-2 border-primary/20 animate-breath`}></div>
            <div className={`absolute inset-2 rounded-full border border-primary/40 animate-spin transition-all duration-1000`} style={{ animationDuration: '8s' }}></div>
            <div className={`absolute inset-4 rounded-full bg-primary/10 backdrop-blur-sm border border-primary shadow-[0_0_30px_rgba(var(--primary-rgb),0.3)] flex items-center justify-center`}>
              <div className="font-headline font-black text-xs text-primary tracking-widest">{assistantName.substring(0,2).toUpperCase()}</div>
            </div>
            {/* Scanner Line */}
            <div className="absolute top-0 left-0 right-0 h-[1px] bg-primary/40 animate-pulse-slow"></div>
          </div>
        </div>

        <div className="absolute bottom-6 left-8">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse"></div>
            <h2 className="font-headline text-3xl font-black tracking-tighter text-on-surface uppercase">{assistantName}</h2>
          </div>
          <p className="font-label text-[10px] text-on-surface-variant uppercase tracking-[0.3em] font-medium opacity-60">Neural Kernel Revision 2.5.L // STATUS: ACTIVE</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-surface-container-low p-6 border border-outline-variant/10 relative overflow-hidden group">
          <div className="absolute top-0 left-0 w-1 h-full bg-primary/20"></div>
          <label className="font-label text-xs uppercase tracking-widest text-primary mb-2 block font-bold transition-transform group-hover:translate-x-1">Assistant Name</label>
          <input type="text" value={assistantName} onChange={e => setAssistantName(e.target.value)}
            className="w-full bg-surface-container-highest/50 border border-outline-variant/20 p-3 text-on-surface font-mono text-sm focus:border-primary outline-none transition-colors" />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/10 relative overflow-hidden group">
          <div className="absolute top-0 left-0 w-1 h-full bg-secondary/20"></div>
          <label className="font-label text-xs uppercase tracking-widest text-secondary mb-2 block font-bold transition-transform group-hover:translate-x-1">Idle State Label</label>
          <input type="text" value={idleLabel} onChange={e => setIdleLabel(e.target.value)}
            className="w-full bg-surface-container-highest/50 border border-outline-variant/20 p-3 text-on-surface font-mono text-sm focus:border-secondary outline-none transition-colors" />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/10 md:col-span-2 relative">
          <label className="font-label text-xs uppercase tracking-widest text-tertiary mb-2 block font-bold">Base Kernel Greeting</label>
          <input type="text" value={greeting} onChange={e => setGreeting(e.target.value)}
            className="w-full bg-surface-container-highest/50 border border-outline-variant/20 p-3 text-on-surface font-mono text-sm focus:border-tertiary outline-none transition-colors" />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/10 md:col-span-2 relative">
          <label className="font-label text-xs uppercase tracking-widest text-on-surface mb-4 block font-bold">Activation Keyphrases</label>
          <div className="flex flex-wrap gap-2 mb-4 min-h-[40px] p-2 bg-surface-container-highest/20 border border-dashed border-outline-variant/20">
            {wakeWords.split(',').map((word, idx) => {
              const trimmed = word.trim();
              if (!trimmed) return null;
              return (
                <div key={idx} className="bg-primary/10 border border-primary/30 px-3 py-1 flex items-center gap-2 group animate-in zoom-in duration-200">
                  <span className="font-label text-xs font-bold text-primary tracking-wide uppercase">{trimmed}</span>
                  <button 
                    onClick={() => {
                      const words = wakeWords.split(',').map(w => w.trim()).filter(w => w !== trimmed);
                      setWakeWords(words.join(', '));
                    }}
                    className="material-symbols-outlined text-[14px] text-primary/50 hover:text-error transition-colors"
                  >
                    close
                  </button>
                </div>
              );
            })}
            {wakeWords.trim() === '' && (
              <span className="font-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em] self-center ml-2">No keyphrases active</span>
            )}
          </div>
          <div className="flex gap-2">
            <input 
              type="text" 
              placeholder="+ ADD NEW PHRASE (ENTER)..."
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const val = (e.target as HTMLInputElement).value.trim().toLowerCase();
                  if (val && !wakeWords.includes(val)) {
                    setWakeWords(wakeWords ? `${wakeWords}, ${val}` : val);
                    (e.target as HTMLInputElement).value = '';
                  }
                }
              }}
              className="flex-grow bg-surface-container-highest/50 border border-outline-variant/20 p-3 text-on-surface font-mono text-xs focus:border-primary outline-none transition-colors" 
            />
          </div>
        </div>
      </div>

      <div className="pt-12 border-t border-outline-variant/10">
        <div className="bg-[#1a0505] p-8 border border-error/20 flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="space-y-1">
            <h3 className="font-headline font-bold text-error uppercase tracking-widest text-lg">Memory Vault Purge</h3>
            <p className="font-label text-xs text-on-surface-variant">Securely wipe all persistent cognitive context and user profiling data.</p>
          </div>
          <button 
            onClick={handlePurgeMemory} 
            className={`px-10 py-4 font-label text-xs font-bold uppercase tracking-widest transition-all duration-300 ${purgeConfirm ? 'bg-error text-on-error scale-105 shadow-[0_0_20px_rgba(244,67,54,0.4)]' : 'bg-surface-container-highest text-error border border-error/30 hover:bg-error/10 hover:border-error'}`}
          >
            {purgeConfirm ? 'SECURE ERASE INITIALIZED' : 'WIPE MEMORY'}
          </button>
        </div>
      </div>
    </div>
  );

  const renderThreads = () => (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h2 className="font-headline text-3xl font-bold tracking-tight text-on-surface uppercase mb-2">Listener Perception</h2>
        <p className="font-label text-sm text-on-surface-variant">Configure how Yuki hears and recognizes the boundaries of human speech.</p>
      </div>

      <div className="bg-surface-container-low p-8 border border-outline-variant/20 relative overflow-hidden group">
        <div className="absolute inset-0 dot-grid opacity-5"></div>
        <div className="relative z-10">
          <h3 className="font-label text-xs uppercase tracking-[0.2em] text-primary mb-6 font-bold flex items-center gap-3">
            <span className="w-2 h-2 bg-primary rounded-none rotate-45 animate-spin" style={{ animationDuration: '4s' }}></span>
            Neural Sensitivity Calibration
          </h3>
          
          <div className="h-24 bg-surface-container-highest/30 border border-outline-variant/10 relative overflow-hidden flex items-end gap-1 px-4 pb-4">
            {/* Simulated Waveform Bars */}
            {Array.from({ length: 48 }).map((_, i) => {
              const height = 10 + Math.random() * 40;
              return (
                <div key={i} className="flex-1 bg-primary/20 transition-all duration-500" 
                  style={{ height: `${height}%`, opacity: height > (speechThold * 100) ? 0.8 : 0.2 }}></div>
              );
            })}
            
            {/* Draggable Threshold Line Overlay */}
            <div className="absolute left-0 right-0 border-t border-error/60 z-20 pointer-events-none flex items-center justify-end px-4 transition-all duration-300"
              style={{ bottom: `${(speechThold * 100)}%` }}>
              <span className="font-label text-[7px] text-error bg-error/10 px-2 py-0.5 uppercase tracking-widest -translate-y-full border-l border-r border-error/20">Active Trigger: {speechThold.toFixed(2)}</span>
            </div>
            
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-t from-primary/10 to-transparent"></div>
          </div>
          <p className="font-label text-[9px] text-on-surface-variant mt-4 opacity-50 uppercase tracking-widest italic">Synchronize trigger bounds with ambient noise floor for optimal performance.</p>
        </div>
      </div>

      <div className="bg-surface-container-low p-6 border border-outline-variant/20">
        <h3 className="font-label text-xs uppercase tracking-widest text-primary mb-4 font-bold">Whisper Engine Model</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {WHISPER_MODELS.map(m => {
            const active = whisperModel === m.id;
            return (
              <div key={m.id} onClick={() => setWhisperModel(m.id)}
                className={`p-4 border cursor-pointer transition-colors ${active ? 'border-primary bg-primary/10' : 'border-outline-variant/20 bg-surface-container hover:border-primary/50'}`}>
                <div className={`font-headline font-bold text-lg ${active ? 'text-primary' : 'text-on-surface'}`}>{m.label}</div>
                <div className="font-label text-[10px] text-on-surface-variant mt-1">{m.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-surface-container-low p-6 border border-outline-variant/20">
          <div className="flex justify-between font-label text-xs uppercase tracking-widest mb-4">
            <span className="text-secondary font-bold">Silence Timeout (s)</span>
            <span className="text-on-surface">{silenceTime.toFixed(1)}s</span>
          </div>
          <input type="range" min="0.5" max="3.0" step="0.1" value={silenceTime} onChange={e => setSilenceTime(Number(e.target.value))} className="w-full" style={{ accentColor: '#7799ff' }} />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/20">
          <div className="flex justify-between font-label text-xs uppercase tracking-widest mb-4">
            <span className="text-tertiary font-bold">Noise Thold</span>
            <span className="text-on-surface">{silenceThold}</span>
          </div>
          <input type="range" min="100" max="800" value={silenceThold} onChange={e => setSilenceThold(Number(e.target.value))} className="w-full" style={{ accentColor: '#ff6f7e' }} />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/20 md:col-span-2">
          <div className="flex justify-between font-label text-xs uppercase tracking-widest mb-4">
            <span className="text-primary font-bold">Max Record Duration (s)</span>
            <span className="text-on-surface">{maxRecordSecs}s</span>
          </div>
          <input type="range" min="5" max="30" step="1" value={maxRecordSecs} onChange={e => setMaxRecordSecs(Number(e.target.value))} className="w-full" style={{ accentColor: '#8ff5ff' }} />
          <p className="font-label text-[8px] text-on-surface-variant mt-3 uppercase tracking-wider opacity-50 italic">Global cut-off safety for long voice descriptors.</p>
        </div>
      </div>
    </div>
  );

  const renderNeural = () => (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h2 className="font-headline text-3xl font-bold tracking-tight text-on-surface uppercase mb-2">Neural Linkage</h2>
        <p className="font-label text-sm text-on-surface-variant">Configure logic engines and fallback architectures.</p>
      </div>

      <div className="bg-surface-container-low p-6 border border-outline-variant/20 relative group">
        <label className="font-label text-xs uppercase tracking-[0.2em] text-primary mb-4 block font-bold">Primary Neural Path Mode</label>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { id: 'auto', label: 'Automatic', desc: 'Resilient Cascade' },
            { id: 'gemini', label: 'Gemini', desc: 'Google Flash' },
            { id: 'openai', label: 'OpenAI', desc: 'GPT-4o Mini' },
            { id: 'ollama', label: 'Local', desc: 'Host Native' }
          ].map(p => (
            <div key={p.id} onClick={() => setBrainProvider(p.id)}
              className={`p-4 border cursor-pointer transition-all ${brainProvider === p.id ? 'border-primary bg-primary/10' : 'border-outline-variant/20 bg-surface-container hover:border-primary/50'}`}>
              <div className={`font-headline font-bold text-sm ${brainProvider === p.id ? 'text-primary' : 'text-on-surface'}`}>{p.label}</div>
              <div className="font-label text-[9px] text-on-surface-variant mt-1 uppercase tracking-tighter">{p.desc}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8">
        {/* Gemini Selection */}
        <div className="relative group">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-primary/20 to-primary/5 rounded-none blur opacity-0 group-hover:opacity-100 transition duration-500" />
          <div className="relative bg-surface-container-low border border-outline-variant/10 p-8 flex flex-col md:flex-row gap-8 items-start">
            <div className="w-16 h-16 flex-shrink-0 bg-primary/10 flex items-center justify-center rounded-none border border-primary/20">
              <span className="material-symbols-outlined text-primary text-3xl">psychology</span>
            </div>
            
            <div className="flex-grow space-y-6 w-full">
              <div className="flex justify-between items-center">
                <div className="space-y-1">
                  <h3 className="font-headline text-lg font-bold text-on-surface uppercase tracking-wide">Google Gemini Configuration</h3>
                  <div className="flex items-center gap-2">
                    <div className={`h-1.5 w-1.5 rounded-full ${googleApiKey ? 'bg-primary shadow-[0_0_8px_var(--md-sys-color-primary)]' : 'bg-outline-variant'}`} />
                    <span className="font-label text-[10px] uppercase tracking-tighter text-on-surface-variant">
                      {googleApiKey ? 'Neural Link Ready' : 'Awaiting Credential'}
                    </span>
                  </div>
                </div>
                <a href="https://aistudio.google.com/app/apikey" target="_blank" className="font-label text-[10px] text-primary hover:underline uppercase tracking-widest font-bold">API Console</a>
              </div>

              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-lite'].map(m => (
                    <button key={m} onClick={() => setGeminiModel(m)}
                      className={`px-4 py-2 border font-mono text-[10px] transition-all ${geminiModel === m ? 'bg-primary border-primary text-background font-bold shadow-lg shadow-primary/20' : 'border-outline-variant/20 text-on-surface-variant hover:border-primary/50'}`}>
                      {m.toUpperCase()}
                    </button>
                  ))}
                  <div className={`px-2 py-1 flex items-center border ${!['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-lite'].includes(geminiModel) ? 'border-primary bg-primary/5' : 'border-outline-variant/20'}`}>
                     <input type="text" placeholder="CUSTOM..." value={!['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-lite'].includes(geminiModel) ? geminiModel : ''} 
                      onChange={e => setGeminiModel(e.target.value)}
                      className="bg-transparent border-none outline-none font-mono text-[10px] text-on-surface placeholder:text-on-surface-variant/30 w-24" />
                  </div>
                </div>

                <div className="relative flex items-center">
                  <input 
                    type={showGoogle ? "text" : "password"} 
                    value={googleApiKey} 
                    onChange={e => setGoogleApiKey(e.target.value)} 
                    placeholder="Paste Google AI Studio Key..."
                    className="w-full bg-surface-container-high/40 border border-outline-variant/10 p-4 font-mono text-xs text-on-surface focus:border-primary/50 outline-none transition-all placeholder:text-on-surface-variant/30" 
                  />
                  <button onClick={() => setShowGoogle(!showGoogle)} className="absolute right-4 text-on-surface-variant/50 hover:text-primary transition-colors">
                    <span className="material-symbols-outlined text-lg">{showGoogle ? 'visibility_off' : 'visibility'}</span>
                  </button>
                </div>
                
                <div className="pt-2">
                  <label className="font-label text-[9px] uppercase text-on-surface-variant font-bold block mb-2">Resilience Fallback</label>
                  <input type="text" value={geminiFallback} onChange={e => setGeminiFallback(e.target.value)} className="w-full bg-surface-container-highest/30 border border-outline-variant/10 p-2 text-on-surface font-mono text-[10px] outline-none focus:border-primary" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* OpenAI Card */}
        <div className="relative group">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-secondary/20 to-secondary/5 rounded-none blur opacity-0 group-hover:opacity-100 transition duration-500" />
          <div className="relative bg-surface-container-low border border-outline-variant/10 p-8 flex flex-col md:flex-row gap-8 items-start">
            <div className="w-16 h-16 flex-shrink-0 bg-secondary/10 flex items-center justify-center rounded-none border border-secondary/20">
              <span className="material-symbols-outlined text-secondary text-3xl">smart_toy</span>
            </div>
            
            <div className="flex-grow space-y-6 w-full">
              <div className="flex justify-between items-center">
                <div className="space-y-1">
                  <h3 className="font-headline text-lg font-bold text-on-surface uppercase tracking-wide">OpenAI Interface</h3>
                  <div className="flex items-center gap-2">
                    <div className={`h-1.5 w-1.5 rounded-full ${openaiApiKey ? 'bg-secondary shadow-[0_0_8px_var(--md-sys-color-secondary)]' : 'bg-outline-variant'}`} />
                    <span className="font-label text-[10px] uppercase tracking-tighter text-on-surface-variant">
                      {openaiApiKey ? 'Neural Link Ready' : 'Awaiting Credential'}
                    </span>
                  </div>
                </div>
                <a href="https://platform.openai.com/api-keys" target="_blank" className="font-label text-[10px] text-secondary hover:underline uppercase tracking-widest font-bold">API Console</a>
              </div>

              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {['gpt-4o-mini', 'gpt-4o', 'o1-mini'].map(m => (
                    <button key={m} onClick={() => setOpenaiModel(m)}
                      className={`px-4 py-2 border font-mono text-[10px] transition-all ${openaiModel === m ? 'bg-secondary border-secondary text-background font-bold shadow-lg shadow-secondary/20' : 'border-outline-variant/20 text-on-surface-variant hover:border-secondary/50'}`}>
                      {m.toUpperCase()}
                    </button>
                  ))}
                  <div className={`px-2 py-1 flex items-center border ${!['gpt-4o-mini', 'gpt-4o', 'o1-mini'].includes(openaiModel) ? 'border-secondary bg-secondary/5' : 'border-outline-variant/20'}`}>
                     <input type="text" placeholder="CUSTOM..." value={!['gpt-4o-mini', 'gpt-4o', 'o1-mini'].includes(openaiModel) ? openaiModel : ''} 
                      onChange={e => setOpenaiModel(e.target.value)}
                      className="bg-transparent border-none outline-none font-mono text-[10px] text-on-surface placeholder:text-on-surface-variant/30 w-24" />
                  </div>
                </div>

                <div className="relative flex items-center">
                  <input 
                    type={showOpenai ? "text" : "password"} 
                    value={openaiApiKey} 
                    onChange={e => setOpenaiApiKey(e.target.value)} 
                    placeholder="sk-..."
                    className="w-full bg-surface-container-high/40 border border-outline-variant/10 p-4 font-mono text-xs text-on-surface focus:border-secondary/50 outline-none transition-all placeholder:text-on-surface-variant/30" 
                  />
                  <button onClick={() => setShowOpenai(!showOpenai)} className="absolute right-4 text-on-surface-variant/50 hover:text-secondary transition-colors">
                    <span className="material-symbols-outlined text-lg">{showOpenai ? 'visibility_off' : 'visibility'}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Ollama Selection */}
        <div className="bg-surface-container-low p-6 border-l-4 border-tertiary space-y-6">
          <div>
            <label className="font-label text-xs uppercase text-tertiary font-bold tracking-widest">Ollama Local Native</label>
            <p className="font-label text-[10px] text-on-surface-variant mt-1">Host-resident intelligence (Offline capable).</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
             <div className="space-y-2">
               <label className="font-label text-[9px] uppercase text-on-surface-variant">Recommended Models</label>
               <div className="flex flex-wrap gap-2">
                 {['phi4', 'gemma3:4b', 'mistral', 'llama3.2'].map(m => (
                   <button key={m} onClick={() => setOllamaModel(m)}
                     className={`px-3 py-1.5 border font-mono text-[9px] transition-all ${ollamaModel === m ? 'bg-tertiary border-tertiary text-background font-bold' : 'border-outline-variant/10 text-on-surface-variant hover:border-tertiary/50'}`}>
                     {m.toUpperCase()}
                   </button>
                 ))}
               </div>
               <input type="text" value={ollamaModel} onChange={e => setOllamaModel(e.target.value)} className="w-full bg-surface-container-highest/30 border border-outline-variant/10 p-3 text-on-surface font-mono text-xs outline-none focus:border-tertiary transition-colors mt-2" placeholder="OR CUSTOM MODEL NAME..." />
             </div>
             <div className="space-y-2">
               <label className="font-label text-[9px] uppercase text-on-surface-variant">Connection Protocol</label>
               <input type="text" value={ollamaUrl} onChange={e => setOllamaUrl(e.target.value)} className="w-full bg-surface-container-highest/30 border border-outline-variant/10 p-3 text-on-surface font-mono text-xs outline-none focus:border-tertiary transition-colors" placeholder="URL (e.g. http://localhost:11434)" />
             </div>
          </div>
        </div>
      </div>

      <div className="bg-surface-container-low p-6 border border-outline-variant/20 flex items-center justify-between cursor-pointer hover:bg-surface-container" onClick={() => setRouterOn(!routerOn)}>
        <div>
          <div className="font-headline font-bold text-lg text-on-surface uppercase tracking-wider">Fast Path Router</div>
          <div className="font-label text-[10px] text-on-surface-variant">Bypass Neural processing for local OS intents (faster).</div>
        </div>
        <div className={`w-12 h-6 rounded-none flex items-center p-1 transition-colors ${routerOn ? 'bg-primary' : 'bg-surface-container-highest border border-outline-variant/50'}`}>
          <div className={`h-4 w-4 bg-background transition-transform ${routerOn ? 'translate-x-6' : 'translate-x-0'}`} />
        </div>
      </div>

      {/* Neural Logic Schematic */}
      <div className="bg-surface-container-low p-8 border border-outline-variant/20 relative overflow-hidden">
        <div className="absolute inset-0 dot-grid opacity-5"></div>
        <h3 className="font-label text-xs uppercase tracking-[0.2em] text-primary mb-10 font-bold flex items-center gap-3 relative z-10">
          <span className="w-2 h-2 bg-primary rounded-full animate-pulse"></span>
          Neural Logic Topology
        </h3>

        <div className="relative flex items-center justify-between gap-4 max-w-4xl mx-auto px-10 pb-4">
          {/* Connector Lines */}
          <div className="absolute top-1/2 left-0 right-0 h-[1px] bg-outline-variant/20 -translate-y-1/2"></div>
          
          {[
            { label: 'INPUT', icon: 'mic', color: 'on-surface-variant' },
            { label: 'ROUTER', icon: 'alt_route', color: 'primary' },
            { label: 'LLM CORE', icon: 'neurology', color: 'primary' },
            { label: 'SYNTHESIS', icon: 'record_voice_over', color: 'secondary' }
          ].map((node, i) => (
            <div key={node.label} className="relative z-10 flex flex-col items-center group">
              <div 
                className={`w-14 h-14 rounded-full bg-surface-container border border-outline-variant/40 flex items-center justify-center transition-all duration-500`}
                style={{ 
                  borderColor: i > 0 ? `var(--md-sys-color-${node.color})` : undefined,
                  boxShadow: `0 0 20px rgba(var(--${node.color}-rgb), 0.1)`
                }}
              >
                <span className={`material-symbols-outlined text-[24px]`} style={{ color: `var(--md-sys-color-${node.color})` }}>{node.icon}</span>
              </div>
              <div className="absolute -bottom-8 font-label text-[9px] uppercase tracking-widest text-on-surface-variant font-bold whitespace-nowrap">{node.label}</div>
              {i < 3 && (
                <div className="absolute left-[calc(100%+8px)] top-1/2 -translate-y-1/2 flex items-center gap-1 opacity-40">
                  <div className="w-1 h-1 rounded-full bg-primary/40"></div>
                  <div className="w-1 h-1 rounded-full bg-primary/40 animate-pulse"></div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-surface-container-low p-6 border border-outline-variant/20">
          <div className="flex justify-between font-label text-xs uppercase tracking-widest mb-4">
            <span className="text-primary font-bold">Router Fuzzy Thold</span>
            <span className="text-on-surface">{fuzzyThold.toFixed(2)}</span>
          </div>
          <input type="range" min="0.5" max="1.0" step="0.01" value={fuzzyThold} onChange={e => setFuzzyThold(Number(e.target.value))} className="w-full" style={{ accentColor: '#8ff5ff' }} />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/20 flex items-center justify-between cursor-pointer hover:bg-surface-container" onClick={() => setLogFastPath(!logFastPath)}>
          <div>
            <div className="font-label text-xs font-bold text-on-surface uppercase tracking-widest">Fast Path Logging</div>
            <div className="font-label text-[8px] text-on-surface-variant uppercase mt-1">Detailed routing telemetry.</div>
          </div>
          <div className={`w-10 h-5 rounded-none flex items-center p-1 transition-colors ${logFastPath ? 'bg-primary' : 'bg-surface-container-highest border border-outline-variant/50'}`}>
            <div className={`h-3 w-3 bg-background transition-transform ${logFastPath ? 'translate-x-5' : 'translate-x-0'}`} />
          </div>
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/20">
          <label className="font-label text-xs uppercase tracking-widest text-secondary font-bold mb-2 block">AI Correction Model</label>
          <input type="text" value={correctionModel} onChange={e => setCorrectionModel(e.target.value)} className="w-full bg-surface-container-highest border border-outline-variant/20 p-2 text-on-surface font-mono text-xs outline-none focus:border-secondary transition-colors" />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/20 flex items-center justify-between cursor-pointer hover:bg-surface-container" onClick={() => setUseLiteFallback(!useLiteFallback)}>
          <div>
            <div className="font-label text-xs font-bold text-on-surface uppercase tracking-widest">Use Lite Fallback</div>
            <div className="font-label text-[8px] text-on-surface-variant uppercase mt-1">Auto-switch to 2.5 Flash Lite on 429.</div>
          </div>
          <div className={`w-10 h-5 rounded-none flex items-center p-1 transition-colors ${useLiteFallback ? 'bg-primary' : 'bg-surface-container-highest border border-outline-variant/50'}`}>
            <div className={`h-3 w-3 bg-background transition-transform ${useLiteFallback ? 'translate-x-5' : 'translate-x-0'}`} />
          </div>
        </div>
      </div>
    </div>
  );


  const renderNexus = () => (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h2 className="font-headline text-3xl font-bold tracking-tight text-on-surface uppercase mb-2">Interface Nexus</h2>
        <p className="font-label text-sm text-on-surface-variant">Manage external research engines and neural connectivity bridges.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Browser Engine Selection */}
        <div className="bg-surface-container-low p-8 border border-outline-variant/20 relative overflow-hidden group">
          <div className="absolute inset-0 dot-grid opacity-5"></div>
          <h3 className="font-label text-xs uppercase tracking-[0.2em] text-primary mb-6 font-bold flex items-center gap-3">
            <span className="w-2 h-2 bg-primary animate-pulse"></span>
            Neural Research Engine
          </h3>
          
          <div className="grid grid-cols-2 gap-4">
            {[
              { id: 'chrome', label: 'Chrome', icon: 'globe', desc: 'Standard Engine' },
              { id: 'brave', label: 'Brave', icon: 'shield', desc: 'Secure Sandbox' }
            ].map(b => (
              <div key={b.id} onClick={() => setBrowserPreferred(b.id)}
                className={`p-6 border cursor-pointer transition-all flex flex-col items-center gap-4 ${browserPreferred === b.id ? 'border-primary bg-primary/10 shadow-[0_0_20px_rgba(var(--primary-rgb),0.1)]' : 'border-outline-variant/20 bg-surface-container hover:border-primary/50'}`}>
                <span className="material-symbols-outlined text-4xl" style={{ color: browserPreferred === b.id ? 'var(--md-sys-color-primary)' : 'var(--md-sys-color-on-surface-variant)' }}>{b.icon}</span>
                <div className="text-center">
                  <div className={`font-headline font-bold text-sm ${browserPreferred === b.id ? 'text-primary' : 'text-on-surface'}`}>{b.label.toUpperCase()}</div>
                  <div className="font-label text-[9px] text-on-surface-variant mt-1 uppercase tracking-tighter">{b.desc}</div>
                </div>
              </div>
            ))}
          </div>
          <p className="font-label text-[9px] text-on-surface-variant mt-6 opacity-50 uppercase tracking-widest italic leading-relaxed">
            Yuki uses these engines to perceive live web content. Isolated profiles are used to prevent session collisions.
          </p>
        </div>

        {/* Connectivity Control */}
        <div className="space-y-8">
          <div className="bg-surface-container-low p-6 border border-outline-variant/20 flex items-center justify-between cursor-pointer hover:bg-surface-container" onClick={() => setBrowserAutoLaunch(!browserAutoLaunch)}>
            <div>
              <div className="font-label text-xs font-bold text-on-surface uppercase tracking-widest">Autonomous Launch</div>
              <div className="font-label text-[8px] text-on-surface-variant uppercase mt-1">Initialize engine during kernel boot.</div>
            </div>
            <div className={`w-10 h-5 rounded-none flex items-center p-1 transition-colors ${browserAutoLaunch ? 'bg-primary' : 'bg-surface-container-highest border border-outline-variant/50'}`}>
              <div className={`h-3 w-3 bg-background transition-transform ${browserAutoLaunch ? 'translate-x-5' : 'translate-x-0'}`} />
            </div>
          </div>

          <div className="bg-surface-container-low p-6 border border-outline-variant/20 relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-secondary/20 to-secondary/5 blur opacity-0 group-hover:opacity-100 transition duration-500" />
            <div className="relative space-y-4">
              <label className="font-label text-xs uppercase tracking-widest text-secondary font-bold block">Neural Link Port (CDP)</label>
              <div className="flex gap-2">
                <input type="number" value={browserCdpPort} onChange={e => setBrowserCdpPort(Number(e.target.value))} 
                  className="flex-grow bg-surface-container-highest/50 border border-outline-variant/20 p-3 text-on-surface font-mono text-sm focus:border-secondary outline-none transition-colors" />
                <div className="bg-secondary/10 px-4 flex items-center border border-secondary/20">
                  <span className="font-mono text-[10px] text-secondary font-bold">TCP</span>
                </div>
              </div>
              <p className="font-label text-[8px] text-on-surface-variant uppercase tracking-widest opacity-60">
                Communication bridge for agentic navigation tasks. Default: 9222.
              </p>
            </div>
          </div>

          <div className="bg-surface-container-low p-6 border border-outline-variant/20">
            <label className="font-label text-xs uppercase tracking-widest text-on-surface-variant font-bold mb-3 block">Resilience Fallback</label>
            <div className="flex items-center gap-4">
               <select value={browserFallback} onChange={e => setBrowserFallback(e.target.value)}
                className="w-full bg-surface-container-highest border border-outline-variant/20 p-3 text-on-surface font-label text-xs outline-none focus:border-primary transition-colors appearance-none">
                <option value="chrome">CHROME CORE</option>
                <option value="brave">BRAVE SHIELD</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Interface Logic Schematic (Nexus Style) */}
      <div className="bg-[#0a0a0f] p-10 border border-primary/20 relative overflow-hidden">
        <div className="absolute inset-0 grid grid-cols-6 grid-rows-4 opacity-5 pointer-events-none">
          {Array.from({ length: 24 }).map((_, i) => (
            <div key={i} className="border border-primary/10"></div>
          ))}
        </div>
        
        <div className="relative z-10 flex flex-col items-center">
          <div className="w-12 h-12 rounded-full border border-primary/40 bg-primary/5 flex items-center justify-center animate-pulse mb-6">
            <span className="material-symbols-outlined text-primary">hub</span>
          </div>
          <h3 className="font-headline text-lg font-black text-primary tracking-[0.3em] uppercase mb-1">Nexus Bridge</h3>
          <p className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest mb-10 opacity-60 italic">Multi-Engine Orchestration Layer</p>
          
          <div className="flex items-center gap-12">
            <div className="flex flex-col items-center gap-2">
              <div className="w-10 h-10 border border-outline-variant/30 flex items-center justify-center text-on-surface-variant">
                <span className="material-symbols-outlined">browser_updated</span>
              </div>
              <span className="font-label text-[8px] uppercase tracking-tighter">Playwright API</span>
            </div>
            <div className="w-12 h-[1px] bg-gradient-to-r from-transparent via-primary/40 to-transparent"></div>
            <div className="flex flex-col items-center gap-2">
              <div className="w-10 h-10 border border-primary/40 rounded-full flex items-center justify-center text-primary bg-primary/10">
                <span className="material-symbols-outlined animate-spin" style={{ animationDuration: '10s' }}>settings_heart</span>
              </div>
              <span className="font-label text-[8px] uppercase tracking-tighter text-primary">Yuki Logic</span>
            </div>
            <div className="w-12 h-[1px] bg-gradient-to-r from-transparent via-secondary/40 to-transparent"></div>
            <div className="flex flex-col items-center gap-2">
              <div className="w-10 h-10 border border-outline-variant/30 flex items-center justify-center text-on-surface-variant">
                <span className="material-symbols-outlined">terminal</span>
              </div>
              <span className="font-label text-[8px] uppercase tracking-tighter">CDP Bridge</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderConfig = () => (
    <div className="space-y-12 animate-in fade-in duration-500">
      {/* Section A: Provider Selector */}
      <section>
        <div className="mb-6">
          <h2 className="font-headline text-3xl font-bold tracking-tight text-on-surface mb-2 uppercase">Neural Providers</h2>
          <p className="font-label text-sm text-on-surface-variant">Select source architecture for vocal synthesis.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-1">
          {/* Provider 1: Edge-TTS */}
          <div onClick={() => setTtsProvider('edge-tts')}
            className={`bg-surface-container-low p-6 border-l-2 cursor-pointer transition-opacity ${ttsProvider === 'edge-tts' ? 'border-primary' : 'border-outline-variant/20 opacity-60 hover:opacity-100'}`}>
            <div className="flex justify-between items-start mb-8">
              <div className={`font-label text-xs font-bold ${ttsProvider === 'edge-tts' ? 'text-primary' : 'text-on-surface-variant'}`}>EDGE-TTS</div>
              <span className="material-symbols-outlined text-primary">{ttsProvider === 'edge-tts' ? 'check_circle' : 'radio_button_unchecked'}</span>
            </div>
            <div className="space-y-4">
              <div className="flex justify-between font-label text-[10px]">
                <span className="text-on-surface-variant">API USAGE</span>
                <span className="text-primary">FREE</span>
              </div>
              <div className="h-[2px] bg-surface-container-highest w-full overflow-hidden">
                <div className="h-full bg-primary w-[100%]"></div>
              </div>
            </div>
          </div>
          {/* Provider 2: ElevenLabs */}
          <div onClick={() => setTtsProvider('elevenlabs')}
            className={`bg-surface-container-low p-6 border-l-2 cursor-pointer transition-opacity ${ttsProvider === 'elevenlabs' ? 'border-secondary' : 'border-outline-variant/20 opacity-60 hover:opacity-100'}`}>
            <div className="flex justify-between items-start mb-8">
              <div className={`font-label text-xs font-bold ${ttsProvider === 'elevenlabs' ? 'text-secondary' : 'text-on-surface-variant'}`}>ELEVENLABS</div>
              <span className="material-symbols-outlined text-secondary">{ttsProvider === 'elevenlabs' ? 'check_circle' : 'radio_button_unchecked'}</span>
            </div>
            <div className="space-y-4">
              <div className="flex justify-between font-label text-[10px]">
                <span className="text-on-surface-variant">CHAR LIMIT</span>
                <span className="text-secondary">{elBudget}</span>
              </div>
              <div className="h-[2px] bg-surface-container-highest w-full overflow-hidden">
                <div className="h-full bg-secondary" style={{ width: `${(elBudget / 1000) * 100}%` }}></div>
              </div>
            </div>
          </div>
          {/* Provider 3: Pyttsx3 */}
          <div onClick={() => setTtsProvider('pyttsx3')}
            className={`bg-surface-container-low p-6 border-l-2 cursor-pointer transition-opacity ${ttsProvider === 'pyttsx3' ? 'border-tertiary' : 'border-outline-variant/20 opacity-60 hover:opacity-100'}`}>
            <div className="flex justify-between items-start mb-8">
              <div className={`font-label text-xs font-bold ${ttsProvider === 'pyttsx3' ? 'text-tertiary' : 'text-on-surface-variant'}`}>PYTTSX3</div>
              <span className="material-symbols-outlined text-tertiary">{ttsProvider === 'pyttsx3' ? 'check_circle' : 'radio_button_unchecked'}</span>
            </div>
            <div className="space-y-4">
              <div className="flex justify-between font-label text-[10px]">
                <span className="text-on-surface-variant">CPU LOAD</span>
                <span className="text-tertiary">OFFLINE</span>
              </div>
              <div className="h-[2px] bg-surface-container-highest w-full overflow-hidden">
                <div className="h-full bg-tertiary w-[20%]"></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Section B: Vocal Entities (Hybrid UI) */}
      <section className="space-y-12">
        {/* B1: Featured Identities (Premium Cards) */}
        <div>
          <div className="mb-6">
            <h2 className="font-headline text-2xl font-bold tracking-tight text-primary mb-1 uppercase">Neural Identities</h2>
            <p className="font-label text-xs text-on-surface-variant">Primary high-fidelity vocal configurations.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { id: 'en-IN-NeerjaNeural', name: 'YUKI-01', desc: 'SYMPATHETIC / FEMALE', color: 'primary', img: 'https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?q=80&w=600&auto=format&fit=crop' },
              { id: 'en-US-GuyNeural', name: 'NOVA-CORE', desc: 'AUTHORITATIVE / MALE', color: 'secondary', img: 'https://images.unsplash.com/photo-1614741118887-7a4ee193a5fa?q=80&w=600&auto=format&fit=crop' },
              { id: 'en-GB-SoniaNeural', name: 'PULSE-B', desc: 'TECHNICAL / FEMALE', color: 'tertiary', img: 'https://images.unsplash.com/photo-1558591710-4b4a1ae0f04d?q=80&w=600&auto=format&fit=crop' }
            ].map(identity => {
              // Smart check: matching is selected if either ttsVoice matches OR 
              // (if elevenlabs is active) elVoiceId matches this identity
              const isSelected = ttsProvider === 'elevenlabs' 
                ? elVoiceId === identity.id 
                : ttsVoice === identity.id;
              const borderColors: Record<string, string> = { "primary": "border-primary", "secondary": "border-secondary", "tertiary": "border-tertiary" };
              const textColors: Record<string, string> = { "primary": "text-primary", "secondary": "text-secondary", "tertiary": "text-tertiary" };

              return (
                <div key={identity.id} onClick={() => handleVoiceSelect(identity.id, 'edge-tts')}
                  className={`group relative bg-surface-container-low border transition-all duration-300 cursor-pointer overflow-hidden ${isSelected ? `${borderColors[identity.color]} shadow-lg shadow-${identity.color}/10` : 'border-outline-variant/30 hover:border-surface-variant'}`}>
                  <div className="aspect-[16/10] relative overflow-hidden bg-surface-container-highest">
                    <img src={identity.img} className={`w-full h-full object-cover transition-all duration-700 ${isSelected ? 'opacity-60 scale-105' : 'opacity-30 group-hover:opacity-40 group-hover:scale-105'}`} />
                    <div className="absolute inset-0 bg-gradient-to-t from-surface-container-low via-transparent to-transparent"></div>
                    <div className="absolute bottom-4 left-4">
                      <div className={`font-headline font-bold text-xl leading-none ${textColors[identity.color]}`}>{identity.name}</div>
                      <div className="font-label text-[10px] text-on-surface-variant mt-1 tracking-widest uppercase">{identity.desc}</div>
                    </div>
                    
                    <div className="absolute top-4 right-4 flex items-center gap-2">
                       <button 
                        onClick={(e) => { e.stopPropagation(); handlePreviewVoice(identity.id, 'edge-tts'); }}
                        className={`w-8 h-8 rounded-full flex items-center justify-center backdrop-blur-md border transition-all ${previewing === identity.id ? 'bg-primary border-primary animate-pulse text-background' : 'bg-surface-container/60 border-outline-variant/30 text-on-surface hover:bg-primary/20 hover:border-primary'}`}
                      >
                        <span className="material-symbols-outlined text-sm">{previewing === identity.id ? 'graphic_eq' : 'play_arrow'}</span>
                      </button>
                      {isSelected && (
                        <div className={`animate-in fade-in zoom-in duration-300`}>
                          <span className={`material-symbols-outlined ${textColors[identity.color]} fill-1`}>verified</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="p-3">
                    <div className={`text-center py-1 font-label text-[9px] tracking-[0.2em] font-bold border transition-colors ${isSelected ? `bg-${identity.color}/10 ${borderColors[identity.color]} ${textColors[identity.color]}` : 'bg-surface-bright border-outline-variant/30 text-on-surface-variant'}`}>
                      {isSelected ? 'ACTIVE NEURAL PATH' : 'STANDBY MODE'}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* B2: Extended Library (Horizontal Carousel) */}
        <div className="relative group/library">
          <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between border-b border-outline-variant/10 pb-4 gap-4">
            <div>
              <h2 className="font-headline text-xl font-bold tracking-tight text-on-surface mb-1 uppercase">Extended Library</h2>
              <p className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest">{availableVoices.filter(v => v.gender.toLowerCase() === genderFilter).length} {genderFilter} Models Available</p>
            </div>
            
            <div className="flex flex-col md:flex-row items-center gap-4">
              {/* Slider Style Multi-Toggle */}
              <div className="bg-surface-container-low p-1 border border-outline-variant/20 flex relative w-48">
                <div className={`absolute top-1 bottom-1 w-[50%] bg-primary/20 border border-primary/30 transition-all duration-300 ease-out`}
                  style={{ left: genderFilter === 'female' ? '4px' : 'calc(50% - 4px)' }} />
                <button onClick={() => { setGenderFilter('female'); carouselRef.current?.scrollTo({ left: 0 }); }} className={`flex-1 relative z-10 py-1.5 font-label text-[9px] uppercase tracking-widest transition-colors ${genderFilter === 'female' ? 'text-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>Female</button>
                <button onClick={() => { setGenderFilter('male'); carouselRef.current?.scrollTo({ left: 0 }); }} className={`flex-1 relative z-10 py-1.5 font-label text-[9px] uppercase tracking-widest transition-colors ${genderFilter === 'male' ? 'text-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>Male</button>
              </div>

              <div className="w-full md:w-64 bg-surface-container-low border border-outline-variant/30 px-3 py-1.5 flex items-center gap-3 focus-within:border-primary transition-colors">
                <span className="material-symbols-outlined text-on-surface-variant scale-75">search</span>
                <input type="text" placeholder="FILTER MODELS..." value={voiceSearch} onChange={e => setVoiceSearch(e.target.value)}
                  className="bg-transparent border-none outline-none font-label text-[10px] text-on-surface uppercase tracking-widest w-full placeholder:text-on-surface-variant/40" />
              </div>
            </div>
          </div>

          {/* Left/Right Navigation Arrows */}
          <button onClick={() => scrollCarousel('left')} 
            className="absolute left-4 top-[65%] -translate-y-1/2 z-20 w-10 h-10 bg-surface-container/60 backdrop-blur-md border border-outline-variant/30 rounded-full flex items-center justify-center text-on-surface opacity-0 group-hover/library:opacity-100 transition-all hover:bg-primary/20 hover:border-primary">
            <span className="material-symbols-outlined">chevron_left</span>
          </button>
          <button onClick={() => scrollCarousel('right')} 
            className="absolute right-4 top-[65%] -translate-y-1/2 z-20 w-10 h-10 bg-surface-container/60 backdrop-blur-md border border-outline-variant/30 rounded-full flex items-center justify-center text-on-surface opacity-0 group-hover/library:opacity-100 transition-all hover:bg-primary/20 hover:border-primary">
            <span className="material-symbols-outlined">chevron_right</span>
          </button>

          {/* Left/Right Fade Indicators */}
          <div className="absolute left-0 top-24 bottom-0 w-12 bg-gradient-to-r from-surface-container-low/80 to-transparent z-10 pointer-events-none opacity-0 group-hover/library:opacity-100 transition-opacity"></div>
          <div className="absolute right-0 top-24 bottom-0 w-12 bg-gradient-to-l from-surface-container-low/80 to-transparent z-10 pointer-events-none opacity-0 group-hover/library:opacity-100 transition-opacity"></div>

          <div ref={carouselRef} className="flex flex-row overflow-x-auto gap-4 pb-6 hide-scrollbar snap-x snap-mandatory scroll-smooth">
            {availableVoices
              .filter(v => ![ 'en-IN-NeerjaNeural', 'en-US-GuyNeural', 'en-GB-SoniaNeural' ].includes(v.id))
              .filter(v => {
                const matchesSearch = v.name.toLowerCase().includes(voiceSearch.toLowerCase()) || 
                                     v.id.toLowerCase().includes(voiceSearch.toLowerCase()) || 
                                     v.locale.toLowerCase().includes(voiceSearch.toLowerCase());
                const matchesGender = v.gender.toLowerCase() === genderFilter;
                return matchesSearch && matchesGender;
              })
              .map(voice => {
                const isSelected = ttsProvider === 'elevenlabs'
                  ? elVoiceId === voice.id
                  : ttsVoice === voice.id;

                return (
                  <div key={voice.id} onClick={() => handleVoiceSelect(voice.id, voice.provider)}
                    className={`min-width-[240px] flex-shrink-0 snap-start p-5 border transition-all duration-300 cursor-pointer flex flex-col justify-between h-[160px] relative overflow-hidden ${isSelected ? 'border-primary bg-primary/10' : 'border-outline-variant/20 bg-surface-container-low hover:border-primary/40'}`}>
                    
                    {/* Visual Decor */}
                    <div className="absolute -right-4 -top-4 w-12 h-12 border border-outline-variant/10 rotate-45 pointer-events-none"></div>
                    
                    <div className="relative z-10">
                      {/* Actions Area */}
                      <div className="flex items-center justify-between relative z-10">
                        <div className={`font-headline font-bold text-xs uppercase tracking-wider ${isSelected ? 'text-primary' : 'text-on-surface'}`}>{voice.name}</div>
                        <div className="flex items-center gap-2">
                          <button 
                            onClick={(e) => { e.stopPropagation(); handlePreviewVoice(voice.id, voice.provider); }}
                            className={`w-8 h-8 rounded-full flex items-center justify-center border transition-all ${previewing === voice.id ? 'bg-primary border-primary animate-pulse text-background' : 'bg-surface-container-highest/50 border-outline-variant/20 text-on-surface-variant hover:text-primary hover:border-primary/50'}`}
                          >
                            <span className="material-symbols-outlined text-[16px]">{previewing === voice.id ? 'graphic_eq' : 'play_arrow'}</span>
                          </button>
                          {isSelected && <span className="material-symbols-outlined text-primary text-sm fill-1">verified</span>}
                        </div>
                      </div>
                      <div className="font-label text-[8px] text-on-surface-variant uppercase tracking-[0.2em]">{voice.locale.split('-')[1]} // {voice.gender}</div>
                    </div>

                    <div className="relative z-10 mt-auto pt-4 border-t border-outline-variant/10">
                      <div className={`font-mono text-[8px] truncate ${isSelected ? 'text-primary/70' : 'text-on-surface-variant/40'}`}>{voice.id}</div>
                      <div className={`mt-2 flex gap-1`}>
                        <div className={`flex-1 py-1 text-center font-label text-[7px] uppercase tracking-widest border ${isSelected ? 'bg-primary/20 border-primary text-primary' : 'bg-surface-bright border-outline-variant/30 text-on-surface-variant'}`}>
                          {isSelected ? 'ACTIVE_NEURAL' : 'STANDBY'}
                        </div>
                        {voice.isPremium && (
                          <div className="bg-tertiary/10 border border-tertiary/30 text-tertiary px-2 py-1 font-label text-[6px] uppercase tracking-tighter flex items-center shrink-0">
                            PREMIUM
                          </div>
                        )}
                        {voice.isMultilingual && (
                          <div className="bg-secondary/10 border border-secondary/30 text-secondary px-2 py-1 font-label text-[6px] uppercase tracking-tighter flex items-center shrink-0">
                            MULTILINGUAL
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            
            {availableVoices.length === 0 && (
              <div className="w-full py-20 text-center border border-dashed border-outline-variant/20 flex-shrink-0">
                <div className="animate-pulse font-label text-[9px] text-on-surface-variant uppercase tracking-[0.3em]">Querying Global Neural Registry...</div>
              </div>
            )}

            {availableVoices.length > 0 && availableVoices.filter(v => ![ 'en-IN-NeerjaNeural', 'en-US-GuyNeural', 'en-GB-SoniaNeural' ].includes(v.id)).filter(v => v.gender.toLowerCase() === genderFilter).length === 0 && (
              <div className="w-full py-20 text-center flex-shrink-0">
                <div className="font-label text-[9px] text-on-surface-variant uppercase tracking-widest">No models match criteria in this category.</div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Section C: Technical Sliders */}
      <section className="bg-surface-container-low p-8 border border-outline-variant/20 relative overflow-hidden">
        <div className="absolute top-0 right-0 p-4 font-label text-[8px] text-tertiary/30 rotate-90 origin-top-right select-none">VOCAL_CORE_V2.0</div>
        <div className="mb-10 flex justify-between items-start">
          <div>
            <h2 className="font-headline text-3xl font-bold text-on-surface uppercase tracking-tight">Vocal Synthesis Engine</h2>
            <p className="font-label text-xs text-on-surface-variant mt-2">Manage neural voice identities and bio-synthesis parameters.</p>
          </div>
        </div>

        {/* ElevenLabs Secret Card */}
        <div className="mb-12 relative group">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-tertiary/20 to-tertiary/5 rounded-none blur opacity-0 group-hover:opacity-100 transition duration-500" />
          <div className="relative bg-surface-container border border-outline-variant/10 p-8 flex flex-col md:flex-row gap-8 items-start">
            <div className="w-16 h-16 flex-shrink-0 bg-tertiary/10 flex items-center justify-center rounded-none border border-tertiary/20">
              <span className="material-symbols-outlined text-tertiary text-3xl">waves</span>
            </div>
            
            <div className="flex-grow space-y-6 w-full">
              <div className="flex justify-between items-center">
                <div className="space-y-1">
                  <h3 className="font-headline text-lg font-bold text-on-surface uppercase tracking-wide">ElevenLabs Premium Config</h3>
                  <div className="flex items-center gap-2">
                    <div className={`h-1.5 w-1.5 rounded-full ${elApiKey ? 'bg-tertiary shadow-[0_0_8px_var(--md-sys-color-tertiary)]' : 'bg-outline-variant'}`} />
                    <span className="font-label text-[10px] uppercase tracking-tighter text-on-surface-variant">
                      {elApiKey ? 'Synthesis Link Ready' : 'Awaiting Credential'}
                    </span>
                  </div>
                </div>
                <a href="https://elevenlabs.io/app/settings/api-keys" target="_blank" className="font-label text-[10px] text-tertiary hover:underline uppercase tracking-widest font-bold">API Console</a>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="relative flex items-center">
                  <input 
                    type={showEl ? "text" : "password"} 
                    value={elApiKey} 
                    onChange={e => setElApiKey(e.target.value)} 
                    placeholder="API Key..."
                    className="w-full bg-surface-container-high/40 border border-outline-variant/10 p-4 font-mono text-xs text-on-surface focus:border-tertiary/50 outline-none transition-all placeholder:text-on-surface-variant/30" 
                  />
                  <button onClick={() => setShowEl(!showEl)} className="absolute right-4 text-on-surface-variant/50 hover:text-tertiary transition-colors">
                    <span className="material-symbols-outlined text-lg">{showEl ? 'visibility_off' : 'visibility'}</span>
                  </button>
                </div>
                <div className="space-y-2">
                  <input type="text" value={elVoiceId} onChange={e => setElVoiceId(e.target.value)} placeholder="Active Voice Signature (Manual ID)..." className="w-full bg-surface-container-high/40 border border-outline-variant/10 p-4 font-mono text-xs text-on-surface focus:border-tertiary/50 outline-none transition-all placeholder:text-on-surface-variant/30" />
                  <div className="px-2 font-label text-[8px] text-tertiary/60 uppercase tracking-widest">Master Signature for Synthesis</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
          <div className="space-y-8">
            <div className="space-y-4">
              <div className="flex justify-between font-label text-xs uppercase tracking-widest">
                <span className="text-primary font-bold">Resampling Quality</span>
                <span className="text-on-surface">{speechThold.toFixed(2)}</span>
              </div>
              <div className="relative flex items-center">
                <input className="w-full" max="0.95" min="0.1" step="0.05" type="range" value={speechThold} onChange={e => setSpeechThold(Number(e.target.value))} />
                <div className="absolute -bottom-6 flex justify-between w-full font-label text-[8px] text-on-surface-variant">
                  <span>SENSITIVE</span>
                  <span>NORMAL</span>
                  <span>STRICT</span>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between font-label text-xs uppercase tracking-widest">
                <span className="text-secondary font-bold">ElevenLabs Budget</span>
                <span className="text-on-surface">{elBudget} CHARS</span>
              </div>
              <div className="relative flex items-center">
                <input className="w-full" max="1000" min="50" step="50" style={{ accentColor: '#7799ff' }} type="range" value={elBudget} onChange={e => setElBudget(Number(e.target.value))} />
                <div className="absolute -bottom-6 flex justify-between w-full font-label text-[8px] text-on-surface-variant">
                  <span>STRICT</span>
                  <span>BALANCED</span>
                  <span>MAX</span>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-8">
            <div className="space-y-4">
              <div className="flex justify-between font-label text-xs uppercase tracking-widest">
                <span className="text-tertiary font-bold">Base Volume Gain</span>
                <span className="text-on-surface">{gainDb.toFixed(1)}x</span>
              </div>
              <div className="relative flex items-center">
                <input className="w-full" max="2.0" min="0.1" step="0.1" style={{ accentColor: '#ff6f7e' }} type="range" value={gainDb} onChange={e => setGainDb(Number(e.target.value))} />
                <div className="absolute -bottom-6 flex justify-between w-full font-label text-[8px] text-on-surface-variant">
                  <span>MUTED</span>
                  <span>NORMAL</span>
                  <span>BOOST</span>
                </div>
              </div>
            </div>
            <div className="pt-4 grid grid-cols-2 gap-2">
              <div onClick={() => setSpatialAudio(!spatialAudio)}
                className={`p-3 flex items-center gap-3 cursor-pointer border transition-colors ${spatialAudio ? 'bg-primary/20 border-primary' : 'bg-surface-container border-transparent hover:border-outline-variant'}`}>
                <div className={`w-2 h-2 ${spatialAudio ? 'bg-primary animate-pulse' : 'bg-on-surface-variant/30'}`}></div>
                <div className="font-label text-[10px] uppercase text-on-surface-variant">Spatial Audio: {spatialAudio ? 'ON' : 'OFF'}</div>
              </div>
              <div onClick={() => setResamplingHq(!resamplingHq)}
                className={`p-3 flex items-center gap-3 cursor-pointer border transition-colors ${resamplingHq ? 'bg-secondary/20 border-secondary' : 'bg-surface-container border-transparent hover:border-outline-variant'}`}>
                <div className={`w-2 h-2 ${resamplingHq ? 'bg-secondary animate-pulse' : 'bg-on-surface-variant/30'}`}></div>
                <div className="font-label text-[10px] uppercase text-on-surface-variant">Resampling: {resamplingHq ? 'HQ' : 'STD'}</div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );

  return (
    <div className="flex flex-col h-full w-full relative z-10 animate-fade-in bg-transparent">
      {/* Horizontal Config Navigation Pill Bar */}
      <div className="px-8 pt-8 pb-4 shrink-0 border-b border-outline-variant/10">
        <div className="flex space-x-6 overflow-x-auto hide-scrollbar">
          {[
            { id: 'identity', label: 'Identity' },
            { id: 'intelligence', label: 'Intelligence' },
            { id: 'voices', label: 'Voices' },
            { id: 'listener', label: 'Listener' },
            { id: 'nexus', label: 'Nexus' }
          ].map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id as Tab)}
              className={`pb-4 border-b-2 font-label text-xs font-bold tracking-widest uppercase transition-colors whitespace-nowrap ${activeTab === tab.id ? 'border-primary text-primary' : 'border-transparent text-secondary opacity-60 hover:opacity-100 hover:text-on-surface'}`}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Settings Content Area */}
      <div className="flex-1 overflow-y-auto p-8 relative hide-scrollbar">
        <div className="max-w-5xl mx-auto pb-20">
          {activeTab === 'identity' && renderCore()}
          {activeTab === 'intelligence' && renderNeural()}
          { activeTab === 'voices' && renderConfig()}
          { activeTab === 'listener' && renderThreads()}
          { activeTab === 'nexus' && renderNexus()}
        </div>
      </div>

      {/* Fixed Status Container at Top Right */}
      <div className="absolute top-6 right-8 flex items-center gap-4 z-50">
        <span className={`text-[10px] font-label font-bold uppercase tracking-widest text-primary transition-opacity duration-300 ${saved ? 'opacity-100' : 'opacity-0'}`}>
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse"></span>
            NEURAL SYNC COMPLETED
          </span>
        </span>
      </div>
    </div>
  );
}
