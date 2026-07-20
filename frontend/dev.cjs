#!/usr/bin/env node
// ponytail: orchestrate Python API server + Vite together so `npm run dev` is the one command
// zero deps — uses only Node stdlib (child_process)
const { spawn } = require('node:child_process')
const path = require('node:path')
const fs = require('node:fs')

const ROOT = path.resolve(__dirname, '..')
const PY = process.env.PYTHON || 'python3'
const PORT = process.env.PORT || '8765'

function start(label, cmd, args, opts = {}) {
  // ponytail: Python needs cwd=ROOT (data/, radar.py); Vite needs cwd=frontend/ (index.html, vite.config.js)
  const cwd = opts.cwd || ROOT
  const p = spawn(cmd, args, { stdio: 'inherit', cwd, ...opts })
  p.on('exit', code => {
    console.log(`\n[${label}] exited (${code}). Shutting down siblings.`)
    cleanup(code ?? 0)
  })
  return p
}

let py, vite, exiting = false
function cleanup(code = 0) {
  if (exiting) return
  exiting = true
  for (const p of [vite, py]) {
    try { p && !p.killed && p.kill('SIGTERM') } catch {}
  }
  setTimeout(() => process.exit(code), 300)
}
process.on('SIGINT', () => cleanup(0))
process.on('SIGTERM', () => cleanup(0))

py = start('python', PY, ['radar.py', 'serve', PORT])

// ponytail: tiny delay so Python binds :8765 before Vite starts proxying /api
setTimeout(() => {
  // ponytail: invoke local node_modules/.bin/vite — avoids npx fetching a different version
  const localVite = path.join(__dirname, 'node_modules', '.bin', 'vite')
  if (fs.existsSync(localVite)) {
    vite = start('vite', localVite, [], { cwd: __dirname, env: { ...process.env } })
  } else {
    console.log('[dev] local vite not found, falling back to npx (run `npm install` first)')
    vite = start('vite', 'npx', ['vite'], { cwd: __dirname, env: { ...process.env } })
  }
}, 1200)

console.log('[dev] Python API on :' + PORT + ' · Vite on :5173 (proxies /api → :' + PORT + ')')