import { useState, useEffect } from 'react';

interface Toast {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title?: string;
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Demo toast on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      setToasts([
        {
          id: '1',
          message: 'Aether Neural Interface initialized.',
          type: 'info',
        },
      ]);
    }, 1500);

    return () => clearTimeout(timer);
  }, []);

  // Auto-dismiss after 5s
  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setTimeout(() => {
      setToasts((prev) => prev.slice(1));
    }, 5000);
    return () => clearTimeout(timer);
  }, [toasts]);

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 flex flex-col gap-3 z-[9999] pointer-events-none">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={() => removeToast(toast.id)} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [isExiting, setIsExiting] = useState(false);

  const handleDismiss = () => {
    setIsExiting(true);
    setTimeout(onDismiss, 300);
  };

  const typeConfig = {
    info: 'bg-surface-container-high border-cyan-500/30 text-slate-100',
    success: 'bg-emerald-950/80 border-emerald-500/30 text-emerald-100',
    warning: 'bg-amber-950/80 border-amber-500/30 text-amber-100',
    error: 'bg-rose-950/80 border-rose-500/30 text-rose-100',
  };

  const iconConfig = {
    info: 'info',
    success: 'check_circle',
    warning: 'warning',
    error: 'error',
  };

  return (
    <div
      className={`pointer-events-auto flex items-center gap-3 px-4 py-3 min-w-[300px] max-w-md rounded-lg border backdrop-blur-xl shadow-xl transition-all duration-300 ${
        isExiting ? 'opacity-0 translate-x-4' : 'opacity-100 translate-x-0'
      } ${typeConfig[toast.type as keyof typeof typeConfig] || typeConfig.info}`}
      role="alert"
    >
      <span className="material-symbols-outlined text-lg opacity-80">
        {iconConfig[toast.type as keyof typeof iconConfig] || 'info'}
      </span>
      <div className="flex-1 flex flex-col">
        {toast.title && <h4 className="text-sm font-bold m-0 leading-tight">{toast.title}</h4>}
        <p className="text-sm opacity-90 m-0 leading-tight">{toast.message}</p>
      </div>
      <button 
        className="w-6 h-6 flex items-center justify-center rounded-full hover:bg-white/10 transition-colors opacity-60 hover:opacity-100" 
        onClick={handleDismiss} 
        aria-label="Dismiss"
      >
        <span className="material-symbols-outlined text-sm">close</span>
      </button>
    </div>
  );
}
