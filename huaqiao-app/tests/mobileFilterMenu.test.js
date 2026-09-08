import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  FILTER_MENU_Z_INDEX,
  FILTER_OVERLAY_Z_INDEX,
  IDENTITY_MENU_OPTIONS,
  SORT_MENU_OPTIONS,
  applyFilterSelection,
  armOverlayGhostClickGuard,
  filterMenuLabel,
  nextActiveMenu,
  optionLabels,
  panelStyleFromTriggerRect,
  universityPaintWhenFilterOpen,
} from '../src/mobileFilterMenu.js'
import { browseUniversities } from '../src/universityBrowse.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const appVuePath = path.resolve(here, '../src/App.vue')
const menuVuePath = path.resolve(here, '../src/MobileFilterMenu.vue')
const cssPath = path.resolve(here, '../src/styles.css')

function universitySection() {
  const app = fs.readFileSync(appVuePath, 'utf8')
  return app.split("tab === 'universities'")[1]?.split("tab === 'schedule'")[0] || ''
}

test('identity menu only has 国际生 / 华侨生', () => {
  assert.deepEqual(optionLabels(IDENTITY_MENU_OPTIONS), ['国际生', '华侨生'])
  assert.deepEqual(IDENTITY_MENU_OPTIONS.map((o) => o.value), ['international', 'huaqiao'])
  assert.equal(filterMenuLabel('international', IDENTITY_MENU_OPTIONS), '国际生')
  assert.equal(filterMenuLabel('huaqiao', IDENTITY_MENU_OPTIONS), '华侨生')
  const labels = optionLabels(IDENTITY_MENU_OPTIONS)
  assert.ok(!labels.includes('全部地区'))
  assert.ok(!labels.includes('全部层级'))
  assert.ok(!labels.includes('全部领域'))
  assert.ok(!labels.includes('推荐'))
  const univ = universitySection()
  assert.match(univ, /univIdentityMenuOptions/)
  assert.doesNotMatch(univ, /全部地区/)
  assert.doesNotMatch(univ, /全部层级/)
  assert.doesNotMatch(univ, /全部领域/)
})

test('sort menu only has 推荐 / A-Z', () => {
  assert.deepEqual(optionLabels(SORT_MENU_OPTIONS), ['推荐', 'A-Z'])
  assert.deepEqual(SORT_MENU_OPTIONS.map((o) => o.value), ['recommend', 'az'])
  const labels = optionLabels(SORT_MENU_OPTIONS)
  assert.ok(!labels.includes('地区'))
  assert.ok(!labels.includes('院校层次'))
  assert.ok(!labels.includes('国际生'))
  const app = fs.readFileSync(appVuePath, 'utf8')
  assert.match(app, /univSortMenuOptions = SORT_MENU_OPTIONS/)
})

test('only one active menu at a time', () => {
  assert.equal(nextActiveMenu('', 'target'), 'target')
  assert.equal(nextActiveMenu('target', 'sort'), 'sort')
  assert.equal(nextActiveMenu('sort', 'province'), 'province')
  assert.equal(nextActiveMenu('target', 'target'), '')
  assert.deepEqual(applyFilterSelection('international', 'huaqiao'), {
    next: 'huaqiao',
    changed: true,
    close: true,
  })
  const app = fs.readFileSync(appVuePath, 'utf8')
  assert.match(app, /const univActiveMenu = ref\(''\)/)
  assert.equal((app.match(/univActiveMenu/g) || []).length > 5, true)
})

