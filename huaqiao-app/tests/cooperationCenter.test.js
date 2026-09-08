import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const appVuePath = path.resolve(here, '../src/App.vue')
const coopVuePath = path.resolve(here, '../src/CooperationCenter.vue')
const apiPath = path.resolve(here, '../src/api.js')
const cssPath = path.resolve(here, '../src/styles.css')

test('home cooperation entry and route exist without tabbar item', () => {
  const app = fs.readFileSync(appVuePath, 'utf8')
  assert.match(app, /text="合作中心"/)
  assert.match(app, /openPage\('cooperation'\)/)
  assert.match(app, /tab === 'cooperation'/)
  assert.match(app, /cooperation: '合作中心'/)
  assert.match(app, /#\/cooperation/)
  assert.match(app, /van-tabbar-item name="home"/)
  assert.doesNotMatch(app, /<van-tabbar-item[^>]*>合作中心/)
})

test('cooperation page loads public API and does not hardcode brands', () => {
  const vue = fs.readFileSync(coopVuePath, 'utf8')
  const api = fs.readFileSync(apiPath, 'utf8')
  assert.match(api, /cooperation:\s*\(\)\s*=> request\('\/api\/cooperation'\)/)
  assert.match(vue, /api\.cooperation\(\)/)
  assert.match(vue, /item\.brand_name/)
  assert.match(vue, /contact\.wechat/)
  assert.match(vue, /contact\.qr_url/)
  assert.doesNotMatch(vue, /清华大学/)
  assert.doesNotMatch(vue, /your-service@example.com/)
})

test('cooperation mobile layout tokens prevent overflow', () => {
  const css = fs.readFileSync(cssPath, 'utf8')
  assert.match(css, /\.coop-page[\s\S]{0,80}overflow-x:\s*hidden/)
  assert.match(css, /\.coop-brand-name[\s\S]{0,80}word-break:\s*break-word/)
  assert.match(css, /\.coop-line b, \.coop-line a[\s\S]{0,120}overflow-wrap:\s*anywhere/)
})
