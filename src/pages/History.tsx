import type { ChatMessage } from '../App';

interface HistoryProps {
  messages: ChatMessage[];
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

function formatDateHeading(date: Date): string {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) return 'Today';
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return date.toLocaleDateString('en-IN', { weekday: 'long', month: 'long', day: 'numeric' });
}

const ICONS: Record<string, string> = {
  assistant: 'auto_awesome',
  user:      'person',
};

export default function History({ messages }: HistoryProps) {
  // Pair user+assistant messages into exchanges
  const exchanges: { user?: ChatMessage; assistant?: ChatMessage; date: Date }[] = [];

  let i = 0;
  while (i < messages.length) {
    const cur = messages[i];
    if (cur.role === 'user') {
      const next = messages[i + 1];
      if (next && next.role === 'assistant') {
        exchanges.push({ user: cur, assistant: next, date: cur.timestamp });
        i += 2;
      } else {
        exchanges.push({ user: cur, date: cur.timestamp });
        i += 1;
      }
    } else {
      exchanges.push({ assistant: cur, date: cur.timestamp });
      i += 1;
    }
  }

  // Group exchanges by date
  const groups: { heading: string; items: typeof exchanges }[] = [];
  let currentHeading = '';
  for (const ex of [...exchanges].reverse()) {
    const heading = formatDateHeading(ex.date);
    if (heading !== currentHeading) {
      groups.push({ heading, items: [] });
      currentHeading = heading;
    }
    groups[groups.length - 1].items.push(ex);
  }

  return (
    <div className="absolute inset-0 overflow-y-auto px-8 md:px-12 pt-12 pb-32 subtle-scrollbar bg-transparent">
      <header className="mb-16 max-w-5xl">
        <h1 className="font-headline text-5xl tracking-tight text-on-surface mb-4">
          Activity <span className="text-primary">Timeline</span>
        </h1>
        <p className="font-body text-on-surface-variant tracking-wide max-w-2xl leading-relaxed">
          Your real conversation history with Yuki — {messages.length} messages recorded this session.
        </p>
      </header>

      {exchanges.length === 0 ? (
        <div className="max-w-5xl flex flex-col items-center justify-center py-32 gap-6 text-center">
          <div className="w-20 h-20 rounded-full bg-surface-container-high flex items-center justify-center">
            <span className="material-symbols-outlined text-4xl text-on-surface-variant">history</span>
          </div>
          <p className="text-on-surface-variant font-body text-lg">No conversations yet this session.</p>
          <p className="text-on-surface-variant/60 text-sm">Say "Hey Yuki" or click the orb to get started.</p>
        </div>
      ) : (
        <section className="max-w-5xl space-y-6">
          {groups.map((group) => (
            <div key={group.heading}>
              <div className="flex items-center gap-4 mb-6 mt-8 first:mt-0">
                <span className="font-label text-[10px] uppercase tracking-[0.2em] text-on-surface-variant font-bold">
                  {group.heading}
                </span>
                <div className="h-[1px] flex-grow bg-surface-container-high" />
              </div>

              {group.items.map((ex, idx) => (
                <div
                  key={idx}
                  className="group relative bg-surface-container-low hover:bg-surface-container-high transition-all duration-300 rounded-xl p-8 cursor-pointer flex items-start gap-8 mb-4"
                >
                  <div className="flex-shrink-0 pt-1">
                    <div className="w-12 h-12 rounded-full bg-surface-container-highest flex items-center justify-center">
                      <span className="material-symbols-outlined text-primary">
                        {ICONS[ex.user ? 'user' : 'assistant']}
                      </span>
                    </div>
                  </div>
                  <div className="flex-grow space-y-3">
                    <div className="flex justify-between items-start gap-4">
                      <h3 className="font-headline text-xl text-on-surface tracking-tight">
                        "{ex.user?.text ?? ex.assistant?.text}"
                      </h3>
                      <span className="font-label text-xs text-on-surface-variant tracking-widest uppercase flex-shrink-0">
                        {formatTime(ex.date)}
                      </span>
                    </div>
                    {ex.user && ex.assistant && (
                      <div className="font-body text-on-surface-variant leading-relaxed border-l-2 border-primary/20 pl-6 py-1 text-sm">
                        {ex.assistant.text}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
