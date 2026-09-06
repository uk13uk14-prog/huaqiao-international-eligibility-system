/** Frontend Admin Console V2 capability mapping.

Mirrors backend admin_rbac without replacing it. UI visibility must work even when
/me.permissions is stale or omits a newly added SUPER_ADMIN-only cap.
Legacy DB role `admin` === SUPER_ADMIN.
*/

export const PROFILE_WRITE = 'student360.profile.write'

const SUPER_ADMIN_ROLES = new Set(['admin', 'super_admin'])

const SUPER_ADMIN_CAPS = Object.freeze([
  'admin.login',
  'dashboard.read',
  'users.read',
  'users.write',
  'students.read',
  'students.write',
  'students.assign',
  'student360.read',
  'student360.write',
  PROFILE_WRITE,
  'followups.read',
  'followups.write',
  'consultations.read',
  'consultations.write',
  'employees.read',
  'employees.write',
  'consultants.read',
  'consultants.write',
  'roles.read',
  'roles.write',
  'ai.generate',
  'ai.review',
  'ai.publish',
  'audit.read',
  'settings.read',
  'settings.write',
])

const OPERATIONS_ADMIN_CAPS = Object.freeze(
  SUPER_ADMIN_CAPS.filter(
    (c) => !['employees.write', 'roles.write', 'settings.write', PROFILE_WRITE].includes(c),
  ),
)

const CONSULTANT_CAPS = Object.freeze([
  'admin.login',
  'dashboard.read',
  'students.read',
  'students.write',
  'student360.read',
  'student360.write',
  'followups.read',
  'followups.write',
  'consultations.read',
  'consultations.write',
  'consultants.read',
  'ai.generate',
])

const SUPPORT_CAPS = Object.freeze([
  'admin.login',
  'dashboard.read',
  'users.read',
  'students.read',
  'student360.read',
  'followups.read',
  'followups.write',
  'consultations.read',
  'consultations.write',
])

export const ROLE_CAPABILITIES = Object.freeze({
  super_admin: SUPER_ADMIN_CAPS,
  operations_admin: OPERATIONS_ADMIN_CAPS,
  consultant: CONSULTANT_CAPS,
  support: SUPPORT_CAPS,
})

export function resolveConsoleRole(me) {
  if (!me) return ''
  const candidates = [me.console_role, me.role, me.user?.role, me.user?.console_role]
  for (const raw of candidates) {
    const key = String(raw || '').trim().toLowerCase()
    if (SUPER_ADMIN_ROLES.has(key)) return 'super_admin'
    if (key === 'operations_admin' || key === 'consultant' || key === 'support') return key
  }
  return ''
}

export function isSuperAdmin(me) {
  return resolveConsoleRole(me) === 'super_admin'
}

function apiPermissions(me) {
  const raw = me?.permissions
  if (Array.isArray(raw)) return raw.map((x) => String(x || '').trim()).filter(Boolean)
  return []
}

export function permissionsFor(me) {
  const role = resolveConsoleRole(me)
  const fromRole = ROLE_CAPABILITIES[role] || []
  const set = new Set([...fromRole, ...apiPermissions(me)])
  if (role !== 'super_admin') set.delete(PROFILE_WRITE)
  else set.add(PROFILE_WRITE)
  return [...set]
}

export function canCapability(me, cap) {
  const need = String(cap || '').trim()
  if (!need) return false
  if (need === PROFILE_WRITE) return isSuperAdmin(me)
  return permissionsFor(me).includes(need)
}
