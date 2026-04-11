import { useRef, useEffect, useState, useCallback, memo, useMemo } from 'react';
import type { OrbState, ChatMessage } from '../App';
import energySphere from '../assets/energy-sphere.png';

interface AgentViewProps {
  viewMode: 'chat' | 'voice';
  orbState: OrbState;
  statusLabel: string;
  transcription: string;
  messages: ChatMessage[];
  clarifyQuestion?: string;
  clarifyOptions?: string[];
  isHotListening?: boolean;
  onTrigger: () => void;
  onSendMessage: (text: string) => void;
  onChoice: (choice: string) => void;
  selectedProvider?: string;
  onProviderChange?: (p: string) => void;
}

const PROVIDER_CONFIG: Record<string, { label: string, color: string, icon: string }> = {
  auto: { label: 'Automatic', color: '#fbbf24', icon: 'auto_awesome' },
  gemini: { label: 'Gemini Link', color: '#8ff5ff', icon: 'flare' },
  openai: { label: 'OpenAI Link', color: '#10a37f', icon: 'psychology' },
  ollama: { label: 'Local Link', color: '#d946ef', icon: 'hub' },
};

/* ── State config ─────────────────────────────────────────────────────────── */

const STATE = {
  idle: {
    label: 'YUKI.SYS',
    iconColor: '#8ff5ff',
    ringColor: 'rgba(143,245,255,0.18)',
    glow: 'rgba(143,245,255,0.06)',
    orbClass: 'orb-idle',
    ringClass: 'ring-idle',
  },
  listening: {
    label: 'LISTENING',
    iconColor: '#8ff5ff',
    ringColor: 'rgba(143,245,255,0.35)',
    glow: 'rgba(143,245,255,0.14)',
    orbClass: 'orb-listening',
    ringClass: 'ring-listening',
  },
  processing: {
    label: 'PROCESSING',
    iconColor: '#fbbf24',
    ringColor: 'rgba(251,191,36,0.30)',
    glow: 'rgba(251,191,36,0.10)',
    orbClass: 'orb-processing',
    ringClass: 'ring-processing',
  },
  speaking: {
    label: 'RESPONDING',
    iconColor: '#ff32c8',
    ringColor: 'rgba(255,50,200,0.35)',
    glow: 'rgba(255,50,200,0.12)',
    orbClass: 'orb-speaking',
    ringClass: 'ring-speaking',
  },
} satisfies Record<OrbState, { label: string; iconColor: string; ringColor: string; glow: string; orbClass: string; ringClass: string }>;

const ICON_MAP: Record<OrbState, string> = {
  idle: 'graphic_eq',
  listening: 'mic',
  processing: 'cognition',
  speaking: 'volume_up',
};

