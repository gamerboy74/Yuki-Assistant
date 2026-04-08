import './TitleBar.css';

export default function TitleBar() {
  const handleMinimize = () => {
    window.yukiAPI?.minimize();
  };
  const handleMaximize = () => {
    window.yukiAPI?.maximize();
  };
  // Hides to tray — Yuki keeps listening in background
  const handleClose = () => {
    window.yukiAPI?.hide();
  };

  return (
    <header className="titlebar" id="titlebar">
      {/* Drag region with brand */}
      <div className="titlebar-drag-region">
        <div className="titlebar-brand">
          <div className="titlebar-logo">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="var(--accent-primary)" strokeWidth="2" />
              <circle cx="12" cy="12" r="4" fill="var(--accent-secondary)" />
              <path d="M12 2 L14 8 L12 6 L10 8 Z"  fill="var(--accent-primary)" opacity="0.7" />
              <path d="M12 22 L14 16 L12 18 L10 16 Z" fill="var(--accent-primary)" opacity="0.7" />
              <path d="M2 12 L8 10 L6 12 L8 14 Z"  fill="var(--accent-primary)" opacity="0.7" />
              <path d="M22 12 L16 10 L18 12 L16 14 Z" fill="var(--accent-primary)" opacity="0.7" />
            </svg>
          </div>
          <span className="titlebar-title">Yuki</span>
          <span className="titlebar-shortcut">Voice AI</span>
        </div>
      </div>

      {/* Window controls */}
      <div className="titlebar-controls">
        {/* Minimize */}
        <button
          className="titlebar-btn titlebar-btn--minimize"
          onClick={handleMinimize}
          title="Minimize"
          aria-label="Minimize"
          id="btn-minimize"
        >
          <svg width="10" height="10" viewBox="0 0 10 10">
            <rect x="1" y="4.5" width="8" height="1.5" rx="0.75" fill="currentColor" />
          </svg>
        </button>

        {/* Maximize */}
        <button
          className="titlebar-btn titlebar-btn--maximize"
          onClick={handleMaximize}
          title="Maximize"
          aria-label="Maximize"
          id="btn-maximize"
        >
          <svg width="10" height="10" viewBox="0 0 10 10">
            <rect x="1" y="1" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.5" fill="none" />
          </svg>
        </button>

        {/* Close → hides to tray */}
        <button
          className="titlebar-btn titlebar-btn--close"
          onClick={handleClose}
          title="Hide to tray (Yuki keeps listening)"
          aria-label="Hide to tray"
          id="btn-close"
        >
          <svg width="10" height="10" viewBox="0 0 10 10">
            <path d="M2 2L8 8M8 2L2 8" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </header>
  );
}
