const { spawn } = require('node:child_process')
const { existsSync } = require('node:fs')
const { resolve } = require('node:path')
const server = resolve(__dirname, '../../server')
const venv = resolve(
  server,
  process.platform === 'win32' ? 'app/.venv/Scripts/python.exe' : 'app/.venv/bin/python',
)
const child = spawn(existsSync(venv) ? venv : 'python', [resolve(__dirname, 'api_server.py')], {
  cwd: server,
  stdio: 'inherit',
})
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal))
child.on('exit', (code) => process.exit(code || 0))
