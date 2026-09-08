import { buildAuthHeaders, getSaasToken, parseHttpErrorMessage } from './authToken.js'

const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const { headers: extraHeaders, ...rest } = options
  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: buildAuthHeaders(extraHeaders || {}),
  })
  if (!response.ok) {
    const text = await response.text()
    const err = new Error(parseHttpErrorMessage(response.status, text))
    err.status = response.status
    throw err
  }
  return response.json()
}

export { getSaasToken, buildAuthHeaders, parseHttpErrorMessage }

export const api = {
  judgeHuaqiao: (data) => request('/api/eligibility/huaqiao', { method: 'POST', body: JSON.stringify(data) }),
  judgeInternational: (data) => request('/api/eligibility/international', { method: 'POST', body: JSON.stringify(data) }),
  records: (kind = '') => request(`/api/records${kind ? `?kind=${kind}` : ''}`),
  laws: (keyword = '') => request(`/api/laws${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`),
  policies: (keyword = '') => request(`/api/policies${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`),
  universities: (target = 'international', field = '', filters = {}) => {
    const params = new URLSearchParams({ target, field, ...filters })
    return request(`/api/universities?${params.toString()}`)
  },
  schedules: (target = 'international', month = '', filters = {}) => {
    const params = new URLSearchParams({ target, ...(month ? { month } : {}), ...filters })
    return request(`/api/schedules?${params.toString()}`)
  },
  recommendations: (target, intendedField = '', score = '') => request(`/api/recommendations?target=${target}&intended_field=${encodeURIComponent(intendedField)}${score ? `&score=${score}` : ''}`),
  /** 客户端打开时上报，失败静默忽略 */
  telemetrySession(payload) {
    return fetch(`${API_BASE}/api/telemetry/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).catch(() => {})
  },
  submitConsultation: (data) => request('/api/consultation', { method: 'POST', body: JSON.stringify(data) }),
  cooperation: () => request('/api/cooperation'),
}
