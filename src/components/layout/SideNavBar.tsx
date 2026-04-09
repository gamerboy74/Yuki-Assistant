// SideNavBar.tsx ─ Aetheris fixed left sidebar navigation

interface SideNavBarProps {
  activePage: string;
  onNavigate: (page: string) => void;
  onTrigger: () => void;
}

const NAV_ITEMS = [
  { id: 'dashboard',icon: 'grid_view',     label: 'Core' },
  { id: 'listen',   icon: 'mic',           label: 'Listen' },
  { id: 'chat',     icon: 'chat_bubble',   label: 'Chat',  iconFill: true },
  { id: 'history',  icon: 'history',       label: 'Time' },
  { id: 'settings', icon: 'tune',          label: 'Tune' },
];

export default function SideNavBar({ activePage, onNavigate, onTrigger }: SideNavBarProps) {
  return (
    <aside className="fixed left-0 top-16 bottom-0 w-20 flex flex-col items-center py-6 z-40 bg-surface-container-low">
      {/* Nav items */}
      <div className="flex flex-col gap-8 flex-1">
        {NAV_ITEMS.map((item) => {
          const isActive = activePage === item.id ||
                           (item.id === 'chat' && activePage === 'chat') ||
                           (item.id === 'listen' && activePage === 'listen');
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className="flex flex-col items-center gap-1 group"
            >
              <div
                className={`p-3 rounded-lg transition-all duration-300 ${
                  isActive
                    ? 'text-primary bg-surface-container-high'
                    : 'text-on-surface/40 group-hover:text-primary group-hover:bg-surface-container-high/50'
                }`}
              >
                <span
                  className="material-symbols-outlined"
                  style={
                    isActive && item.iconFill
                      ? { fontVariationSettings: "'FILL' 1" }
                      : undefined
                  }
                >
                  {item.icon}
                </span>
              </div>
              <span
                className={`font-label tracking-wider uppercase text-[10px] font-semibold transition-colors ${
                  isActive ? 'text-primary' : 'text-on-surface/40 group-hover:text-primary/70'
                }`}
              >
                {item.label}
              </span>
            </button>
          );
        })}
      </div>

      {/* Bolt FAB — manual trigger */}
      <button
        onClick={onTrigger}
        className="w-12 h-12 orb-gradient rounded-full flex items-center justify-center
                   hover:scale-95 active:scale-90 transition-transform"
        style={{ boxShadow: '0 0 20px rgba(143,245,255,0.3)' }}
        title="Trigger Aetheris"
      >
        <span
          className="material-symbols-outlined text-on-primary-fixed"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          bolt
        </span>
      </button>
    </aside>
  );
}
