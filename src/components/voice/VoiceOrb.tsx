import { useState } from 'react';

type OrbState = 'idle' | 'listening' | 'speaking' | 'processing';

interface VoiceOrbProps {
  state?: OrbState;
  onClick?: () => void;
}

export function VoiceOrb({ state = 'idle', onClick }: VoiceOrbProps) {
  // Determine animation states based on the orb's state
  const isListening = state === 'listening';
  const isSpeaking = state === 'speaking';
  const isProcessing = state === 'processing';

  return (
    <div className="relative group flex items-center justify-center">
      {/* Outer Glows/Rings */}
      <div 
        className={`absolute -inset-16 border-[1px] border-tertiary-container/30 rounded-full transition-all duration-1000 ${
          isListening ? 'scale-[1.3] opacity-80 animate-ping' : 'scale-110 opacity-40'
        }`}
      />
      <div 
        className={`absolute -inset-8 border-[1px] border-tertiary-container/40 rounded-full transition-all duration-700 ${
          isSpeaking ? 'scale-[1.2] opacity-80' : 'scale-105 opacity-60'
        }`}
      />
      
      {/* Internal Spinners for Processing */}
      {isProcessing && (
        <div className="absolute inset-0 border-4 border-dashed border-cyan-400/50 rounded-full animate-[spin_3s_linear_infinite]" />
      )}

      {/* Glassmorphic Orb Body */}
      <div 
        onClick={onClick}
        className={`relative w-64 h-64 sm:w-80 sm:h-80 rounded-full bg-surface-container-low/50 backdrop-blur-3xl border border-white/10 flex items-center justify-center overflow-hidden cursor-pointer transition-all duration-500 ease-out-expo ${
          state !== 'idle' ? 'orb-pulse scale-105 shadow-[0_0_100px_rgba(34,211,238,0.3)]' : 'hover:scale-105'
        }`}
      >
        {/* Internal Volumetric Glows */}
        <div className="absolute inset-0 orb-inner-glow transition-opacity duration-500" />
        
        {/* Fluid states */}
        <div 
          className={`absolute w-64 h-64 bg-gradient-to-tr from-cyan-400/30 to-indigo-500/30 rounded-full blur-3xl transition-all duration-1000 ${
            isListening ? 'scale-125 translate-y-4' : 'opacity-50 translate-x-4 -translate-y-6'
          }`}
        />
        <div 
          className={`absolute w-48 h-48 bg-gradient-to-bl from-teal-300/20 to-transparent rounded-full blur-2xl transition-all duration-1000 ${
            isSpeaking ? 'scale-150 -translate-y-4' : 'opacity-40 -translate-x-10 translate-y-8'
          }`}
        />
        
        {/* Center Node / Icon */}
        <div className="relative z-10 w-24 h-24 flex items-center justify-center">
          <div className={`absolute inset-0 bg-cyan-300 blur-2xl scale-150 transition-opacity duration-500 ${isListening || isSpeaking ? 'opacity-40' : 'opacity-20'}`} />
          <span 
            className="material-symbols-outlined text-cyan-300 text-6xl transition-all duration-300 drop-shadow-[0_0_15px_rgba(34,211,238,0.8)]" 
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {isListening ? 'mic' : isProcessing ? 'autorenew' : 'graphic_eq'}
          </span>
        </div>
      </div>

      {/* Lower Waveform Visualizer (Only active when speaking/listening) */}
      <div 
        className={`absolute -bottom-20 left-1/2 -translate-x-1/2 flex items-end gap-1 h-12 w-48 transition-all duration-500 ${
          isSpeaking || isListening ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        }`}
      >
        <div className="flex-1 bg-cyan-400/30 h-1/2 rounded-full animate-[bounce_1s_infinite_100ms]"></div>
        <div className="flex-1 bg-cyan-400/50 h-3/4 rounded-full animate-[bounce_1.2s_infinite_200ms]"></div>
        <div className="flex-1 bg-cyan-400 h-full rounded-full animate-[bounce_0.8s_infinite_300ms] shadow-lg shadow-cyan-400/50"></div>
        <div className="flex-1 bg-cyan-400/60 h-2/3 rounded-full animate-[bounce_1s_infinite_400ms]"></div>
        <div className="flex-1 bg-cyan-400/40 h-1/2 rounded-full animate-[bounce_1.1s_infinite_500ms]"></div>
      </div>
    </div>
  );
}
