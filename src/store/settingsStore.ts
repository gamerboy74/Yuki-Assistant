import { create } from 'zustand';

interface SettingsState {
  // Navigation
  activeTab: string;
  saved: boolean;
  isHydrated: boolean;

  // Identity
  assistantName: string;
  idleLabel: string;
  greeting: string;
  wakeWords: string;

  // Listener (Whisper/VAD)
  whisperModel: string;
  silenceThold: number;
  silenceTime: number;
  maxRecordSecs: number;
  speechThold: number;

  // Neural (AI)
  geminiModel: string;
  geminiFallback: string;
  geminiProvider: 'google_ai_studio' | 'vertex_ai';
  vertexProjectId: string;
  vertexLocation: string;
  useLiteFallback: boolean;
  openaiModel: string;
  ollamaModel: string;
  ollamaUrl: string;
  brainProvider: string;
  routerOn: boolean;
  fuzzyThold: number;
  logFastPath: boolean;
  correctionModel: string;

  // Voices (TTS)
  ttsProvider: string;
  ttsVoice: string;
  elBudget: number;
  gainDb: number;
  ttsSpeed: number;
  spatialAudio: boolean;
  resamplingHq: boolean;

  // Secrets
  googleApiKey: string;
  vertexKeyString: string;
  openaiApiKey: string;
  elApiKey: string;
  elVoiceId: string;

  // Nexus (Chrome)
  browserPreferred: string;
  browserFallback: string;
  browserAutoLaunch: boolean;
  browserCdpPort: number;

  // Dynamic
  availableVoices: any[];
  voiceSearch: string;
  genderFilter: 'female' | 'male';
  previewing: string | null;
  availableGeminiModels: string[];

  // Actions
  setTab: (tab: string) => void;
  updateSetting: (key: keyof SettingsState, value: any) => void;
  loadConfig: () => Promise<void>;
  saveConfig: () => Promise<void>;
  setVoices: (voices: any[], chunk?: number) => void;
  purgeMemory: () => void;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  activeTab: 'identity',
  saved: false,
  isHydrated: false,

  assistantName: 'Yuki',
  idleLabel: 'SAY "HEY YUKI"',
  greeting: '',
  wakeWords: 'hey yuki',

  whisperModel: 'base',
  silenceThold: 300,
  silenceTime: 1.2,
  maxRecordSecs: 12,
  speechThold: 0.65,

  geminiModel: 'gemini-2.5-flash',
  geminiFallback: 'gemini-2.5-flash-lite',
  geminiProvider: 'google_ai_studio',
  vertexProjectId: '',
  vertexLocation: 'us-central1',
  useLiteFallback: true,
  openaiModel: 'gpt-4o-mini',
  ollamaModel: 'gemma3:4b',
  ollamaUrl: 'http://localhost:11434',
  brainProvider: 'auto',
  routerOn: true,
  fuzzyThold: 0.72,
  logFastPath: true,
  correctionModel: 'gemma3:4b',

  ttsProvider: 'edge-tts',
  ttsVoice: 'en-US-AvaMultilingualNeural',
  elBudget: 2000,
  gainDb: 1.0,
  ttsSpeed: 0.9,
  spatialAudio: false,
  resamplingHq: true,

  googleApiKey: '',
  vertexKeyString: '',
  openaiApiKey: '',
  elApiKey: '',
  elVoiceId: '',

  browserPreferred: 'chrome',
  browserFallback: 'brave',
  browserAutoLaunch: true,
  browserCdpPort: 9222,

  availableVoices: JSON.parse(localStorage.getItem('yuki_cached_voices') || '[]'),
  availableGeminiModels: JSON.parse(localStorage.getItem('yuki_cached_models') || '[]').length > 0 
    ? JSON.parse(localStorage.getItem('yuki_cached_models')!)
    : [
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-preview",
        "gemini-3.1-flash-lite-preview",
        "gemini-3.1-flash-live-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash"
      ],
  voiceSearch: '',
  genderFilter: 'female',
  previewing: null,

  setTab: (activeTab) => set({ activeTab }),
  updateSetting: (key, value) => {
    set({ [key]: value } as any);
    if (key === 'availableGeminiModels') {
      localStorage.setItem('yuki_cached_models', JSON.stringify(value));
    }
  },

