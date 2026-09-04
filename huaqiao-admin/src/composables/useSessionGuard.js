import { Capacitor } from '@capacitor/core'
import { App as CapApp } from '@capacitor/app'
import { api, ApiError, clearToken, getToken } from '../api/client'
import router from '../router'

/**
 * Re-validate /api/admin/v1/me on native resume / tab visible.
 * 401/403 → clear JWT and force login. Never stores server secrets.
 */
export async function validateAdminSession() {
  if (!getToken()) return false
  try {
    const me = await api.me()
    if (!me?.console_role) {
      clearToken()
      return false
    }
    return true
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearToken()
      return false
    }
    return true
  }
}

export function installSessionGuard() {
  async function ensureOrLogin() {
    if (!getToken()) return
    const ok = await validateAdminSession()
    if (!ok && router.currentRoute.value.path !== '/login') {
      await router.replace('/login')
    }
  }

  if (Capacitor.isNativePlatform()) {
    CapApp.addListener('appStateChange', ({ isActive }) => {
      if (isActive) ensureOrLogin()
    })
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && getToken()) ensureOrLogin()
  })
}
