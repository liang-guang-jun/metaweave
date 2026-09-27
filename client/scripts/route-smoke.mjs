import { spawn } from 'node:child_process'

const host = '127.0.0.1'
const port = '4173'
const server = spawn('pnpm', ['preview', '--host', host, '--port', port], { stdio: 'ignore' })
const urls = ['/login', '/register', '/tenant/acme', '/app']

try {
  let ready = false
  for (let attempt = 0; attempt < 30 && !ready; attempt += 1) {
    try {
      const response = await fetch(`http://${host}:${port}/login`)
      ready = response.ok
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
  }
  if (!ready) throw new Error('Preview server did not become ready.')
  for (const url of urls) {
    const response = await fetch(`http://${host}:${port}${url}`)
    const html = await response.text()
    if (!response.ok || !html.includes('<div id="root">')) throw new Error(`${url} returned an invalid app shell.`)
    console.log(`Route OK: ${url}`)
  }
} finally {
  server.kill('SIGTERM')
}
