import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useConfig } from './hooks/useConfig';
import AgentView from './pages/AgentView';
import History from './pages/History';
import Settings from './pages/Settings';
import Dashboard from './pages/Dashboard';
import MiniWidget from './components/MiniWidget';

export type Page = 'chat' | 'listen' | 'history' | 'settings' | 'dashboard';
export type OrbState = 'idle' | 'listening' | 'speaking' | 'processing';

export interface YukiMsg {
  type: string;
  seq?: number;
  turn_id?: string;
  ts?: number;
  text?: string;
  question?: string;
  options?: string[];
  data?: any;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: Date;
}

// Note: Global yukiAPI is defined in vite-env.d.ts

/* ── Cosmic Constants ────────────────────────────────────────────────────── */

const SHELL_GLOW = {
  idle: 'rgba(143,245,255,0.06)',
  listening: 'rgba(143,245,255,0.14)',
  processing: 'rgba(251,191,36,0.10)',
  speaking: 'rgba(255,50,200,0.12)',
};

function CosmicField() {
  const stars = useMemo(() => Array.from({ length: 200 }, (_, i) => ({
    id: i,
    size: Math.random() < 0.7 ? 1 : Math.random() < 0.85 ? 1.5 : 2.5,
    top: Math.random() * 100,
    left: Math.random() * 100,
    dur: 3 + Math.random() * 6,
    delay: Math.random() * 8,
    minOp: 0.05 + Math.random() * 0.2,
    maxOp: 0.35 + Math.random() * 0.5,
  })), []);

  const shoots = useMemo(() => Array.from({ length: 5 }, (_, i) => ({
    id: i,
    top: Math.random() * 60,
    left: Math.random() * 80,
    width: 60 + Math.random() * 100,
    dur: 4 + Math.random() * 10,
    delay: -(Math.random() * 12),
  })), []);

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      {stars.map(s => (
        <div key={s.id} className="absolute rounded-full bg-white" style={{
          width: s.size, height: s.size,
          top: `${s.top}%`, left: `${s.left}%`,
          animation: `starTwinkle ${s.dur.toFixed(1)}s ease-in-out infinite ${(-s.delay).toFixed(1)}s`,
          ['--min-op' as any]: s.minOp,
          ['--max-op' as any]: s.maxOp,
        }} />
      ))}
      {shoots.map(s => (
        <div key={s.id} className="absolute" style={{
          top: `${s.top}%`, left: `${s.left}%`,
          width: s.width, height: 1,
          background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.7), transparent)',
          transform: 'rotate(-30deg)',
          animation: `shootStar ${s.dur.toFixed(1)}s linear infinite ${s.delay.toFixed(1)}s`,
          opacity: 0,
        }} />
      ))}
    </div>
  );
}

