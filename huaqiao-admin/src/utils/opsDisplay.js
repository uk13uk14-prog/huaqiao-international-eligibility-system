/**
 * Admin ops display helpers — humanize empties / bools / enums.
 * Never surface raw JSON, cipher, tokens, or true/false to operators.
 */

export const EMPTY = {
  pending: '待补充',
  unset: '未设置',
  judge: '待判定',
  official: '待官方公布',
  unassigned: '未分配',
  none: '暂无记录',
  noTargets: '尚未添加目标大学',
  name: '待补姓名',
}

const PLACEHOLDERS = new Set([
  '', '—', '-', 'null', 'NULL', 'None', 'none', 'undefined', 'N/A', 'n/a',
  '未命名学生', '待补姓名',
])

export function isBlank(v) {
  if (v == null) return true
  if (typeof v === 'string' && PLACEHOLDERS.has(v.trim())) return true
  if (Array.isArray(v) && !v.length) return true
  if (typeof v === 'object' && !Array.isArray(v) && !Object.keys(v).length) return true
  return false
}

export function human(v, fallback = EMPTY.pending) {
  if (typeof v === 'boolean') return v ? '是' : '否'
  if (isBlank(v)) return fallback
  if (typeof v === 'number' && Number.isFinite(v)) return String(v)
  const s = String(v).trim()
  if (PLACEHOLDERS.has(s)) return fallback
  if (s === 'true') return '是'
  if (s === 'false') return '否'
  return s
}

export function humanBool(v, fallback = EMPTY.pending) {
  if (v === true || v === 'true' || v === 1 || v === '1' || v === '是' || v === 'yes') return '是'
  if (v === false || v === 'false' || v === 0 || v === '0' || v === '否' || v === 'no') return '否'
  if (isBlank(v)) return fallback
  return human(v, fallback)
}

export function humanDate(v, fallback = EMPTY.pending) {
  if (isBlank(v)) return fallback
  const s = String(v).trim()
  if (s === '待官方公布' || s.toUpperCase() === 'PENDING_OFFICIAL') return EMPTY.official
  if (/^\d{4}-\d{2}-\d{2}T/.test(s)) return s.slice(0, 10)
  return s
}

export function humanDateTime(v, fallback = EMPTY.pending) {
  if (isBlank(v)) return fallback
  const s = String(v).trim()
  if (/^\d{4}-\d{2}-\d{2}T/.test(s)) {
    return s.replace('T', ' ').replace(/\.\d+Z?$/, '').replace(/Z$/, '')
  }
  return s
}

export function pick(...vals) {
  for (const v of vals) {
    if (!isBlank(v)) return v
  }
  return null
}

export const CSCA_STATUS_ZH = {
  NOT_PLANNED: '未计划',
  PLANNED: '计划参加',
  REGISTERED: '已报名',
  TAKEN: '已考试',
  RESULT_AVAILABLE: '已出分',
}

export function cscaStatusLabel(status, fallbackLabel) {
  if (!isBlank(fallbackLabel) && fallbackLabel !== status) return String(fallbackLabel)
  const key = String(status || '').toUpperCase()
  if (!key) return EMPTY.pending
  return CSCA_STATUS_ZH[key] || human(status)
}

export const RISK_ZH = {
  NONE: '无',
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
  CRITICAL: '严重',
}

export function riskLabel(level) {
  const key = String(level || 'NONE').toUpperCase()
  return RISK_ZH[key] || human(level, '无')
}

export function riskTagType(level) {
  const key = String(level || 'NONE').toUpperCase()
  if (key === 'CRITICAL' || key === 'HIGH') return 'danger'
  if (key === 'MEDIUM') return 'warning'
  return 'info'
}

