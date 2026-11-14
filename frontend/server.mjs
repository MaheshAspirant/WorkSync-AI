/**
 * Sandbox-safe static preview server.
 *
 * Serves the production bundle and proxies /api to the FastAPI backend. It uses
 * only Node's built-in modules, so it does not need to spawn esbuild (which the
 * Windows sandbox blocks). `npm run dev` still uses the standard Vite dev server
 * in normal development environments.
 */
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'dist')
const port = Number(process.env.PORT || 4173)
const target = new URL(process.env.API_TARGET || 'http://127.0.0.1:8000')
const mime = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2',
}

const server = http.createServer((req, res) => {
  if (req.url.startsWith('/api')) {
    const proxyReq = http.request(
      {
        hostname: target.hostname,
        port: target.port || 80,
        path: req.url,
        method: req.method,
        headers: { ...req.headers, host: target.host },
      },
      (proxyRes) => {
        res.writeHead(proxyRes.statusCode || 502, proxyRes.headers)
        proxyRes.pipe(res)
      },
    )
    proxyReq.on('error', (error) => {
      res.writeHead(502, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ error: { message: `API proxy error: ${error.message}` } }))
    })
    req.pipe(proxyReq)
    return
  }

  const urlPath = decodeURIComponent(req.url.split('?')[0])
  let filePath = path.join(root, urlPath === '/' ? 'index.html' : urlPath)
  if (!filePath.startsWith(root)) {
    res.writeHead(403)
    res.end('Forbidden')
    return
  }
  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    filePath = path.join(root, 'index.html')
  }
  fs.readFile(filePath, (error, content) => {
    if (error) {
      res.writeHead(404)
      res.end('Not found')
      return
    }
    res.writeHead(200, { 'Content-Type': mime[path.extname(filePath)] || 'application/octet-stream' })
    res.end(content)
  })
})

server.listen(port, '127.0.0.1', () => {
  console.log(`WorkSync AI frontend preview: http://127.0.0.1:${port}`)
  console.log(`API proxy target: ${target.origin}`)
})
