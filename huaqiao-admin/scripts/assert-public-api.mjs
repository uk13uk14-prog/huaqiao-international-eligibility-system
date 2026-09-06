import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const dist = new URL('../dist/', import.meta.url).pathname
const mustHave = 'https://api.guoqiaoplan.com'
// Forbidden as concrete URLs (ignore library regex vocab containing the word localhost)
const bannedExact = [
  'http://localhost',
  'https://localhost',
  'http://127.0.0.1',
  'https://127.0.0.1',
  'http://0.0.0.0',
  'http://192.168.',
  'http://10.',
]

function walk(dir) {
  const out = []
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) out.push(...walk(p))
    else if (/\.(js|css|html|json)$/.test(name)) out.push(p)
  }
  return out
}

let foundApi = false
const hits = []
for (const file of walk(dist)) {
  const text = readFileSync(file, 'utf8')
  if (text.includes(mustHave)) foundApi = true
  for (const b of bannedExact) {
    if (text.includes(b)) hits.push(`${file} contains ${b}`)
  }
}
if (!foundApi) {
  console.error('FAIL: production API base not embedded:', mustHave)
  process.exit(1)
}
if (hits.length) {
  console.error('FAIL: private/local URLs in dist:\n' + hits.join('\n'))
  process.exit(1)
}
console.log('PUBLIC_API_EMBEDDED=PASS')
console.log('PRIVATE_URLS_REMAINING=NO')
