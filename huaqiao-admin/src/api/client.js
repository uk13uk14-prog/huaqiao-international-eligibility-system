const TOKEN_KEY = 'guoqiao_admin_token'

/** API base from env — never hardcode production URL. Empty = same-origin / Vite proxy. */
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

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(url(path), { ...options, headers })
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text }
  }
  if (!res.ok) {
    const detail = data?.detail
    const msg = typeof detail === 'string' ? detail : JSON.stringify(detail || data)
    throw new Error(msg || `HTTP ${res.status}`)
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
