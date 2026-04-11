import React from 'react';

interface NexusPanelProps {
  state: {
    browserPreferred: string;
    browserAutoLaunch: boolean;
    browserCdpPort: number;
  };
  onUpdate: (path: string, value: any) => void;
}

export function NexusPanel({ state, onUpdate }: NexusPanelProps) {
  return (
    <div className="space-y-12 panel-enter">
      <div>
        <h2 className="font-headline text-3xl font-bold tracking-tight text-on-surface uppercase mb-2">Interface Nexus</h2>
        <p className="font-label text-sm text-on-surface-variant">Configure deep-level browser integration and the research engine core.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-surface-container-low p-8 border border-outline-variant/20 group">
          <h3 className="font-label text-xs uppercase tracking-[0.2em] text-primary mb-6 font-bold flex items-center gap-3">
            <span className="material-symbols-outlined text-sm">globe</span>
            Research Instance
          </h3>
          <div className="grid grid-cols-2 gap-4">
            {['chrome', 'brave'].map(b => (
              <div key={b} onClick={() => onUpdate('chrome.preferred', b)}
                className={`p-6 border cursor-pointer transition-all flex flex-col items-center gap-4 ${state.browserPreferred === b ? 'border-primary bg-primary/10' : 'border-outline-variant/20 bg-surface-container hover:border-primary/40'}`}>
                <div className={`font-headline font-bold text-sm ${state.browserPreferred === b ? 'text-primary' : 'text-on-surface'}`}>{b.toUpperCase()} ENGINE</div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-surface-container-low p-8 border border-outline-variant/20">
           <h3 className="font-label text-xs uppercase tracking-[0.2em] text-secondary mb-6 font-bold">Automation Protocol</h3>
           <div className="space-y-4">
             <div className="flex items-center justify-between p-4 bg-surface-container border border-outline-variant/10">
                <span className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant">Auto-Launch Hub</span>
                <div onClick={() => onUpdate('chrome.auto_launch', !state.browserAutoLaunch)} 
                  className={`w-12 h-6 rounded-none flex items-center p-1 cursor-pointer transition-colors ${state.browserAutoLaunch ? 'bg-secondary' : 'bg-surface-container-highest border border-outline-variant/50'}`}>
                  <div className={`h-4 w-4 bg-background transition-transform ${state.browserAutoLaunch ? 'translate-x-6' : 'translate-x-0'}`} />
                </div>
             </div>
             <div className="p-4 bg-surface-container border border-outline-variant/10 space-y-2">
                <span className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant">CDP Bridge Port</span>
                <input type="number" value={state.browserCdpPort} onChange={e => onUpdate('chrome.cdp_port', parseInt(e.target.value))} 
                  className="w-full bg-surface-container-highest border border-outline-variant/20 p-2 text-on-surface font-mono text-xs outline-none focus:border-secondary transition-colors" />
             </div>
           </div>
        </div>
      </div>
    </div>
  );
}
