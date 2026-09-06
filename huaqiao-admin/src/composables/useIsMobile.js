import { onMounted, onUnmounted, ref, computed } from 'vue'
import { Capacitor } from '@capacitor/core'

const MQ = '(max-width: 900px)'

export function isMobileViewport() {
  if (typeof window === 'undefined') return false
  if (Capacitor.isNativePlatform()) return true
  return window.matchMedia(MQ).matches
}

/** Shared mobile breakpoint — desktop shell stays intact above 900px. */
export function useIsMobile() {
  const matches = ref(isMobileViewport())
  let mql

  function sync() {
    matches.value = Capacitor.isNativePlatform() || Boolean(mql?.matches)
  }

  onMounted(() => {
    mql = window.matchMedia(MQ)
    sync()
    mql.addEventListener('change', sync)
  })
  onUnmounted(() => {
    mql?.removeEventListener('change', sync)
  })

  return {
    isMobile: computed(() => matches.value),
    isNative: Capacitor.isNativePlatform(),
  }
}
