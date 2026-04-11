import React, { memo, useState, useRef } from 'react';
import { SettingsState } from './useSettingsReducer';

interface VoicesPanelProps {
  state: SettingsState['tts'];
  secrets: SettingsState['secrets'];
  availableVoices: any[];
  previewingId: string | null;
  onUpdate: (field: string, value: any) => void;
  onVoiceSelect: (voiceId: string, provider: string) => void;
  onPreview: (voiceId: string, provider: string) => void;
}

export const VoicesPanel = memo(({ 
  state, 
  secrets, 
  availableVoices, 
  previewingId,
  onUpdate,
  onVoiceSelect,
  onPreview
}: VoicesPanelProps) => {
  const [showEl, setShowEl] = useState(false);
  const [voiceSearch, setVoiceSearch] = useState('');
  const [genderFilter, setGenderFilter] = useState<'female' | 'male'>('female');
  const carouselRef = useRef<HTMLDivElement>(null);

  const scrollCarousel = (direction: 'left' | 'right') => {
    if (carouselRef.current) {
      const scrollAmount = 400;
      carouselRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth'
      });
    }
  };

  return (
    <div className="space-y-12 panel-enter">
      {/* Section A: Provider Selector */}
      <section>
        <div className="mb-6">
          <h2 className="font-headline text-3xl font-bold tracking-tight text-on-surface mb-2 uppercase">Neural Providers</h2>
          <p className="font-label text-sm text-on-surface-variant">Select source architecture for vocal synthesis.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-1">
          {[
            { id: 'edge-tts', label: 'EDGE-TTS', color: 'primary', usage: 'FREE', progress: 100 },
            { id: 'elevenlabs', label: 'ELEVENLABS', color: 'secondary', usage: `LIMIT: ${state.elevenlabsBudget}`, progress: (state.elevenlabsBudget / 1000) * 100 },
            { id: 'pyttsx3', label: 'PYTTSX3', color: 'tertiary', usage: 'OFFLINE', progress: 20 }
          ].map(p => (
            <div key={p.id} onClick={() => onUpdate('tts.provider', p.id)}
              className={`bg-surface-container-low p-6 border-l-2 cursor-pointer transition-opacity ${state.provider === p.id ? `border-${p.color}` : 'border-outline-variant/20 opacity-60 hover:opacity-100'}`}>
              <div className="flex justify-between items-start mb-8">
                <div className={`font-label text-xs font-bold ${state.provider === p.id ? `text-${p.color}` : 'text-on-surface-variant'}`}>{p.label}</div>
                <span className={`material-symbols-outlined text-${p.color}`}>{state.provider === p.id ? 'check_circle' : 'radio_button_unchecked'}</span>
              </div>
              <div className="space-y-4">
                <div className="flex justify-between font-label text-[10px]">
                  <span className="text-on-surface-variant">API USAGE</span>
                  <span className={`text-${p.color}`}>{p.usage}</span>
                </div>
                <div className="h-[2px] bg-surface-container-highest w-full overflow-hidden">
                  <div className={`h-full bg-${p.color}`} style={{ width: `${p.progress}%` }}></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Section B: Vocal Entities */}
      <section className="space-y-12">
        <div>
          <div className="mb-6">
            <h2 className="font-headline text-2xl font-bold tracking-tight text-primary mb-1 uppercase">Neural Identities</h2>
            <p className="font-label text-xs text-on-surface-variant">Primary high-fidelity vocal configurations.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { id: 'en-IN-NeerjaNeural', name: 'YUKI-01', desc: 'SYMPATHETIC / FEMALE', color: 'primary', img: 'https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?q=80&w=600&auto=format&fit=crop' },
              { id: 'en-US-GuyNeural', name: 'NOVA-CORE', desc: 'AUTHORITATIVE / MALE', color: 'secondary', img: 'https://images.unsplash.com/photo-1614741118887-7a4ee193a5fa?q=80&w=600&auto=format&fit=crop' },
              { id: 'en-GB-SoniaNeural', name: 'PULSE-B', desc: 'TECHNICAL / FEMALE', color: 'tertiary', img: 'https://images.unsplash.com/photo-1558591710-4b4a1ae0f04d?q=80&w=600&auto=format&fit=crop' }
            ].map(identity => {
              const isSelected = state.provider === 'elevenlabs' 
                ? secrets.elVoiceId === identity.id 
                : state.voice === identity.id;
              
              const borderColors: Record<string, string> = { "primary": "border-primary", "secondary": "border-secondary", "tertiary": "border-tertiary" };
              const textColors: Record<string, string> = { "primary": "text-primary", "secondary": "text-secondary", "tertiary": "text-tertiary" };

              return (
                <div key={identity.id} onClick={() => onVoiceSelect(identity.id, 'edge-tts')}
                  className={`group relative bg-surface-container-low border transition-all duration-300 cursor-pointer overflow-hidden identity-card ${isSelected ? `${borderColors[identity.color]} shadow-lg shadow-${identity.color}/10` : 'border-outline-variant/30 hover:border-surface-variant'}`}>
                  <div className="aspect-[16/10] relative overflow-hidden bg-surface-container-highest">
                    <img src={identity.img} className={`w-full h-full object-cover transition-all duration-700 ${isSelected ? 'opacity-60 scale-105' : 'opacity-30 group-hover:opacity-40 group-hover:scale-105'}`} />
                    <div className="absolute inset-0 bg-gradient-to-t from-surface-container-low via-transparent to-transparent"></div>
                    <div className="absolute bottom-4 left-4">
                      <div className={`font-headline font-bold text-xl leading-none ${textColors[identity.color]}`}>{identity.name}</div>
                      <div className="font-label text-[10px] text-on-surface-variant mt-1 tracking-widest uppercase">{identity.desc}</div>
                    </div>
                    
                    <div className="absolute top-4 right-4 flex items-center gap-2">
                       <button 
                        onClick={(e) => { e.stopPropagation(); onPreview(identity.id, 'edge-tts'); }}
                        className={`w-8 h-8 rounded-full flex items-center justify-center backdrop-blur-md border transition-all ${previewingId === identity.id ? 'bg-primary border-primary animate-pulse text-background' : 'bg-surface-container/60 border-outline-variant/30 text-on-surface hover:bg-primary/20 hover:border-primary'}`}
                      >
                        <span className="material-symbols-outlined text-sm">{previewingId === identity.id ? 'graphic_eq' : 'play_arrow'}</span>
                      </button>
                      {isSelected && (
                        <div className={`animate-in fade-in zoom-in duration-300`}>
                          <span className={`material-symbols-outlined ${textColors[identity.color]} fill-1`}>verified</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="p-3">
                    <div className={`text-center py-1 font-label text-[9px] tracking-[0.2em] font-bold border transition-colors ${isSelected ? `bg-${identity.color}/10 ${borderColors[identity.color]} ${textColors[identity.color]}` : 'bg-surface-bright border-outline-variant/30 text-on-surface-variant'}`}>
                      {isSelected ? 'ACTIVE NEURAL PATH' : 'STANDBY MODE'}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Extended Library Library */}
        <div className="relative group/library">
          <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between border-b border-outline-variant/10 pb-4 gap-4">
            <div>
              <h2 className="font-headline text-xl font-bold tracking-tight text-on-surface mb-1 uppercase">Extended Library</h2>
              <p className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest">{availableVoices.filter(v => v.gender.toLowerCase() === genderFilter).length} {genderFilter} Models Available</p>
            </div>
            
            <div className="flex flex-col md:flex-row items-center gap-4">
              <div className="bg-surface-container-low p-1 border border-outline-variant/20 flex relative w-48">
                <div className={`absolute top-1 bottom-1 w-[50%] bg-primary/20 border border-primary/30 transition-all duration-300 ease-out`}
                  style={{ left: genderFilter === 'female' ? '4px' : 'calc(50% - 4px)' }} />
                <button onClick={() => { setGenderFilter('female'); carouselRef.current?.scrollTo({ left: 0 }); }} className={`flex-1 relative z-10 py-1.5 font-label text-[9px] uppercase tracking-widest transition-colors ${genderFilter === 'female' ? 'text-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>Female</button>
                <button onClick={() => { setGenderFilter('male'); carouselRef.current?.scrollTo({ left: 0 }); }} className={`flex-1 relative z-10 py-1.5 font-label text-[9px] uppercase tracking-widest transition-colors ${genderFilter === 'male' ? 'text-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>Male</button>
              </div>

              <div className="w-full md:w-64 bg-surface-container-low border border-outline-variant/30 px-3 py-1.5 flex items-center gap-3 focus-within:border-primary transition-colors">
                <span className="material-symbols-outlined text-on-surface-variant scale-75">search</span>
                <input type="text" placeholder="FILTER MODELS..." value={voiceSearch} onChange={e => setVoiceSearch(e.target.value)}
                  className="bg-transparent border-none outline-none font-label text-[10px] text-on-surface uppercase tracking-widest w-full placeholder:text-on-surface-variant/40" />
              </div>
            </div>
          </div>

          <button onClick={() => scrollCarousel('left')} className="absolute left-4 top-[65%] -translate-y-1/2 z-20 w-10 h-10 bg-surface-container/60 backdrop-blur-md border border-outline-variant/30 rounded-full flex items-center justify-center text-on-surface opacity-0 group-hover/library:opacity-100 transition-all hover:bg-primary/20 hover:border-primary">
            <span className="material-symbols-outlined">chevron_left</span>
          </button>
          <button onClick={() => scrollCarousel('right')} className="absolute right-4 top-[65%] -translate-y-1/2 z-20 w-10 h-10 bg-surface-container/60 backdrop-blur-md border border-outline-variant/30 rounded-full flex items-center justify-center text-on-surface opacity-0 group-hover/library:opacity-100 transition-all hover:bg-primary/20 hover:border-primary">
            <span className="material-symbols-outlined">chevron_right</span>
          </button>

          <div ref={carouselRef} className="flex flex-row overflow-x-auto gap-4 pb-6 hide-scrollbar snap-x snap-mandatory scroll-smooth">
            {availableVoices
              .filter(v => ![ 'en-IN-NeerjaNeural', 'en-US-GuyNeural', 'en-GB-SoniaNeural' ].includes(v.id))
              .filter(v => {
                const matchesSearch = v.name.toLowerCase().includes(voiceSearch.toLowerCase()) || 
                                     v.id.toLowerCase().includes(voiceSearch.toLowerCase()) || 
                                     v.locale.toLowerCase().includes(voiceSearch.toLowerCase());
                const matchesGender = v.gender.toLowerCase() === genderFilter;
                return matchesSearch && matchesGender;
              })
              .map(voice => {
                const isSelected = state.provider === 'elevenlabs' ? secrets.elVoiceId === voice.id : state.voice === voice.id;
                return (
                  <div key={voice.id} onClick={() => onVoiceSelect(voice.id, voice.provider)}
                    className={`min-width-[240px] flex-shrink-0 snap-start p-5 border transition-all duration-300 cursor-pointer flex flex-col justify-between h-[160px] relative overflow-hidden ${isSelected ? 'border-primary bg-primary/10' : 'border-outline-variant/20 bg-surface-container-low hover:border-primary/40'}`}>
                    <div className="absolute -right-4 -top-4 w-12 h-12 border border-outline-variant/10 rotate-45 pointer-events-none"></div>
                    <div className="relative z-10 text-left">
                      <div className="flex items-center justify-between relative z-10">
                        <div className={`font-headline font-bold text-xs uppercase tracking-wider ${isSelected ? 'text-primary' : 'text-on-surface'}`}>{voice.name}</div>
                        <div className="flex items-center gap-2">
                          <button onClick={(e) => { e.stopPropagation(); onPreview(voice.id, voice.provider); }}
                            className={`w-8 h-8 rounded-full flex items-center justify-center border transition-all ${previewingId === voice.id ? 'bg-primary border-primary animate-pulse text-background' : 'bg-surface-container-highest/50 border-outline-variant/20 text-on-surface-variant hover:text-primary hover:border-primary/50'}`}>
                            <span className="material-symbols-outlined text-[16px]">{previewingId === voice.id ? 'graphic_eq' : 'play_arrow'}</span>
                          </button>
                        </div>
                      </div>
                      <div className="font-label text-[8px] text-on-surface-variant uppercase tracking-[0.2em]">{voice.locale.split('-')[1]} // {voice.gender}</div>
                    </div>
                    <div className="relative z-10 mt-auto pt-4 border-t border-outline-variant/10 text-left">
                      <div className={`font-mono text-[8px] truncate ${isSelected ? 'text-primary/70' : 'text-on-surface-variant/40'}`}>{voice.id}</div>
                      <div className={`mt-2 flex gap-1`}>
                        <div className={`flex-1 py-1 text-center font-label text-[7px] uppercase tracking-widest border ${isSelected ? 'bg-primary/20 border-primary text-primary' : 'bg-surface-bright border-outline-variant/30 text-on-surface-variant'}`}>
                          {isSelected ? 'ACTIVE_NEURAL' : 'STANDBY'}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      </section>

      {/* Synthesis Config */}
      <section className="bg-surface-container-low p-8 border border-outline-variant/20 relative overflow-hidden">
        <h2 className="font-headline text-3xl font-bold text-on-surface uppercase tracking-tight mb-8">Vocal Synthesis Engine</h2>

        {/* ElevenLabs Secret Card */}
        <div className="mb-12 relative group">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-tertiary/20 to-tertiary/5 rounded-none blur opacity-0 group-hover:opacity-100 transition duration-500" />
          <div className="relative bg-surface-container border border-outline-variant/10 p-8 flex flex-col md:flex-row gap-8 items-start">
            <div className="w-16 h-16 flex-shrink-0 bg-tertiary/10 flex items-center justify-center rounded-none border border-tertiary/20">
              <span className="material-symbols-outlined text-tertiary text-3xl">waves</span>
            </div>
            
            <div className="flex-grow space-y-6 w-full">
              <div className="flex justify-between items-center">
                <div className="space-y-1 text-left">
                  <h3 className="font-headline text-lg font-bold text-on-surface uppercase tracking-wide">ElevenLabs Premium Config</h3>
                  <div className="flex items-center gap-2">
                    <div className={`h-1.5 w-1.5 rounded-full ${secrets.elApiKey ? 'bg-tertiary shadow-[0_0_8px_var(--md-sys-color-tertiary)]' : 'bg-outline-variant'}`} />
                    <span className="font-label text-[10px] uppercase tracking-tighter text-on-surface-variant">
                      {secrets.elApiKey ? 'Synthesis Link Ready' : 'Awaiting Credential'}
                    </span>
                  </div>
                </div>
                <a href="https://elevenlabs.io/app/settings/api-keys" target="_blank" className="font-label text-[10px] text-tertiary hover:underline uppercase tracking-widest font-bold">API Console</a>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="relative flex items-center">
                  <input type={showEl ? "text" : "password"} value={secrets.elApiKey} onChange={e => onUpdate('secrets.elApiKey', e.target.value)} placeholder="API Key..."
                    className="w-full bg-surface-container-high/40 border border-outline-variant/10 p-4 font-mono text-xs text-on-surface focus:border-tertiary/50 outline-none transition-all" />
                  <button onClick={() => setShowEl(!showEl)} className="absolute right-4 text-on-surface-variant/50 hover:text-tertiary">
                    <span className="material-symbols-outlined text-lg">{showEl ? 'visibility_off' : 'visibility'}</span>
                  </button>
                </div>
                <input type="text" value={secrets.elVoiceId} onChange={e => onUpdate('secrets.elVoiceId', e.target.value)} placeholder="Voice Signature..." className="w-full bg-surface-container-high/40 border border-outline-variant/10 p-4 font-mono text-xs text-on-surface focus:border-tertiary/50 outline-none transition-all" />
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 text-left">
          <div className="space-y-8">
            <div className="space-y-4">
              <div className="flex justify-between font-label text-xs uppercase tracking-widest">
                <span className="text-secondary font-bold">ElevenLabs Budget</span>
                <span className="text-on-surface">{state.elevenlabsBudget} CHARS</span>
              </div>
              <input className="w-full settings-range" max="1000" min="50" step="50" style={{ accentColor: '#7799ff' }} type="range" value={state.elevenlabsBudget} onChange={e => onUpdate('tts.elevenlabsBudget', Number(e.target.value))} />
            </div>
            <div className="space-y-4">
              <div className="flex justify-between font-label text-xs uppercase tracking-widest">
                <span className="text-tertiary font-bold">Base Volume Gain</span>
                <span className="text-on-surface">{state.gainDb.toFixed(1)}x</span>
              </div>
              <input className="w-full settings-range" max="2.0" min="0.1" step="0.1" style={{ accentColor: '#ff6f7e' }} type="range" value={state.gainDb} onChange={e => onUpdate('tts.gainDb', Number(e.target.value))} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div onClick={() => onUpdate('tts.spatialAudio', !state.spatialAudio)}
              className={`p-3 flex items-center gap-3 cursor-pointer border transition-colors ${state.spatialAudio ? 'bg-primary/20 border-primary' : 'bg-surface-container border-transparent hover:border-outline-variant'}`}>
              <div className={`w-2 h-2 ${state.spatialAudio ? 'bg-primary animate-pulse' : 'bg-on-surface-variant/30'}`}></div>
              <div className="font-label text-[10px] uppercase text-on-surface-variant">Spatial Audio</div>
            </div>
            <div onClick={() => onUpdate('tts.resamplingHq', !state.resamplingHq)}
              className={`p-3 flex items-center gap-3 cursor-pointer border transition-colors ${state.resamplingHq ? 'bg-secondary/20 border-secondary' : 'bg-surface-container border-transparent hover:border-outline-variant'}`}>
              <div className={`w-2 h-2 ${state.resamplingHq ? 'bg-secondary animate-pulse' : 'bg-on-surface-variant/30'}`}></div>
              <div className="font-label text-[10px] uppercase text-on-surface-variant">Resampling: HQ</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
});