export default function App() {
  const config = useConfig();
  const [currentPage, setCurrentPage] = useState<Page>('listen');
  const [isMiniMode, setIsMiniMode] = useState<boolean>(false);

  // ── Shared voice / agent state ──────────────────────────────────────────
  const [orbState, setOrbState] = useState<OrbState>('idle');
  const [statusLabel, setStatusLabel] = useState<string>(config.idleLabel);
  const [transcription, setTranscription] = useState<string>('');
  const [clarifyQuestion, setClarifyQuestion] = useState<string>('');
  const [clarifyOptions, setClarifyOptions] = useState<string[]>([]);
  const [isHotListening, setIsHotListening] = useState<boolean>(false);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speakingWatchdog = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSeqRef = useRef<number>(0);
  const activeTurnRef = useRef<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '0',
      role: 'assistant',
      text: config.greeting,
      timestamp: new Date(),
    },
  ]);
  const [systemStats, setSystemStats] = useState<any>(null);
  const [systemLogs, setSystemLogs] = useState<{id: string, text: string, ts: Date}[]>([]);
  const [sessionUsage, setSessionUsage] = useState({ input: 0, output: 0, cost: 0.0, turns: 0 });
  
  // ── Neural Provider State ──
  const [selectedProvider, setSelectedProvider] = useState<string>(config.brain?.provider || 'auto');

  // Sync state with config when it loads
  useEffect(() => {
    if (config.brain?.provider) {
      setSelectedProvider(config.brain.provider);
    }
  }, [config.brain?.provider]);

  const handleProviderChange = useCallback((provider: string) => {
    setSelectedProvider(provider);
    if (window.yukiAPI) {
      // Create a copy of the current config and update the provider
      const newConfig = { ...config, brain: { ...config.brain, provider } };
      window.yukiAPI.saveSettings(newConfig);
    }
  }, [config]);

  // ── IPC bridge: Python → Electron → React ────────────────────────────────
  useEffect(() => {
    if (!window.yukiAPI) return;

    window.yukiAPI.onState((msg: YukiMsg) => {
      console.log('[Yuki state]', msg);
      if (typeof msg.seq === 'number') {
        if (msg.seq <= lastSeqRef.current) return;
        lastSeqRef.current = msg.seq;
      }
      if (msg.type === 'processing' && msg.turn_id) {
        activeTurnRef.current = msg.turn_id;
      }
      const turnScoped = new Set(['processing', 'transcript', 'loading', 'speaking', 'response', 'turn_completed', 'idle']);
      if (msg.turn_id && activeTurnRef.current && msg.turn_id !== activeTurnRef.current && turnScoped.has(msg.type)) {
        return;
      }

      const clearSpeakingWatchdog = () => {
        if (speakingWatchdog.current) {
          clearTimeout(speakingWatchdog.current);
          speakingWatchdog.current = null;
        }
      };

      const armSpeakingWatchdog = () => {
        clearSpeakingWatchdog();
        speakingWatchdog.current = setTimeout(() => {
          setOrbState('idle');
          setStatusLabel(config.idleLabel);
          setIsHotListening(false);
        }, 15000);
      };

      switch (msg.type) {
        case 'idle':
          clearSpeakingWatchdog();
          if (idleTimer.current) clearTimeout(idleTimer.current);
          // Small delay before going truly idle to prevent flickering during turn transitions
          idleTimer.current = setTimeout(() => {
            setOrbState('idle');
            setStatusLabel(config.idleLabel);
            setIsHotListening(false);
            setClarifyQuestion('');
            setClarifyOptions([]);
            // Clear transcription after a moment of idle
            setTimeout(() => setTranscription(''), 2000); 
          }, 800);
          break;
        case 'wake':
          clearSpeakingWatchdog();
          if (idleTimer.current) clearTimeout(idleTimer.current);
          setOrbState('listening');
          setStatusLabel('LISTENING...');
          setIsHotListening(false);
          setTranscription('');
          setClarifyQuestion('');
          setClarifyOptions([]);
          break;
        case 'listening':
          clearSpeakingWatchdog();
          if (idleTimer.current) clearTimeout(idleTimer.current);
          setOrbState('listening');
          setStatusLabel('LISTENING...');
          setIsHotListening(false);
          setTranscription('');
          break;
        case 'hot_listen':
          clearSpeakingWatchdog();
          if (idleTimer.current) clearTimeout(idleTimer.current);
          setOrbState('idle');
          setIsHotListening(false);
          setStatusLabel(config.idleLabel);
          break;
        case 'transcript':
          clearSpeakingWatchdog();
          if (idleTimer.current) clearTimeout(idleTimer.current);
          setIsHotListening(false);
          setOrbState('processing');
          setStatusLabel('UNDERSTANDING...');
          setTranscription(msg.text || '');
          if (msg.text) {
            setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', text: msg.text!, timestamp: new Date() }]);
          }
          break;
        case 'processing':
          clearSpeakingWatchdog();
          if (idleTimer.current) clearTimeout(idleTimer.current);
          if (orbState === 'speaking') return;
          setOrbState('processing');
          setStatusLabel('THINKING...');
          break;
        case 'loading':
          clearSpeakingWatchdog();
          if (idleTimer.current) clearTimeout(idleTimer.current);
          if (orbState === 'speaking') return;
          setOrbState('processing');
          setStatusLabel(msg.text?.toUpperCase() || 'LOADING...');
          break;
        case 'speaking':
          if (idleTimer.current) clearTimeout(idleTimer.current);
          setOrbState('speaking');
          setStatusLabel('RESPONDING');
          armSpeakingWatchdog();
          // Clear transcription faster when we start responding
          setTimeout(() => setTranscription(''), 200);
          break;
        case 'partial-response':
          if (msg.text) {
            setMessages(prev => {
              const last = prev[prev.length - 1];
              // If last message has same turn_id or is a temporary thinking state, append/update
              if (last && last.id === msg.turn_id && last.role === 'assistant') {
                return [...prev.slice(0, -1), { ...last, text: last.text + ' ' + msg.text }];
              }
              return [...prev.filter(m => m.id !== 'temp-processing'), { id: msg.turn_id || (Date.now() + 1).toString(), role: 'assistant', text: msg.text!, timestamp: new Date() }];
            });
          }
          break;
        case 'response':
          if (idleTimer.current) clearTimeout(idleTimer.current);
          setOrbState('speaking');
          setStatusLabel('RESPONDING');
          armSpeakingWatchdog();
          if (msg.text) {
            setMessages(prev => {
              const exists = prev.find(m => m.id === msg.turn_id);
              if (exists) {
                // Finalize the text if it's vastly different or just stick with it
                return prev.map(m => m.id === msg.turn_id ? { ...m, text: msg.text! } : m);
              }
              return [...prev.filter(m => m.id !== 'temp-processing'), { id: msg.turn_id || (Date.now() + 1).toString(), role: 'assistant', text: msg.text!, timestamp: new Date() }];
            });
          }
          break;
        case 'turn_completed':
          if (msg.turn_id && activeTurnRef.current === msg.turn_id) activeTurnRef.current = null;
          break;
        case 'clarify':
          clearSpeakingWatchdog();
          if (idleTimer.current) clearTimeout(idleTimer.current);
          setOrbState('processing');
          setStatusLabel('NEEDS YOUR INPUT');
          setClarifyQuestion(msg.question || 'Which one?');
          setClarifyOptions(msg.options || []);
          setTranscription('');
          break;
        case 'error':
          clearSpeakingWatchdog();
          if (idleTimer.current) clearTimeout(idleTimer.current);
          setOrbState('idle');
          setStatusLabel('ERROR');
          if (msg.text) {
            setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', text: `⚠️ ${msg.text}`, timestamp: new Date() }]);
          }
          break;
        case 'status':
          if (msg.data) setSystemStats(msg.data);
          break;
        case 'usage_update':
          setSessionUsage({
            input: msg.data?.input || 0,
            output: msg.data?.output || 0,
            cost: msg.data?.cost || 0.0,
            turns: msg.data?.turns || 0
          });
          break;
        case 'log':
          if (msg.text) {
            setSystemLogs(prev => [
              { id: Date.now().toString(), text: msg.text!, ts: new Date() },
              ...prev.slice(0, 49) // Keep last 50
            ]);
          }
          break;
      }
    });

    return () => {
      window.yukiAPI?.removeStateListener();
      if (idleTimer.current) clearTimeout(idleTimer.current);
      if (speakingWatchdog.current) clearTimeout(speakingWatchdog.current);
    };
  }, []);

  useEffect(() => {
    const tid = setTimeout(() => {
      window.yukiAPI?.sendUIReady?.();
    }, 500);
    return () => clearTimeout(tid);
  }, []);

  useEffect(() => {
    if (window.yukiAPI) {
      window.yukiAPI.onLoadHistory((loadedMessages: ChatMessage[]) => {
        if (!Array.isArray(loadedMessages)) return;
        const hydrated = loadedMessages.filter(m => m && m.timestamp).map(m => ({ ...m, timestamp: new Date(m.timestamp) }));
        if (hydrated.length > 0) setMessages(hydrated);
      });
    }
  }, []);

  useEffect(() => {
    if (window.yukiAPI && messages.length > 0) {
      const timer = setTimeout(() => window.yukiAPI?.saveHistory(messages), 500);
      return () => clearTimeout(timer);
    }
  }, [messages]);

  const handleTrigger = useCallback(() => {
    if (window.yukiAPI) {
      if (orbState === 'listening') {
        window.yukiAPI.cancelTrigger();
      } else {
        window.yukiAPI.trigger();
      }
    } else {
      if (orbState === 'listening') {
        setOrbState('idle');
        setStatusLabel(config.idleLabel);
      } else if (orbState === 'idle') {
        setOrbState('listening');
        setStatusLabel('LISTENING...');
        setTimeout(() => {
          setOrbState('processing');
          setStatusLabel('THINKING...');
          setTranscription('Open Google Chrome');
          setTimeout(() => { setOrbState('idle'); setStatusLabel(config.idleLabel); }, 3500);
        }, 2500);
      }
    }
  }, [orbState]);

  const handleSendMessage = useCallback((text: string) => {
    const userMsg: ChatMessage = { id: Date.now().toString(), role: 'user', text, timestamp: new Date() };
    setMessages(prev => [...prev, userMsg]);
    if (window.yukiAPI) {
      window.yukiAPI.sendMessage(text);
    } else {
      setTimeout(() => {
        setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'assistant', text: `Got: ${text}`, timestamp: new Date() }]);
      }, 800);
    }
  }, []);

  const handleChoice = useCallback((choice: string) => {
    setClarifyQuestion(''); setClarifyOptions([]);
    setTranscription(`Chose: ${choice}`);
    window.yukiAPI?.sendChoice(choice);
  }, []);

  const navigateTo = (page: string) => setCurrentPage(page as Page);

  const renderPage = () => {
    switch (currentPage) {
      case 'chat':
      case 'listen':
        return (
          <AgentView 
            viewMode={currentPage === 'chat' ? 'chat' : 'voice'} 
            orbState={orbState} 
            statusLabel={statusLabel} 
            transcription={transcription} 
            messages={messages} 
            clarifyQuestion={clarifyQuestion} 
            clarifyOptions={clarifyOptions} 
            isHotListening={isHotListening} 
            onTrigger={handleTrigger} 
            onSendMessage={handleSendMessage} 
            onChoice={handleChoice} 
            selectedProvider={selectedProvider}
            onProviderChange={handleProviderChange}
          />
        );
      case 'history': return <History messages={messages} />;
      case 'settings': return <Settings />;
      case 'dashboard': return <Dashboard stats={systemStats} logs={systemLogs} usage={sessionUsage} />;
      default: return null;
    }
  };

  if (isMiniMode) {
    return <MiniWidget orbState={orbState} onTrigger={handleTrigger} onExpand={() => { setIsMiniMode(false); window.yukiAPI?.setMode?.('full'); }} onClose={() => { setIsMiniMode(false); window.yukiAPI?.setMode?.('full'); window.yukiAPI?.hide?.(); }} />;
  }

  return (
    <div className="flex flex-col h-full w-full bg-[#00000f] text-on-surface font-body overflow-hidden outline-none relative">

      {/* Global Cosmic Background */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute inset-0 transition-all duration-1000" style={{
          background: `radial-gradient(ellipse 60% 40% at 15% 20%, rgba(120,0,180,0.18) 0%, transparent 60%),
                       radial-gradient(ellipse 50% 35% at 85% 75%, rgba(0,80,200,0.14) 0%, transparent 60%),
                       radial-gradient(ellipse 40% 50% at 70% 10%, rgba(180,0,120,0.12) 0%, transparent 55%)`,
          animation: 'nebulaDrift1 25s ease-in-out infinite alternate'
        }} />
        <div className="absolute inset-0" style={{
          background: `radial-gradient(ellipse 45% 55% at 80% 25%, rgba(255,0,180,0.07) 0%, transparent 60%),
                       radial-gradient(ellipse 55% 35% at 20% 65%, rgba(100,0,255,0.09) 0%, transparent 60%)`,
          animation: 'nebulaDrift2 32s ease-in-out infinite alternate'
        }} />
        <div className="absolute inset-0 transition-all duration-1000"
          style={{ background: `radial-gradient(ellipse 65% 50% at 50% 55%, ${SHELL_GLOW[orbState]}, transparent 70%)` }}
        />
        <div className="absolute inset-0"
          style={{ background: 'radial-gradient(ellipse 80% 80% at 50% 50%, transparent 40%, rgba(0,0,0,0.8) 100%)' }}
        />
        <CosmicField />
      </div>

      <div className="fixed inset-0 pointer-events-none opacity-[0.025] dot-grid z-0" />

      {/* Top Drag Region Header */}
      <header className="h-[28px] bg-black/40 backdrop-blur-xl w-full flex justify-between items-center px-3 border-b border-white/5 drag-region shrink-0 z-50">
        <div className="text-[10px] font-label tracking-widest text-primary opacity-50 no-drag-region cursor-default select-none">
          YUKI.SYS / {currentPage.toUpperCase()}
        </div>
        <div className="flex gap-4 no-drag-region items-center">
          <span onClick={() => window.yukiAPI?.minimize?.()} className="material-symbols-outlined text-primary text-[14px] cursor-pointer hover:text-white transition-colors" title='Minimize'>remove</span>
          <span onClick={() => window.yukiAPI?.maximize?.()} className="material-symbols-outlined text-primary text-[14px] cursor-pointer hover:text-white transition-colors" title='Maximize'>check_box_outline_blank</span>
          <span onClick={() => window.yukiAPI?.close?.()} className="material-symbols-outlined text-primary text-[14px] cursor-pointer hover:text-error transition-colors" title='Close'>close</span>
        </div>
      </header>

      {/* Main App Body */}
      <div className="flex flex-1 overflow-hidden relative z-10">
        <aside className="w-[200px] h-full bg-black/40 backdrop-blur-2xl flex flex-col border-r border-white/5 shrink-0 z-40 relative">
          <div className="p-6">
            <div className="font-headline font-extrabold text-primary tracking-tighter text-xl cursor-default select-none">YUKI.SYS</div>
            <div className="font-label text-[10px] text-secondary opacity-80 mt-1 uppercase truncate">STATUS: {orbState === 'idle' ? 'STABLE' : orbState}</div>
          </div>
          <nav className="flex-1 mt-4">
            <div className="flex flex-col">
              {[
                { id: 'dashboard', icon: 'grid_view', label: 'Monitor' },
                { id: 'listen', icon: 'graphic_eq', label: 'Agent' },
                { id: 'history', icon: 'history', label: 'Vault Logs' },
                { id: 'settings', icon: 'manufacturing', label: 'Config' }
              ].map(tab => {
                const isActive = currentPage === tab.id || (currentPage === 'chat' && tab.id === 'listen');
                return (
                  <button key={tab.id} onClick={() => navigateTo(tab.id)}
                    className={`flex items-center font-label text-[12px] font-medium pl-4 py-3 transition-all duration-150 ${isActive ? 'text-primary border-l-2 border-primary bg-white/5' : 'text-secondary opacity-60 hover:opacity-100 hover:bg-white/5'}`}>
                    <span className="material-symbols-outlined align-middle mr-2 text-[18px]">{tab.icon}</span>
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </nav>

          <div className="p-4 mt-auto space-y-2">
            <div className="p-3 bg-primary-container/10 border border-primary/20 cursor-default select-none">
              <div className="font-label text-[10px] text-primary-fixed mb-1 uppercase">Orb Mode</div>
              <div className="text-[10px] font-label text-on-surface-variant truncate uppercase">{orbState}</div>
            </div>
            <button onClick={handleTrigger} className={`w-full py-3 font-headline font-bold text-xs tracking-widest transition-colors relative overflow-hidden group ${orbState === 'listening' ? 'bg-error text-on-error hover:bg-error-container' : 'bg-primary text-on-primary hover:bg-primary-dim'}`}>
              {orbState === 'listening' ? 'CANCEL' : 'TRIGGER'}
            </button>
          </div>

          <div className="border-t border-outline-variant/10 px-4 py-4 flex gap-4">
            <span onClick={() => { setIsMiniMode(true); window.yukiAPI?.setMode?.('mini'); }} className="material-symbols-outlined text-secondary opacity-60 cursor-pointer hover:opacity-100 transition-opacity" title="Mini Mode">picture_in_picture_alt</span>
            <span onClick={() => window.yukiAPI?.close?.()} className="material-symbols-outlined text-secondary opacity-60 cursor-pointer hover:text-error transition-colors" title="Shutdown">power_settings_new</span>
          </div>
        </aside>

        <main className="flex-1 overflow-hidden relative bg-transparent z-10 w-full h-full">
          {renderPage()}
        </main>
      </div>
    </div>
  );
}
