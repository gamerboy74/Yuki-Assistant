/**
 * MiniWidget.tsx — Yuki compact floating pill
 *
 * A true glassmorphism pill that floats over the desktop.
 * Shows live state (idle / listening / processing / speaking).
 * Reads the assistant name from yuki.config.json via useConfig.
 */
import { useEffect } from 'react';
import { useConfig } from '../hooks/useConfig';
import type { OrbState } from '../App';

interface MiniWidgetProps {
  onExpand:  () => void;
  onClose:   () => void;
  orbState:  OrbState;
}

/* Per-state visual tokens */
const STATE = {
  idle: {
    color:  '#8ff5ff',
    dot:    'bg-[#8ff5ff]/40',
    label:  'READY',
    pulse:  false,
    icon:   'graphic_eq',
    border: 'rgba(143,245,255,0.12)',
    glow:   'rgba(143,245,255,0.06)',
  },
  listening: {
    color:  '#8ff5ff',
    dot:    'bg-[#8ff5ff]',
    label:  'LISTENING',
    pulse:  true,
    icon:   'mic',
    border: 'rgba(143,245,255,0.35)',
    glow:   'rgba(143,245,255,0.15)',
  },
  processing: {
    color:  '#fbbf24',
    dot:    'bg-amber-400',
    label:  'THINKING',
    pulse:  true,
    icon:   'cognition',
    border: 'rgba(251,191,36,0.30)',
    glow:   'rgba(251,191,36,0.10)',
  },
  speaking: {
    color:  '#34d399',
    dot:    'bg-emerald-400',
    label:  'SPEAKING',
    pulse:  true,
    icon:   'volume_up',
    border: 'rgba(52,211,153,0.30)',
    glow:   'rgba(52,211,153,0.10)',
  },
};

export default function MiniWidget({ onExpand, onClose, orbState }: MiniWidgetProps) {
  const { name } = useConfig();
  const s = STATE[orbState];

  /* Alt+Space shortcut */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.altKey && e.code === 'Space') { e.preventDefault(); window.yukiAPI?.trigger(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    /* Full-screen centering wrapper — background intentionally transparent */
    <div className="h-screen w-full flex items-center justify-center overflow-hidden drag-region">

      {/* ── Floating Pill ───────────────────────────────────────────────────── */}
      <div
        className="relative group drag-region"
        style={{ filter: `drop-shadow(0 12px 40px ${s.glow})` }}
      >

        {/* Outer glow ring — only visible when active */}
        <div
          className="absolute -inset-px rounded-2xl pointer-events-none transition-all duration-700"
          style={{
            boxShadow: orbState !== 'idle'
              ? `0 0 0 1px ${s.border}, 0 0 20px ${s.glow}`
              : 'none',
            borderRadius: 'inherit',
          }}
        />

        {/* Pill body — true glassmorphism */}
        <div
          className="glass-mini relative flex items-center gap-3 px-4 py-3 rounded-2xl pointer-events-auto transition-all duration-500"
          style={{
            borderColor: s.border,
            minWidth: 300,
          }}
        >

          {/* ── Left: Orb + Name + State ─────────────────────────────────── */}
          <div className="flex items-center gap-3 flex-1 min-w-0">

            {/* Mini orb */}
            <button
              onClick={() => window.yukiAPI?.trigger()}
              className="relative flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 hover:scale-110 focus:outline-none no-drag-region"
              style={{
                background: `radial-gradient(circle at 35% 35%, ${s.color}25 0%, ${s.color}08 60%, transparent)`,
                border: `1px solid ${s.color}50`,
                boxShadow: orbState !== 'idle' ? `0 0 16px ${s.color}30` : 'none',
              }}
              title="Trigger voice"
            >
              {/* Spinning ring for processing */}
              {orbState === 'processing' && (
                <div
                  className="absolute inset-0 rounded-full"
                  style={{
                    border: '1.5px solid transparent',
                    borderTopColor: s.color,
                    animation: 'spin 1.5s linear infinite',
                  }}
                />
              )}
              <span
                className="material-symbols-outlined text-lg transition-all duration-300"
                style={{
                  fontSize: 18,
                  color: s.color,
                  fontVariationSettings: "'FILL' 1",
                  filter: `drop-shadow(0 0 6px ${s.color}80)`,
                }}
              >
                {s.icon}
              </span>

              {/* Listening waveform bars inside orb */}
              {orbState === 'listening' && (
                <span
                  className="absolute inset-0 rounded-full"
                  style={{ background: `${s.color}08` }}
                />
              )}
            </button>

            {/* Name + state */}
            <div className="flex flex-col min-w-0">
              <span
                className="font-headline text-sm font-semibold tracking-tight leading-tight truncate"
                style={{ color: s.color }}
              >
                {name}
              </span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span
                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${s.dot} ${s.pulse ? 'animate-pulse' : ''}`}
                />
                <span
                  className="text-[9px] font-bold tracking-[0.2em] uppercase"
                  style={{ color: `${s.color}90` }}
                >
                  {s.label}
                </span>
              </div>
            </div>
          </div>

          {/* ── Divider ──────────────────────────────────────────────────── */}
          <div className="w-px h-6 bg-white/[0.06] flex-shrink-0" />

          {/* ── Right: Action buttons ─────────────────────────────────────  */}
          <div className="flex items-center gap-0.5 flex-shrink-0 no-drag-region">

            {/* Expand */}
            <button
              onClick={onExpand}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-white/30 hover:text-white/70 hover:bg-white/[0.06] transition-all duration-200"
              title="Expand"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>open_in_full</span>
            </button>

            {/* Close */}
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-white/20 hover:text-red-400/80 hover:bg-red-500/[0.08] transition-all duration-200"
              title="Close"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
            </button>
          </div>

        </div>

        {/* ── Hover hint ─────────────────────────────────────────────────── */}
        <div className="absolute top-full left-1/2 -translate-x-1/2 mt-3 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none whitespace-nowrap">
          <div className="glass-mini px-3 py-1.5 rounded-full flex items-center gap-2">
            <span className="material-symbols-outlined text-[11px]" style={{ color: s.color }}>keyboard</span>
            <span className="text-[10px] text-white/50 tracking-wide">
              <kbd className="text-white/70 font-sans">Alt + Space</kbd> to activate
            </span>
          </div>
        </div>

      </div>
    </div>
  );
}
