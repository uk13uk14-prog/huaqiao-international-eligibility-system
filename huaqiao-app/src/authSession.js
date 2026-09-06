/**
 * Student auth helpers — reuse existing /api/auth/* contract only.
 * No second auth backend; no secrets in client.
 */

export function buildRegisterPayload({ name, email, password }) {
  const trimmedName = String(name || '').trim()
  const trimmedEmail = String(email || '').trim().toLowerCase()
  const local = trimmedEmail.split('@')[0] || 'user'
  const tenant_name = (trimmedName || local || '个人用户').slice(0, 64)
  return {
    tenant_name: tenant_name.length >= 2 ? tenant_name : `用户${local}`.slice(0, 64),
    tenant_type: 'personal',
    email: trimmedEmail,
    password: String(password || ''),
    name: trimmedName || local || '用户',
  }
}

export function validateRegisterForm(input = {}) {
  const name = input.name
  const email = input.email
  const password = input.password
  const confirm = input.passwordConfirm ?? input.password_confirm
  if (!String(name || '').trim()) return '请填写姓名'
  if (!String(email || '').trim()) return '请填写邮箱'
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email).trim())) return '邮箱格式不正确'
  if (String(password || '').length < 6) return '密码至少 6 位'
  if (password !== confirm) return '两次输入的密码不一致'
  return ''
}

export function validateLoginForm({ email, password }) {
  if (!String(email || '').trim()) return '请填写邮箱'
  if (!String(password || '')) return '请填写密码'
  return ''
}

/** Map API / network errors to safe user-facing copy (never swallow). */
export function mapAuthError(error) {
  if (!error) return '操作失败，请重试'
  const status = error.status
  if (status === 401) return '邮箱或密码错误'
  if (status === 400) return error.message || '请求无效'
  if (status === 409) return error.message || '邮箱已注册'
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return '无法连接服务器'
  const msg = String(error.message || '')
  if (/Failed to fetch|NetworkError|network|ECONNREFUSED|超时|timeout/i.test(msg)) {
    return '无法连接服务器'
  }
  return msg || '操作失败，请重试'
}

/** Normalize /me + login/register user payloads for UI. */
export function normalizeSaasUser(raw) {
  if (!raw || typeof raw !== 'object') return null
  // Backend contract: trial_active / trial_days_remaining / trial_status
  const trialActive = Boolean(raw.trial_active)
  const trialDays = raw.trial_days_remaining ?? null
  const trialStatus = raw.trial_status ?? null
  return {
    ...raw,
    trial_active: trialActive,
    trial_days_remaining: trialDays,
    trial_status: trialStatus,
    plan_code: raw.plan_code || raw.plan || 'free',
    paid: Boolean(raw.paid),
  }
}