  loadConfig: async () => {
    try {
      let data;
      // @ts-ignore
      if (window.yukiAPI?.getSettings) {
        // @ts-ignore
        data = await window.yukiAPI.getSettings();
      } else {
        const resp = await fetch('/yuki.config.json');
        data = await resp.json();
      }

      if (!data) return;

      set({
        assistantName: data.assistant?.name || 'Yuki',
        idleLabel: data.assistant?.idle_label || 'SAY "HEY YUKI"',
        greeting: data.assistant?.greeting || '',
        wakeWords: data.assistant?.wake_words?.join(', ') || 'hey yuki',
        whisperModel: data.whisper?.model_size || 'base',
        silenceThold: data.whisper?.silence_threshold || 300,
        silenceTime: data.whisper?.silence_timeout || 1.2,
        maxRecordSecs: data.whisper?.max_record_secs ?? 12,
        geminiModel: data.gemini?.google_ai_studio?.model || data.gemini?.model || 'gemini-2.0-flash',
        geminiFallback: data.gemini?.fallback_model || 'gemini-2.5-flash-lite',
        geminiProvider: data.gemini?.provider || 'google_ai_studio',
        vertexProjectId: data.gemini?.vertex_ai?.project_id || '',
        vertexLocation: data.gemini?.vertex_ai?.location || 'us-central1',
        useLiteFallback: data.gemini?.use_lite_fallback ?? true,
        openaiModel: data.openai?.model || 'gpt-4o-mini',
        ollamaModel: data.ollama?.model || 'gemma3:4b',
        ollamaUrl: data.ollama?.base_url || 'http://localhost:11434',
        brainProvider: data.brain?.provider || 'auto',
        routerOn: data.router?.enabled ?? true,
        fuzzyThold: data.router?.fuzzy_threshold ?? 0.72,
        logFastPath: data.router?.log_fast_path ?? true,
        correctionModel: data.ai_correction?.model ?? 'gemma3:4b',
        ttsProvider: data.tts?.provider || 'elevenlabs',
        ttsVoice: data.assistant?.tts_voice || 'en-IN-NeerjaNeural',
        elBudget: data.tts?.elevenlabs_char_budget || 300,
        speechThold: data.vad?.speech_threshold || 0.65,
        gainDb: data.tts?.gain_db ?? 1.0,
        ttsSpeed: data.tts?.speed ?? 1.0,
        spatialAudio: data.tts?.spatial_audio ?? false,
        resamplingHq: data.tts?.resampling_hq ?? true,
        googleApiKey: data.gemini?.google_ai_studio?.api_key || data.gemini?.google_api_key || '',
        vertexKeyString: data.gemini?.vertex_ai?.key_string || '',
        openaiApiKey: data.openai?.openai_api_key || '',
        elApiKey: data.tts?.elevenlabs_api_key || '',
        elVoiceId: data.tts?.elevenlabs_voice_id || '',
        browserPreferred: data.chrome?.preferred || 'chrome',
        browserFallback: data.chrome?.fallback || 'brave',
        browserAutoLaunch: data.chrome?.auto_launch ?? true,
        browserCdpPort: data.chrome?.cdp_port ?? 9222,
        isHydrated: true
      });
    } catch (err) {
      console.error("Store: Could not load config", err);
    }
  },

  saveConfig: async () => {
    const s = get();
    if (!s.isHydrated) return;

    const payload = {
      assistant: {
        name: s.assistantName,
        wake_words: s.wakeWords.split(',').map(w => w.trim()).filter(Boolean),
        greeting: s.greeting,
        idle_label: s.idleLabel,
        tts_voice: s.ttsVoice
      },
      gemini: { 
        google_ai_studio: {
          api_key: s.googleApiKey,
          model: s.geminiModel
        },
        vertex_ai: {
          project_id: s.vertexProjectId,
          location: s.vertexLocation,
          key_string: s.vertexKeyString
        },
        provider: s.geminiProvider,
        fallback_model: s.geminiFallback, 
        use_lite_fallback: s.useLiteFallback
      },
      openai: { 
        model: s.openaiModel, 
        openai_api_key: s.openaiApiKey 
      },
      ollama: { model: s.ollamaModel, base_url: s.ollamaUrl },
      ai_correction: { model: s.correctionModel },
      router: { 
        enabled: s.routerOn, 
        fuzzy_threshold: s.fuzzyThold, 
        log_fast_path: s.logFastPath 
      },
      vad: { speech_threshold: s.speechThold },
      whisper: {
        model_size: s.whisperModel,
        silence_threshold: s.silenceThold,
        silence_timeout: s.silenceTime,
        max_record_secs: s.maxRecordSecs
      },
      tts: { 
        provider: s.ttsProvider,
        elevenlabs_char_budget: s.elBudget,
        elevenlabs_api_key: s.elApiKey,
        elevenlabs_voice_id: s.elVoiceId,
        gain_db: s.gainDb,
        speed: s.ttsSpeed,
        spatial_audio: s.spatialAudio,
        resampling_hq: s.resamplingHq
      },
      brain: { provider: s.brainProvider },
      chrome: {
        preferred: s.browserPreferred,
        fallback: s.browserFallback,
        auto_launch: s.browserAutoLaunch,
        cdp_port: s.browserCdpPort
      }
    };

    // @ts-ignore
    window.yukiAPI?.saveSettings?.(payload);
    set({ saved: true });
    setTimeout(() => set({ saved: false }), 2000);
  },

  setVoices: (voices, chunk) => {
    if (!chunk || chunk === 1) {
      set({ availableVoices: voices });
    } else {
      set(state => {
        const existingIds = new Set(state.availableVoices.map(v => v.id));
        const newVoices = voices.filter(v => !existingIds.has(v.id));
        return { availableVoices: [...state.availableVoices, ...newVoices] };
      });
    }
    // Persist to local storage after a short delay to avoid rapid writes
    localStorage.setItem('yuki_cached_voices', JSON.stringify(get().availableVoices));
  },

  purgeMemory: () => {
    // @ts-ignore
    window.yukiAPI?.purgeMemory?.();
  }
}));
