import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// ponytail: serve parent dir + proxy /api to Python server on 8765 (started by dev.js)
const PY_PORT = process.env.PORT || '8765'
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    open: true,
    fs: {
      allow: [fileURLToPath(new URL('../', import.meta.url))]
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