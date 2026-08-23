/**
 * 将 Vite 构建产物复制到 hbuilder-pack/www，供 HBuilderX 5+ App 替换 www 使用。
 */
const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const dist = path.join(root, 'dist')
const out = path.join(root, 'hbuilder-pack', 'www')

if (!fs.existsSync(dist)) {
  console.error('请先执行 npm run build')
  process.exit(1)
}

fs.rmSync(out, { recursive: true, force: true })
fs.mkdirSync(out, { recursive: true })
fs.cpSync(dist, out, { recursive: true })
console.log('已输出到 hbuilder-pack/www，详见 hbuilder-pack/README.txt')
