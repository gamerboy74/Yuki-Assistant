import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  base: './',
  root: '.',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist/renderer',
    emptyOutDir: true,
    target: 'esnext', // Target modern browsers for better performance
    minify: 'terser', // Higher quality minification
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          utils: ['zustand', 'react-router-dom'], 
        },
      },
    },
    assetsInlineLimit: 10240, // Inline assets smaller than 10KB (base64) to reduce IO latency
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
