const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('yukiAPI', {
  // Window controls
  minimize: ()         => ipcRenderer.send('window:minimize'),
  maximize: ()         => ipcRenderer.send('window:maximize'),
  close:    ()         => ipcRenderer.send('window:close'),
  hide:     ()         => ipcRenderer.send('window:hide'),
  setMode:  (mode)     => ipcRenderer.send('window:set-mode', mode),

  // Receive state events from Python backend.
  // Safe to call multiple times — removes previous listener first.
  onState: (callback) => {
    ipcRenderer.removeAllListeners('yuki:state');
    ipcRenderer.on('yuki:state', (_event, msg) => callback(msg));
  },

  // Send user clarification choice back to Python
  sendChoice: (choice) => ipcRenderer.send('yuki:choice', choice),

  // Manually trigger Aetheris (orb / mic click)
  trigger: () => ipcRenderer.send('yuki:trigger'),
  cancelTrigger: () => ipcRenderer.send('yuki:cancel-trigger'),

  // Send a typed text message to Python
  sendMessage: (text) => ipcRenderer.send('yuki:message', text),

  // Notify Python that the React UI has fully mounted
  sendUIReady: () => ipcRenderer.send('yuki:ui-ready'),

  // History
  saveHistory: (messages) => ipcRenderer.send('yuki:save-history', messages),
  onLoadHistory: (callback) => {
    ipcRenderer.removeAllListeners('yuki:load-history');
    ipcRenderer.on('yuki:load-history', (_event, messages) => callback(messages));
  },

  // Remove state listener on cleanup

  removeStateListener: () => ipcRenderer.removeAllListeners('yuki:state'),
});

