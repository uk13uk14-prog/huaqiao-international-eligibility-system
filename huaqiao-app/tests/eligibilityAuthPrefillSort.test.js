import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  SAAS_TOKEN_KEY,
  buildAuthHeaders,
  getSaasToken,
  isExpiredAuthStatus,
  parseHttpErrorMessage,
  setSaasToken,
} from '../src/authToken.js'
import { mapStudentToEligibilityPrefills, mergeEligibilityForm } from '../src/eligibilityPrefill.js'
import {
  SORT_MENU_OPTIONS,
  SORT_MENU_Z_INDEX,
  SORT_OVERLAY_Z_INDEX,
  applySortSelection,
  armOverlayGhostClickGuard,
  panelStyleFromTriggerRect,
  sortMenuLabel,
  universityChromeWhenMenuOpen,
} from '../src/sortMenu.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const cssPath = path.resolve(here, '../src/styles.css')
const sortVuePath = path.resolve(here, '../src/SortMenu.vue')
const appVuePath = path.resolve(here, '../src/App.vue')
const apiPath = path.resolve(here, '../src/api.js')

function mockLocalStorage() {
  const map = new Map()
  globalThis.localStorage = {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => { map.set(k, String(v)) },
    removeItem: (k) => { map.delete(k) },
  }
  return map
}

test('authenticated eligibility submit: shared token persists and builds Authorization', () => {
  mockLocalStorage()
  setSaasToken('tok-login')
  assert.equal(globalThis.localStorage.getItem(SAAS_TOKEN_KEY), 'tok-login')
  assert.equal(getSaasToken(), 'tok-login')
  const headers = buildAuthHeaders()
  assert.equal(headers.Authorization, 'Bearer tok-login')
  assert.equal(headers['Content-Type'], 'application/json')
})

test('login state still present after simulated refresh (same localStorage key)', () => {
  mockLocalStorage()
  setSaasToken('tok-refresh')
  assert.equal(getSaasToken(), 'tok-refresh')
  assert.equal(buildAuthHeaders().Authorization, 'Bearer tok-refresh')
})

test('eligibility API client source uses buildAuthHeaders / Bearer', () => {
  const src = fs.readFileSync(apiPath, 'utf8')
  assert.match(src, /buildAuthHeaders/)
  assert.match(src, /judgeInternational/)
  assert.match(src, /parseHttpErrorMessage/)
})

test('expired or missing token: no Authorization; 401 asks to re-login', () => {
  mockLocalStorage()
  assert.equal(buildAuthHeaders().Authorization, undefined)
  assert.equal(isExpiredAuthStatus(401), true)
  assert.equal(isExpiredAuthStatus(200), false)
  assert.equal(parseHttpErrorMessage(401, '{"detail":"请先登录"}'), '请先登录')
  assert.equal(parseHttpErrorMessage(403, '{"detail":"无权限"}'), '无权限')
})

test('student profile preload fills identity / residence / major / score', () => {
  const student = {
    id: 12,
    display_name: '李华',
    judge_prefills: {
      name: '李华',
      birth_date: '2008-05-01',
      current_nationality: '美国',
      has_foreign_nationality: true,
      has_chinese_nationality: false,
      passport_info: 'E123',
    },
    profile: {
      basic_info: {
        chinese_name: '李华',
        english_name: 'Li Hua',
        birth_date: '2008-05-01',
        current_country: '美国',
      },
      identity: {
        current_nationality: '美国',
        has_foreign_nationality: true,
        has_chinese_nationality: false,
        foreign_permanent_residence: '美国',
        overseas_residence_info: '近2年18个月，近4年36个月，单年11个月',
        birth_country: '美国',
        passport_info: 'E123',
      },
      goals: { targets: [{ major: '计算机科学' }] },
      courses: {
        grades: [{ grade_type: 'Actual', score: '680' }],
        language_exams: [{ exam_type: 'TOEFL', overall_score: '100' }],
      },
      csca: { csca_score: '210' },
    },
  }
  const prefills = mapStudentToEligibilityPrefills(student)
  assert.equal(prefills.name, '李华')
  assert.equal(prefills.birth_date, '2008-05-01')
  assert.equal(prefills.current_nationality, '美国')
  assert.equal(prefills.has_foreign_nationality, true)
  assert.equal(prefills.permanent_residence_country, '美国')
  assert.equal(prefills.overseas_residence_months_last_2y, 18)
  assert.equal(prefills.overseas_residence_months_last_4y, 36)
  assert.equal(prefills.annual_months_overseas, 11)
  assert.equal(prefills.intended_field, '理工')
  assert.equal(prefills.score, 680)
  assert.equal(prefills.born_abroad, true)
})

