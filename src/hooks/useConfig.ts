/**
 * useConfig — loads yuki.config.json at build time via Vite JSON import.
 * This is the React side of the single-source-of-truth config system.
 * Both Python and React read from the same file in the project root.
 *
 * Usage:
 *   import { useConfig } from '../hooks/useConfig';
 *   const { name, idleLabel, greeting } = useConfig();
 */
import config from '../../yuki.config.json';

export interface AssistantConfig {
  name:      string;
  wakeWords: string[];
  greeting:  string;
  idleLabel: string;
  ttsVoice:  string;
  brain: {
    provider: string;
  };
}

export function useConfig(): AssistantConfig {
  const a = config.assistant;
  return {
    name:      a.name,
    wakeWords: a.wake_words,
    greeting:  a.greeting,
    idleLabel: a.idle_label,
    ttsVoice:  a.tts_voice,
    brain: {
      provider: (config as any).brain?.provider || 'gemini'
    }
  };
}

// Also export raw config for non-hook access
export { config as rawConfig };
