import { existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'

const app = 'huaqiao-app'
const hasLock = existsSync(`${app}/package-lock.json`)
const hasModules = existsSync(`${app}/node_modules/vite`)
const install = hasModules
  ? null
  : hasLock
    ? ['npm', ['ci', '--prefix', app]]
    : ['npm', ['install', '--prefix', app]]
if (install) {
  const r = spawnSync(install[0], install[1], { stdio: 'inherit', shell: false })
  if (r.status) process.exit(r.status || 1)
}
const b = spawnSync('npm', ['run', 'build', '--prefix', app], { stdio: 'inherit', shell: false })
process.exit(b.status || 0)
