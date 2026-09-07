<template>
  <div class="sort-menu" :class="{ 'is-open': open }">
    <button
      ref="triggerEl"
      type="button"
      class="sort-menu__trigger"
      :aria-expanded="open ? 'true' : 'false'"
      aria-haspopup="listbox"
      @click.stop="toggle"
    >
      <span class="sort-menu__value">{{ currentLabel }}</span>
      <span class="sort-menu__caret" aria-hidden="true">{{ open ? '▲' : '▼' }}</span>
    </button>
    <Teleport to="body">
      <div
        v-if="open"
        class="sort-menu-overlay"
        aria-hidden="true"
        @pointerdown.prevent.stop="onOverlayGuard"
        @touchstart.prevent.stop="onOverlayGuard"
        @touchmove.prevent.stop
        @pointerup.prevent.stop="onOverlayClose"
        @touchend.prevent.stop="onOverlayClose"
        @click.prevent.stop="onOverlayClose"
      />
      <div
        v-if="open"
        class="sort-menu-panel"
        role="listbox"
        :style="panelStyle"
        @pointerdown.stop
        @pointerup.stop
        @click.stop
        @touchstart.stop
        @touchend.stop
      >
        <button
          v-for="opt in resolvedOptions"
          :key="opt.value"
          type="button"
          class="sort-menu-item"
          :class="{ 'is-selected': opt.value === modelValue }"
          role="option"
          :aria-selected="opt.value === modelValue ? 'true' : 'false'"
          @click.stop="select(opt.value)"
        >
          <span>{{ opt.text }}</span>
          <span v-if="opt.value === modelValue" class="sort-menu-check" aria-hidden="true">✓</span>
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  applySortSelection,
  armOverlayGhostClickGuard,
  panelStyleFromTriggerRect,
  SORT_MENU_OPTIONS,
  sortMenuLabel,
} from './sortMenu.js'

const props = defineProps({
  modelValue: { type: String, default: 'recommend' },
  options: { type: Array, default: () => SORT_MENU_OPTIONS },
})
const emit = defineEmits(['update:modelValue', 'open-change'])

const open = ref(false)
const triggerEl = ref(null)
const panelStyle = ref({ top: '0px', left: '0px', width: '160px' })
let disarmGhost = null

const resolvedOptions = computed(() => {
  const list = Array.isArray(props.options) && props.options.length ? props.options : SORT_MENU_OPTIONS
  return list.map((o) => ({ text: o.text || o.label || o.value, value: o.value }))
})
const currentLabel = computed(() => sortMenuLabel(props.modelValue, resolvedOptions.value))

function placePanel() {
  const el = triggerEl.value
  const rect = el?.getBoundingClientRect?.()
  const vw = typeof window !== 'undefined' ? window.innerWidth : 390
  panelStyle.value = panelStyleFromTriggerRect(rect, { viewportWidth: vw })
}

function setOpen(next) {
  const v = !!next
  if (open.value === v) return
  open.value = v
  if (v) {
    nextTick(() => placePanel())
  }
  emit('open-change', v)
}

function toggle() {
  setOpen(!open.value)
}

function close() {
  setOpen(false)
}

function onOverlayGuard(e) {
  e.preventDefault()
  e.stopPropagation()
}

function onOverlayClose(e) {
  e.preventDefault()
  e.stopPropagation()
  if (e.type === 'touchend' || e.type === 'pointerup') {
    disarmGhost?.()
    disarmGhost = armOverlayGhostClickGuard()
  }
  close()
}

function select(value) {
  const result = applySortSelection(props.modelValue, value)
  if (result.changed) emit('update:modelValue', result.next)
  close()
}

function onViewportChange() {
  if (open.value) placePanel()
}

watch(open, (v) => {
  if (typeof window === 'undefined') return
  if (v) {
    window.addEventListener('resize', onViewportChange)
    window.addEventListener('scroll', onViewportChange, true)
  } else {
    window.removeEventListener('resize', onViewportChange)
    window.removeEventListener('scroll', onViewportChange, true)
  }
})

onBeforeUnmount(() => {
  disarmGhost?.()
  disarmGhost = null
  if (typeof window === 'undefined') return
  window.removeEventListener('resize', onViewportChange)
  window.removeEventListener('scroll', onViewportChange, true)
})
</script>

<style>
.sort-menu { min-width: 0; }
.sort-menu__trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  width: 100%;
  min-height: 28px;
  padding: 0 2px;
  border: 0;
  background: transparent;
  font-size: 13px;
  color: #14213d;
  text-align: left;
}
.dark .sort-menu__trigger,
html.dark .sort-menu__trigger { color: #e2e8f0; }
.sort-menu.is-open .sort-menu__trigger { color: #2563eb; font-weight: 600; }
.sort-menu__value { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sort-menu__caret { font-size: 10px; color: #64748b; flex: none; }
.sort-menu.is-open .sort-menu__caret { color: #2563eb; }

.sort-menu-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(0, 0, 0, 0.25);
  pointer-events: auto;
  touch-action: none;
  opacity: 1;
}

.sort-menu-panel {
  position: fixed;
  z-index: 3001;
  box-sizing: border-box;
  background: #ffffff;
  opacity: 1;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18);
  overflow: hidden;
  pointer-events: auto;
  touch-action: manipulation;
}
html.dark .sort-menu-panel {
  background: #0f172a;
  border-color: #475569;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45);
}

.sort-menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-height: 44px;
  padding: 10px 14px;
  border: 0;
  border-bottom: 1px solid #f1f5f9;
  background: #ffffff;
  color: #14213d;
  font-size: 15px;
  text-align: left;
  opacity: 1;
}
.sort-menu-item:last-child { border-bottom: 0; }
.sort-menu-item.is-selected {
  color: #2563eb;
  background: #eff6ff;
  font-weight: 600;
}
.sort-menu-check { color: #2563eb; font-size: 16px; flex: none; }
html.dark .sort-menu-item {
  background: #0f172a;
  color: #e2e8f0;
  border-bottom-color: #334155;
}
html.dark .sort-menu-item.is-selected {
  color: #93c5fd;
  background: #1e3a5f;
}
</style>