test('AZ and underlying page interaction disabled when menu open', () => {
  const open = universityPaintWhenFilterOpen(true)
  assert.equal(open.listDisplay, 'none')
  assert.equal(open.azDisplay, 'none')
  assert.equal(open.filterInnerDisplay, 'none')
  assert.equal(open.azPointerEvents, 'none')
  assert.equal(open.pagePointerEvents, 'none')
  const closed = universityPaintWhenFilterOpen(false)
  assert.equal(closed.azPointerEvents, 'auto')
  assert.equal(closed.pagePointerEvents, 'auto')

  const app = fs.readFileSync(appVuePath, 'utf8')
  const univ = universitySection()
  assert.match(univ, /:inert="univMenuOpen"/)
  assert.match(univ, /is-inert': univMenuOpen/)
  assert.match(app, /univ-filter-menu-open/)

  const css = fs.readFileSync(cssPath, 'utf8')
  assert.match(css, /\.univ-filter-menu-open \.univ-az/)
  assert.match(css, /\.univ-filter-menu-open \.univ-layout/)
  assert.match(css, /\.univ-filter-menu-open \.mf-label/)
  assert.match(css, /display:\s*none !important/)
  assert.match(css, /\.univ-az\.is-inert[\s\S]{0,80}pointer-events:\s*none/)
})

test('native filter menu teleports fixed overlay + solid panel', () => {
  const vue = fs.readFileSync(menuVuePath, 'utf8')
  assert.match(vue, /Teleport to="body"/)
  assert.match(vue, /mfm-overlay/)
  assert.match(vue, /mfm-panel/)
  assert.match(vue, /z-index:\s*10000/)
  assert.match(vue, /z-index:\s*10001/)
  assert.equal(FILTER_OVERLAY_Z_INDEX, 10000)
  assert.equal(FILTER_MENU_Z_INDEX, 10001)
  assert.ok(FILTER_MENU_Z_INDEX > FILTER_OVERLAY_Z_INDEX)
  const overlayBlock = vue.match(/\.mfm-overlay\s*\{[\s\S]*?\}/)
  const panelBlock = vue.match(/\.mfm-panel\s*\{[\s\S]*?\}/)
  assert.ok(overlayBlock && panelBlock)
  assert.match(overlayBlock[0], /position:\s*fixed/)
  assert.match(overlayBlock[0], /inset:\s*0/)
  assert.match(panelBlock[0], /position:\s*fixed/)
  assert.match(panelBlock[0], /background:\s*#ffffff/i)
  assert.match(panelBlock[0], /opacity:\s*1/)
  assert.doesNotMatch(panelBlock[0], /background:\s*rgba\(/)
  assert.doesNotMatch(panelBlock[0], /backdrop-filter/)
  assert.match(vue, /@click\.prevent\.stop="onOverlayClose"/)
  assert.match(vue, /@touchstart\.prevent\.stop="onOverlayGuard"/)
  assert.match(vue, /@touchend\.prevent\.stop="onOverlayClose"/)
  assert.match(vue, /@click\.stop="select/)
})

test('region / level / major menus keep their own option lists', () => {
  const app = fs.readFileSync(appVuePath, 'utf8')
  assert.match(app, /全部地区/)
  assert.match(app, /全部层级/)
  assert.match(app, /全部领域/)
  assert.match(app, /'C9'/)
  assert.match(app, /'双一流'/)
  assert.match(app, /'985'/)
  assert.match(app, /'211'/)
  const univ = universitySection()
  assert.match(univ, /provinceOptions/)
  assert.match(univ, /tagOptions/)
  assert.match(univ, /univFieldOptions/)
})

test('first university DOM title is #1 清华大学 and recommend keeps Tsinghua first', () => {
  const app = fs.readFileSync(appVuePath, 'utf8')
  assert.match(app, /#\{\{\s*school\.ranking\s*\}\} \{\{\s*school\.name\s*\}\}/)
  assert.match(app, /class="univ-card-head"/)
  assert.match(app, /class="univ-list-spacer"/)
  const list = [
    { id: 1, name: '清华大学', province: '北京', ranking: 1, tags: 'C9', fields: '理工' },
    { id: 2, name: '北京大学', province: '北京', ranking: 2, tags: 'C9', fields: '综合' },
  ]
  const first = browseUniversities(list, { sort: 'recommend' }).items[0]
  assert.equal(first.name, '清华大学')
  assert.equal(first.ranking, 1)
  assert.equal(`#${first.ranking} ${first.name}`, '#1 清华大学')
  const css = fs.readFileSync(cssPath, 'utf8')
  assert.doesNotMatch(css, /清华大学/)
  assert.doesNotMatch(css, /translateY/)
  const listBlock = css.match(/\.univ-list\s*\{[\s\S]*?\}/)
  assert.doesNotMatch(listBlock[0], /margin-top:\s*-/)
})

test('overlay ghost-click guard still swallows the next document click', () => {
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
  const style = panelStyleFromTriggerRect({ left: 20, bottom: 120, width: 80 }, { viewportWidth: 390 })
  assert.equal(style.top, '126px')
  assert.match(style.width, /16\dpx/)
})
