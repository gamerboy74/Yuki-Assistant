const { contextBridge, ipcRenderer } = require('electron');

// Global registry for state listeners to prevent cross-contamination
const stateListeners = new Set();
ipcRenderer.on('yuki:state', (_event, msg) => {
  stateListeners.forEach(callback => {
    try { 
      if (typeof callback === 'function') callback(msg); 
    } catch (e) { 
      console.error('IPC Callback Error:', e); 
    }
  });
});

contextBridge.exposeInMainWorld('yukiAPI', {
  // Window controls
  minimize: ()         => ipcRenderer.send('window:minimize'),
  maximize: ()         => ipcRenderer.send('window:maximize'),
  close:    ()         => ipcRenderer.send('window:close'),
  hide:     ()         => ipcRenderer.send('window:hide'),
  setMode:  (mode)     => ipcRenderer.send('window:set-mode', mode),

  // Receive state events from Python backend.
  onState: (callback) => {
    stateListeners.add(callback);
    // Note: We don't return the cleanup function because contextBridge strips it.
    // Instead, components should use removeStateListener(callback).
  },

  // Targeted removal (or global if needed for legacy components)
  removeStateListener: (callback) => {
    if (callback) stateListeners.delete(callback);
    else stateListeners.clear();
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

  // Settings & Memory
  saveSettings: (payload) => ipcRenderer.send('yuki:save-settings', payload),
  getSettings:  () => ipcRenderer.invoke('yuki:get-settings'),
  purgeMemory:  () => ipcRenderer.send('yuki:purge-memory'),
  sendCommand:  (cmd)     => ipcRenderer.send('yuki:command', cmd),
});
