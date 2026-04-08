// TopNavBar.tsx ─ Yuki fixed top navigation with drag region for Electron

interface TopNavBarProps {
  activePage: string;
  onNavigate: (page: string) => void;
  onMiniToggle?: () => void;
}

const NAV_LINKS = [
  { id: 'chat',     label: 'Intelligence' },
  { id: 'history',  label: 'History' },
  { id: 'settings', label: 'Settings' },
];

export default function TopNavBar({ activePage, onNavigate, onMiniToggle }: TopNavBarProps) {
  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 bg-background drag-region"
      style={{ boxShadow: '0 0 32px rgba(143,245,255,0.08)' }}
    >
      <nav className="flex justify-between items-center w-full px-8 h-16 max-w-[1920px] mx-auto">
        {/* Left: Brand + nav links */}
        <div className="flex items-center gap-8">
          <span className="font-headline text-xl font-bold text-primary tracking-tighter select-none">
            Yuki
          </span>

          <div className="hidden md:flex gap-6 no-drag-region">
            {NAV_LINKS.map((link) => (
              <button
                key={link.id}
                onClick={() => onNavigate(link.id)}
                className={`font-label tracking-widest text-sm transition-colors duration-300 ${
                  activePage === link.id
                    ? 'text-primary border-b-2 border-primary pb-1'
                    : 'text-on-surface/60 hover:text-on-surface'
                }`}
              >
                {link.label}
              </button>
            ))}
          </div>
        </div>

        {/* Right: Search + window controls */}
        <div className="flex items-center gap-3 no-drag-region">
          <div className="relative group">
            <input
              className="bg-surface-container-highest text-sm rounded-lg px-4 py-2 w-56 outline-none border-none
                         focus:ring-1 focus:ring-primary/30 transition-all duration-300
                         placeholder:text-on-surface-variant/40 text-on-surface"
              placeholder="Search parameters..."
              type="text"
            />
            <span className="material-symbols-outlined absolute right-3 top-2 text-on-surface-variant/60 text-lg select-none">
              search
            </span>
          </div>

          {/* Window controls */}
          <button
            onClick={() => onMiniToggle ? onMiniToggle() : window.yukiAPI?.minimize()}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-surface-container-high
                       transition-colors text-on-surface-variant hover:text-on-surface"
            title="Mini Mode"
          >
            <span className="material-symbols-outlined text-base">remove</span>
          </button>
          <button
            onClick={() => window.yukiAPI?.maximize()}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-surface-container-high
                       transition-colors text-on-surface-variant hover:text-on-surface"
            title="Maximize"
          >
            <span className="material-symbols-outlined text-base">crop_square</span>
          </button>
          <button
            onClick={() => window.yukiAPI?.close()}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-error/20
                       transition-colors text-on-surface-variant hover:text-error"
            title="Close"
          >
            <span className="material-symbols-outlined text-base">close</span>
          </button>

          <button className="material-symbols-outlined text-primary hover:bg-surface-container-high p-2 rounded-full transition-colors ml-1">
            account_circle
          </button>
        </div>
      </nav>
    </header>
  );
}
