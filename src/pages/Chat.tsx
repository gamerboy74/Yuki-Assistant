import { useState, useRef, useEffect } from 'react';
import './Chat.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: Date;
}

const INITIAL_MESSAGES: Message[] = [
  {
    id: '1',
    role: 'assistant',
    text: "Hey! I'm Aether, your neural interface. Try saying \"Hey Aether\" or type a command below.",
    timestamp: new Date(),
  },
];

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState('');
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const sendMessage = () => {
    const text = input.trim();
    if (!text) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');

    // Simulate assistant response
    setTimeout(() => {
      const reply: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: getResponse(text),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, reply]);
    }, 800);
  };

  const getResponse = (input: string): string => {
    const lower = input.toLowerCase();
    if (lower.includes('time')) {
      return `It's currently ${new Date().toLocaleTimeString()}.`;
    }
    if (lower.includes('hello') || lower.includes('hi') || lower.includes('hey')) {
      return "Hello! What can I do for you today?";
    }
    if (lower.includes('play') && lower.includes('music')) {
      return "🎵 Opening Spotify and playing your favorites...";
    }
    if (lower.includes('work mode')) {
      return "🖥️ Activating work mode: Opening VS Code, Terminal, and muting notifications.";
    }
    if (lower.includes('screenshot')) {
      return "📸 Screenshot captured and saved to Desktop!";
    }
    return `I understood: "${input}". This feature will be connected to the AI backend soon.`;
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTime = (date: Date) =>
    date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="chat-page">
      <div className="chat-header">
        <h1 className="text-heading" style={{ fontSize: 'var(--text-xl)' }}>
          Conversation
        </h1>
        <span className="chat-msg-count text-mono">{messages.length} messages</span>
      </div>

      <div className="chat-thread" ref={threadRef} id="chat-thread">
        {messages.map((msg, i) => (
          <div
            key={msg.id}
            className={`chat-bubble chat-bubble--${msg.role} animate-fade-in-up`}
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <div className="chat-bubble-avatar">
              {msg.role === 'assistant' ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="var(--accent-primary)" strokeWidth="2" />
                  <circle cx="12" cy="12" r="4" fill="var(--accent-secondary)" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" strokeWidth="2">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M20 21a8 8 0 1 0-16 0" />
                </svg>
              )}
            </div>
            <div className="chat-bubble-content">
              <div className="chat-bubble-meta">
                <span className="chat-bubble-name">
                  {msg.role === 'assistant' ? 'Aether' : 'You'}
                </span>
                <span className="chat-bubble-time text-mono">{formatTime(msg.timestamp)}</span>
              </div>
              <p className="chat-bubble-text">{msg.text}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="chat-input-bar" id="chat-input-bar">
        <button className="chat-mic-btn btn-icon" aria-label="Voice input" id="btn-chat-mic">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
          </svg>
        </button>
        <input
          className="chat-input"
          type="text"
          placeholder="Type a message or command..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          id="chat-input"
          autoComplete="off"
        />
        <button
          className="chat-send-btn btn-primary"
          onClick={sendMessage}
          disabled={!input.trim()}
          aria-label="Send message"
          id="btn-send"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  );
}
