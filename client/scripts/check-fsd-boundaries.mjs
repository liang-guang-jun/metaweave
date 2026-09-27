import { readdir, readFile } from 'node:fs/promises'
import { relative, resolve } from 'node:path'

const root = resolve(process.cwd(), 'src')
const layers = ['shared', 'entities', 'features', 'widgets', 'pages', 'app']
const rank = Object.fromEntries(layers.map((layer, index) => [layer, index]))
const violations = []

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory()) files.push(...await sourceFiles(path))
    else if (/\.(ts|tsx)$/.test(entry.name)) files.push(path)
  }
  return files
}

for (const file of await sourceFiles(root)) {
  const source = await readFile(file, 'utf8')
  const sourceLayer = relative(root, file).split('/')[0]
  if (!layers.includes(sourceLayer)) continue
  const imports = [...source.matchAll(/from\s+['"]@\/([^/'"]+)/g)].map((match) => match[1])
  for (const importedLayer of imports) {
    if (!layers.includes(importedLayer)) continue
    if (rank[sourceLayer] < rank[importedLayer]) violations.push(`${relative(process.cwd(), file)} imports ${importedLayer}`)
  }
}

if (violations.length) {
  console.error('FSD boundary violations:')
  for (const violation of violations) console.error(`- ${violation}`)
  process.exitCode = 1
} else {
  console.log('FSD boundaries: OK')
}