test('empty profile does not wipe default form; profile beats draft', () => {
  const defaults = {
    name: '',
    intended_field: '综合',
    score: null,
    overseas_residence_months_last_4y: 24,
    has_foreign_nationality: true,
  }
  const empty = mapStudentToEligibilityPrefills({ id: 1, profile: { basic_info: {}, identity: {}, goals: { targets: [] }, courses: {} } })
  assert.deepEqual(empty, {})
  const mergedBlank = mergeEligibilityForm(defaults, { profile: empty })
  assert.equal(mergedBlank.intended_field, '综合')
  assert.equal(mergedBlank.overseas_residence_months_last_4y, 24)
  assert.equal(mergedBlank.has_foreign_nationality, true)

  const merged = mergeEligibilityForm(defaults, {
    draft: { name: '草稿名', intended_field: '体育' },
    profile: { name: '档案名', intended_field: '医药' },
  })
  assert.equal(merged.name, '档案名')
  assert.equal(merged.intended_field, '医药')
})

test('sort dropdown selection and click-through prevention helpers', () => {
  assert.equal(sortMenuLabel('recommend'), '推荐')
  assert.equal(sortMenuLabel('az'), 'A-Z')
  assert.deepEqual(applySortSelection('recommend', 'recommend'), { next: 'recommend', changed: false, close: true })
  assert.deepEqual(applySortSelection('recommend', 'az'), { next: 'az', changed: true, close: true })
  const openChrome = universityChromeWhenMenuOpen(true)
  assert.equal(openChrome.overlay, true)
  assert.equal(openChrome.azPointerEvents, 'none')
  assert.equal(openChrome.overlayPointerEvents, 'auto')
  assert.equal(openChrome.filterPointerEvents, 'none')
  const closedChrome = universityChromeWhenMenuOpen(false)
  assert.equal(closedChrome.azPointerEvents, 'auto')
  assert.equal(closedChrome.filterPointerEvents, 'auto')
  assert.ok(SORT_MENU_OPTIONS.some((o) => o.value === 'az'))
  assert.equal(SORT_OVERLAY_Z_INDEX, 3000)
  assert.equal(SORT_MENU_Z_INDEX, 3001)
  assert.ok(SORT_MENU_Z_INDEX > SORT_OVERLAY_Z_INDEX)
  const style = panelStyleFromTriggerRect({ left: 20, bottom: 120, width: 80 }, { viewportWidth: 390 })
  assert.equal(style.top, '124px')
  assert.match(style.width, /16\dpx/)
})

test('overlay ghost-click guard swallows the next document click', () => {
  const calls = []
  const listeners = { click: [], touchend: [] }
  const doc = {
    addEventListener(type, fn, capture) {
      if (capture) listeners[type]?.push(fn)
    },
    removeEventListener(type, fn, capture) {
      if (!capture || !listeners[type]) return
      listeners[type] = listeners[type].filter((x) => x !== fn)
    },
  }
  const disarm = armOverlayGhostClickGuard(doc, 20)
  const ev = {
    preventDefault() { calls.push('prevent') },
    stopPropagation() { calls.push('stop') },
  }
  listeners.click[0](ev)
  assert.ok(calls.includes('prevent'))
  assert.ok(calls.includes('stop'))
  disarm()
  assert.equal(listeners.click.length, 0)
})

