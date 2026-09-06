import test from 'node:test'
import assert from 'node:assert/strict'
import {
  PROFILE_WRITE,
  canCapability,
  isSuperAdmin,
  permissionsFor,
  resolveConsoleRole,
} from '../src/utils/adminCapabilities.js'
import { human, identityPairLabel, planCodeLabel } from '../src/utils/opsDisplay.js'

const legacyAdminMe = {
  console_role: 'super_admin',
  user: { email: 'admin@example.com', role: 'admin' },
  permissions: [],
}

const stalePermsMe = {
  console_role: 'super_admin',
  user: { email: 'admin@example.com', role: 'admin' },
  permissions: ['dashboard.read', 'student360.write'],
}

const roleOnlyMe = {
  user: { email: 'admin@example.com', role: 'admin' },
  permissions: [],
}

test('LEGACY_ADMIN_MAPS_SUPER_ADMIN', () => {
  assert.equal(resolveConsoleRole(legacyAdminMe), 'super_admin')
  assert.equal(resolveConsoleRole(roleOnlyMe), 'super_admin')
  assert.equal(isSuperAdmin(legacyAdminMe), true)
})

test('SUPER_ADMIN_PROFILE_WRITE_CAPABILITY', () => {
  assert.equal(canCapability(legacyAdminMe, PROFILE_WRITE), true)
  assert.equal(canCapability(stalePermsMe, PROFILE_WRITE), true)
  assert.equal(canCapability(roleOnlyMe, PROFILE_WRITE), true)
  assert.equal(permissionsFor(legacyAdminMe).includes(PROFILE_WRITE), true)
})

test('SUPER_ADMIN_EDIT_BUTTONS', () => {
  assert.equal(canCapability(legacyAdminMe, PROFILE_WRITE), true, 'SUPER_ADMIN_EDIT_NAME_BUTTON')
  assert.equal(canCapability(stalePermsMe, PROFILE_WRITE), true, 'SUPER_ADMIN_EDIT_BASIC_BUTTON')
  assert.equal(canCapability(legacyAdminMe, PROFILE_WRITE), true, 'SUPER_ADMIN_SAVE_BASIC_BUTTON')
})

test('OTHER_ROLES_HIDDEN', () => {
  for (const role of ['operations_admin', 'consultant', 'support']) {
    const me = { console_role: role, user: { role }, permissions: ['student360.write', PROFILE_WRITE] }
    assert.equal(resolveConsoleRole(me), role)
    assert.equal(canCapability(me, PROFILE_WRITE), false, `${role} must not see profile edit`)
    assert.equal(permissionsFor(me).includes(PROFILE_WRITE), false)
  }
})

test('NOT_ASSESSED_HUMANIZED', () => {
  assert.equal(human('NOT_ASSESSED'), '待评估')
  assert.equal(identityPairLabel('NOT_ASSESSED', 'NOT_ASSESSED'), '国际生：待评估 · 华侨生：待评估')
  assert.equal(human('国际生:NOT_ASSESSED'), '国际生：待评估')
})

test('PRO_TRIAL_HUMANIZED', () => {
  assert.equal(planCodeLabel('pro_trial'), '7天 Pro 体验')
  assert.equal(human('pro_trial'), '7天 Pro 体验')
})
