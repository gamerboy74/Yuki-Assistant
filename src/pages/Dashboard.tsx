import { useEffect, useState } from 'react';

interface DashboardProps {
  stats: any;
  logs: {id: string, text: string, ts: Date}[];
}

export default function Dashboard({ stats, logs }: DashboardProps) {
  const [time, setTime] = useState(new Date());

  const weather = stats?.weather;

  const getWeatherIcon = (code: number) => {
    if (code === 0) return 'sunny';
    if (code <= 3) return 'partly_cloudy_day';
    if (code <= 48) return 'foggy';
    if (code <= 55) return 'rainy_light';
    if (code <= 65) return 'rainy';
    if (code <= 75) return 'ac_unit';
    if (code <= 82) return 'thunderstorm';
    return 'thunderstorm';
  };

  const getWeatherDesc = (code: number) => {
    if (code === 0) return 'Clear Sky';
    if (code === 1) return 'Mainly Clear';
    if (code === 2) return 'Partly Cloudy';
    if (code === 3) return 'Overcast';
    if (code <= 48) return 'Foggy';
    if (code <= 55) return 'Drizzle';
    if (code <= 65) return 'Rain';
    if (code <= 75) return 'Snow';
    return 'Stormy';
  };

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatDate = (d: Date) => {
    return d.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
  };

  const formatTime = (d: Date) => {
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="h-full w-full p-8 overflow-y-auto subtle-scrollbar animate-fade-in relative z-10 bg-transparent">
      
      {/* Header section */}
      <header className="mb-10 flex justify-between items-end">
        <div>
          <h1 className="text-4xl font-light tracking-tight text-on-surface mb-1">
            Good {time.getHours() < 12 ? 'Morning' : time.getHours() < 18 ? 'Afternoon' : 'Evening'}, <span className="text-primary font-medium">Boss</span>
          </h1>
          <p className="text-on-surface-variant/60 font-label tracking-wide uppercase text-xs">
            {formatDate(time)}
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-mono text-on-surface tracking-tighter">
            {formatTime(time)}
          </div>
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        
        {/* System Health Widget */}
        <div className="glass-card p-6 flex flex-col gap-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-symbols-outlined text-primary text-xl">database</span>
            <h3 className="font-medium text-on-surface">System Health</h3>
          </div>
          
          <div className="space-y-4">
            {/* CPU */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-label">
                <span className="text-on-surface-variant">CPU LOAD</span>
                <span className="text-primary">{stats?.cpu || 0}%</span>
              </div>
              <div className="h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
                <div 
                  className="h-full bg-primary transition-all duration-1000 ease-out" 
                  style={{ width: `${stats?.cpu || 0}%` }}
                />
              </div>
            </div>

            {/* RAM */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-label">
                <span className="text-on-surface-variant">MEMORY</span>
                <span className="text-secondary">{stats?.ram || 0}%</span>
              </div>
              <div className="h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
                <div 
                  className="h-full bg-secondary transition-all duration-1000 ease-out" 
                  style={{ width: `${stats?.ram || 0}%` }}
                />
              </div>
            </div>

            {/* Battery */}
            {stats?.battery?.percent !== null && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-label">
                  <span className="text-on-surface-variant">BATTERY</span>
                  <span className="text-tertiary">{stats?.battery?.percent}%</span>
                </div>
                <div className="h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-1000 ease-out ${stats?.battery?.charging ? 'bg-green-400' : 'bg-tertiary'}`} 
                    style={{ width: `${stats?.battery?.percent || 0}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Weather Widget (Dynamic) */}
        <div className="glass-card p-6 flex flex-col items-center justify-center text-center overflow-hidden relative">
           {/* Decorative background circle */}
           <div className="absolute -top-10 -right-10 w-32 h-32 bg-primary/10 rounded-full blur-3xl pointer-events-none" />
           
           <span className="material-symbols-outlined text-5xl text-primary mb-4 animate-fade-in" style={{ fontVariationSettings: "'FILL' 1" }}>
             {weather ? getWeatherIcon(weather.condition_code) : 'cloud_queue'}
           </span>
           <div className="text-4xl font-light text-on-surface mb-1">
             {weather ? `${Math.round(weather.temp)}°C` : '--°C'}
           </div>
           <div className="text-on-surface-variant font-label tracking-widest text-[10px] uppercase mb-4">
             {weather 
               ? `${getWeatherDesc(weather.condition_code)} · ${weather.city}` 
               : 'Locating System...'}
           </div>
           
           <div className="flex gap-4 w-full pt-4 border-t border-outline-variant/10">
             <div className="flex-1">
               <div className="text-[10px] text-on-surface-variant/40 uppercase mb-1">Wind</div>
               <div className="text-xs">{weather ? `${weather.wind} km/h` : '--'}</div>
             </div>
             <div className="flex-1">
               <div className="text-[10px] text-on-surface-variant/40 uppercase mb-1">Humidity</div>
               <div className="text-xs">{weather ? `${weather.humidity}%` : '--'}</div>
             </div>
             <div className="flex-1">
               <div className="text-[10px] text-on-surface-variant/40 uppercase mb-1">UV</div>
               <div className="text-xs">{weather ? (weather.uv > 5 ? 'High' : 'Low') : '--'}</div>
             </div>
           </div>
        </div>

        {/* Network & Activity */}
        <div className="glass-card p-6 flex flex-col gap-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-symbols-outlined text-primary text-xl">network_intelligence</span>
            <h3 className="font-medium text-on-surface">Connectivity</h3>
          </div>
          
          <div className="flex items-center justify-between py-2 border-b border-outline-variant/10">
             <span className="text-xs text-on-surface-variant">Status</span>
             <span className="flex items-center gap-1.5 text-xs text-green-400">
               <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
               Connected
             </span>
          </div>

          <div className="flex items-center justify-between py-2 border-b border-outline-variant/10">
             <span className="text-xs text-on-surface-variant">LLM Backend</span>
             <span className="text-xs text-on-surface font-mono">{stats?.ai_model || 'GPT-4o (Online)'}</span>
          </div>

          <div className="flex items-center justify-between py-2 border-b border-outline-variant/10">
             <span className="text-xs text-on-surface-variant">Signal Traffic</span>
             <div className="flex gap-3 text-[10px] font-mono">
                <span className="text-primary" title="Total Bytes Sent">↑ {(stats?.network?.sent / 1024 / 1024 || 0).toFixed(1)}MB</span>
                <span className="text-secondary" title="Total Bytes Received">↓ {(stats?.network?.recv / 1024 / 1024 || 0).toFixed(1)}MB</span>
             </div>
          </div>

          <div className="mt-2 text-[10px] text-on-surface-variant/40 uppercase tracking-widest mb-2">Recent Events</div>
          <div className="space-y-3 max-h-[140px] overflow-y-auto subtle-scrollbar pr-1">
             {logs.length > 0 ? logs.map(log => (
               <div key={log.id} className="flex gap-3 items-start animate-fade-in">
                 <div className="w-1 h-1 rounded-full bg-primary mt-1.5 shrink-0" />
                 <div className="flex flex-col gap-0.5">
                   <p className="text-[11px] text-on-surface/80 leading-tight">{log.text}</p>
                   <span className="text-[8px] text-on-surface-variant/40 font-mono">
                     {log.ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                   </span>
                 </div>
               </div>
             )) : (
               <>
                 <div className="flex gap-3 items-start opacity-40">
                   <div className="w-1 h-1 rounded-full bg-primary mt-1.5" />
                   <p className="text-[11px] text-on-surface/70 leading-relaxed">System initialized successfully.</p>
                 </div>
                 <div className="flex gap-3 items-start opacity-40">
                   <div className="w-1 h-1 rounded-full bg-primary mt-1.5" />
                   <p className="text-[11px] text-on-surface/70 leading-relaxed">Voice recognition engine standby.</p>
                 </div>
               </>
             )}
          </div>
        </div>

      </div>

      {/* Visual background element - kept for additional depth */}
      <div className="fixed bottom-0 right-0 w-[500px] h-[500px] bg-primary/5 rounded-full blur-[120px] pointer-events-none -z-10 translate-x-1/2 translate-y-1/2" />
    </div>
  );
}
