<template>
  <div class="mfm" :class="{ 'is-open': open }">
    <button
      ref="triggerEl"
      type="button"
      class="mfm-trigger"
      :aria-expanded="open ? 'true' : 'false'"
      :aria-label="title || currentLabel"
      aria-haspopup="listbox"
      @click.stop="toggle"
    >
      <span class="mfm-trigger__value">{{ currentLabel }}</span>
      <span class="mfm-trigger__caret" aria-hidden="true">{{ open ? '▲' : '▼' }}</span>
    </button>
    <Teleport to="body">
      <div
        v-if="open"
        class="mfm-overlay"
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
        class="mfm-panel"
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
          :key="String(opt.value)"
          type="button"
          class="mfm-item"
          :class="{ 'is-selected': opt.value === modelValue }"
          role="option"
          :aria-selected="opt.value === modelValue ? 'true' : 'false'"
          @click.stop="select(opt.value)"
        >
          <span>{{ opt.label }}</span>
          <span v-if="opt.value === modelValue" class="mfm-check" aria-hidden="true">✓</span>
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  applyFilterSelection,
  armOverlayGhostClickGuard,
  filterMenuLabel,
  lockPageScroll,
  nextActiveMenu,
  normalizeFilterOptions,
  panelStyleFromTriggerRect,
} from './mobileFilterMenu.js'

const props = defineProps({
  menuId: { type: String, required: true },
  title: { type: String, default: '' },
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },
  activeId: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'update:activeId', 'select', 'close'])

const triggerEl = ref(null)
const panelStyle = ref({ top: '0px', left: '0px', width: '168px' })
let disarmGhost = null
let unlockPageScroll = null

const open = computed(() => props.activeId === props.menuId)
const resolvedOptions = computed(() => normalizeFilterOptions(props.options))
const currentLabel = computed(() => filterMenuLabel(props.modelValue, resolvedOptions.value))

function placePanel() {
  const rect = triggerEl.value?.getBoundingClientRect?.()
  const vw = typeof window !== 'undefined' ? window.innerWidth : 390
  panelStyle.value = panelStyleFromTriggerRect(rect, { viewportWidth: vw })
}

function toggle() {
  emit('update:activeId', nextActiveMenu(props.activeId, props.menuId))
}

function close() {
  if (!open.value) return
  emit('update:activeId', '')
  emit('close')
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
  const result = applyFilterSelection(props.modelValue, value)
  if (result.changed) emit('update:modelValue', result.next)
  emit('select', result.next)
  close()
}

function onViewportChange() {
  if (open.value) placePanel()
}

watch(open, (v) => {
  if (typeof window === 'undefined') return
  if (v) {
    nextTick(() => placePanel())
    unlockPageScroll?.()
    unlockPageScroll = lockPageScroll()
    window.addEventListener('resize', onViewportChange)
    window.addEventListener('scroll', onViewportChange, true)
  } else {
    unlockPageScroll?.()
    unlockPageScroll = null
    window.removeEventListener('resize', onViewportChange)
    window.removeEventListener('scroll', onViewportChange, true)
  }
})

onBeforeUnmount(() => {
  disarmGhost?.()
  unlockPageScroll?.()
  unlockPageScroll = null
  if (typeof window === 'undefined') return
  window.removeEventListener('resize', onViewportChange)
  window.removeEventListener('scroll', onViewportChange, true)
})
</script>

<style>
.mfm { min-width: 0; }
.mfm-trigger {
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
.dark .mfm-trigger,
html.dark .mfm-trigger { color: #e2e8f0; }
.mfm.is-open .mfm-trigger { color: #2563eb; font-weight: 600; }
.mfm-trigger__value { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mfm-trigger__caret { font-size: 10px; color: #64748b; flex: none; }
.mfm.is-open .mfm-trigger__caret { color: #2563eb; }

.mfm-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  background: rgba(0, 0, 0, 0.35);
  pointer-events: auto;
  touch-action: none;
}

.mfm-panel {
  position: fixed;
  z-index: 10001;
  box-sizing: border-box;
  max-height: min(60vh, 420px);
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  background: #ffffff;
  opacity: 1;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18);
  pointer-events: auto;
  touch-action: manipulation;
}
html.dark .mfm-panel {
  background: #0f172a;
  border-color: #475569;
}

.mfm-item {
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
.mfm-item:last-child { border-bottom: 0; }
.mfm-item.is-selected {
  color: #2563eb;
  background: #eff6ff;
  font-weight: 600;
}
.mfm-check { color: #2563eb; font-size: 16px; flex: none; }
html.dark .mfm-item {
  background: #0f172a;
  color: #e2e8f0;
  border-bottom-color: #334155;
}
html.dark .mfm-item.is-selected {
  color: #93c5fd;
  background: #1e3a5f;
}
</style>
