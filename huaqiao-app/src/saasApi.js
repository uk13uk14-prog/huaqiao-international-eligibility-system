const SAAS_BASE = (import.meta.env.VITE_SAAS_API || '/saas-api').replace(/\/$/, '')

function url(path) {
  if (!path.startsWith('/')) path = '/' + path
  return `${SAAS_BASE}${path}`
}

function authHeaders(extra = {}) {
  const t = localStorage.getItem('saas_token') || ''
  return {
    'Content-Type': 'application/json',
    ...(t ? { Authorization: `Bearer ${t}` } : {}),
    ...extra,
  }
}

async function saasRequest(path, options = {}) {
  const response = await fetch(url(path), { ...options, headers: { ...authHeaders(), ...(options.headers || {}) } })
  if (!response.ok) {
    const text = await response.text()
    try {
      const json = JSON.parse(text)
      const detail = json.detail
      let message = text
      if (detail && typeof detail === 'object' && detail.message) message = detail.message
      else if (typeof detail === 'string') message = detail
      const err = new Error(message || `SaaS请求失败：${response.status}`)
      err.status = response.status
      err.detail = detail
      throw err
    } catch (e) {
      if (e instanceof SyntaxError) {
        const err = new Error(text || `SaaS请求失败：${response.status}`)
        err.status = response.status
        throw err
      }
      throw e
    }
  }
  const ct = response.headers.get('content-type') || ''
  if (ct.includes('application/json')) return response.json()
  return response.text()
}

export function setSaasToken(token) {
  if (token) localStorage.setItem('saas_token', token)
  else localStorage.removeItem('saas_token')
}

export function getSaasToken() {
  return localStorage.getItem('saas_token') || ''
}

export const saasApi = {
  login: (email, password) =>
    saasRequest('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  register: (data) => saasRequest('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  me: () => saasRequest('/api/me'),

  plans: () => saasRequest('/api/plans'),

  createPayment: (plan_code, channel = 'mock') =>
    saasRequest('/api/payments/create', { method: 'POST', body: JSON.stringify({ plan_code, channel }) }),

  mockPay: (order_no) => saasRequest(`/api/payments/mock/${encodeURIComponent(order_no)}/pay`, { method: 'POST', body: '{}' }),

  redeem: (code) => saasRequest('/api/billing/redeem', { method: 'POST', body: JSON.stringify({ code }) }),

  universities: (target = 'international', field = '', filters = {}) => {
    const params = new URLSearchParams({ target, field, ...filters })
    return saasRequest(`/api/universities?${params.toString()}`)
  },

  schedules: (target = 'international', month = '', filters = {}) => {
    const params = new URLSearchParams({ target, ...(month ? { month: String(month) } : {}), ...filters })
    return saasRequest(`/api/schedules?${params.toString()}`)
  },

  vaultGet: () => saasRequest('/api/vault/profile'),

  vaultPut: (profile) => saasRequest('/api/vault/profile', { method: 'PUT', body: JSON.stringify({ profile }) }),

  students: () => saasRequest('/api/students'),
  createStudent: (data) => saasRequest('/api/students', { method: 'POST', body: JSON.stringify(data || {}) }),
  student: (id) => saasRequest(`/api/students/${id}`),
  patchStudentSection: (id, section, data) =>
    saasRequest(`/api/students/${id}/sections/${section}`, { method: 'PATCH', body: JSON.stringify({ data }) }),
  completeStudentWizard: (id) => saasRequest(`/api/students/${id}/complete-wizard`, { method: 'POST', body: '{}' }),
  studentWriteback: (id, data) =>
    saasRequest(`/api/students/${id}/eligibility/writeback`, { method: 'POST', body: JSON.stringify(data) }),
  softDeleteStudent: (id) => saasRequest(`/api/students/${id}/soft-delete`, { method: 'POST', body: '{}' }),
  membershipEntitlements: () => saasRequest('/api/membership/entitlements'),
  studentTimeline: (id) => saasRequest(`/api/students/${id}/timeline-matches`),
  studentPortrait: (id) => saasRequest(`/api/students/${id}/portrait`),
  studentTimelineItems: (id) => saasRequest(`/api/students/${id}/timeline`),
  regenerateStudentTimeline: (id) => saasRequest(`/api/students/${id}/timeline/regenerate`, { method: 'POST', body: '{}' }),
  createManualTimeline: (id, data) => saasRequest(`/api/students/${id}/timeline/manual`, { method: 'POST', body: JSON.stringify(data) }),
  patchTimelineItem: (id, itemId, data) =>
    saasRequest(`/api/students/${id}/timeline/${itemId}`, { method: 'PATCH', body: JSON.stringify(data) }),

  expertCreate: (data) => saasRequest('/api/expert/consultations', { method: 'POST', body: JSON.stringify(data) }),

  expertList: () => saasRequest('/api/expert/consultations'),

  expertDetail: (id) => saasRequest(`/api/expert/consultations/${id}`),

  publishedConsultations: (studentId) =>
    saasRequest(`/api/students/${studentId}/published-consultations`),

  reminders: () => saasRequest('/api/member/reminders'),

  notifications: (params = {}) => {
    const q = new URLSearchParams()
    if (params.unread_only) q.set('unread_only', '1')
    if (params.category) q.set('category', params.category)
    const qs = q.toString()
    return saasRequest(`/api/notifications${qs ? `?${qs}` : ''}`)
  },
  notificationUnreadCount: () => saasRequest('/api/notifications/unread-count'),
  notificationPopups: () => saasRequest('/api/notifications/popups'),
  notificationRead: (id) => saasRequest(`/api/notifications/${id}/read`, { method: 'POST', body: '{}' }),
  notificationPopupShown: (id) =>
    saasRequest(`/api/notifications/${id}/popup-shown`, { method: 'POST', body: '{}' }),
  notificationPrefs: () => saasRequest('/api/notifications/preferences'),
  updateNotificationPrefs: (data) =>
    saasRequest('/api/notifications/preferences', { method: 'PUT', body: JSON.stringify(data) }),

  askAssistant: (question, context = '', mode = 'qa') =>
    saasRequest('/api/assistant/ask', { method: 'POST', body: JSON.stringify({ question, context, mode }) }),
}
