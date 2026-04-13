/// <reference types="vite/client" />

interface YukiAPI {
  minimize: () => void;
  maximize: () => void;
  close: () => void;
  hide: () => void;
  setMode: (mode: string) => void;
  onState: (callback: (msg: any) => void) => void;
  sendChoice: (choice: string) => void;
  trigger: () => void;
  cancelTrigger: () => void;
  sendMessage: (text: string) => void;
  sendUIReady: () => void;
  saveHistory: (messages: any[]) => void;
  onLoadHistory: (callback: (messages: any[]) => void) => void;
  removeStateListener: (callback?: (msg: any) => void) => void;
  saveSettings: (payload: any) => void;
  getSettings: () => Promise<any>;
  purgeMemory: () => void;
  sendCommand: (cmd: any) => void;
}

interface Window {
  yukiAPI: YukiAPI;
}
