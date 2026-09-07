/**
 * Sort dropdown behaviour helpers (solid menu, no click-through).
 * Overlay + panel teleport to document.body so they escape university
 * toolbar / univ-screen stacking contexts (isolation, overflow, sticky).
 */

export const SORT_MENU_OPTIONS = [
  { text: '推荐', value: 'recommend' },
  { text: 'A-Z', value: 'az' },
]

/** Overlay above page + Vant dropdowns (~2000); menu above overlay. */
export const SORT_OVERLAY_Z_INDEX = 3000
export const SORT_MENU_Z_INDEX = 3001

export function sortMenuLabel(value, options = SORT_MENU_OPTIONS) {
  const hit = (options || []).find((o) => o.value === value)
  return hit?.text || options[0]?.text || '推荐'
}

/**
 * Clicking the current option closes without a redundant state change.
 */
export function applySortSelection(current, clicked) {
  return {
    next: clicked,
    changed: clicked !== current,
    close: true,
  }
}

export function universityChromeWhenMenuOpen(open) {
  return {
    overlay: !!open,
    azPointerEvents: open ? 'none' : 'auto',
    overlayPointerEvents: open ? 'auto' : 'none',
    filterPointerEvents: open ? 'none' : 'auto',
    toolbarSticky: 'relative',
  }
}

/**
 * iOS synthesizes a click on whatever sits under a just-removed overlay.
 * Swallow the following click/touchend in capture for one gesture.
 */
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

/** Viewport (fixed) coordinates — do not subtract a local host rect. */
export function panelStyleFromTriggerRect(rect, { gap = 4, minWidth = 160, viewportWidth = 390 } = {}) {
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
