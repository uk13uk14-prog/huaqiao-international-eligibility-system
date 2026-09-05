import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildRegisterPayload,
  mapAuthError,
  normalizeSaasUser,
  validateLoginForm,
  validateRegisterForm,
} from '../src/authSession.js'
import {
  SORT_OPTIONS,
  browseUniversities,
  matchesUniversityQuery,
  pinyinInitial,
  sortUniversities,
} from '../src/universityBrowse.js'

test('buildRegisterPayload hides tenant fields from end users', () => {
  const p = buildRegisterPayload({ name: '张三', email: 'zhang@example.com', password: 'secret1' })
  assert.equal(p.tenant_type, 'personal')
  assert.equal(p.tenant_name, '张三')
  assert.equal(p.email, 'zhang@example.com')
  assert.equal(p.name, '张三')
  assert.equal(p.password, 'secret1')
})

test('validateRegisterForm catches mismatch and short password', () => {
  assert.match(validateRegisterForm({ name: 'A', email: 'a@b.com', password: '123', passwordConfirm: '123' }), /6/)
  assert.match(
    validateRegisterForm({ name: 'A', email: 'a@b.com', password: '123456', passwordConfirm: 'x' }),
    /不一致/,
  )
  assert.equal(
    validateRegisterForm({ name: 'A', email: 'a@b.com', password: '123456', passwordConfirm: '123456' }),
    '',
  )
})

test('validateLoginForm and mapAuthError cover 401/network', () => {
  assert.match(validateLoginForm({ email: '', password: 'x' }), /邮箱/)
  assert.equal(mapAuthError({ status: 401, message: 'nope' }), '邮箱或密码错误')
  assert.equal(mapAuthError({ message: 'Failed to fetch' }), '无法连接服务器')
})

test('normalizeSaasUser maps trial_active backend fields', () => {
  const u = normalizeSaasUser({
    email: 't@example.com',
    plan_code: 'pro_trial',
    trial_active: true,
    trial_days_remaining: 7,
    trial_status: 'ACTIVE',
    paid: true,
  })
  assert.equal(u.trial_active, true)
  assert.equal(u.trial_days_remaining, 7)
  assert.equal(u.plan_code, 'pro_trial')
  assert.equal(u.paid, true)
})

test('university browse search / az sort / letters', () => {
  const list = [
    { id: 1, name: '清华大学', province: '北京', ranking: 1, tags: 'C9', fields: '理工', advantage_majors: '计算机' },
    { id: 2, name: '北京大学', province: '北京', ranking: 2, tags: 'C9', fields: '综合', advantage_majors: '文科' },
    { id: 3, name: '中山大学', province: '广东', ranking: 10, tags: '985', fields: '综合', advantage_majors: '医学' },
  ]
  assert.equal(matchesUniversityQuery(list[0], '清华'), true)
  assert.equal(matchesUniversityQuery(list[0], '深圳'), false)
  assert.equal(pinyinInitial('清华大学'), 'Q')
  assert.equal(pinyinInitial('北京大学'), 'B')
  const az = sortUniversities(list, 'az').map((s) => s.name)
  assert.deepEqual(az, ['北京大学', '清华大学', '中山大学'])
  const browsed = browseUniversities(list, { query: '北京', sort: 'recommend' })
  assert.equal(browsed.items.length, 2)
  assert.ok(SORT_OPTIONS.some((o) => o.value === 'az'))
})