test('sort menu vue teleports overlay+panel to body with solid menu', () => {
  const vue = fs.readFileSync(sortVuePath, 'utf8')
  assert.match(vue, /Teleport to="body"/)
  assert.match(vue, /closeTick/)
  assert.match(vue, /sort-menu-overlay/)
  assert.match(vue, /background:\s*#ffffff/i)
  assert.match(vue, /background:\s*rgba\(\s*0,\s*0,\s*0,\s*0\.25\s*\)/)
  assert.match(vue, /z-index:\s*3000/)
  assert.match(vue, /z-index:\s*3001/)
  assert.match(vue, /position:\s*fixed/)
  assert.match(vue, /pointer-events:\s*auto/)
  assert.match(vue, /touchend\.prevent\.stop="onOverlayClose"/)
  assert.match(vue, /touchstart\.prevent\.stop="onOverlayGuard"/)
  assert.doesNotMatch(vue, /touchstart\.prevent\.stop="close"/)
  assert.doesNotMatch(vue, /univ-sort-layer/)
  assert.doesNotMatch(vue, /UNIV_SORT_LAYER_ID/)
  assert.doesNotMatch(vue, /\.sort-menu-panel[^{]*\{[^}]*opacity:\s*0\.\d/)
  const panelBlock = vue.match(/\.sort-menu-panel\s*\{[\s\S]*?\}/)
  assert.ok(panelBlock)
  assert.match(panelBlock[0], /background:\s*#ffffff/i)
  assert.match(panelBlock[0], /opacity:\s*1/)
  assert.doesNotMatch(panelBlock[0], /background:\s*rgba\(/)
})

test('university list CSS: first card uses list gap, not margin collapsing; az inert when menu open', () => {
  const css = fs.readFileSync(cssPath, 'utf8')
  const listBlock = css.match(/\.univ-list\s*\{[\s\S]*?\}/)
  assert.ok(listBlock, 'univ-list block')
  assert.match(listBlock[0], /display:\s*flex/)
  assert.match(listBlock[0], /flex-direction:\s*column/)
  assert.match(listBlock[0], /gap:\s*12px/)
  const cardBlock = css.match(/\.univ-card\s*\{[\s\S]*?\}/)
  assert.ok(cardBlock, 'univ-card block')
  assert.match(cardBlock[0], /margin:\s*0/)
  assert.match(css, /\.univ-results/)
  assert.match(css, /\.univ-list-spacer/)
  assert.match(css, /\.univ-toolbar \.van-search[\s\S]{0,280}position:\s*static/)
  assert.match(css, /\.univ-az\.is-inert/)
  assert.match(css, /\.univ-filter-menu-open \.univ-layout/)
  assert.match(css, /display:\s*none !important/)
  assert.match(css, /pointer-events:\s*none/)
  assert.doesNotMatch(css, /\.univ-sort-layer/)
  assert.doesNotMatch(css, /gq-univ-sort-open/)
  const screenBlock = css.match(/\.univ-screen\s*\{[\s\S]*?\}/)
  assert.ok(screenBlock, 'univ-screen block')
  assert.doesNotMatch(screenBlock[0], /isolation:\s*isolate/)
  const toolbarBlock = css.match(/\/\* University native filter[\s\S]{0,500}\.univ-toolbar \{[\s\S]{0,180}\}/)
  assert.ok(toolbarBlock, 'toolbar block')
  assert.doesNotMatch(toolbarBlock[0], /position:\s*sticky/)
})

test('university DOM title exists; recommend sort keeps first school first', () => {
  const app = fs.readFileSync(appVuePath, 'utf8')
  assert.match(app, /#\{\{\s*school\.ranking\s*\}\} \{\{\s*school\.name\s*\}\}/)
  assert.match(app, /class="univ-card-head"/)
  assert.match(app, /class="univ-results"/)
  assert.match(app, /univActiveMenu/)
  assert.match(app, /MobileFilterMenu/)
  assert.doesNotMatch(app, /univ-sort-layer/)
  assert.doesNotMatch(app, /UNIV_SORT_LAYER/)
  const univSection = app.split("tab === 'universities'")[1]?.split("tab === 'schedule'")[0] || ''
  assert.doesNotMatch(univSection, /van-dropdown-menu/)
  assert.doesNotMatch(univSection, /van-dropdown-item/)
  assert.doesNotMatch(univSection, /van-popup/)
  const scheduleSection = app.split("tab === 'schedule'")[1]?.split("tab === 'history'")[0] || ''
  assert.doesNotMatch(scheduleSection, /van-dropdown-menu/)
  assert.doesNotMatch(scheduleSection, /van-dropdown-item/)
  assert.match(scheduleSection, /MobileFilterMenu/)
  assert.match(scheduleSection, /timelineActiveMenu/)
})

test('iPhone-width layout tokens exist for 390/393/430 class screens', () => {
  const css = fs.readFileSync(cssPath, 'utf8')
  assert.match(css, /safe-area-inset-top/)
  assert.match(css, /padding-bottom:\s*calc\(64px \+ env\(safe-area-inset-bottom\)\)/)
  const widths = [390, 393, 430]
  for (const w of widths) {
    const panel = panelStyleFromTriggerRect({ left: 12, bottom: 180, width: 90 }, { viewportWidth: w })
    const left = Number(String(panel.left).replace('px', ''))
    const width = Number(String(panel.width).replace('px', ''))
    assert.ok(left >= 8, `${w} left`)
    assert.ok(left + width <= w - 4, `${w} panel stays on screen`)
  }
})

test('preview build badge is gated by VITE_PREVIEW_DIAGNOSTIC and not shown by default', () => {
  const badge = fs.readFileSync(path.resolve(here, '../src/PreviewBuildBadge.vue'), 'utf8')
  const app = fs.readFileSync(appVuePath, 'utf8')
  assert.match(badge, /PREVIEW BUILD/)
  assert.match(badge, /VITE_PREVIEW_DIAGNOSTIC/)
  assert.match(badge, /VITE_PREVIEW_HEAD/)
  assert.match(badge, /z-index:\s*2147483647/)
  assert.match(app, /PreviewBuildBadge/)
  assert.doesNotMatch(badge, /userAgent|user-agent/)
})
