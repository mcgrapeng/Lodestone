import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// ponytail: proxy /api to the Python radar.py serve (127.0.0.1:8765 by default).
const PY_PORT = process.env.PORT || '8765'
// ponytail: IPv4 explicit — 'localhost' on macOS resolves to ::1 first, and our
// Python serve binds 127.0.0.1 only (loopback IPv4), so a 'localhost' proxy target
// hangs the request. Force IPv4 with 127.0.0.1.
const PY_TARGET = `http://127.0.0.1:${PY_PORT}`

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: Number(process.env.VITE_PORT || 5174),
    host: '127.0.0.1',
    strictPort: true,
    fs: {
      allow: [fileURLToPath(new URL('../', import.meta.url))],
    },
    proxy: {
      '/api': {
        target: PY_TARGET,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
