/**
 * AgentView.tsx — Yuki Voice Agent Interface
 *
 * Layout: Full-screen orb-centered voice experience.
 * The orb IS the agent — it breathes, listens, pulses, speaks.
 * Chat is secondary, revealed below.
 */

import { useRef, useEffect, useState, useCallback, memo } from 'react';
import type { OrbState, ChatMessage } from '../App';

/* ── Sub-components for performance ───────────────────────────────────────── */

const MessageThread = memo(({ messages, colorPrimary, orbState }: { messages: ChatMessage[], colorPrimary: string, orbState: OrbState }) => {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex flex-col gap-1 animate-fade-in ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
        >
          {msg.role === 'user' ? (
            <div className="max-w-[75%] px-4 py-2.5 rounded-2xl rounded-br-sm bg-surface-container-high text-on-surface text-sm font-light">
              {msg.text}
            </div>
          ) : (
            <div className="max-w-[75%] flex gap-2.5 items-start">
              <div
                className="w-1.5 h-1.5 rounded-full mt-2 flex-shrink-0"
                style={{ background: colorPrimary }}
              />
              <p className="text-on-surface text-sm font-light leading-relaxed">
                {msg.text}
              </p>
            </div>
          )}
        </div>
      ))}

      {/* Processing dots in chat */}
      {orbState === 'processing' && (
        <div className="flex items-start gap-2.5 animate-fade-in">
          <div className="w-1.5 h-1.5 rounded-full mt-2.5 opacity-50" style={{ background: colorPrimary }} />
          <div className="flex gap-1.5 items-center pt-1">
            {[0, 150, 300].map(delay => (
              <div
                key={delay}
                className="w-2 h-2 rounded-full animate-bounce"
                style={{ background: colorPrimary, opacity: 0.6, animationDelay: `${delay}ms` }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

interface AgentViewProps {
  viewMode:        'chat' | 'voice';
  orbState:        OrbState;
  statusLabel:     string;
  transcription:   string;
  messages:        ChatMessage[];
  clarifyQuestion: string;
  clarifyOptions:  string[];
  isHotListening:  boolean;
  onTrigger:       () => void;
  onSendMessage:   (text: string) => void;
  onChoice:        (choice: string) => void;
}

/* ── State → visual config ───────────────────────────────────────────────── */
const STATE_CONFIG = {
  idle: {
    ring1: 'scale-100 opacity-20',
    ring2: 'scale-100 opacity-10',
    ring3: 'scale-100 opacity-[0.05]',
    glow:  'opacity-20',
    orb:   'scale-100',
    shadow: '0 0 60px rgba(143,245,255,0.08)',
    label:  'opacity-40',
  },
  listening: {
    ring1: 'scale-110 opacity-60',
    ring2: 'scale-125 opacity-40',
    ring3: 'scale-150 opacity-20',
    glow:  'opacity-60',
    orb:   'scale-105',
    shadow: '0 0 120px rgba(143,245,255,0.35)',
    label:  'opacity-100',
  },
  processing: {
    ring1: 'scale-105 opacity-30',
    ring2: 'scale-115 opacity-20',
    ring3: 'scale-130 opacity-10',
    glow:  'opacity-30',
    orb:   'scale-100',
    shadow: '0 0 80px rgba(251,191,36,0.25)',
    label:  'opacity-100',
  },
  speaking: {
    ring1: 'scale-115 opacity-70',
    ring2: 'scale-130 opacity-50',
    ring3: 'scale-155 opacity-25',
    glow:  'opacity-70',
    orb:   'scale-108',
    shadow: '0 0 140px rgba(52,211,153,0.35)',
    label:  'opacity-100',
  },
} as const;

const STATE_COLORS = {
  idle:       { primary: '#8ff5ff', bg: 'rgba(143,245,255,0.03)' },
  listening:  { primary: '#8ff5ff', bg: 'rgba(143,245,255,0.12)' },
  processing: { primary: '#fbbf24', bg: 'rgba(251,191,36,0.08)'  },
  speaking:   { primary: '#34d399', bg: 'rgba(52,211,153,0.10)'  },
};

const ICON_MAP = {
  idle:       'graphic_eq',
  listening:  'mic',
  processing: 'cognition',
  speaking:   'volume_up',
};

export default function AgentView({
  viewMode,
  orbState,
  statusLabel,
  transcription,
  messages,
  clarifyQuestion,
  clarifyOptions,
  isHotListening,
  onTrigger,
  onSendMessage,
  onChoice,
}: AgentViewProps) {
  const [inputText,    setInputText]    = useState('');
  const [showChat,     setShowChat]     = useState(true);
  const [lastResponse, setLastResponse] = useState('');
  const [greeting,     setGreeting]     = useState('Hello');
  const threadRef = useRef<HTMLDivElement>(null);

  // Sync showChat with viewMode when it changes
  useEffect(() => {
    setShowChat(viewMode === 'chat');
  }, [viewMode]);

  // Time-based greeting
  useEffect(() => {
    const hour = new Date().getHours();
    if (hour < 12) setGreeting('Good morning');
    else if (hour < 18) setGreeting('Good afternoon');
    else setGreeting('Good evening');
  }, []);

  const color   = STATE_COLORS[orbState];
  const cfg     = STATE_CONFIG[orbState];
  const isActive = orbState !== 'idle';

  // Track last assistant message for the main display – keep it visible even after finish speaking
  useEffect(() => {
    const last = [...messages].reverse().find(m => m.role === 'assistant');
    if (last) {
      setLastResponse(last.text);
    }
  }, [messages]);

  // Reset display when a new interaction begins (listening)
  useEffect(() => {
    if (orbState === 'listening') {
      setLastResponse('');
    }
  }, [orbState]);

  // Auto-scroll chat
  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(() => {
    const text = inputText.trim();
    if (!text) return;
    onSendMessage(text);
    setInputText('');
    setShowChat(true);
  }, [inputText, onSendMessage]);

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  // Number of visualizer bars to render (more when speaking)
  const BAR_COUNT = orbState === 'speaking' ? 40 : orbState === 'listening' ? 32 : 20;

  return (
    <div
      className="relative flex flex-col h-full overflow-hidden"
      style={{ background: '#0c0e11' }}
    >

      {/* ── Full-page ambient background glow ─────────────────────────────── */}
      <div
        className="absolute inset-0 pointer-events-none transition-all duration-1000"
        style={{
          background: `radial-gradient(ellipse 70% 60% at 50% 50%, ${color.bg} 0%, transparent 70%)`,
        }}
      />

      {/* ── Dot-grid texture ──────────────────────────────────────────────── */}
      <div className="absolute inset-0 pointer-events-none dot-grid opacity-[0.025]" />

      {/* ── Ambient Floating Particles ──────────────────────────────────────  */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="absolute rounded-full bg-primary/10 animate-float blur-sm"
            style={{
              width: Math.random() * 4 + 2,
              height: Math.random() * 4 + 2,
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 5}s`,
              animationDuration: `${Math.random() * 10 + 10}s`,
            }}
          />
        ))}
      </div>

      {/* ══ MAIN ORB ZONE ═════════════════════════════════════════════════  */}
      <div
        className={`flex-1 flex flex-col items-center justify-center transition-all duration-700 ease-out-expo ${
          viewMode === 'chat' ? 'pt-2 pb-2' : (showChat ? 'pt-4' : 'pt-0')
        }`}
        style={{ 
          minHeight: viewMode === 'chat' ? '180px' : (showChat ? '45%' : '65%'),
          maxHeight: viewMode === 'chat' ? '240px' : 'none'
        }}
      >

        {/* ── Outer decorative rings ───────────────────────────────────────  */}
        <div className="relative flex items-center justify-center">

          {/* Ring 3 — outermost */}
          <div
            className={`absolute rounded-full border border-current transition-all duration-1000 ease-out`}
            style={{
              width: viewMode === 'chat' ? 240 : 380, 
              height: viewMode === 'chat' ? 240 : 380,
              color: color.primary,
              opacity: 0,
              ...(orbState === 'listening'  && { opacity: 0.08, transform: 'scale(1.05)' }),
              ...(orbState === 'speaking'   && { opacity: 0.12, transform: 'scale(1.08)' }),
            }}
          />

          {/* Ring 2 */}
          <div
            className="absolute rounded-full border transition-all duration-700 ease-out"
            style={{
              width: viewMode === 'chat' ? 180 : 300, 
              height: viewMode === 'chat' ? 180 : 300,
              borderColor: color.primary,
              opacity: isActive ? 0.18 : 0.06,
              transform: isActive ? 'scale(1.04)' : 'scale(1)',
            }}
          />

          {/* Ring 1 — innermost ring */}
          <div
            className="absolute rounded-full border-2 transition-all duration-500 ease-out"
            style={{
              width: viewMode === 'chat' ? 140 : 234, 
              height: viewMode === 'chat' ? 140 : 234,
              borderColor: color.primary,
              opacity: isActive ? 0.45 : 0.12,
              transform: isActive ? 'scale(1.02)' : 'scale(1)',
            }}
          />

          {/* ── The Orb ────────────────────────────────────────────────────  */}
          <button
            onClick={onTrigger}
            className="relative rounded-full flex items-center justify-center cursor-pointer transition-all duration-500 focus:outline-none group overflow-hidden"
            style={{
              width: viewMode === 'chat' ? 100 : 208, // Adjusted from 208 (52*4) to 100
              height: viewMode === 'chat' ? 100 : 208,
              background: `radial-gradient(circle at 35% 35%, ${color.primary}22 0%, ${color.primary}08 50%, transparent 70%)`,
              border: `1px solid ${color.primary}30`,
              boxShadow: isActive
                ? `0 0 80px ${color.primary}30, 0 0 160px ${color.primary}15, inset 0 0 60px ${color.primary}08`
                : `0 0 40px ${color.primary}10, inset 0 0 30px ${color.primary}04`,
              backdropFilter: 'blur(20px)',
              transform: isActive ? 'scale(1.04)' : 'scale(1)',
            }}
            aria-label="Activate Yuki"
          >
            {/* Inner fluid glow */}
            <div
              className="absolute inset-4 rounded-full transition-all duration-700"
              style={{
                background: `radial-gradient(circle at 40% 40%, ${color.primary}18 0%, transparent 60%)`,
                filter: 'blur(8px)',
              }}
            />

            {/* Processing spin ring */}
            {orbState === 'processing' && (
              <div
                className="absolute inset-6 rounded-full"
                style={{
                  border: `1.5px solid transparent`,
                  borderTopColor: color.primary,
                  borderRightColor: `${color.primary}50`,
                  animation: 'spin 1.5s linear infinite',
                }}
              />
            )}

            {/* Icon */}
            <span
              className="relative z-10 material-symbols-outlined transition-all duration-300"
              style={{
                fontSize: viewMode === 'chat' ? 32 : 52,
                color: color.primary,
                fontVariationSettings: "'FILL' 1",
                filter: `drop-shadow(0 0 12px ${color.primary}90)`,
              }}
            >
              {ICON_MAP[orbState]}
            </span>

            {/* Hover ring */}
            <div
              className="absolute inset-0 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300"
              style={{ boxShadow: `0 0 0 2px ${color.primary}40` }}
            />
          </button>
        </div>

        {/* ── Waveform visualizer bars ──────────────────────────────────────  */}
        {viewMode !== 'chat' && (
          <div
            className="flex items-end justify-center mt-10 transition-all duration-500 gap-[3px]"
            style={{
              height: 52,
              opacity: isActive ? 1 : 0.2,
            }}
          >
          {Array.from({ length: BAR_COUNT }).map((_, i) => {
            const center   = BAR_COUNT / 2;
            const dist     = Math.abs(i - center) / center;
            const baseH    = orbState === 'speaking'
              ? (1 - dist * 0.5) * 44 + Math.random() * 8
              : orbState === 'listening'
              ? (1 - dist * 0.6) * 36 + Math.random() * 10
              : 6 + (1 - dist) * 10;
            const delay    = (i / BAR_COUNT) * 1.2;
            const duration = 0.6 + Math.random() * 0.6;

            return (
              <div
                key={i}
                className="rounded-full flex-shrink-0"
                style={{
                  width: 3,
                  minHeight: 4,
                  height: `${Math.max(4, baseH)}px`,
                  background: color.primary,
                  opacity: isActive ? 0.4 + (1 - dist) * 0.6 : 0.3,
                  animation: isActive
                    ? `visualizerBar ${duration}s ease-in-out ${delay}s infinite alternate`
                    : 'none',
                  boxShadow: (i === Math.floor(center) || i === Math.ceil(center)) && isActive
                    ? `0 0 8px ${color.primary}`
                    : 'none',
                }}
              />
            );
          })}
        </div>
        )}

        {/* ── Status label ─────────────────────────────────────────────────  */}
        <div
          className={`${viewMode === 'chat' ? 'mt-2' : 'mt-6'} font-label text-xs tracking-[0.25em] uppercase transition-all duration-500`}
          style={{ color: isHotListening ? '#8ff5ff' : color.primary, opacity: isActive || isHotListening ? 1 : 0.35 }}
        >
          {isHotListening ? 'READY FOR MORE...' : orbState === 'idle' ? `${greeting}, Boss` : statusLabel}
        </div>

        {/* Spoken/transcript overlays intentionally hidden for a cleaner orb view. */}

        {/* ── Clarification buttons ─────────────────────────────────────────  */}
        {clarifyQuestion && clarifyOptions.length > 0 && (
          <div className="mt-8 flex flex-col items-center gap-3 animate-slide-up px-12 max-w-lg w-full">
            <p className="text-on-surface-variant text-sm tracking-wide text-center">
              {clarifyQuestion}
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {clarifyOptions.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => onChoice(opt)}
                  className="px-4 py-2 rounded-full text-xs font-semibold border transition-all duration-200 hover:scale-105"
                  style={{
                    borderColor: `${color.primary}40`,
                    color: color.primary,
                    background: `${color.primary}0a`,
                  }}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Show chat toggle ──────────────────────────────────────────────  */}
        <button
          onClick={() => setShowChat(v => !v)}
          className="mt-8 flex items-center gap-2 text-on-surface-variant/40 hover:text-on-surface-variant/70 transition-colors text-xs tracking-widest uppercase font-label"
        >
          <span className="material-symbols-outlined text-sm">
            {showChat ? 'expand_less' : 'chat_bubble'}
          </span>
          {showChat ? 'Hide chat' : 'Show chat'}
        </button>
      </div>

      {/* ══ CHAT LOG (secondary, collapsible) ═════════════════════════════  */}
      {showChat && (
        <div
          ref={threadRef}
          className={`flex-1 overflow-y-auto px-8 pt-4 pb-28 subtle-scrollbar border-t border-outline-variant/10 animate-slide-up bg-black/20`}
          style={{ maxHeight: viewMode === 'chat' ? 'none' : '45%' }}
        >
          <MessageThread messages={messages} colorPrimary={color.primary} orbState={orbState} />
        </div>
      )}

      {/* ══ INPUT BAR (always visible at bottom) ══════════════════════════  */}
      <div className="absolute bottom-0 left-0 right-0 px-8 pb-6 pt-12 bg-gradient-to-t from-background via-background/95 to-transparent pointer-events-none z-20">
        <div className="max-w-xl mx-auto pointer-events-auto">
          <div className="relative group">
            {/* Hover glow */}
            <div
              className="absolute -inset-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-sm"
              style={{ background: `${color.primary}20` }}
            />
            {/* Input pill */}
            <div
              className="relative flex items-center px-5 py-3 rounded-full gap-3 transition-all duration-300"
              style={{
                background: 'rgba(17,20,23,0.8)',
                border: `1px solid ${isActive ? color.primary + '40' : 'rgba(70,72,75,0.4)'}`,
                backdropFilter: 'blur(20px)',
                boxShadow: isActive ? `0 0 20px ${color.primary}15` : 'none',
              }}
            >
              <span
                className="material-symbols-outlined text-lg flex-shrink-0 transition-colors duration-300"
                style={{ color: isActive ? color.primary : 'rgba(170,171,175,0.5)' }}
              >
                auto_awesome
              </span>

              <input
                type="text"
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                onKeyDown={handleKey}
                placeholder={isActive ? statusLabel.toLowerCase() + '...' : 'Type something to Yuki...'}
                className="flex-1 bg-transparent outline-none border-none text-on-surface text-sm font-light placeholder:text-on-surface-variant/30 min-w-0"
              />

              {/* Send button */}
              {inputText && (
                <button
                  onClick={handleSend}
                  className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all duration-200 hover:scale-110"
                  style={{
                    background: `${color.primary}20`,
                    border: `1px solid ${color.primary}50`,
                  }}
                >
                  <span className="material-symbols-outlined text-sm" style={{ color: color.primary }}>
                    arrow_upward
                  </span>
                </button>
              )}

              {/* Mic button */}
              {!inputText && (
                <button
                  onClick={onTrigger}
                  className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300 ${isActive ? 'animate-pulse' : 'hover:scale-110'}`}
                  style={{
                    background: isActive ? `${color.primary}30` : `${color.primary}15`,
                    border: `1px solid ${color.primary}40`,
                  }}
                >
                  <span
                    className="material-symbols-outlined text-sm"
                    style={{ color: color.primary, fontVariationSettings: "'FILL' 1" }}
                  >
                    mic
                  </span>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
