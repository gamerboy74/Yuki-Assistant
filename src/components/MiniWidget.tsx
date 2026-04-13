/**
 * MiniWidget.tsx — Yuki compact floating pill (v4)
 *
 * Design principles (senior dev approach):
 * ─────────────────────────────────────────
 * 1. The Electron window is transparent + frameless at 480×80px.
 * 2. THIS component draws the actual rounded pill — giving us full
 *    design control (rounded corners, glow, backdrop, shadows).
 * 3. The pill floats over a fully transparent window background.
 * 4. Matches the cosmic HUD aesthetic of the main App.tsx exactly.
 * 5. The EnergyOrb is scaled down and clipped — same component, no dupe code.
 */

import { useEffect } from 'react';
import { useSettingsStore } from '../store/settingsStore';
import type { OrbState } from '../App';

interface MiniWidgetProps {
  onTrigger: () => void;
  onExpand: () => void;
  onClose: () => void;
  orbState: OrbState;
}

/* Per-state visual tokens — mirrors App.tsx SHELL_GLOW palette */
const STATE = {
  idle: {
    color: '#8ff5ff',
    accent: 'rgba(143,245,255,0.18)',
    label: 'READY',
    dot: 'bg-cyan-300/50',
    pulse: false,
  },
  listening: {
    color: '#8ff5ff',
    accent: 'rgba(143,245,255,0.32)',
    label: 'LISTENING',
    dot: 'bg-cyan-300',
    pulse: true,
  },
  processing: {
    color: '#fbbf24',
    accent: 'rgba(251,191,36,0.28)',
    label: 'THINKING',
    dot: 'bg-amber-400',
    pulse: true,
  },
  speaking: {
    color: '#ff32c8',
    accent: 'rgba(255,50,200,0.28)',
    label: 'SPEAKING',
    dot: 'bg-pink-400',
    pulse: true,
  },
};

export default function MiniWidget({ onTrigger, onExpand, onClose, orbState }: MiniWidgetProps) {
  const { assistantName: name, loadConfig } = useSettingsStore();
  const s = STATE[orbState];

  useEffect(() => { loadConfig(); }, []);

  /* Alt+Space shortcut */
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.altKey && e.code === 'Space') { e.preventDefault(); onTrigger(); }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onTrigger]);

  return (
    /*
      Root = transparent full-window canvas (Electron window is frameless+transparent).
      The pill floats inside with rounded corners + shadow — THIS is what gives
      the appearance of a floating rounded widget, not the OS window.
    */
    <div className="h-screen w-full flex items-end justify-center pb-2 overflow-hidden">

      {/* ── The Pill ──────────────────────────────────────────────────────────── */}
      <div
        className="
          relative w-full mx-2 h-[68px]
          flex items-center gap-3 px-3
          rounded-[20px] overflow-hidden
          drag-region
        "
        style={{
          /* Deep space base matching App.tsx #00000f */
          background: `
            radial-gradient(ellipse 80% 120% at 10% 50%, rgba(120,0,180,0.22) 0%, transparent 65%),
            radial-gradient(ellipse 60% 100% at 90% 50%, rgba(0,80,200,0.18) 0%, transparent 65%),
            linear-gradient(135deg, #0a0a14 0%, #06050f 100%)
          `,
          /* State-reactive glowing border */
          border: `1px solid ${s.accent}`,
          /* Soft drop shadow matching the cosmic glow */
          boxShadow: `
            0 8px 32px rgba(0,0,0,0.7),
            0 2px 8px rgba(0,0,0,0.5),
            inset 0 1px 0 rgba(255,255,255,0.06),
            0 0 20px ${s.accent}
          `,
          backdropFilter: 'blur(24px)',
        }}
      >
        {/* Reactive state-colour gradient wash over the pill */}
        <div
          className="absolute inset-0 pointer-events-none transition-all duration-700 rounded-[20px]"
          style={{
            background: `radial-gradient(ellipse 50% 120% at 0% 50%, ${s.color}10 0%, transparent 70%)`,
          }}
        />

        {/* ── Lightweight CSS Orb (GPU-efficient, replaces scaled EnergyOrb) ── */}
        <button
          onClick={onTrigger}
          className="relative flex-shrink-0 no-drag-region rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#06050f] focus-visible:ring-primary/80 transition-transform active:scale-95"
          aria-label={`Yuki — ${orbState}`}
          style={{ width: 52, height: 52 }}
        >
          {/* Glow layer */}
          <span
            className="absolute inset-0 rounded-full"
            style={{
              background: `radial-gradient(circle at 38% 35%, ${s.color}33 0%, ${s.color}08 60%, transparent 80%)`,
              boxShadow: `0 0 18px ${s.color}55, inset 0 1px 0 rgba(255,255,255,0.15)`,
              animation: s.pulse ? 'orbBreath 1.8s ease-in-out infinite' : 'orbBreath 3s ease-in-out infinite',
            }}
          />
          {/* Border ring */}
          <span
            className="absolute inset-0 rounded-full"
            style={{ border: `1px solid ${s.color}30` }}
          />
          {/* Icon */}
          <span
            className="absolute inset-0 flex items-center justify-center material-symbols-outlined text-[20px]"
            style={{
              color: s.color,
              filter: `drop-shadow(0 0 6px ${s.color})`,
              fontVariationSettings: "'FILL' 1",
            }}
          >
            {orbState === 'idle' ? 'graphic_eq' : orbState === 'listening' ? 'mic' : orbState === 'processing' ? 'cognition' : 'volume_up'}
          </span>
        </button>

        {/* ── Name + State label ───────────────────────────────────────── */}
        <div className="flex flex-col min-w-0 flex-1 z-10">
          <span
            className="text-sm font-bold tracking-tight leading-tight truncate"
            style={{
              color: s.color,
              fontFamily: "'Outfit', sans-serif",
              letterSpacing: '-0.01em',
            }}
          >
            {name}
          </span>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span
              className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${s.dot} ${s.pulse ? 'animate-pulse' : ''}`}
            />
            <span
              className="text-[9px] font-bold tracking-[0.2em] uppercase"
              style={{ color: `${s.color}99`, fontFamily: "'Outfit', sans-serif" }}
            >
              {s.label}
            </span>
          </div>
        </div>

        {/* ── Divider ──────────────────────────────────────────────────── */}
        <div className="w-px self-stretch my-3 bg-white/10 flex-shrink-0 z-10" />

        {/* ── Action Buttons ───────────────────────────────────────────── */}
        <div className="flex items-center gap-1 flex-shrink-0 z-10 no-drag-region">
          {/* Expand → full window */}
          <button
            onClick={onExpand}
            className="w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-200 text-white/55 hover:text-white hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white/40"
            title="Expand to full window"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 17 }}>open_in_full</span>
          </button>

          {/* Close widget */}
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-200 text-white/55 hover:text-red-400 hover:bg-red-500/[0.10] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-400/40"
            title="Hide widget"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 17 }}>close</span>
          </button>
        </div>
      </div>
    </div>
  );
}
