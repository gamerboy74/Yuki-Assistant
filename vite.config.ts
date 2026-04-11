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
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom')) return 'vendor';
            if (id.includes('zustand') || id.includes('react-router-dom')) return 'utils';
            return 'vendor'; // Fallback for other node_modules
          }
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
