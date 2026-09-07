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
  applySortSelection,
  panelStyleFromTriggerRect,
  sortMenuLabel,
  universityChromeWhenMenuOpen,
} from '../src/sortMenu.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const cssPath = path.resolve(here, '../src/styles.css')
const sortVuePath = path.resolve(here, '../src/SortMenu.vue')
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
  const closedChrome = universityChromeWhenMenuOpen(false)
  assert.equal(closedChrome.azPointerEvents, 'auto')
  assert.ok(SORT_MENU_OPTIONS.some((o) => o.value === 'az'))
  const style = panelStyleFromTriggerRect({ left: 20, bottom: 120, width: 80 }, { viewportWidth: 390 })
  assert.equal(style.top, '124px')
  assert.match(style.width, /16\dpx/)
})

test('sort menu vue uses solid panel, overlay, and no container opacity', () => {
  const vue = fs.readFileSync(sortVuePath, 'utf8')
  assert.match(vue, /sort-menu-overlay/)
  assert.match(vue, /background:\s*#ffffff/i)
  assert.match(vue, /pointerdown\.prevent\.stop="close"/)
  assert.doesNotMatch(vue, /\.sort-menu-panel[^{]*\{[^}]*opacity:\s*0\.\d/)
})

test('university list CSS: first card not clipped; az inert when menu open', () => {
  const css = fs.readFileSync(cssPath, 'utf8')
  assert.match(css, /\.univ-list[\s\S]{0,180}padding:\s*10px/)
  assert.match(css, /\.univ-card[\s\S]{0,280}margin:\s*0 0 10px/)
  assert.doesNotMatch(css, /\.univ-layout\s*\{[^}]*overflow-x:\s*hidden/)
  assert.match(css, /\.univ-toolbar \.van-search[\s\S]{0,80}position:\s*static/)
  assert.match(css, /\.univ-az\.is-inert/)
  assert.match(css, /\.list-screen\.has-sort-menu \.univ-az/)
  assert.match(css, /pointer-events:\s*none/)
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
