// App.tsx — Yuki root shell
// Manages global state (yukiAPI IPC), handles routing between pages,
// and renders the shared TopNavBar + SideNavBar chrome.

import { useState, useEffect, useCallback, useRef } from 'react';
import { useConfig } from './hooks/useConfig';
import TopNavBar from './components/layout/TopNavBar';
import SideNavBar from './components/layout/SideNavBar';
import AgentView  from './pages/AgentView';
import History    from './pages/History';
import Settings   from './pages/Settings';
import Dashboard  from './pages/Dashboard';
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

// Augment window with preload API
declare global {
  interface Window {
    yukiAPI?: {
      minimize:            () => void;
      maximize:            () => void;
      close:               () => void;
      hide:                () => void;
      onState:             (cb: (msg: YukiMsg) => void) => void;
      sendChoice:          (choice: string) => void;
      trigger:             () => void;
      cancelTrigger:       () => void;
      sendMessage:         (text: string) => void;
      sendUIReady:         () => void;
      saveHistory:         (messages: ChatMessage[]) => void;
      onLoadHistory:       (cb: (messages: ChatMessage[]) => void) => void;
      removeStateListener: () => void;
      setMode?:            (mode: string) => void;
    };
  }
}

export default function App() {
  const config = useConfig();
  const [currentPage, setCurrentPage] = useState<Page>('listen');
  const [isMiniMode, setIsMiniMode] = useState<boolean>(false);

  // ── Shared voice / agent state ──────────────────────────────────────────
  const [orbState,          setOrbState]         = useState<OrbState>('idle');
  const [statusLabel,       setStatusLabel]       = useState<string>(config.idleLabel);
  const [transcription,     setTranscription]     = useState<string>('');
  const [clarifyQuestion,   setClarifyQuestion]   = useState<string>('');
  const [clarifyOptions,    setClarifyOptions]    = useState<string[]>([]);
  const [isHotListening,    setIsHotListening]    = useState<boolean>(false);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speakingWatchdog = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSeqRef = useRef<number>(0);
  const activeTurnRef = useRef<string | null>(null);
  const [messages,          setMessages]          = useState<ChatMessage[]>([
    {
      id: '0',
      role: 'assistant',
      text: config.greeting,
      timestamp: new Date(),
    },
  ]);
  const [systemStats,       setSystemStats]       = useState<any>(null);

  // ── IPC bridge: Python → Electron → React ────────────────────────────────
  useEffect(() => {
    if (!window.yukiAPI) {
    console.log('[Yuki] Browser mode — no Electron IPC');
      return;
    }

    window.yukiAPI.onState((msg: YukiMsg) => {
      console.log('[Yuki state]', msg);

      // Ignore out-of-order realtime events.
      if (typeof msg.seq === 'number') {
        if (msg.seq <= lastSeqRef.current) return;
        lastSeqRef.current = msg.seq;
      }

      // Track active turn on processing events.
      if (msg.type === 'processing' && msg.turn_id) {
        activeTurnRef.current = msg.turn_id;
      }

      // Drop stale events from a previous turn.
      const turnScoped = new Set([
        'processing', 'transcript', 'loading', 'speaking', 'response', 'turn_completed', 'idle'
      ]);
      if (
        msg.turn_id &&
        activeTurnRef.current &&
        msg.turn_id !== activeTurnRef.current &&
        turnScoped.has(msg.type)
      ) {
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
          // Debounce idle: short idle flashes (hot-window) shouldn't reset UI
          if (idleTimer.current) clearTimeout(idleTimer.current);
          idleTimer.current = setTimeout(() => {
            setOrbState('idle');
            setStatusLabel(config.idleLabel);
            setIsHotListening(false);
            setClarifyQuestion('');
            setClarifyOptions([]);
            // Faster fade out for transcription
            setTimeout(() => setTranscription(''), 800);
          }, 300); // 300ms debounce — absorbs rapid idle→listening→idle flicker
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
            setMessages(prev => [...prev, {
              id: Date.now().toString(),
              role: 'user',
              text: msg.text!,
              timestamp: new Date(),
            }]);
          }
          break;

        case 'processing':
          clearSpeakingWatchdog();
          if (idleTimer.current) clearTimeout(idleTimer.current);
          // Don't downgrade status if we're already speaking or preparing a response
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
          // Start clearing transcription once she speaks
          setTimeout(() => setTranscription(''), 500);
          break;

        case 'response':
          // This carries the actual text bubble
          if (idleTimer.current) clearTimeout(idleTimer.current);
          setOrbState('speaking');
          setStatusLabel('RESPONDING');
          armSpeakingWatchdog();
          if (msg.text) {
            setMessages(prev => [...prev.filter(m => m.id !== 'temp-processing'), {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              text: msg.text!,
              timestamp: new Date(),
            }]);
          }
          break;

        case 'turn_completed':
          if (msg.turn_id && activeTurnRef.current === msg.turn_id) {
            activeTurnRef.current = null;
          }
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
            setMessages(prev => [...prev, {
              id: Date.now().toString(),
              role: 'assistant',
              text: `⚠️ ${msg.text}`,
              timestamp: new Date(),
            }]);
          }
          break;
        case 'status':
          if (msg.data) {
            setSystemStats(msg.data);
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

  // Tell Python the UI is now fully mounted and ready to receive standard payloads
  useEffect(() => {
    // A tiny timeout ensures initial frame paints are complete
    const tid = setTimeout(() => {
      window.yukiAPI?.sendUIReady?.();
    }, 500);
    return () => clearTimeout(tid);
  }, []);

  // ── History loading/saving ───────────────────────────────────────────────
  useEffect(() => {
    if (window.yukiAPI) {
      window.yukiAPI.onLoadHistory((loadedMessages: ChatMessage[]) => {
        if (!Array.isArray(loadedMessages)) return;
        // Hydrate timestamps if they were serialized as strings
        const hydrated = loadedMessages
          .filter(m => m && m.timestamp)
          .map(m => ({ ...m, timestamp: new Date(m.timestamp) }));
        if (hydrated.length > 0) {
          setMessages(hydrated);
        }
      });
    }
  }, []);

  useEffect(() => {
    // Save history with a small debounce to prevent rapid-fire writes
    if (window.yukiAPI && messages.length > 0) {
      const timer = setTimeout(() => {
        window.yukiAPI?.saveHistory(messages);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [messages]);

  // ── Actions ──────────────────────────────────────────────────────────────
  const handleTrigger = useCallback(() => {
    if (window.yukiAPI) {
      if (orbState === 'listening') {
        window.yukiAPI.cancelTrigger();
      } else {
        window.yukiAPI.trigger();
      }
    } else {
      // Browser demo
      if (orbState === 'listening') {
        setOrbState('idle');
        setStatusLabel(config.idleLabel);
      } else if (orbState === 'idle') {
        setOrbState('listening');
        setStatusLabel('LISTENING...');
        setTimeout(() => {
          setOrbState('processing');
          setStatusLabel('THINKING...');
          const demo = 'Open Google Chrome';
          setTranscription(demo);
          setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', text: demo, timestamp: new Date() }]);
          setTimeout(() => {
            setOrbState('speaking');
            setStatusLabel('RESPONDING');
            const reply = 'Opening Chrome for you!';
            setMessages(prev => [...prev, { id: (Date.now()+1).toString(), role: 'assistant', text: reply, timestamp: new Date() }]);
            setTimeout(() => { setOrbState('idle'); setStatusLabel(config.idleLabel); }, 3500);
          }, 1500);
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
      // Browser demo fallback
      setTimeout(() => {
        const lower = text.toLowerCase();
        let reply = `I understood: "${text}". Connecting to AI backend soon...`;
        if (lower.includes('time')) reply = `It's currently ${new Date().toLocaleTimeString()}.`;
        if (lower.includes('hello') || lower.includes('hi')) reply = 'Hello! What can I do for you today?';
        if (lower.includes('play') && lower.includes('music')) reply = '🎵 Streaming your focus playlist...';
        setMessages(prev => [...prev, { id: (Date.now()+1).toString(), role: 'assistant', text: reply, timestamp: new Date() }]);
      }, 800);
    }
  }, []);

  const handleChoice = useCallback((choice: string) => {
    setClarifyQuestion('');
    setClarifyOptions([]);
    setTranscription(`Chose: ${choice}`);
    window.yukiAPI?.sendChoice(choice);
  }, []);

  const navigateTo = (page: string) => setCurrentPage(page as Page);

  // ── Render ───────────────────────────────────────────────────────────────
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
          />
        );
      case 'history':
        return <History messages={messages} />;
      case 'settings':
        return <Settings />;
      case 'dashboard':
        return <Dashboard stats={systemStats} />;
      default:
        return null;
    }
  };

  if (isMiniMode) {
    return (
      <MiniWidget 
        orbState={orbState}
        onTrigger={handleTrigger}
        onExpand={() => {
          setIsMiniMode(false);
          window.yukiAPI?.setMode?.('full');
        }}
        onClose={() => {
          setIsMiniMode(false);
          window.yukiAPI?.setMode?.('full');
          window.yukiAPI?.hide?.();
        }}
      />
    );
  }

  return (
    <div className="w-full h-full flex flex-col bg-background text-on-surface">
      <TopNavBar 
        activePage={currentPage} 
        onNavigate={navigateTo} 
        stats={systemStats}
        onMiniToggle={() => {
          setIsMiniMode(true);
          window.yukiAPI?.setMode?.('mini');
        }} 
      />

      <div className="flex flex-1 pt-16 h-full overflow-hidden">
        <SideNavBar
          activePage={currentPage}
          onNavigate={navigateTo}
          onTrigger={handleTrigger}
        />

        <main className="ml-20 flex-1 overflow-hidden relative">
          {renderPage()}
        </main>
      </div>

      {/* Dot-grid decorative overlay */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.025] dot-grid z-0" />
    </div>
  );
}
