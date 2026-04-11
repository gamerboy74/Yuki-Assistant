import React, { useEffect, useCallback, useMemo } from 'react';
import { useSettingsStore } from '../store/settingsStore';
import { useSettingsUI } from '../hooks/useSettingsUI';

// High-fidelity modular panels
import { IdentityPanel } from '../components/settings/IdentityPanel';
import { IntelligencePanel } from '../components/settings/IntelligencePanel';
import { ListenerPanel } from '../components/settings/ListenerPanel';
import { VoicesPanel } from '../components/settings/VoicesPanel';
import { NexusPanel } from '../components/settings/NexusPanel';
import { ErrorBoundary } from '../components/common/ErrorBoundary';

export default function Settings() {
  const s = useSettingsStore();
  const { uiState, confirmPurge } = useSettingsUI();
  
  // 1. Initialize & Dynamic Data Ingestion
  useEffect(() => {
    s.loadConfig();

    // Listen for dynamic voices stream from backend
    // @ts-ignore
    if (window.yukiAPI?.onState) {
      // @ts-ignore
      window.yukiAPI.onState((msg: any) => {
        if (msg.type === 'voices') {
          s.setVoices(msg.data, msg.chunk);
        }
      });
    }

    // Request fresh voice list immediately
    // @ts-ignore
    window.yukiAPI?.sendCommand?.({ type: 'get_voices' });
    
    // @ts-ignore
    return () => window.yukiAPI?.removeStateListener?.();
  }, []);

  // 2. Auto-save Heartbeat (Debounced 1.5s)
  useEffect(() => {
    if (!s.isHydrated) return;

    const timer = setTimeout(() => {
      s.saveConfig();
    }, 1500);

    return () => clearTimeout(timer);
  }, [
    s.assistantName, s.idleLabel, s.greeting, s.wakeWords,
    s.whisperModel, s.silenceThold, s.silenceTime, s.maxRecordSecs,
    s.geminiModel, s.geminiFallback, s.openaiModel, s.ollamaModel, s.ollamaUrl, s.routerOn, s.brainProvider,
    s.ttsProvider, s.ttsVoice, s.elBudget, s.speechThold, s.gainDb, s.spatialAudio, s.resamplingHq,
    s.googleApiKey, s.openaiApiKey, s.elApiKey, s.elVoiceId, s.useLiteFallback, s.correctionModel, s.fuzzyThold, s.logFastPath,
    s.browserPreferred, s.browserFallback, s.browserAutoLaunch, s.browserCdpPort
  ]);

  // 3. Action Bridges
  const handleUpdate = useCallback((path: string, value: any) => {
    const mapping: Record<string, keyof typeof s> = {
      'assistant.name': 'assistantName',
      'assistant.idleLabel': 'idleLabel',
      'assistant.greeting': 'greeting',
      'assistant.wakeWords': 'wakeWords',
      'whisper.model': 'whisperModel',
      'whisper.silenceThreshold': 'silenceThold',
      'whisper.silenceTimeout': 'silenceTime',
      'whisper.maxRecordSecs': 'maxRecordSecs',
      'neural.brainProvider': 'brainProvider',
      'neural.geminiModel': 'geminiModel',
      'neural.geminiFallback': 'geminiFallback',
      'neural.openaiModel': 'openaiModel',
      'neural.ollamaModel': 'ollamaModel',
      'neural.ollamaUrl': 'ollamaUrl',
      'neural.routerEnabled': 'routerOn',
      'neural.useLiteFallback': 'useLiteFallback',
      'neural.correctionModel': 'correctionModel',
      'neural.fuzzyThreshold': 'fuzzyThold',
      'neural.logFastPath': 'logFastPath',
      'tts.provider': 'ttsProvider',
      'tts.voice': 'ttsVoice',
      'tts.elevenlabsBudget': 'elBudget',
      'tts.vadThreshold': 'speechThold',
      'tts.gainDb': 'gainDb',
      'tts.spatialAudio': 'spatialAudio',
      'tts.resamplingHq': 'resamplingHq',
      'secrets.googleApiKey': 'googleApiKey',
      'secrets.openaiApiKey': 'openaiApiKey',
      'secrets.elApiKey': 'elApiKey',
      'secrets.elVoiceId': 'elVoiceId',
      'chrome.preferred': 'browserPreferred',
      'chrome.fallback': 'browserFallback',
      'chrome.auto_launch': 'browserAutoLaunch',
      'chrome.cdp_port': 'browserCdpPort'
    };

    const targetKey = mapping[path];
    if (targetKey) {
      // @ts-ignore
      s.updateSetting(targetKey, value);
    }
  }, [s]);

  const handleVoiceSelect = useCallback((voiceId: string, provider: string) => {
    s.updateSetting('ttsVoice', voiceId);
    if (provider === 'elevenlabs' || s.ttsProvider === 'elevenlabs') {
      s.updateSetting('elVoiceId', voiceId);
    }
  }, [s]);

  const handlePreviewVoice = useCallback((voiceId: string, provider: string) => {
    s.updateSetting('previewing', voiceId);
    // @ts-ignore
    window.yukiAPI?.sendCommand?.({ type: 'preview_voice', voiceId, provider });
    setTimeout(() => s.updateSetting('previewing', null), 6000);
  }, [s]);

  const handlePurge = useCallback(() => {
    if (!uiState.purgeConfirm) {
      confirmPurge();
      return;
    }
    s.purgeMemory();
  }, [uiState.purgeConfirm, confirmPurge, s]);

  // 4. State Reconstruction
  const assistantState = useMemo(() => ({
    name: s.assistantName,
    idleLabel: s.idleLabel,
    greeting: s.greeting,
    wakeWords: s.wakeWords
  }), [s.assistantName, s.idleLabel, s.greeting, s.wakeWords]);

  const whisperState = useMemo(() => ({
    model: s.whisperModel,
    silenceThreshold: s.silenceThold,
    silenceTimeout: s.silenceTime,
    maxRecordSecs: s.maxRecordSecs
  }), [s.whisperModel, s.silenceThold, s.silenceTime, s.maxRecordSecs]);

  const neuralState = useMemo(() => ({
    brainProvider: s.brainProvider,
    geminiModel: s.geminiModel,
    geminiFallback: s.geminiFallback,
    openaiModel: s.openaiModel,
    ollamaModel: s.ollamaModel,
    ollamaUrl: s.ollamaUrl,
    routerEnabled: s.routerOn,
    useLiteFallback: s.useLiteFallback,
    correctionModel: s.correctionModel,
    fuzzyThreshold: s.fuzzyThold,
    logFastPath: s.logFastPath
  }), [s.brainProvider, s.geminiModel, s.geminiFallback, s.openaiModel, s.ollamaModel, s.ollamaUrl, s.routerOn, s.useLiteFallback, s.correctionModel, s.fuzzyThold, s.logFastPath]);

  const ttsState = useMemo(() => ({
    provider: s.ttsProvider,
    voice: s.ttsVoice,
    elevenlabsBudget: s.elBudget,
    vadThreshold: s.speechThold,
    gainDb: s.gainDb,
    speed: s.ttsSpeed,
    spatialAudio: s.spatialAudio,
    resamplingHq: s.resamplingHq
  }), [s.ttsProvider, s.ttsVoice, s.elBudget, s.speechThold, s.gainDb, s.ttsSpeed, s.spatialAudio, s.resamplingHq]);

  const secretsState = useMemo(() => ({
    googleApiKey: s.googleApiKey,
    openaiApiKey: s.openaiApiKey,
    elApiKey: s.elApiKey,
    elVoiceId: s.elVoiceId
  }), [s.googleApiKey, s.openaiApiKey, s.elApiKey, s.elVoiceId]);

  const nexusState = useMemo(() => ({
    browserPreferred: s.browserPreferred,
    browserAutoLaunch: s.browserAutoLaunch,
    browserCdpPort: s.browserCdpPort
  }), [s.browserPreferred, s.browserAutoLaunch, s.browserCdpPort]);

  return (
    <div className="flex flex-col h-full w-full relative z-10 animate-fade-in bg-transparent">
      {/* Premium Tab Navigation */}
      <div className="px-8 pt-8 pb-4 shrink-0 border-b border-outline-variant/10 flex items-end justify-between">
        <div className="flex space-x-10 overflow-x-auto hide-scrollbar">
          {[
            { id: 'identity', label: 'IDENTITY', icon: 'fingerprint' }, 
            { id: 'intelligence', label: 'BRAIN', icon: 'psychology' }, 
            { id: 'voices', label: 'VOICE', icon: 'waves' }, 
            { id: 'listener', label: 'EARS', icon: 'hearing' },
            { id: 'nexus', label: 'NEXUS', icon: 'hub' }
          ].map(tab => (
            <button key={tab.id} onClick={() => s.setTab(tab.id)}
              className={`pb-4 border-b-2 font-headline text-xs font-bold tracking-[0.2em] uppercase transition-all duration-300 flex items-center gap-3 ${s.activeTab === tab.id ? 'border-primary text-primary opacity-100 translate-y-0' : 'border-transparent text-secondary opacity-40 hover:opacity-80'}`}>
              <span className="material-symbols-outlined text-[18px]">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
        
        <div className="pb-4 flex items-center gap-4">
           <div className={`h-1 w-1 rounded-full animate-pulse ${s.isHydrated ? 'bg-primary' : 'bg-outline-variant'}`}></div>
           <span className="font-label text-[8px] tracking-[0.3em] text-on-surface-variant font-bold">KERNEL-V2.5 // LOCAL_LINK</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-12 relative hide-scrollbar">
        <div className="max-w-6xl mx-auto pb-32">
          {s.activeTab === 'identity' && (
            <ErrorBoundary fallback={<div className="p-4 text-error font-mono text-[10px]">IDENTITY_PANEL_FAILURE</div>}>
             <IdentityPanel 
               state={assistantState} 
               onUpdate={handleUpdate} 
               onPurge={handlePurge} 
               purgeConfirm={uiState.purgeConfirm} 
             />
            </ErrorBoundary>
          )}

          {s.activeTab === 'intelligence' && (
            <ErrorBoundary fallback={<div className="p-4 text-error font-mono text-[10px]">INTELLIGENCE_PANEL_FAILURE</div>}>
            <IntelligencePanel 
              state={neuralState} 
              secrets={secretsState} 
              onUpdate={handleUpdate} 
            />
            </ErrorBoundary>
          )}

          {s.activeTab === 'voices' && (
            <ErrorBoundary fallback={<div className="p-4 text-error font-mono text-[10px]">VOICES_PANEL_FAILURE</div>}>
            <VoicesPanel 
              state={ttsState} 
              secrets={secretsState} 
              availableVoices={s.availableVoices}
              previewingId={s.previewing}
              onUpdate={handleUpdate}
              onVoiceSelect={handleVoiceSelect}
              onPreview={handlePreviewVoice}
            />
            </ErrorBoundary>
          )}

          {s.activeTab === 'listener' && (
            <ErrorBoundary fallback={<div className="p-4 text-error font-mono text-[10px]">LISTENER_PANEL_FAILURE</div>}>
              <ListenerPanel 
                state={whisperState} 
                tts={ttsState} 
                onUpdate={handleUpdate} 
              />
            </ErrorBoundary>
          )}

          {s.activeTab === 'nexus' && (
            <ErrorBoundary fallback={<div className="p-4 text-error font-mono text-[10px]">NEXUS_PANEL_FAILURE</div>}>
              <NexusPanel 
                state={nexusState} 
                onUpdate={handleUpdate} 
              />
            </ErrorBoundary>
          )}
        </div>
      </div>

      {/* Persistence Notification HUD */}
      <div className="fixed bottom-12 right-12 z-50 pointer-events-none">
        <div className={`bg-primary/20 backdrop-blur-xl border border-primary/30 py-3 px-6 shadow-2xl transition-all duration-700 ${s.saved ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-8 scale-95'}`}>
          <div className="flex items-center gap-4">
             <div className="w-2 h-2 bg-primary animate-ping rounded-none"></div>
             <span className="font-headline font-black text-[10px] tracking-[0.2em] text-primary uppercase">Synchronization Complete</span>
          </div>
        </div>
      </div>
    </div>
  );
}

