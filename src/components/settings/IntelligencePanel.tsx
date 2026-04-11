import React, { memo, useState } from 'react';
import { SettingsState } from './useSettingsReducer';

interface IntelligencePanelProps {
  state: SettingsState['neural'];
  secrets: SettingsState['secrets'];
  onUpdate: (field: string, value: any) => void;
}

export const IntelligencePanel = memo(({ state, secrets, onUpdate }: IntelligencePanelProps) => {
  const [showGoogle, setShowGoogle] = useState(false);
  const [showOpenai, setShowOpenai] = useState(false);

  return (
    <div className="space-y-8 panel-enter">
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
            <div key={p.id} onClick={() => onUpdate('neural.brainProvider', p.id)}
              className={`p-4 border cursor-pointer transition-all ${state.brainProvider === p.id ? 'border-primary bg-primary/10' : 'border-outline-variant/20 bg-surface-container hover:border-primary/50'}`}>
              <div className={`font-headline font-bold text-sm ${state.brainProvider === p.id ? 'text-primary' : 'text-on-surface'}`}>{p.label}</div>
              <div className="font-label text-[9px] text-on-surface-variant mt-1 uppercase tracking-tighter">{p.desc}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8">
        {/* Gemini Card */}
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
                    <div className={`h-1.5 w-1.5 rounded-full ${secrets.googleApiKey ? 'bg-primary shadow-[0_0_8px_var(--md-sys-color-primary)]' : 'bg-outline-variant'}`} />
                    <span className="font-label text-[10px] uppercase tracking-tighter text-on-surface-variant">
                      {secrets.googleApiKey ? 'Neural Link Ready' : 'Awaiting Credential'}
                    </span>
                  </div>
                </div>
                <a href="https://aistudio.google.com/app/apikey" target="_blank" className="font-label text-[10px] text-primary hover:underline uppercase tracking-widest font-bold">API Console</a>
              </div>

              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-lite'].map(m => (
                    <button key={m} onClick={() => onUpdate('neural.geminiModel', m)}
                      className={`px-4 py-2 border font-mono text-[10px] transition-all ${state.geminiModel === m ? 'bg-primary border-primary text-background font-bold shadow-lg shadow-primary/20' : 'border-outline-variant/20 text-on-surface-variant hover:border-primary/50'}`}>
                      {m.toUpperCase()}
                    </button>
                  ))}
                </div>

                <div className="relative flex items-center">
                  <input 
                    type={showGoogle ? "text" : "password"} 
                    value={secrets.googleApiKey} 
                    onChange={e => onUpdate('secrets.googleApiKey', e.target.value)} 
                    placeholder="Paste Google AI Studio Key..."
                    className="w-full bg-surface-container-high/40 border border-outline-variant/10 p-4 font-mono text-xs text-on-surface focus:border-primary/50 outline-none transition-all placeholder:text-on-surface-variant/30" 
                  />
                  <button onClick={() => setShowGoogle(!showGoogle)} className="absolute right-4 text-on-surface-variant/50 hover:text-primary transition-colors">
                    <span className="material-symbols-outlined text-lg">{showGoogle ? 'visibility_off' : 'visibility'}</span>
                  </button>
                </div>
                
                <div className="pt-2">
                  <label className="font-label text-[9px] uppercase text-on-surface-variant font-bold block mb-2">Resilience Fallback</label>
                  <input type="text" value={state.geminiFallback} onChange={e => onUpdate('neural.geminiFallback', e.target.value)} className="w-full bg-surface-container-highest/30 border border-outline-variant/10 p-2 text-on-surface font-mono text-[10px] outline-none focus:border-primary" />
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
                    <div className={`h-1.5 w-1.5 rounded-full ${secrets.openaiApiKey ? 'bg-secondary shadow-[0_0_8px_var(--md-sys-color-secondary)]' : 'bg-outline-variant'}`} />
                    <span className="font-label text-[10px] uppercase tracking-tighter text-on-surface-variant">
                      {secrets.openaiApiKey ? 'Neural Link Ready' : 'Awaiting Credential'}
                    </span>
                  </div>
                </div>
                <a href="https://platform.openai.com/api-keys" target="_blank" className="font-label text-[10px] text-secondary hover:underline uppercase tracking-widest font-bold">API Console</a>
              </div>

              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {['gpt-4o-mini', 'gpt-4o', 'o1-mini'].map(m => (
                    <button key={m} onClick={() => onUpdate('neural.openaiModel', m)}
                      className={`px-4 py-2 border font-mono text-[10px] transition-all ${state.openaiModel === m ? 'bg-secondary border-secondary text-background font-bold shadow-lg shadow-secondary/20' : 'border-outline-variant/20 text-on-surface-variant hover:border-secondary/50'}`}>
                      {m.toUpperCase()}
                    </button>
                  ))}
                </div>

                <div className="relative flex items-center">
                  <input 
                    type={showOpenai ? "text" : "password"} 
                    value={secrets.openaiApiKey} 
                    onChange={e => onUpdate('secrets.openaiApiKey', e.target.value)} 
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

        {/* Ollama Section */}
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
                   <button key={m} onClick={() => onUpdate('neural.ollamaModel', m)}
                     className={`px-3 py-1.5 border font-mono text-[9px] transition-all ${state.ollamaModel === m ? 'bg-tertiary border-tertiary text-background font-bold' : 'border-outline-variant/10 text-on-surface-variant hover:border-tertiary/50'}`}>
                     {m.toUpperCase()}
                   </button>
                 ))}
               </div>
               <input type="text" value={state.ollamaModel} onChange={e => onUpdate('neural.ollamaModel', e.target.value)} className="w-full bg-surface-container-highest/30 border border-outline-variant/10 p-3 text-on-surface font-mono text-xs outline-none focus:border-tertiary transition-colors mt-2" placeholder="OR CUSTOM MODEL NAME..." />
             </div>
             <div className="space-y-2">
               <label className="font-label text-[9px] uppercase text-on-surface-variant">Connection Protocol</label>
               <input type="text" value={state.ollamaUrl} onChange={e => onUpdate('neural.ollamaUrl', e.target.value)} className="w-full bg-surface-container-highest/30 border border-outline-variant/10 p-3 text-on-surface font-mono text-xs outline-none focus:border-tertiary transition-colors" placeholder="URL (e.g. http://localhost:11434)" />
             </div>
          </div>
        </div>
      </div>

      <div className="bg-surface-container-low p-6 border border-outline-variant/20 flex items-center justify-between cursor-pointer hover:bg-surface-container" onClick={() => onUpdate('neural.routerEnabled', !state.routerEnabled)}>
        <div>
          <div className="font-headline font-bold text-lg text-on-surface uppercase tracking-wider">Fast Path Router</div>
          <div className="font-label text-[10px] text-on-surface-variant">Bypass Neural processing for local OS intents (faster).</div>
        </div>
        <div className={`w-12 h-6 rounded-none flex items-center p-1 transition-colors ${state.routerEnabled ? 'bg-primary' : 'bg-surface-container-highest border border-outline-variant/50'}`}>
          <div className={`h-4 w-4 bg-background transition-transform ${state.routerEnabled ? 'translate-x-6' : 'translate-x-0'}`} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-surface-container-low p-6 border border-outline-variant/20">
          <div className="flex justify-between font-label text-xs uppercase tracking-widest mb-4">
            <span className="text-primary font-bold">Router Fuzzy Thold</span>
            <span className="text-on-surface">{state.fuzzyThreshold.toFixed(2)}</span>
          </div>
          <input type="range" min="0.5" max="1.0" step="0.01" value={state.fuzzyThreshold} onChange={e => onUpdate('neural.fuzzyThreshold', Number(e.target.value))} className="w-full settings-range" />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/20 flex items-center justify-between cursor-pointer hover:bg-surface-container" onClick={() => onUpdate('neural.logFastPath', !state.logFastPath)}>
          <div>
            <div className="font-label text-xs font-bold text-on-surface uppercase tracking-widest">Fast Path Logging</div>
            <div className="font-label text-[8px] text-on-surface-variant uppercase mt-1">Detailed routing telemetry.</div>
          </div>
          <div className={`w-10 h-5 rounded-none flex items-center p-1 transition-colors ${state.logFastPath ? 'bg-primary' : 'bg-surface-container-highest border border-outline-variant/50'}`}>
            <div className={`h-3 w-3 bg-background transition-transform ${state.logFastPath ? 'translate-x-5' : 'translate-x-0'}`} />
          </div>
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/20">
          <label className="font-label text-xs uppercase tracking-widest text-secondary font-bold mb-2 block">AI Correction Model</label>
          <input type="text" value={state.correctionModel} onChange={e => onUpdate('neural.correctionModel', e.target.value)} className="w-full bg-surface-container-highest border border-outline-variant/20 p-2 text-on-surface font-mono text-xs outline-none focus:border-secondary transition-colors" />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/20 flex items-center justify-between cursor-pointer hover:bg-surface-container" onClick={() => onUpdate('neural.useLiteFallback', !state.useLiteFallback)}>
          <div>
            <div className="font-label text-xs font-bold text-on-surface uppercase tracking-widest">Use Lite Fallback</div>
            <div className="font-label text-[8px] text-on-surface-variant uppercase mt-1">Auto-switch to 2.5 Flash Lite on 429.</div>
          </div>
          <div className={`w-10 h-5 rounded-none flex items-center p-1 transition-colors ${state.useLiteFallback ? 'bg-primary' : 'bg-surface-container-highest border border-outline-variant/50'}`}>
            <div className={`h-3 w-3 bg-background transition-transform ${state.useLiteFallback ? 'translate-x-5' : 'translate-x-0'}`} />
          </div>
        </div>
      </div>
    </div>
  );
});
