import { useReducer, useCallback } from 'react';

export interface SettingsState {
  assistant: {
    name: string;
    idleLabel: string;
    greeting: string;
    wakeWords: string; // Keep as string for input, split on save
  };
  whisper: {
    model: string;
    silenceThreshold: number;
    silenceTimeout: number;
    maxRecordSecs: number;
  };
  neural: {
    brainProvider: string;
    geminiModel: string;
    geminiFallback: string;
    openaiModel: string;
    ollamaModel: string;
    ollamaUrl: string;
    routerEnabled: boolean;
    useLiteFallback: boolean;
    correctionModel: string;
    fuzzyThreshold: number;
    logFastPath: boolean;
  };
  tts: {
    provider: string;
    voice: string;
    elevenlabsBudget: number;
    vadThreshold: number;
    gainDb: number;
    speed: number;
    spatialAudio: boolean;
    resamplingHq: boolean;
  };
  secrets: {
    googleApiKey: string;
    openaiApiKey: string;
    elApiKey: string;
    elVoiceId: string;
  };
  ui: {
    activeTab: string;
    saved: boolean;
    isHydrated: boolean;
    previewing: string | null;
  };
}

type SettingsAction = 
  | { type: 'UPDATE_FIELD', path: string, value: any }
  | { type: 'HYDRATE', state: Partial<SettingsState> }
  | { type: 'SET_SAVED', value: boolean }
  | { type: 'SET_TAB', tab: string }
  | { type: 'SET_PREVIEWING', voiceId: string | null };

const initialState: SettingsState = {
  assistant: {
    name: 'Yuki',
    idleLabel: 'SAY "HEY YUKI"',
    greeting: '',
    wakeWords: 'hey yuki',
  },
  whisper: {
    model: 'base',
    silenceThreshold: 300,
    silenceTimeout: 1.2,
    maxRecordSecs: 12,
  },
  neural: {
    brainProvider: 'auto',
    geminiModel: 'gemini-2.0-flash',
    geminiFallback: 'gemini-2.5-flash-lite',
    openaiModel: 'gpt-4o-mini',
    ollamaModel: 'gemma3:4b',
    ollamaUrl: 'http://localhost:11434',
    routerEnabled: true,
    useLiteFallback: true,
    correctionModel: 'gemma3:4b',
    fuzzyThreshold: 0.72,
    logFastPath: true,
  },
  tts: {
    provider: 'edge-tts',
    voice: 'en-US-AvaMultilingualNeural',
    elevenlabsBudget: 2000,
    vadThreshold: 0.65,
    gainDb: 1.0,
    speed: 1.0,
    spatialAudio: false,
    resamplingHq: true,
  },
  secrets: {
    googleApiKey: '',
    openaiApiKey: '',
    elApiKey: '',
    elVoiceId: '',
  },
  ui: {
    activeTab: 'identity',
    saved: false,
    isHydrated: false,
    previewing: null,
  }
};

function reducer(state: SettingsState, action: SettingsAction): SettingsState {
  switch (action.type) {
    case 'UPDATE_FIELD': {
      const parts = action.path.split('.');
      const newState = { ...state } as any;
      let current = newState;
      for (let i = 0; i < parts.length - 1; i++) {
        current[parts[i]] = { ...current[parts[i]] };
        current = current[parts[i]];
      }
      current[parts[parts.length - 1]] = action.value;
      return newState;
    }
    case 'HYDRATE':
      return { ...state, ...action.state, ui: { ...state.ui, isHydrated: true } };
    case 'SET_SAVED':
      return { ...state, ui: { ...state.ui, saved: action.value } };
    case 'SET_TAB':
      return { ...state, ui: { ...state.ui, activeTab: action.tab } };
    case 'SET_PREVIEWING':
      return { ...state, ui: { ...state.ui, previewing: action.voiceId } };
    default:
      return state;
  }
}

export function useSettingsReducer() {
  const [state, dispatch] = useReducer(reducer, initialState);

  const updateField = useCallback((path: string, value: any) => {
    dispatch({ type: 'UPDATE_FIELD', path, value });
  }, []);

  return { state, dispatch, updateField };
}
