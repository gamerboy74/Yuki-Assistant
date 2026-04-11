import React, { memo } from 'react';
import { SettingsState } from './useSettingsReducer';

interface IdentityPanelProps {
  state: SettingsState['assistant'];
  onUpdate: (field: string, value: any) => void;
  onPurge: () => void;
  purgeConfirm: boolean;
}

export const IdentityPanel = memo(({ state, onUpdate, onPurge, purgeConfirm }: IdentityPanelProps) => {
  return (
    <div className="space-y-8 panel-enter">
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
              <div className="font-headline font-black text-xs text-primary tracking-widest">{state.name.substring(0,2).toUpperCase()}</div>
            </div>
            <div className="absolute top-0 left-0 right-0 h-[1px] bg-primary/40 animate-pulse-slow"></div>
          </div>
        </div>

        <div className="absolute bottom-6 left-8">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse"></div>
            <h2 className="font-headline text-3xl font-black tracking-tighter text-on-surface uppercase">{state.name}</h2>
          </div>
          <p className="font-label text-[10px] text-on-surface-variant uppercase tracking-[0.3em] font-medium opacity-60">Neural Kernel Revision 2.5.L // STATUS: ACTIVE</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-surface-container-low p-6 border border-outline-variant/10 relative overflow-hidden group">
          <div className="absolute top-0 left-0 w-1 h-full bg-primary/20"></div>
          <label className="font-label text-xs uppercase tracking-widest text-primary mb-2 block font-bold transition-transform group-hover:translate-x-1">Assistant Name</label>
          <input 
            type="text" 
            value={state.name} 
            onChange={e => onUpdate('assistant.name', e.target.value)}
            className="w-full bg-surface-container-highest/50 border border-outline-variant/20 p-3 text-on-surface font-mono text-sm focus:border-primary outline-none transition-colors" 
          />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/10 relative overflow-hidden group">
          <div className="absolute top-0 left-0 w-1 h-full bg-secondary/20"></div>
          <label className="font-label text-xs uppercase tracking-widest text-secondary mb-2 block font-bold transition-transform group-hover:translate-x-1">Idle State Label</label>
          <input 
            type="text" 
            value={state.idleLabel} 
            onChange={e => onUpdate('assistant.idleLabel', e.target.value)}
            className="w-full bg-surface-container-highest/50 border border-outline-variant/20 p-3 text-on-surface font-mono text-sm focus:border-secondary outline-none transition-colors" 
          />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/10 md:col-span-2 relative">
          <label className="font-label text-xs uppercase tracking-widest text-tertiary mb-2 block font-bold">Base Kernel Greeting</label>
          <input 
            type="text" 
            value={state.greeting} 
            onChange={e => onUpdate('assistant.greeting', e.target.value)}
            className="w-full bg-surface-container-highest/50 border border-outline-variant/20 p-3 text-on-surface font-mono text-sm focus:border-tertiary outline-none transition-colors" 
          />
        </div>
        <div className="bg-surface-container-low p-6 border border-outline-variant/10 md:col-span-2 relative">
          <label className="font-label text-xs uppercase tracking-widest text-on-surface mb-4 block font-bold">Activation Keyphrases</label>
          <div className="flex flex-wrap gap-2 mb-4 min-h-[40px] p-2 bg-surface-container-highest/20 border border-dashed border-outline-variant/20">
            {state.wakeWords.split(',').map((word, idx) => {
              const trimmed = word.trim();
              if (!trimmed) return null;
              return (
                <div key={idx} className="bg-primary/10 border border-primary/30 px-3 py-1 flex items-center gap-2 group animate-in zoom-in duration-200">
                  <span className="font-label text-xs font-bold text-primary tracking-wide uppercase">{trimmed}</span>
                  <button 
                    onClick={() => {
                      const words = state.wakeWords.split(',').map(w => w.trim()).filter(w => w !== trimmed);
                      onUpdate('assistant.wakeWords', words.join(', '));
                    }}
                    className="material-symbols-outlined text-[14px] text-primary/50 hover:text-error transition-colors"
                  >
                    close
                  </button>
                </div>
              );
            })}
            {state.wakeWords.trim() === '' && (
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
                  if (val && !state.wakeWords.includes(val)) {
                    onUpdate('assistant.wakeWords', state.wakeWords ? `${state.wakeWords}, ${val}` : val);
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
            onClick={onPurge} 
            className={`px-10 py-4 font-label text-xs font-bold uppercase tracking-widest transition-all duration-300 ${purgeConfirm ? 'bg-error text-on-error scale-105 shadow-[0_0_20px_rgba(244,67,54,0.4)]' : 'bg-surface-container-highest text-error border border-error/30 hover:bg-error/10 hover:border-error'}`}
          >
            {purgeConfirm ? 'SECURE ERASE INITIALIZED' : 'WIPE MEMORY'}
          </button>
        </div>
      </div>
    </div>
  );
});
