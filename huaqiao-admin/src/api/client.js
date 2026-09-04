const TOKEN_KEY = 'guoqiao_admin_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(path, { ...options, headers })
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
  aiKinds: (id) => request(`/api/admin/v1/students/${id}/ai/report-kinds`),
  aiDrafts: (id) => request(`/api/admin/v1/students/${id}/ai/drafts`),
  aiGenerate: (id, report_kind) =>
    request(`/api/admin/v1/students/${id}/ai/generate`, {
      method: 'POST',
      body: JSON.stringify({ report_kind }),
    }),
  aiEdit: (id, draftId, content) =>
    request(`/api/admin/v1/students/${id}/ai/drafts/${draftId}`, {
      method: 'PATCH',
      body: JSON.stringify({ content }),
    }),
  aiApprove: (id, draftId) =>
    request(`/api/admin/v1/students/${id}/ai/drafts/${draftId}/approve`, { method: 'POST' }),
  aiPublish: (id, draftId) =>
    request(`/api/admin/v1/students/${id}/ai/drafts/${draftId}/publish`, { method: 'POST' }),
  settings: () => request('/api/admin/v1/settings'),
  consultations: () => request('/api/admin/expert-consultations'),
}
