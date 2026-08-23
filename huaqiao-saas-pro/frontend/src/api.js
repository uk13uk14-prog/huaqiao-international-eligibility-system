const API_BASE = import.meta.env.VITE_API_BASE || ''
let token = localStorage.getItem('saas_token') || ''
export function setToken(value) { token = value; localStorage.setItem('saas_token', value) }
async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options.headers || {}) }, ...options })
  if (!response.ok) throw new Error(await response.text())
  if ((response.headers.get('content-type') || '').includes('text/plain')) return response.text()
  return response.json()
}
export const api = {
  register: data => request('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: data => request('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request('/api/me'), plans: () => request('/api/plans'), redeem: code => request('/api/billing/redeem', { method: 'POST', body: JSON.stringify({ code }) }), orders: () => request('/api/billing/orders'), createPayment: data => request('/api/payments/create', { method: 'POST', body: JSON.stringify(data) }), paymentStatus: orderNo => request(`/api/payments/${orderNo}`), mockPay: orderNo => request(`/api/payments/mock/${orderNo}/pay`, { method: 'POST', body: '{}' }), laws: (keyword = '') => request(`/api/laws${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`), policies: (keyword = '') => request(`/api/policies${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`),
  judgeInternational: data => request('/api/eligibility/international', { method: 'POST', body: JSON.stringify(data) }), judgeHuaqiao: data => request('/api/eligibility/huaqiao', { method: 'POST', body: JSON.stringify(data) }),
  records: () => request('/api/records'), recordDetail: id => request(`/api/records/${id}`), exportReport: id => request(`/api/records/${id}/report`, { headers: { Accept: 'text/plain' } }), planning: kind => request(`/api/planning/${kind}`), universities: (target='international', field='', filters = {}) => { const params = new URLSearchParams({ target, field, ...filters }); return request(`/api/universities?${params.toString()}`) }, schedules: (target='international', month='', filters = {}) => { const params = new URLSearchParams({ target, ...(month ? { month } : {}), ...filters }); return request(`/api/schedules?${params.toString()}`) }, recommendations: (target='international', field='综合', score='') => request(`/api/recommendations?target=${target}&field=${encodeURIComponent(field)}${score ? `&score=${score}` : ''}`),
  ask: data => request('/api/assistant/ask', { method: 'POST', body: JSON.stringify(data) }),
  adminUsers: () => request('/api/admin/users'), adminStats: () => request('/api/admin/stats'), adminPlans: () => request('/api/admin/plans'), updatePlan: (code, data) => request(`/api/admin/plans/${code}`, { method: 'PATCH', body: JSON.stringify(data) }), adminCodes: () => request('/api/admin/recharge-codes'), createCodes: data => request('/api/admin/recharge-codes', { method: 'POST', body: JSON.stringify(data) })
}
