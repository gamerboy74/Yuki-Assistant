import { useState, useRef, useEffect } from 'react';
import './CommandPalette.css';

interface Command {
  id: string;
  label: string;
  category: string;
  icon: string;
  shortcut?: string;
}

const COMMANDS: Command[] = [
  { id: 'play-music', label: 'Play Music', category: 'Media', icon: '🎵', shortcut: '' },
  { id: 'pause-music', label: 'Pause Music', category: 'Media', icon: '⏸️' },
  { id: 'next-track', label: 'Next Track', category: 'Media', icon: '⏭️' },
  { id: 'work-mode', label: 'Activate Work Mode', category: 'Modes', icon: '🖥️' },
  { id: 'chill-mode', label: 'Activate Chill Mode', category: 'Modes', icon: '🌙' },
  { id: 'focus-mode', label: 'Focus Mode (2 hours)', category: 'Modes', icon: '🎯' },
  { id: 'screenshot', label: 'Take Screenshot', category: 'System', icon: '📸' },
  { id: 'recycle-bin', label: 'Open Recycle Bin', category: 'System', icon: '🗑️' },
  { id: 'notepad', label: 'Open Notepad', category: 'System', icon: '📝' },
  { id: 'clipboard', label: 'Show Clipboard History', category: 'System', icon: '📋' },
  { id: 'whatsapp', label: 'Send WhatsApp Message', category: 'Communication', icon: '💬' },
  { id: 'slack', label: 'Send Slack Message', category: 'Communication', icon: '💼' },
  { id: 'daily-brief', label: 'Daily Briefing', category: 'Info', icon: '☀️' },
  { id: 'weather', label: 'Check Weather', category: 'Info', icon: '🌤️' },
  { id: 'calculate', label: 'Calculator', category: 'Tools', icon: '🧮' },
  { id: 'timer', label: 'Set Timer', category: 'Tools', icon: '⏱️' },
  { id: 'settings', label: 'Open Settings', category: 'App', icon: '⚙️' },
];

interface Props {
  onClose: () => void;
}

export default function CommandPalette({ onClose }: Props) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const filtered = COMMANDS.filter(
    (cmd) =>
      cmd.label.toLowerCase().includes(query.toLowerCase()) ||
      cmd.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      // Execute command
      onClose();
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div className="cmd-palette-overlay" onClick={onClose}>
      <div
        className="cmd-palette animate-scale-in glass-strong"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="cmd-palette-input-wrapper">
          <svg className="cmd-palette-search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={inputRef}
            className="cmd-palette-input"
            type="text"
            placeholder="Type a command..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            id="cmd-palette-input"
          />
          <kbd className="cmd-palette-esc">ESC</kbd>
        </div>

        <div className="cmd-palette-results">
          {filtered.length === 0 ? (
            <div className="cmd-palette-empty">
              <span>No commands matching "{query}"</span>
            </div>
          ) : (
            filtered.map((cmd, i) => (
              <button
                key={cmd.id}
                className={`cmd-palette-item ${i === selectedIndex ? 'cmd-palette-item--selected' : ''}`}
                onMouseEnter={() => setSelectedIndex(i)}
                onClick={onClose}
                id={`cmd-${cmd.id}`}
              >
                <span className="cmd-palette-item-icon">{cmd.icon}</span>
                <span className="cmd-palette-item-label">{cmd.label}</span>
                <span className="cmd-palette-item-category">{cmd.category}</span>
              </button>
            ))
          )}
        </div>

        <div className="cmd-palette-footer">
          <span className="cmd-palette-hint">
            <kbd>↑↓</kbd> Navigate
            <kbd>↵</kbd> Execute
            <kbd>Esc</kbd> Close
          </span>
        </div>
      </div>
    </div>
  );
}
