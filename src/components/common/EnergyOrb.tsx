import { memo } from 'react';
import type { OrbState } from '../../App';
import energySphere from '../../assets/energy-sphere.png';
import './EnergyOrb.css';

interface EnergyOrbProps {
  orbState: OrbState;
  isHotListening?: boolean;
  onTrigger: () => void;
  variant?: 'focus' | 'ambient';
  volume?: number;
}

const ICON_MAP: Record<OrbState, string> = {
  idle: 'graphic_eq',
  listening: 'mic',
  processing: 'cognition',
  speaking: 'volume_up',
};

const STATE_CONFIG = {
  idle: {
    iconColor: '#8ff5ff',
    ringColor: 'rgba(143,245,255,0.18)',
    glow: 'rgba(143,245,255,0.06)',
    orbClass: 'orb-idle',
    ringClass: 'ring-idle',
  },
  listening: {
    iconColor: '#8ff5ff',
    ringColor: 'rgba(143,245,255,0.35)',
    glow: 'rgba(143,245,255,0.14)',
    orbClass: 'orb-listening',
    ringClass: 'ring-listening',
  },
  processing: {
    iconColor: '#fbbf24',
    ringColor: 'rgba(251,191,36,0.30)',
    glow: 'rgba(251,191,36,0.10)',
    orbClass: 'orb-processing',
    ringClass: 'ring-processing',
  },
  speaking: {
    iconColor: '#ff32c8',
    ringColor: 'rgba(255,50,200,0.35)',
    glow: 'rgba(255,50,200,0.12)',
    orbClass: 'orb-speaking',
    ringClass: 'ring-speaking',
  },
};

export const EnergyOrb = memo(({
  orbState,
  isHotListening,
  onTrigger,
  variant = 'focus',
  volume = 0
}: EnergyOrbProps) => {
  const s = STATE_CONFIG[orbState];
  
  // ── Expert: Sentient Reactive Scaling ──
  // We apply a transformation multiplier based on real-time volume RMS.
  // The 'volume' value is 0.0 to 1.0. We map this to a subtle scale throb.
  const reactiveScale = 1 + (volume * 0.15); // Max 15% growth at peak volume
  const glowScale = 1 + (volume * 0.45);      // Stronger glow expansion

  return (
    <div className={`relative flex items-center justify-center select-none transition-all duration-1000 ${s.orbClass} ${variant === 'ambient' ? 'orb-ambient-mode' : ''}`} 
         style={{ width: variant === 'focus' ? 280 : 180, height: variant === 'focus' ? 280 : 180 }}>
      
      {/* Ambient glow */}
      <div
        className="absolute inset-0 rounded-full blur-3xl transition-all duration-100"
        style={{ 
          background: s.glow, 
          transform: variant === 'focus' 
            ? `scale(${1.6 * glowScale})` 
            : `scale(${1.2 * glowScale})` 
        }}
      />

      {/* Ripple rings */}
      <div className={`absolute inset-0 rounded-full border-2 transition-all duration-700 ${s.ringClass}`}
        style={{ borderColor: s.ringColor }} />
      <div className={`absolute rounded-full border transition-all duration-700 ${s.ringClass}`}
        style={{ inset: variant === 'focus' ? -20 : -10, borderColor: s.ringColor, opacity: 0.5 }} />
      {variant === 'focus' && (
        <div className={`absolute rounded-full border transition-all duration-700 ${s.ringClass}`}
            style={{ inset: -44, borderColor: s.ringColor, opacity: 0.2 }} />
      )}

      <button
        onClick={onTrigger}
        aria-label={`Voice agent — ${orbState}`}
        className={`relative z-10 rounded-full overflow-hidden focus:outline-none transition-all duration-100 cursor-pointer ${s.orbClass}`}
        style={{ 
          width: variant === 'focus' ? 220 : 140, 
          height: variant === 'focus' ? 220 : 140,
          transform: `scale(${reactiveScale})`
        }}
      >
        <img 
          src={energySphere} 
          alt="" 
          draggable={false}
          className="absolute inset-0 w-full h-full object-cover rounded-full pointer-events-none orb-img" 
        />
        <div className="absolute inset-0 rounded-full orb-overlay pointer-events-none" />
        
        {/* Scan-line texture for depth */}
        <div
          className="absolute inset-0 rounded-full pointer-events-none opacity-[0.04]"
          style={{
            backgroundImage: 'repeating-linear-gradient(0deg, #fff 0px, #fff 1px, transparent 1px, transparent 3px)',
          }}
        />

        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-12 h-12 rounded-full flex items-center justify-center transition-all duration-500"
            style={{ 
              width: variant === 'focus' ? 64 : 40,
              height: variant === 'focus' ? 64 : 40,
              background: 'rgba(0,0,0,0.45)', 
              backdropFilter: 'blur(12px)', 
              border: '1px solid rgba(255,255,255,0.15)', 
              boxShadow: `0 0 30px ${s.iconColor}40` 
            }}>
            <span 
              className="material-symbols-outlined transition-all duration-500" 
              style={{ 
                fontSize: variant === 'focus' ? '30px' : '20px',
                color: isHotListening ? '#8ff5ff' : s.iconColor, 
                filter: `drop-shadow(0 0 8px ${s.iconColor})`,
                fontVariationSettings: "'FILL' 1"
              }}
            >
              {ICON_MAP[orbState]}
            </span>
          </div>
        </div>
      </button>

      {/* Decorative arcs */}
      <svg className="absolute pointer-events-none" style={{ inset: variant === 'focus' ? -60 : -30, width: '100%', height: '100%' }} viewBox="0 0 400 400">
        <circle cx="200" cy="200" r="185" fill="none" stroke={s.ringColor} strokeWidth="0.5" strokeDasharray="6 18" className="arc-rotate" />
        <circle cx="200" cy="200" r="196" fill="none" stroke={s.ringColor} strokeWidth="0.3" strokeDasharray="2 30" className="arc-reverse" opacity="0.5" />
      </svg>
    </div>
  );
});