/* ── Message Thread ───────────────────────────────────────────────────────── */
const MessageThread = memo(({
  messages,
  iconColor,
  orbState,
}: {
  messages: ChatMessage[];
  iconColor: string;
  orbState: OrbState;
}) => (
  <div className="max-w-3xl mx-auto space-y-8 pb-10">
    {messages.map((msg, idx) => (
      <div
        key={msg.id}
        className={`flex flex-col gap-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
        style={{ animation: `msgIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) both ${idx * 0.05}s` }}
      >
        {/* HUD Metadata Header */}
        <div className={`flex items-center gap-3 px-1 opacity-40 font-mono text-[9px] tracking-widest uppercase
          ${msg.role === 'user' ? 'flex-row-reverse text-right' : 'text-left'}`}>
          <span className="font-bold">{msg.role === 'user' ? 'Local User' : 'Neural Core'}</span>
          <span>//</span>
          <span>{msg.role === 'user' ? 'Protocol: Manual' : 'Protocol: Synthetic'}</span>
          <span>//</span>
          <span>{msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        </div>

        {/* Message Segment */}
        <div
          className={`relative max-w-[85%] px-5 py-4 rounded-sm transition-all duration-500
            ${msg.role === 'user'
              ? 'bg-white/[0.03] border-r-2 border-white/20 text-white/90 shadow-sm'
              : 'bg-primary/5 border-l-2 border-primary/40 text-white shadow-[0_0_20px_rgba(143,245,255,0.03)]'
            }`}
        >
          <p className="leading-relaxed whitespace-pre-wrap text-sm font-light tracking-wide">{msg.text}</p>
          
          {/* Decorative Corner (Assistant only) */}
          {msg.role === 'assistant' && (
            <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-primary/30" />
          )}
        </div>
      </div>
    ))}

    {orbState === 'processing' && (
      <div className="flex flex-col gap-2 items-start" style={{ animation: 'msgIn 0.4s ease both' }}>
        <div className="flex items-center gap-3 px-1 opacity-20 font-mono text-[9px] tracking-widest uppercase">
          <span className="font-bold">Neural Core</span>
          <span>//</span>
          <span className="animate-pulse">Decoding Stream...</span>
        </div>
        <div className="flex gap-1.5 p-4 bg-primary/5 border-l-2 border-primary/10 rounded-sm">
          <div className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-pulse" />
          <div className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-pulse [animation-delay:0.2s]" />
          <div className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-pulse [animation-delay:0.4s]" />
        </div>
      </div>
    )}
  </div>
));

/* ── Energy Orb ───────────────────────────────────────────────────────────── */

function EnergyOrb({
  orbState,
  isHotListening,
  onTrigger,
}: {
  orbState: OrbState;
  isHotListening?: boolean;
  onTrigger: () => void;
}) {
  const s = STATE[orbState];

  return (
    <div className="relative flex items-center justify-center select-none" style={{ width: 280, height: 280 }}>

      {/* ── Ambient background glow ── */}
      <div
        className="absolute inset-0 rounded-full blur-3xl transition-all duration-1000"
        style={{ background: s.glow, transform: 'scale(1.6)' }}
      />

      {/* ── Ripple rings (state-driven) ── */}
      <div className={`absolute inset-0 rounded-full border-2 transition-all duration-700 ${s.ringClass}`}
        style={{ borderColor: s.ringColor }} />
      <div className={`absolute rounded-full border transition-all duration-700 ${s.ringClass}`}
        style={{ inset: -20, borderColor: s.ringColor, opacity: 0.5 }} />
      <div className={`absolute rounded-full border transition-all duration-700 ${s.ringClass}`}
        style={{ inset: -44, borderColor: s.ringColor, opacity: 0.2 }} />

      {/* ── THE ORB BUTTON ── */}
      <button
        onClick={onTrigger}
        aria-label={`Voice agent — ${orbState}`}
        className={`relative z-10 rounded-full overflow-hidden focus:outline-none active:scale-95 transition-transform duration-200 ${s.orbClass}`}
        style={{ width: 220, height: 220 }}
      >
        {/* PNG energy sphere base */}
        <img
          src={energySphere}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 w-full h-full object-cover rounded-full pointer-events-none orb-img"
          draggable={false}
        />

        {/* State-specific overlay blends */}
        <div className="absolute inset-0 rounded-full orb-overlay pointer-events-none" />

        {/* Scan-line texture for depth */}
        <div
          className="absolute inset-0 rounded-full pointer-events-none opacity-[0.04]"
          style={{
            backgroundImage: 'repeating-linear-gradient(0deg, #fff 0px, #fff 1px, transparent 1px, transparent 3px)',
          }}
        />

        {/* Glass center icon pill */}
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
        >
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center"
            style={{
              background: 'rgba(0,0,0,0.45)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(255,255,255,0.15)',
              boxShadow: `0 0 30px ${s.iconColor}40`,
            }}
          >
            <span
              className="material-symbols-outlined text-3xl"
              style={{
                color: isHotListening ? '#8ff5ff' : s.iconColor,
                fontVariationSettings: "'FILL' 1",
                filter: `drop-shadow(0 0 8px ${s.iconColor})`,
              }}
            >
              {ICON_MAP[orbState]}
            </span>
          </div>
        </div>
      </button>

      {/* ── Outer decorative arc ── */}
      <svg
        className="absolute pointer-events-none"
        style={{ inset: -60, width: 'calc(100% + 120px)', height: 'calc(100% + 120px)' }}
        viewBox="0 0 400 400"
      >
        <circle
          cx="200" cy="200" r="185"
          fill="none"
          stroke={s.ringColor}
          strokeWidth="0.5"
          strokeDasharray="6 18"
          className="arc-rotate"
        />
        <circle
          cx="200" cy="200" r="196"
          fill="none"
          stroke={s.ringColor}
          strokeWidth="0.3"
          strokeDasharray="2 30"
          className="arc-reverse"
          opacity="0.5"
        />
      </svg>
    </div>
  );
}

/* ── Main Component ───────────────────────────────────────────────────────── */

export default function AgentView({
  viewMode,
  orbState,
  statusLabel,
  transcription,
  messages,
  clarifyQuestion,
  clarifyOptions = [],
  isHotListening,
  onTrigger,
  onSendMessage,
  onChoice,
  selectedProvider = 'gemini',
  onProviderChange,
}: AgentViewProps) {
  const [inputText, setInputText] = useState('');
  const [showChat, setShowChat] = useState(viewMode === 'chat');
  const [showBrainMenu, setShowBrainMenu] = useState(false);
  const [greeting, setGreeting] = useState('Hello');
  const threadRef = useRef<HTMLDivElement>(null);

  const activeProvider = PROVIDER_CONFIG[selectedProvider] || PROVIDER_CONFIG.gemini;

  useEffect(() => {
    const h = new Date().getHours();
    setGreeting(h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening');
  }, []);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, orbState]);

  const handleSend = useCallback(() => {
    if (!inputText.trim()) return;
    onSendMessage(inputText);
    setInputText('');
  }, [inputText, onSendMessage]);

  const s = STATE[orbState];

  return (
    <div className="relative flex flex-col h-full overflow-hidden bg-transparent text-white selection:bg-cyan-500/30">

      {/* Local state-reactive nebula (adds depth atop global drift) */}
      <div className="absolute inset-0 pointer-events-none transition-all duration-1000"
        style={{ background: `radial-gradient(ellipse 65% 50% at 50% 55%, ${s.glow}, transparent 70%)` }}
      />

      {/* ── Neural Link Selector HUD ── */}
      <div className="absolute top-10 right-10 z-[60]">
        <div className="relative">
          <button
            onClick={() => setShowBrainMenu(!showBrainMenu)}
            className="flex items-center gap-3 bg-black/40 border border-white/5 pr-5 pl-3 py-2 rounded-full backdrop-blur-xl hover:bg-white/5 hover:border-white/20 transition-all select-none group"
            title="Switch Neural Link"
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-all duration-500`}
              style={{ background: `${activeProvider.color}15`, border: `1px solid ${activeProvider.color}30`, boxShadow: `0 0 15px ${activeProvider.color}20` }}>
              <span className="material-symbols-outlined text-[18px] animate-pulse" style={{ color: activeProvider.color }}>
                {activeProvider.icon}
              </span>
            </div>
            <div className="text-left">
              <div className="text-[8px] uppercase tracking-[0.2em] text-white/40 font-bold">Neural Link</div>
              <div className="text-[10px] font-mono tracking-wider opacity-80" style={{ color: activeProvider.color }}>
                {activeProvider.label.toUpperCase()}
              </div>
            </div>
            <span className={`material-symbols-outlined text-white/20 text-[16px] transition-transform duration-300 ${showBrainMenu ? 'rotate-180' : ''}`}>
              expand_more
            </span>
          </button>

          {/* Brain Menu Overlay */}
          {showBrainMenu && (
            <div className="absolute top-full mt-3 right-0 w-64 bg-black/80 border border-white/10 rounded-xl backdrop-blur-3xl shadow-2xl p-2 animate-msgIn overflow-hidden">
              <div className="px-3 py-2 mb-1 border-b border-white/5">
                <div className="text-[8px] uppercase tracking-[0.3em] text-white/20 font-bold">Available Synapses</div>
              </div>
              {Object.entries(PROVIDER_CONFIG).map(([key, cfg]) => (
                <button
                  key={key}
                  onClick={() => {
                    onProviderChange?.(key);
                    setShowBrainMenu(false);
                  }}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg transition-all group/item
                    ${selectedProvider === key ? 'bg-white/5 border border-white/10' : 'hover:bg-white/[0.03] border border-transparent'}`}
                >
                  <div className="w-8 h-8 rounded-full flex items-center justify-center border border-white/5" 
                    style={{ background: selectedProvider === key ? `${cfg.color}15` : 'transparent' }}>
                    <span className="material-symbols-outlined text-[18px]" style={{ color: selectedProvider === key ? cfg.color : 'rgba(255,255,255,0.2)' }}>
                      {cfg.icon}
                    </span>
                  </div>
                  <div className="text-left flex-1">
                    <div className="text-xs font-medium" style={{ color: selectedProvider === key ? 'white' : 'rgba(255,255,255,0.4)' }}>{cfg.label}</div>
                    <div className="text-[9px] opacity-40 uppercase tracking-tighter">
                      {key === 'ollama' ? 'Local Neural Link' : 'Cloud Neural Link'}
                    </div>
                  </div>
                  {selectedProvider === key && (
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.color, boxShadow: `0 0 10px ${cfg.color}` }} />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Orb Zone ── */}
      <div className={`flex-1 flex flex-col items-center justify-center transition-all duration-700 ease-out ${showChat ? 'pt-4' : 'pt-0'}`}>

        <EnergyOrb orbState={orbState} isHotListening={isHotListening} onTrigger={onTrigger} />

        {/* Status */}
        <div className="mt-10 text-center pointer-events-none" style={{ animation: 'fadeUp 0.6s ease both' }}>
          <p className="text-[9px] uppercase tracking-[0.6em] text-white/25 mb-2 font-bold">Protocol Yuki</p>
          <h2
            className="text-xs font-light tracking-[0.35em] uppercase transition-all duration-500"
            style={{ color: isHotListening ? '#8ff5ff' : s.iconColor }}
          >
            {isHotListening ? 'Ready for input…' : orbState === 'idle' ? `${greeting}, boss` : statusLabel}
          </h2>
          {transcription && (
            <p className="mt-4 text-[11px] font-mono text-white/35 max-w-xs mx-auto animate-pulse">
              &gt; {transcription}
            </p>
          )}
        </div>

        {/* Clarify choices */}
        {clarifyQuestion && (
          <div className="mt-8 flex flex-col items-center gap-4 px-6 max-w-md" style={{ animation: 'fadeUp 0.4s ease both' }}>
            <p className="text-gray-400 text-xs text-center leading-relaxed italic">"{clarifyQuestion}"</p>
            <div className="flex flex-wrap justify-center gap-2">
              {clarifyOptions.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => onChoice(opt)}
                  className="px-4 py-1.5 rounded-full text-[11px] font-medium border border-white/10 bg-white/5 hover:bg-white/10 transition-all active:scale-95"
                  style={{ color: s.iconColor }}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Chat Thread ── */}
      {showChat && (
        <div
          ref={threadRef}
          className="flex-[0.7] overflow-y-auto px-6 pb-36 pt-4 border-t border-white/5 bg-black/40 backdrop-blur-xl"
          style={{ animation: 'slideUp 0.4s cubic-bezier(0.2,0.8,0.2,1) both' }}
        >
          <MessageThread messages={messages} iconColor={s.iconColor} orbState={orbState} />
        </div>
      )}

      {/* ── Neural Terminal Input ── */}
      <div className="absolute bottom-0 inset-x-0 p-8 pt-20 bg-gradient-to-t from-black via-black/90 to-transparent pointer-events-none z-50">
        <div className="max-w-2xl mx-auto pointer-events-auto">
          
          {/* Terminal Command Prompt Label */}
          <div className="flex items-center gap-2 mb-2 px-4 opacity-50">
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: activeProvider.color }} />
            <span className="text-[9px] font-mono tracking-[0.2em] uppercase text-white/40">Status: Online // Link: {activeProvider.label} // Cycle: {orbState.toUpperCase()}</span>
          </div>

          <div className={`relative flex items-center gap-3 bg-black/60 border border-white/10 p-3 pl-6 rounded-lg backdrop-blur-3xl shadow-[0_0_50px_rgba(0,0,0,0.5)] transition-all duration-500 group
              ${orbState === 'processing' ? 'border-primary/40 shadow-[0_0_20px_rgba(143,245,255,0.1)]' : 'hover:border-white/20'}`}
          >
            {/* Terminal Prompt Indicator */}
            <div className="flex items-center gap-1.5 group-hover:gap-2 transition-all">
              <span className="text-primary font-mono text-sm font-bold opacity-70 select-none">&gt;_</span>
              
              {/* Neural Waveform Visualizer */}
              <div className="flex items-center gap-[2px] h-3 px-1">
                {[...Array(5)].map((_, i) => (
                  <div
                    key={i}
                    className={`w-[2px] rounded-full transition-all duration-300
                      ${orbState === 'listening' ? 'animate-wave-active' : orbState === 'processing' ? 'animate-wave-thinking' : 'h-1 opacity-20'}`}
                    style={{ 
                      background: activeProvider.color,
                      animationDelay: `${i * 0.1}s`,
                      height: orbState === 'listening' ? '12px' : orbState === 'processing' ? '8px' : '4px'
                    }}
                  />
                ))}
              </div>
            </div>
            
            <input
              className="flex-1 bg-transparent border-none outline-none text-sm font-mono placeholder:text-white/10 text-white selection:bg-primary/30"
              placeholder="Awaiting command..."
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
            />

            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowChat(v => !v)}
                className="p-2 rounded-md text-white/20 hover:text-primary hover:bg-white/5 transition-all"
                title={showChat ? 'Deactivate HUD Overlay' : 'Activate HUD Overlay'}
              >
                <span className="material-symbols-outlined text-[20px]">
                  {showChat ? 'layers_clear' : 'terminal'}
                </span>
              </button>

              <button
                onClick={handleSend}
                disabled={!inputText.trim()}
                className="w-10 h-10 rounded-md flex items-center justify-center transition-all bg-primary/10 border border-primary/20 text-primary hover:bg-primary hover:text-black active:scale-95 disabled:opacity-5 disabled:grayscale"
              >
                <span className="material-symbols-outlined font-bold text-[20px]">play_arrow</span>
              </button>
            </div>

            {/* Subtle Inner Glow */}
            <div className="absolute inset-0 rounded-lg pointer-events-none border border-white/[0.03]" />
          </div>
        </div>
      </div>

      {/* ── All Styles ── */}
      <style>{`
        /* ── Orb base image ── */
        .orb-img {
          transition: filter 0.8s ease, transform 0.8s ease;
        }

        /* ── IDLE: gentle breathe + slow drift ── */
        .orb-idle .orb-img {
          animation: orbBreath 5s ease-in-out infinite;
          filter: brightness(0.75) saturate(1.1);
        }
        .orb-idle .orb-overlay {
          background: radial-gradient(circle at 50% 50%, rgba(143,245,255,0.05) 0%, transparent 70%);
          animation: none;
        }
        .ring-idle {
          animation: ringIdle 6s ease-in-out infinite;
          opacity: 0.25;
        }

        @keyframes orbBreath {
          0%,100% { transform: scale(1);    filter: brightness(0.75) saturate(1.1); }
          50%      { transform: scale(1.04); filter: brightness(0.85) saturate(1.2); }
        }
        @keyframes ringIdle {
          0%,100% { transform: scale(1);    opacity: 0.25; }
          50%      { transform: scale(1.04); opacity: 0.40; }
        }

        /* ── LISTENING: fast pulse + ripple rings ── */
        .orb-listening .orb-img {
          animation: orbListen 1.4s ease-in-out infinite;
          filter: brightness(1) saturate(1.4);
        }
        .orb-listening .orb-overlay {
          background: radial-gradient(circle at 50% 50%, rgba(143,245,255,0.12) 0%, transparent 65%);
          animation: overlayListen 1.4s ease-in-out infinite;
        }
        .ring-listening {
          animation: ringRipple 1.2s ease-out infinite;
        }

        @keyframes orbListen {
          0%,100% { transform: scale(1);    filter: brightness(1) saturate(1.4); }
          50%      { transform: scale(1.06); filter: brightness(1.15) saturate(1.6); }
        }
        @keyframes overlayListen {
          0%,100% { opacity: 0.7; }
          50%      { opacity: 1;   }
        }
        @keyframes ringRipple {
          0%   { transform: scale(1);    opacity: 0.8; }
          100% { transform: scale(1.18); opacity: 0;   }
        }

        /* ── PROCESSING: spin + hue-rotate ── */
        .orb-processing .orb-img {
          animation: orbProcess 2s linear infinite;
          filter: brightness(1) saturate(1.3) hue-rotate(0deg);
        }
        .orb-processing .orb-overlay {
          background: conic-gradient(from 0deg, rgba(251,191,36,0.18) 0%, transparent 50%, rgba(251,191,36,0.18) 100%);
          animation: overlaySpin 2s linear infinite;
        }
        .ring-processing {
          animation: ringProcess 1s ease-in-out infinite;
        }

        @keyframes orbProcess {
          0%   { filter: brightness(1) saturate(1.3) hue-rotate(0deg);   transform: scale(1);    }
          50%  { filter: brightness(1.1) saturate(1.5) hue-rotate(20deg); transform: scale(1.03); }
          100% { filter: brightness(1) saturate(1.3) hue-rotate(0deg);   transform: scale(1);    }
        }
        @keyframes overlaySpin {
          from { transform: rotate(0deg);   }
          to   { transform: rotate(360deg); }
        }
        @keyframes ringProcess {
          0%,100% { transform: scale(1);    opacity: 0.6; }
          50%      { transform: scale(1.08); opacity: 0.9; }
        }

        /* ── SPEAKING: throb + magenta shimmer ── */
        .orb-speaking .orb-img {
          animation: orbSpeak 0.7s ease-in-out infinite;
          filter: brightness(1.1) saturate(1.6);
        }
        .orb-speaking .orb-overlay {
          background: radial-gradient(circle at 45% 45%, rgba(255,50,200,0.22) 0%, transparent 60%);
          animation: overlaySpeak 0.7s ease-in-out infinite;
        }
        .ring-speaking {
          animation: ringSpeak 0.7s ease-in-out infinite;
        }

        @keyframes orbSpeak {
          0%,100% { transform: scale(1);    filter: brightness(1.1) saturate(1.6); }
          40%      { transform: scale(1.07); filter: brightness(1.25) saturate(1.9); }
          70%      { transform: scale(1.04); filter: brightness(1.15) saturate(1.7); }
        }
        @keyframes overlaySpeak {
          0%,100% { opacity: 0.8; }
          50%      { opacity: 1;   }
        }
        @keyframes ringSpeak {
          0%,100% { transform: scale(1);    opacity: 0.9; }
          50%      { transform: scale(1.10); opacity: 0.5; }
        }

        /* ── Decorative arcs ── */
        .arc-rotate  { animation: arcSpin 20s linear infinite; transform-origin: center; transform-box: fill-box; }
        .arc-reverse { animation: arcSpin 30s linear infinite reverse; transform-origin: center; transform-box: fill-box; }
        @keyframes arcSpin {
          from { transform: rotate(0deg);   }
          to   { transform: rotate(360deg); }
        }

        /* ── UI transitions ── */
        @keyframes fadeUp  { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes msgIn   { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }

        /* Custom scrollbar */
        ::-webkit-scrollbar       { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.18); }

        /* Neural Waveform Animations */
        @keyframes waveActive {
          0%, 100% { height: 4px; opacity: 0.3; }
          50% { height: 12px; opacity: 1; }
        }
        .animate-wave-active {
          animation: waveActive 0.6s ease-in-out infinite;
        }

        @keyframes waveThinking {
          0%, 100% { opacity: 0.2; transform: scaleY(1); }
          50% { opacity: 0.8; transform: scaleY(1.5); }
        }
        .animate-wave-thinking {
          animation: waveThinking 1s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
