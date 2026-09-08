/**
 * University library native filter menus (no Vant dropdown).
 */

export const FILTER_OVERLAY_Z_INDEX = 10000
export const FILTER_MENU_Z_INDEX = 10001

export const UNIV_FILTER_IDS = ['target', 'sort', 'province', 'tag', 'field']
export const TIMELINE_FILTER_IDS = ['identity', 'month', 'region', 'level', 'feature']

export const IDENTITY_MENU_OPTIONS = [
  { label: '国际生', value: 'international' },
  { label: '华侨生', value: 'huaqiao' },
]

export const SORT_MENU_OPTIONS = [
  { label: '推荐', value: 'recommend' },
  { label: 'A-Z', value: 'az' },
]

export function normalizeFilterOptions(options) {
  return (Array.isArray(options) ? options : []).map((o) => {
    const label = o.label || o.text || String(o.value ?? '')
    return { label, text: o.text || label, value: o.value }
  })
}

export function filterMenuLabel(value, options) {
  const list = normalizeFilterOptions(options)
  const hit = list.find((o) => o.value === value)
  return hit?.label || list[0]?.label || ''
}

export function optionLabels(options) {
  return normalizeFilterOptions(options).map((o) => o.label)
}

export function nextActiveMenu(current, clicked) {
  return current === clicked ? '' : clicked
}

export function applyFilterSelection(current, clicked) {
  return {
    next: clicked,
    changed: clicked !== current,
    close: true,
  }
}

export function universityPaintWhenFilterOpen(open) {
  return {
    listDisplay: open ? 'none' : '',
    azDisplay: open ? 'none' : '',
    filterInnerDisplay: open ? 'none' : '',
    azPointerEvents: open ? 'none' : 'auto',
    pagePointerEvents: open ? 'none' : 'auto',
    onlyOneMenu: true,
    bodyScrollLocked: !!open,
  }
}

export function timelinePaintWhenFilterOpen(open) {
  return {
    listDisplay: open ? 'none' : '',
    filterInnerDisplay: open ? 'none' : '',
    pagePointerEvents: open ? 'none' : 'auto',
    onlyOneMenu: true,
    bodyScrollLocked: !!open,
  }
}

export function lockPageScroll(doc = typeof document !== 'undefined' ? document : null) {
  if (!doc?.body) return () => {}
  const html = doc.documentElement
  const body = doc.body
  const prevHtmlOverflow = html?.style?.overflow
  const prevBodyOverflow = body.style.overflow
  if (html) html.style.overflow = 'hidden'
  body.style.overflow = 'hidden'
  body.classList.add('native-filter-menu-open')
  const onTouchMove = (e) => {
    const t = e.target
    if (t && typeof t.closest === 'function' && t.closest('.mfm-panel')) return
    if (typeof e.preventDefault === 'function') e.preventDefault()
  }
  doc.addEventListener('touchmove', onTouchMove, { capture: true, passive: false })
  return () => {
    if (html) html.style.overflow = prevHtmlOverflow || ''
    body.style.overflow = prevBodyOverflow || ''
    body.classList.remove('native-filter-menu-open')
    doc.removeEventListener('touchmove', onTouchMove, { capture: true })
  }
}

export function panelStyleFromTriggerRect(rect, { gap = 6, minWidth = 168, viewportWidth = 390 } = {}) {
  if (!rect) return { top: '0px', left: '0px', width: `${minWidth}px` }
  const width = Math.max(minWidth, Math.round(rect.width || 0))
  let left = Math.round(rect.left || 0)
  const maxLeft = Math.max(8, Math.round(viewportWidth) - width - 8)
  if (left > maxLeft) left = maxLeft
  if (left < 8) left = 8
  return {
    top: `${Math.round((rect.bottom || 0) + gap)}px`,
    left: `${left}px`,
    width: `${width}px`,
  }
}

export function armOverlayGhostClickGuard(doc = typeof document !== 'undefined' ? document : null, delayMs = 350) {
  if (!doc?.addEventListener) return () => {}
  const swallow = (ev) => {
    ev.preventDefault()
    ev.stopPropagation()
  }
  doc.addEventListener('click', swallow, true)
  doc.addEventListener('touchend', swallow, true)
  const t = setTimeout(() => {
    doc.removeEventListener('click', swallow, true)
    doc.removeEventListener('touchend', swallow, true)
  }, delayMs)
  return () => {
    clearTimeout(t)
    doc.removeEventListener('click', swallow, true)
    doc.removeEventListener('touchend', swallow, true)
  }
}
