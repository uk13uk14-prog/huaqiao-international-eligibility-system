/**
 * Single H5 auth token source.
 * Login, /me restore, SaaS client, and eligibility API must share this key.
 */
export const SAAS_TOKEN_KEY = 'saas_token'

function defaultStorage() {
  try {
    return globalThis.localStorage
  } catch {
    return null
  }
}

export function getSaasToken(storage = defaultStorage()) {
  try {
    return storage?.getItem?.(SAAS_TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setSaasToken(token, storage = defaultStorage()) {
  if (!storage) return
  try {
    if (token) storage.setItem(SAAS_TOKEN_KEY, String(token))
    else storage.removeItem(SAAS_TOKEN_KEY)
  } catch {
    /* private mode / quota */
  }
}

export function clearSaasToken(storage = defaultStorage()) {
  setSaasToken('', storage)
}

/** Headers for authenticated JSON APIs. Empty Authorization when no token. */
export function buildAuthHeaders(extra = {}, storage = defaultStorage()) {
  const token = getSaasToken(storage)
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  }
}

export function parseHttpErrorMessage(status, text) {
  let detail = ''
  const raw = String(text || '')
  try {
    const json = JSON.parse(raw)
    if (json && typeof json.detail === 'string') detail = json.detail
    else if (json?.detail && typeof json.detail.message === 'string') detail = json.detail.message
  } catch {
    /* not JSON */
  }
  if (status === 401) return detail || '请先登录'
  return detail || raw || `请求失败：${status}`
}

export function isExpiredAuthStatus(status) {
  return Number(status) === 401
}
