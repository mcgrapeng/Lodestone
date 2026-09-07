#!/usr/bin/env node
// ponytail: orchestrate Python API server + Vite together so `npm run dev` is the one command
// ponytail: port auto-discovery — Python may bind to 8765 OR a fallback (8766, 8767, ...)
// if the requested port is taken. We parse its [serve-port] marker line, then spawn Vite
// with the actual port via the PORT env var (vite.config.ts reads `process.env.PORT`).
// zero deps — uses only Node stdlib (child_process)
const { spawn } = require('node:child_process')
const path = require('node:path')
const fs = require('node:fs')

const ROOT = path.resolve(__dirname, '..')
const PY = process.env.PYTHON || 'python3'
const PORT = process.env.PORT || '8765'

function start(label, cmd, args, opts = {}) {
  const cwd = opts.cwd || ROOT
  const p = spawn(cmd, args, { stdio: ['ignore', 'pipe', 'pipe'], cwd, ...opts })
  p.on('exit', code => {
    console.log(`\n[${label}] exited (${code}). Shutting down siblings.`)
    cleanup(code ?? 0)
  })
  return p
}

let py, vite, exiting = false, portSet = false, actualPyPort = null
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

// ponytail: spawn Python FIRST so we can discover the actual bound port before
// starting Vite (which needs to know where to proxy /api/*).
py = start('python', PY, ['radar.py', 'serve', PORT])
let pyOutBuf = ''
py.stdout.on('data', (chunk) => {
  const text = chunk.toString()
  process.stdout.write(text)
  pyOutBuf += text
  // ponytail: parse the first [serve-port] NNNN line and, once seen, spawn Vite.
  // Using a regex on a growing buffer (rather than line-by-line) is fine — the
  // marker only ever appears once at startup.
  if (!portSet) {
    const m = pyOutBuf.match(/\[serve-port\]\s+(\d+)/)
    if (m) {
      portSet = true
      actualPyPort = m[1]
      spawnVite(actualPyPort)
    }
  }
})
py.stderr.on('data', (chunk) => process.stderr.write(chunk))

function spawnVite(pyPort) {
  const localVite = path.join(__dirname, 'node_modules', '.bin', 'vite')
  // ponytail: --host 127.0.0.1 forces IPv4 binding (default vite listens on [::1] only
  // which browsers that resolve localhost to IPv4 can't reach). Vite's default
  // `strictPort: false` already auto-walks to 5174/5175/... when 5173 is taken —
  // no extra arg needed.
  const hostArgs = process.argv.includes('--ipv6-only') ? [] : ['--host', '127.0.0.1']
  const env = { ...process.env, PORT: pyPort }
  // ponytail: spawn Vite with stdio: 'inherit' so its banner (`Local: http://...`)
  // shows up directly in the terminal. The Python-side stdio: 'pipe' is still
  // needed above because we parse its [serve-port] marker — that's the only
  // reason dev.cjs can't inherit everything.
  function spawnViteProcess(cmd, args) {
    const p = spawn(cmd, args, { stdio: 'inherit', cwd: __dirname, env })
    p.on('exit', (code) => {
      console.log(`\n[vite→:${pyPort}] exited (${code}). Shutting down siblings.`)
      cleanup(code ?? 0)
    })
    return p
  }
  console.log(`[dev] Python on :${pyPort} · starting Vite (proxy /api → :${pyPort})`)
  if (fs.existsSync(localVite)) {
    vite = spawnViteProcess(localVite, hostArgs)
  } else {
    console.log('[dev] local vite not found, falling back to npx (run `npm install` first)')
    vite = spawnViteProcess('npx', ['vite', ...hostArgs])
  }
}

// ponytail: 10s safety net — if Python never prints [serve-port] (e.g. crash on
// startup), exit loudly instead of hanging forever.
setTimeout(() => {
  if (!portSet) {
    console.error('[dev] Python did not print [serve-port] within 10s — exiting')
    cleanup(1)
  }
}, 10_000)
