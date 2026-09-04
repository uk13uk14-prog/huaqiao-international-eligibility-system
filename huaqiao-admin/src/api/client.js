const TOKEN_KEY = 'guoqiao_admin_token'

/** API base from env — production builds must embed https://api.guoqiaoplan.com via .env.production */
const API_BASE = (import.meta.env.VITE_ADMIN_API_BASE || '').replace(/\/$/, '')

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

function url(path) {
  if (!API_BASE) return path
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'unknown' } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(url(path), { ...options, headers })
  } catch (e) {
    throw new ApiError('无法连接服务器，请稍后重试', {
      status: 0,
      code: 'network',
      cause: e,
    })
  }

  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text }
  }

  if (!res.ok) {
    const detail = data?.detail
    const detailStr = typeof detail === 'string' ? detail : null
    if (res.status === 401) {
      throw new ApiError('邮箱或密码错误', { status: 401, code: 'unauthorized' })
    }
    if (res.status === 403) {
      throw new ApiError('当前账号无权进入运营后台', { status: 403, code: 'forbidden' })
    }
    const msg =
      detailStr ||
      (typeof detail === 'object' && detail ? `请求失败（HTTP ${res.status}）` : null) ||
      `请求失败（HTTP ${res.status}）`
    throw new ApiError(msg, { status: res.status, code: 'http' })
  }
  return data
}

export const api = {
  apiBase: API_BASE || '(same-origin / vite proxy)',
  login: (email, password) =>
    request('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => request('/api/admin/v1/me'),
  dashboard: () => request('/api/admin/v1/dashboard'),
  users: (q) => request(`/api/admin/v1/users${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  user: (id) => request(`/api/admin/v1/users/${id}`),
  students: (q) => request(`/api/admin/v1/students${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  student360: (id) => request(`/api/admin/v1/students/${id}`),
  studentTimeline: (id) => request(`/api/admin/v1/students/${id}/timeline`),
  studentEligibility: (id) => request(`/api/admin/v1/students/${id}/eligibility`),
  studentConsultations: (id) => request(`/api/admin/v1/students/${id}/consultations`),
  aiDrafts: (id) => request(`/api/admin/v1/students/${id}/ai-drafts`),
  aiGenerate: (id, report_kind, submit_review = false) =>
    request(`/api/admin/v1/students/${id}/ai-drafts`, {
      method: 'POST',
      body: JSON.stringify({ report_kind, submit_review }),
    }),
  aiEdit: (id, draftId, content, submit_review = true) =>
    request(`/api/admin/v1/students/${id}/ai-drafts/${draftId}`, {
      method: 'PATCH',
      body: JSON.stringify({ content, submit_review }),
    }),
  aiApprove: (id, draftId) =>
    request(`/api/admin/v1/students/${id}/ai-drafts/${draftId}/approve`, { method: 'POST' }),
  aiPublish: (id, draftId) =>
    request(`/api/admin/v1/students/${id}/ai-drafts/${draftId}/publish`, { method: 'POST' }),
  settings: () => request('/api/admin/v1/settings'),
  consultations: () => request('/api/admin/expert-consultations'),
}
