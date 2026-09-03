/**
 * SaaS login regression against running Vite (:5180) + API (:8010).
 * Usage (from any cwd with puppeteer-core available):
 *   node /workspace/huaqiao-saas-pro/frontend/tests/login.e2e.mjs
 */
import assert from 'node:assert/strict'
import { createRequire } from 'module'
import { pathToFileURL } from 'node:url'

const require = createRequire(import.meta.url)
let puppeteer
try {
  puppeteer = require('/tmp/node_modules/puppeteer-core')
} catch {
  puppeteer = (await import(pathToFileURL('/tmp/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js').href)).default
}

const BASE = process.env.SAAS_URL || 'http://127.0.0.1:5180'
const EMAIL = process.env.SAAS_EMAIL || 'demo@example.com'
const PASSWORD = process.env.SAAS_PASSWORD || 'demo123456'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function withPage(fn) {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || '/usr/local/bin/google-chrome',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1400,900'],
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 1400, height: 900 })
  try {
    return await fn(page)
  } finally {
    await browser.close()
  }
}

async function clearSession(page) {
  await page.goto(BASE, { waitUntil: 'networkidle0', timeout: 60000 })
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload({ waitUntil: 'networkidle0' })
  await sleep(500)
}

async function fillLogin(page) {
  await page.waitForSelector('[data-testid="login-submit"]')
  const email = await page.$('[data-testid="login-email"]')
  const pass = await page.$('[data-testid="login-password"]')
  assert.ok(email && pass, 'login inputs missing')
  await email.click({ clickCount: 3 })
  await email.type(EMAIL)
  await pass.click({ clickCount: 3 })
  await pass.type(PASSWORD)
  return pass
}

console.log('1) page load')
await withPage(async (page) => {
  await clearSession(page)
  assert.ok(await page.$('[data-testid="login-submit"]'))
  assert.ok(await page.$('[data-testid="login-email"]'))
  assert.ok(await page.$('[data-testid="login-password"]'))
})

console.log('2-8) click login → POST → token → home')
let authUrl = ''
await withPage(async (page) => {
  const api = []
  page.on('request', (r) => {
    if (r.url().includes('/api/auth/login')) api.push({ method: r.method(), url: r.url(), body: r.postData() })
  })
  page.on('response', (r) => {
    if (r.url().includes('/api/auth/login')) api.push({ status: r.status() })
  })
  await clearSession(page)
  await fillLogin(page)
  await page.click('[data-testid="login-submit"]')
  await sleep(2500)
  const state = await page.evaluate(() => ({
    token: localStorage.getItem('saas_token'),
    loggedIn: document.body.innerText.includes('退出'),
  }))
  assert.ok(api.some((x) => x.method === 'POST'), 'POST not sent')
  assert.ok(api.some((x) => x.status === 200), 'login not 200')
  assert.ok(state.token, 'token not saved')
  assert.equal(state.loggedIn, true, 'home not shown')
  authUrl = api.find((x) => x.method === 'POST').url
  console.log('  AUTH_REQUEST_URL=', authUrl)
})

console.log('5b) Enter key login')
await withPage(async (page) => {
  const api = []
  page.on('request', (r) => {
    if (r.url().includes('/api/auth/login')) api.push(r.method())
  })
  await clearSession(page)
  const pass = await fillLogin(page)
  await pass.press('Enter')
  await sleep(2500)
  assert.ok(api.includes('POST'), 'Enter did not POST')
  assert.equal(await page.evaluate(() => document.body.innerText.includes('退出')), true)
})

console.log('9) refresh keeps login')
await withPage(async (page) => {
  await clearSession(page)
  await fillLogin(page)
  await page.click('[data-testid="login-submit"]')
  await sleep(2000)
  await page.reload({ waitUntil: 'networkidle0' })
  await sleep(1000)
  assert.equal(await page.evaluate(() => document.body.innerText.includes('退出')), true)
})

console.log('10) logout clears token')
await withPage(async (page) => {
  await clearSession(page)
  await fillLogin(page)
  await page.click('[data-testid="login-submit"]')
  await sleep(2000)
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find((b) => (b.textContent || '').includes('退出'))
    btn?.click()
  })
  await page.waitForSelector('[data-testid="login-submit"]', { timeout: 10000 })
  assert.equal(await page.evaluate(() => localStorage.getItem('saas_token')), null)
})

console.log('LOGIN_AUTOMATED_TEST=PASS')
