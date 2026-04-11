import React, { Component, ReactNode } from 'react';

interface EBProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface EBState {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<EBProps, EBState> {
  constructor(props: EBProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): EBState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[Yuki ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="p-6 bg-error-container/20 border border-error/30 rounded-lg m-4 backdrop-blur-md">
          <div className="flex items-center gap-3 mb-4 text-error">
            <span className="material-symbols-outlined">warning</span>
            <h3 className="font-headline font-bold">Component Synchronization Failure</h3>
          </div>
          <pre className="text-[11px] font-mono text-on-error-container bg-black/40 p-4 rounded border border-white/5 mb-4 overflow-auto max-h-[150px] opacity-80">
            {this.state.error?.message}
          </pre>
          <button 
            onClick={() => this.setState({ hasError: false })}
            className="px-4 py-2 bg-error text-on-error font-label text-xs tracking-widest hover:bg-red-600 transition-colors"
          >
            RESTORE SUBSYSTEM
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
