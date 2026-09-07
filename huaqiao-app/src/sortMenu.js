/**
 * Sort dropdown behaviour helpers (solid menu, no click-through).
 */

export const SORT_MENU_OPTIONS = [
  { text: '推荐', value: 'recommend' },
  { text: 'A-Z', value: 'az' },
]

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

export const UNIV_SORT_LAYER_ID = 'univ-sort-layer'

export function universityChromeWhenMenuOpen(open) {
  return {
    overlay: !!open,
    azPointerEvents: open ? 'none' : 'auto',
    overlayPointerEvents: open ? 'auto' : 'none',
    filterPointerEvents: open ? 'none' : 'auto',
    toolbarSticky: open ? 'relative' : 'sticky',
  }
}

/** Convert viewport rects into coordinates inside a host stacking layer. */
export function relativeTriggerRect(triggerRect, hostRect) {
  if (!triggerRect) return null
  if (!hostRect) return triggerRect
  return {
    left: (triggerRect.left || 0) - (hostRect.left || 0),
    right: (triggerRect.right || 0) - (hostRect.left || 0),
    top: (triggerRect.top || 0) - (hostRect.top || 0),
    bottom: (triggerRect.bottom || 0) - (hostRect.top || 0),
    width: triggerRect.width || 0,
    height: triggerRect.height || 0,
  }
}

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
