import React, { memo } from 'react';
import { SettingsState } from './useSettingsReducer';

interface ListenerPanelProps {
  state: SettingsState['whisper'];
  tts: SettingsState['tts'];
  onUpdate: (field: string, value: any) => void;
}

const WHISPER_MODELS = [
  { id: 'tiny', label: 'Tiny', desc: 'Fastest, lower accuracy' },
  { id: 'base', label: 'Base', desc: 'Balanced speed/accuracy' },
  { id: 'small', label: 'Small', desc: 'Better accuracy, slower' },
  { id: 'medium', label: 'Medium', desc: 'High accuracy, requires more RAM' },
];

export const ListenerPanel = memo(({ state, tts, onUpdate }: ListenerPanelProps) => {
  return (
    <div className="space-y-8 panel-enter">
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
                <div key={i} className="flex-1 bg-primary/20 threshold-bar" 
                  style={{ height: `${height}%`, opacity: height > (tts.vadThreshold * 100) ? 0.8 : 0.2 }}></div>
              );
            })}
            
            {/* Threshold Line Overlay */}
            <div className="absolute left-0 right-0 border-t border-error/60 z-20 pointer-events-none flex items-center justify-end px-4 transition-all duration-300"
              style={{ bottom: `${(tts.vadThreshold * 100)}%` }}>
              <span className="font-label text-[7px] text-error bg-error/10 px-2 py-0.5 uppercase tracking-widest -translate-y-full border-l border-r border-error/20">Active Trigger: {tts.vadThreshold.toFixed(2)}</span>
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
            const active = state.model === m.id;
            return (
              <div key={m.id} onClick={() => onUpdate('whisper.model', m.id)}
                className={`p-4 border cursor-pointer transition-colors text-left ${active ? 'border-primary bg-primary/10' : 'border-outline-variant/20 bg-surface-container hover:border-primary/50'}`}>
                <div className={`font-headline font-bold text-lg ${active ? 'text-primary' : 'text-on-surface'}`}>{m.label}</div>
                <div className="font-label text-[10px] text-on-surface-variant mt-1">{m.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-left">
        <div className="bg-surface-container-low p-6 border border-outline-variant/20">
          <div className="flex justify-between font-label text-xs uppercase tracking-widest mb-4">
            <span className="text-secondary font-bold">Silence Timeout (s)</span>
            <span className="text-on-surface">{state.silenceTimeout.toFixed(1)}s</span>
          </div>
          <input type="range" min="0.5" max="3.0" step="0.1" value={state.silenceTimeout} onChange={e => onUpdate('whisper.silenceTimeout', Number(e.target.value))} className="w-full settings-range" style={{ accentColor: '#7799ff' }} />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/20">
          <div className="flex justify-between font-label text-xs uppercase tracking-widest mb-4">
            <span className="text-tertiary font-bold">Noise Thold</span>
            <span className="text-on-surface">{state.silenceThreshold}</span>
          </div>
          <input type="range" min="100" max="800" value={state.silenceThreshold} onChange={e => onUpdate('whisper.silenceThreshold', Number(e.target.value))} className="w-full settings-range" style={{ accentColor: '#ff6f7e' }} />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/20 md:col-span-2">
          <div className="flex justify-between font-label text-xs uppercase tracking-widest mb-4">
            <span className="text-primary font-bold">Max Record Duration (s)</span>
            <span className="text-on-surface">{state.maxRecordSecs}s</span>
          </div>
          <input type="range" min="5" max="30" step="1" value={state.maxRecordSecs} onChange={e => onUpdate('whisper.maxRecordSecs', Number(e.target.value))} className="w-full settings-range" style={{ accentColor: '#8ff5ff' }} />
          <p className="font-label text-[8px] text-on-surface-variant mt-3 uppercase tracking-wider opacity-50 italic">Global cut-off safety for long voice descriptors.</p>
        </div>
      </div>
    </div>
  );
});
