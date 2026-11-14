import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = fs.readFileSync(path.join(root, 'index.html'), 'utf8')
const html = source
  .replace('<script type="module" src="/src/main.jsx"></script>', '<script type="module" src="/assets/app.js"></script>')
  .replace('</head>', '    <link rel="stylesheet" href="/assets/app.css" />\n  </head>')

fs.mkdirSync(path.join(root, 'dist'), { recursive: true })
fs.writeFileSync(path.join(root, 'dist/index.html'), html)
console.log('Wrote dist/index.html')
