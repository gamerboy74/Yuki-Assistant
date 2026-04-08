// App.tsx — Yuki root shell
// Manages global state (yukiAPI IPC), handles routing between pages,
// and renders the shared TopNavBar + SideNavBar chrome.

import { useState, useEffect, useCallback } from 'react';
import { useConfig } from './hooks/useConfig';
import TopNavBar from './components/layout/TopNavBar';
import SideNavBar from './components/layout/SideNavBar';
import AgentView  from './pages/AgentView';
import History    from './pages/History';
import Settings   from './pages/Settings';
import MiniWidget from './components/MiniWidget';

export type Page = 'chat' | 'listen' | 'history' | 'settings';

export type OrbState = 'idle' | 'listening' | 'speaking' | 'processing';

export interface YukiMsg {
  type: string;
  text?: string;
  question?: string;
  options?: string[];
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
      sendMessage:         (text: string) => void;
      saveHistory:         (messages: ChatMessage[]) => void;
      onLoadHistory:       (cb: (messages: ChatMessage[]) => void) => void;
      removeStateListener: () => void;
      setMode?:            (mode: string) => void;
    };
  }
}

export default function App() {
  const config = useConfig();
  const [currentPage, setCurrentPage] = useState<Page>('chat');
  const [isMiniMode, setIsMiniMode] = useState<boolean>(false);

  // ── Shared voice / agent state ──────────────────────────────────────────
  const [orbState,          setOrbState]         = useState<OrbState>('idle');
  const [statusLabel,       setStatusLabel]       = useState<string>(config.idleLabel);
  const [transcription,     setTranscription]     = useState<string>('');
  const [clarifyQuestion,   setClarifyQuestion]   = useState<string>('');
  const [clarifyOptions,    setClarifyOptions]    = useState<string[]>([]);
  const [messages,          setMessages]          = useState<ChatMessage[]>([
    {
      id: '0',
      role: 'assistant',
      text: config.greeting,
      timestamp: new Date(),
    },
  ]);

  // ── IPC bridge: Python → Electron → React ────────────────────────────────
  useEffect(() => {
    if (!window.yukiAPI) {
    console.log('[Yuki] Browser mode — no Electron IPC');
      return;
    }

    window.yukiAPI.onState((msg: YukiMsg) => {
      console.log('[Yuki state]', msg);

      switch (msg.type) {
        case 'idle':
          setOrbState('idle');
          setStatusLabel(config.idleLabel);
          setTranscription('');
          setClarifyQuestion('');
          setClarifyOptions([]);
          break;

        case 'wake':
          setOrbState('listening');
          setStatusLabel('LISTENING...');
          setTranscription('');
          setClarifyQuestion('');
          setClarifyOptions([]);
          break;

        case 'listening':
          setOrbState('listening');
          setStatusLabel('LISTENING...');
          break;

        case 'transcript':
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
          setOrbState('processing');
          setStatusLabel('THINKING...');
          break;

        case 'speaking':
        case 'response':
          setOrbState('speaking');
          setStatusLabel('RESPONDING');
          if (msg.text) {
            setMessages(prev => [...prev, {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              text: msg.text!,
              timestamp: new Date(),
            }]);
          }
          break;

        case 'clarify':
          setOrbState('processing');
          setStatusLabel('NEEDS YOUR INPUT');
          setClarifyQuestion(msg.question || 'Which one?');
          setClarifyOptions(msg.options || []);
          setTranscription('');
          break;

        case 'error':
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

        case 'loading':
          setOrbState('processing');
          setStatusLabel(msg.text?.toUpperCase() || 'LOADING...');
          break;
      }
    });

    return () => window.yukiAPI?.removeStateListener();
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
    // Save on every message change, ignore the first default greeting if it's the only one
    if (window.yukiAPI && messages.length > 0) {
      window.yukiAPI.saveHistory(messages);
    }
  }, [messages]);

  // ── Actions ──────────────────────────────────────────────────────────────
  const handleTrigger = useCallback(() => {
    if (window.yukiAPI) {
      window.yukiAPI.trigger();
    } else {
      // Browser demo
      if (orbState === 'idle') {
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
            orbState={orbState}
            statusLabel={statusLabel}
            transcription={transcription}
            messages={messages}
            clarifyQuestion={clarifyQuestion}
            clarifyOptions={clarifyOptions}
            onTrigger={handleTrigger}
            onSendMessage={handleSendMessage}
            onChoice={handleChoice}
          />
        );
      case 'history':
        return <History messages={messages} />;
      case 'settings':
        return <Settings />;
      default:
        return null;
    }
  };

  if (isMiniMode) {
    return (
      <MiniWidget 
        orbState={orbState}
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
