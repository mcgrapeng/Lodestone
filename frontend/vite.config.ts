import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// ponytail: proxy /api to the Python radar.py serve (127.0.0.1:8765 by default).
const PY_PORT = process.env.PORT || '8765'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    fs: {
      allow: [fileURLToPath(new URL('../', import.meta.url))],
    },
    proxy: {
      '/api': {
        target: `http://localhost:${PY_PORT}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
