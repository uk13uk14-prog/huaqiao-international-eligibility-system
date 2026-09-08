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
  TIMELINE_FILTER_IDS,
  applyFilterSelection,
  armOverlayGhostClickGuard,
  filterMenuLabel,
  lockPageScroll,
  nextActiveMenu,
  optionLabels,
  panelStyleFromTriggerRect,
  timelinePaintWhenFilterOpen,
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

function scheduleSection() {
  const app = fs.readFileSync(appVuePath, 'utf8')
  return app.split("tab === 'schedule'")[1]?.split("tab === 'history'")[0] || ''
}

function expectedMonthOptions() {
  return [{ text: '全部月份', value: '' }, ...Array.from({ length: 12 }, (_, i) => ({ text: `${i + 1}月`, value: i + 1 }))]
}

function quotedList(src, constName) {
  const m = src.match(new RegExp(`const ${constName} = \\[([^\\]]+)\\]`))
  if (!m) return []
  return [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1])
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
  assert.match(panelBlock[0], /overflow-y:\s*auto/)
  assert.match(panelBlock[0], /-webkit-overflow-scrolling:\s*touch/)
  assert.match(vue, /lockPageScroll/)
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

test('timeline identity options are only 国际生 / 华侨生', () => {
  const labels = optionLabels(IDENTITY_MENU_OPTIONS)
  assert.deepEqual(labels, ['国际生', '华侨生'])
  const sched = scheduleSection()
  assert.match(sched, /menu-id="identity"/)
  assert.match(sched, /:options="targetOptions"/)
  assert.doesNotMatch(sched, /全部月份/)
  assert.ok(!labels.includes('全部地区'))
  assert.ok(!labels.includes('全部层级'))
  assert.ok(!labels.includes('全部特色'))
})

test('timeline month options are 全部月份 + 1-12月 only', () => {
  const expected = expectedMonthOptions()
  assert.deepEqual(optionLabels(expected), ['全部月份', '1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'])
  const app = fs.readFileSync(appVuePath, 'utf8')
  assert.match(app, /\{ text: '全部月份', value: '' \}/)
  assert.match(app, /length: 12/)
  assert.match(app, /\$\{i \+ 1\}月/)
  const sched = scheduleSection()
  assert.match(sched, /menu-id="month"/)
  assert.match(sched, /:options="monthOptions"/)
  const monthBlock = sched.split('menu-id="month"')[1]?.split('menu-id="region"')[0] || ''
  assert.doesNotMatch(monthBlock, /全部地区/)
  assert.doesNotMatch(monthBlock, /全部层级/)
  assert.doesNotMatch(monthBlock, /全部特色/)
  assert.doesNotMatch(monthBlock, /国际生/)
})

test('timeline region / level / feature options stay isolated', () => {
  const app = fs.readFileSync(appVuePath, 'utf8')
  const regions = quotedList(app, 'provinceOptions')
  const levels = quotedList(app, 'tagOptions')
  const features = quotedList(app, 'featureOptions')
  assert.equal(regions[0], '全部地区')
  assert.ok(regions.includes('北京'))
  assert.ok(!regions.includes('全部月份'))
  assert.ok(!regions.includes('全部层级'))
  assert.ok(!regions.includes('全部特色'))
  assert.deepEqual(levels, ['全部层级', 'C9', '双一流', '985', '211'])
  assert.ok(!levels.includes('全部月份'))
  assert.ok(!levels.includes('全部地区'))
  assert.deepEqual(features, ['全部特色', '体育', '音乐', '艺术', '师范'])
  assert.ok(!features.includes('全部月份'))
  const sched = scheduleSection()
  assert.match(sched, /menu-id="region"/)
  assert.match(sched, /:options="provinceOptions"/)
  assert.match(sched, /menu-id="level"/)
  assert.match(sched, /:options="tagOptions"/)
  assert.match(sched, /menu-id="feature"/)
  assert.match(sched, /:options="featureOptions"/)
})

test('timeline uses a single activeMenu and blocks click-through', () => {
  assert.deepEqual(TIMELINE_FILTER_IDS, ['identity', 'month', 'region', 'level', 'feature'])
  assert.equal(nextActiveMenu('', 'month'), 'month')
  assert.equal(nextActiveMenu('month', 'region'), 'region')
  assert.equal(nextActiveMenu('month', 'month'), '')
  const open = timelinePaintWhenFilterOpen(true)
  assert.equal(open.onlyOneMenu, true)
  assert.equal(open.listDisplay, 'none')
  assert.equal(open.filterInnerDisplay, 'none')
  assert.equal(open.pagePointerEvents, 'none')
  assert.equal(open.bodyScrollLocked, true)
  const app = fs.readFileSync(appVuePath, 'utf8')
  assert.match(app, /const timelineActiveMenu = ref\(''\)/)
  const sched = scheduleSection()
  assert.doesNotMatch(sched, /van-dropdown-menu/)
  assert.doesNotMatch(sched, /van-dropdown-item/)
  const css = fs.readFileSync(cssPath, 'utf8')
  assert.match(css, /\.schedule-filter-menu-open \.card-list/)
  assert.match(css, /\.schedule-filter-menu-open \.mf-label/)
  assert.match(css, /body\.native-filter-menu-open \.mf-label/)
  assert.match(css, /display:\s*none !important/)
})

test('timeline month menu source does not render other filter labels', () => {
  const sched = scheduleSection()
  const month = sched.split('menu-id="month"')[1]?.split('menu-id="region"')[0] || ''
  assert.match(month, /monthOptions/)
  assert.doesNotMatch(month, /provinceOptions/)
  assert.doesNotMatch(month, /tagOptions/)
  assert.doesNotMatch(month, /featureOptions/)
  assert.doesNotMatch(month, /targetOptions/)
})

test('page scroll lock allows panel touchmove and blocks the rest', () => {
  const calls = []
  const classList = new Set()
  const listeners = []
  const html = { style: { overflow: '' } }
  const body = {
    style: { overflow: '' },
    classList: {
      add: (c) => classList.add(c),
      remove: (c) => classList.delete(c),
    },
  }
  const doc = {
    documentElement: html,
    body,
    addEventListener(type, fn, opts) { listeners.push({ type, fn, opts }) },
    removeEventListener(type, fn) { const i = listeners.findIndex((x) => x.type === type && x.fn === fn); if (i >= 0) listeners.splice(i, 1) },
  }
  const unlock = lockPageScroll(doc)
  assert.equal(html.style.overflow, 'hidden')
  assert.equal(body.style.overflow, 'hidden')
  assert.ok(classList.has('native-filter-menu-open'))
  const touch = listeners.find((x) => x.type === 'touchmove')
  assert.ok(touch)
  touch.fn({
    target: { closest: () => null },
    preventDefault() { calls.push('prevent') },
  })
  assert.deepEqual(calls, ['prevent'])
  touch.fn({
    target: { closest: (sel) => (sel === '.mfm-panel' ? {} : null) },
    preventDefault() { calls.push('panel') },
  })
  assert.ok(!calls.includes('panel'))
  unlock()
  assert.equal(listeners.length, 0)
  assert.ok(!classList.has('native-filter-menu-open'))
})