export function eligibilityBadge(conclusion, qualified) {
  const text = String(conclusion || '').trim()
  if (qualified === true) return { label: text || '符合', type: 'success' }
  if (qualified === false) return { label: text || '不符合', type: 'danger' }
  if (!text) return { label: EMPTY.judge, type: 'info' }
  if (/不符合|不合格/.test(text)) return { label: text, type: 'danger' }
  if (/需补|待补|材料|可能|待定/.test(text)) return { label: text, type: 'warning' }
  if (/符合|通过|合格/.test(text)) return { label: text, type: 'success' }
  return { label: text, type: '' }
}

export const FOLLOW_SOURCE_ZH = {
  HUMAN: '人工',
  AI_ASSISTED: 'AI辅助',
  SYSTEM: '系统',
}

export function followSourceLabel(source) {
  const key = String(source || 'HUMAN').toUpperCase()
  return FOLLOW_SOURCE_ZH[key] || human(source, '人工')
}

export function followSourceTag(source) {
  const key = String(source || 'HUMAN').toUpperCase()
  if (key === 'AI_ASSISTED') return 'warning'
  if (key === 'SYSTEM') return 'info'
  return 'success'
}

export const TIMELINE_STATUS_ZH = {
  TODO: '待办',
  PENDING: '待办',
  UPCOMING: '即将到期',
  DUE_SOON: '即将到期',
  OVERDUE: '逾期',
  DONE: '已完成',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
  OPEN: '待办',
}

export function timelineStatusLabel(status) {
  const key = String(status || '').toUpperCase()
  if (!key) return EMPTY.pending
  return TIMELINE_STATUS_ZH[key] || human(status)
}

export function daysRemaining(deadline) {
  if (isBlank(deadline)) return null
  const s = String(deadline).slice(0, 10)
  const d = new Date(`${s}T00:00:00`)
  if (Number.isNaN(d.getTime())) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((d - today) / 86400000)
}

export function daysRemainingLabel(deadline) {
  const n = daysRemaining(deadline)
  if (n == null) return EMPTY.pending
  if (n < 0) return `逾期 ${Math.abs(n)} 天`
  if (n === 0) return '今天'
  return `剩余 ${n} 天`
}

export const TARGET_PRIORITY_ZH = {
  reach: '冲刺',
  REACH: '冲刺',
  match: '稳妥',
  MATCH: '稳妥',
  target: '稳妥',
  TARGET: '稳妥',
  safety: '保底',
  SAFETY: '保底',
  backup: '保底',
  BACKUP: '保底',
}

export function targetPriorityLabel(p) {
  if (isBlank(p)) return EMPTY.pending
  return TARGET_PRIORITY_ZH[p] || TARGET_PRIORITY_ZH[String(p).toUpperCase()] || human(p)
}

export const ROLE_ZH = {
  super_admin: '超级管理员',
  consultant: '顾问',
  support: '客服',
  admin: '超级管理员',
}

export const ROLE_BLURB = {
  super_admin: '可查看全部学生、分配顾问、审核并发布 AI 报告、管理系统设置。',
  consultant: '可查看被分配学生、记录跟进、使用 AI 辅助，并可提交审核。',
  support: '可查看基础资料与用户信息、记录沟通；不可发布专家报告。',
}

export const CAPABILITY_ZH = {
  'admin.login': '登录管理后台',
  'admin.dashboard': '查看工作台',
  'admin.users.read': '查看用户列表',
  'admin.students.read': '查看学生列表',
  'admin.student360.read': '查看学生 360',
  'admin.student360.write': '编辑学生档案 / 跟进',
  'admin.ai.generate': '使用 AI 生成草稿',
  'admin.ai.edit': '编辑 AI 草稿',
  'admin.ai.approve': '审核 AI 报告',
  'admin.ai.publish': '发布专家报告',
  'admin.sensitive.unmask': '查看敏感信息',
  'admin.settings': '管理系统设置',
}

export function roleLabel(role) {
  const key = String(role || '').toLowerCase()
  return ROLE_ZH[key] || human(role, '未分配角色')
}

export function capabilityLabel(cap) {
  return CAPABILITY_ZH[cap] || human(cap)
}
