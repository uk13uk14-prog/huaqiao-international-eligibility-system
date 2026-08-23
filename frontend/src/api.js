const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `请求失败：${response.status}`)
  }
  return response.json()
}

export const api = {
  judgeHuaqiao: (data) => request('/api/eligibility/huaqiao', { method: 'POST', body: JSON.stringify(data) }),
  judgeInternational: (data) => request('/api/eligibility/international', { method: 'POST', body: JSON.stringify(data) }),
  records: (kind = '') => request(`/api/records${kind ? `?kind=${kind}` : ''}`),
  laws: (keyword = '') => request(`/api/laws${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`),
  policies: (keyword = '') => request(`/api/policies${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`),
  universities: (target = '', keyword = '', filters = {}) => {
    const params = new URLSearchParams({ target, keyword, ...filters })
    return request(`/api/universities?${params.toString()}`)
  },
  schedules: (target = '', month = '', filters = {}) => {
    const params = new URLSearchParams({ target, ...(month ? { month } : {}), ...filters })
    return request(`/api/schedules?${params.toString()}`)
  },
  recommendations: (target, intendedField = '', score = '') => request(`/api/recommendations?target=${target}&intended_field=${encodeURIComponent(intendedField)}${score ? `&score=${score}` : ''}`),
  submitConsultation: (data) => request('/api/consultation', { method: 'POST', body: JSON.stringify(data) }),
  telemetrySession(payload) {
    return fetch(`${API_BASE}/api/telemetry/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).catch(() => {})
  },
}
