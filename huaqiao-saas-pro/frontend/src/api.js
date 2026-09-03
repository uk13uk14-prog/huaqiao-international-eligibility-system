const API_BASE = import.meta.env.VITE_API_BASE || ''
export const TOKEN_STORAGE_KEY = 'saas_token'
let token = localStorage.getItem(TOKEN_STORAGE_KEY) || ''

/** Keep in-memory token aligned with localStorage (refresh / multi-tab / manual set). */
export function syncTokenFromStorage() {
  token = localStorage.getItem(TOKEN_STORAGE_KEY) || ''
  return token
}

export function getToken() {
  return syncTokenFromStorage()
}

export function setToken(value) {
  token = value || ''
  if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token)
  else localStorage.removeItem(TOKEN_STORAGE_KEY)
}

export function clearToken() {
  setToken('')
}

async function request(path, options = {}) {
  const auth = getToken()
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(auth ? { Authorization: `Bearer ${auth}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  })
  if (!response.ok) {
    const text = await response.text()
    try {
      const json = JSON.parse(text)
      const detail = json.detail
      let message = text
      if (detail && typeof detail === 'object' && detail.message) message = detail.message
      else if (typeof detail === 'string') message = detail
      const err = new Error(message)
      err.status = response.status
      err.detail = detail
      err.body = json
      throw err
    } catch (e) {
      if (e instanceof SyntaxError) throw new Error(text || `请求失败：${response.status}`)
      throw e
    }
  }
  if ((response.headers.get('content-type') || '').includes('text/plain')) return response.text()
  return response.json()
}
export const api = {
  register: data => request('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: data => request('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request('/api/me'), plans: () => request('/api/plans'), redeem: code => request('/api/billing/redeem', { method: 'POST', body: JSON.stringify({ code }) }), orders: () => request('/api/billing/orders'), createPayment: data => request('/api/payments/create', { method: 'POST', body: JSON.stringify(data) }), paymentStatus: orderNo => request(`/api/payments/${orderNo}`), mockPay: orderNo => request(`/api/payments/mock/${orderNo}/pay`, { method: 'POST', body: '{}' }), laws: (keyword = '') => request(`/api/laws${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`), policies: (keyword = '') => request(`/api/policies${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`),
  membershipEntitlements: () => request('/api/membership/entitlements'),
  judgeInternational: data => request('/api/eligibility/international', { method: 'POST', body: JSON.stringify(data) }), judgeHuaqiao: data => request('/api/eligibility/huaqiao', { method: 'POST', body: JSON.stringify(data) }),
  records: () => request('/api/records'), recordDetail: id => request(`/api/records/${id}`), exportReport: id => request(`/api/records/${id}/report`, { headers: { Accept: 'text/plain' } }), planning: kind => request(`/api/planning/${kind}`), universities: (target='international', field='', filters = {}) => { const params = new URLSearchParams({ target, field, ...filters }); return request(`/api/universities?${params.toString()}`) }, schedules: (target='international', month='', filters = {}) => { const params = new URLSearchParams({ target, ...(month ? { month } : {}), ...filters }); return request(`/api/schedules?${params.toString()}`) }, recommendations: (target='international', field='综合', score='') => request(`/api/recommendations?target=${target}&field=${encodeURIComponent(field)}${score ? `&score=${score}` : ''}`),
  ask: data => request('/api/assistant/ask', { method: 'POST', body: JSON.stringify(data) }),
  students: () => request('/api/students'),
  createStudent: data => request('/api/students', { method: 'POST', body: JSON.stringify(data || {}) }),
  student: id => request(`/api/students/${id}`),
  patchStudentSection: (id, section, data) => request(`/api/students/${id}/sections/${section}`, { method: 'PATCH', body: JSON.stringify({ data }) }),
  completeStudentWizard: id => request(`/api/students/${id}/complete-wizard`, { method: 'POST', body: '{}' }),
  studentWriteback: (id, data) => request(`/api/students/${id}/eligibility/writeback`, { method: 'POST', body: JSON.stringify(data) }),
  softDeleteStudent: id => request(`/api/students/${id}/soft-delete`, { method: 'POST', body: '{}' }),
  archiveStudent: id => request(`/api/students/${id}/archive`, { method: 'POST', body: '{}' }),
  studentTimeline: id => request(`/api/students/${id}/timeline-matches`),
  studentPortrait: id => request(`/api/students/${id}/portrait`),
  studentTimelineItems: id => request(`/api/students/${id}/timeline`),
  regenerateStudentTimeline: id => request(`/api/students/${id}/timeline/regenerate`, { method: 'POST', body: '{}' }),
  createManualTimeline: (id, data) => request(`/api/students/${id}/timeline/manual`, { method: 'POST', body: JSON.stringify(data) }),
  patchTimelineItem: (id, itemId, data) => request(`/api/students/${id}/timeline/${itemId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  adminUsers: () => request('/api/admin/users'), adminStats: () => request('/api/admin/stats'), adminPlans: () => request('/api/admin/plans'), updatePlan: (code, data) => request(`/api/admin/plans/${code}`, { method: 'PATCH', body: JSON.stringify(data) }), adminCodes: () => request('/api/admin/recharge-codes'), createCodes: data => request('/api/admin/recharge-codes', { method: 'POST', body: JSON.stringify(data) }),
  adminSetStudentProfileLimit: (userId, student_profile_limit_override) => request(`/api/admin/users/${userId}/student-profile-limit`, { method: 'PATCH', body: JSON.stringify({ student_profile_limit_override }) }),
}
