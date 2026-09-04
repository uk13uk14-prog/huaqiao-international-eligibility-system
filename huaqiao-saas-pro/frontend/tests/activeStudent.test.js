/**
 * Active student switch unit tests (node:test + vue).
 * Covers bidirectional switch, rapid race guard, persistence, invalid fallback, isolation maps.
 */
import { createRequire } from 'module'
import assert from 'node:assert/strict'
import test from 'node:test'
import { pathToFileURL } from 'node:url'
import path from 'node:path'

const require = createRequire(import.meta.url)
const vuePath = require.resolve('vue')
const storePath = path.resolve('src/activeStudent.js')

// Ensure vue is resolvable for the ESM store import.
await import(pathToFileURL(vuePath).href)
const store = await import(pathToFileURL(storePath).href)

function memoryStorage(seed = {}) {
  const map = new Map(Object.entries(seed))
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => { map.set(k, String(v)) },
    removeItem: (k) => { map.delete(k) },
    _map: map,
  }
}

function resetStore(storage = memoryStorage()) {
  store.clearActiveStudent()
  // Re-bind persistence helpers against memory storage via wrappers in tests.
  return storage
}

test('normalizeStudentId rejects name/index/email-like values', () => {
  assert.equal(store.normalizeStudentId('兰恩'), null)
  assert.equal(store.normalizeStudentId('0'), null)
  assert.equal(store.normalizeStudentId(-1), null)
  assert.equal(store.normalizeStudentId('12'), 12)
  assert.equal(store.normalizeStudentId(3), 3)
})

test('A→B and B→A bidirectional switch by student_id', () => {
  store.clearActiveStudent()
  const list = [
    { id: 1, display_name: '兰恩' },
    { id: 2, display_name: 'Student B' },
  ]
  store.syncStudentsAndActive(list, 1)
  assert.equal(store.activeStudentId.value, 1)
  assert.equal(store.setActiveStudentId(2), true)
  assert.equal(store.activeStudentId.value, 2)
  assert.equal(store.setActiveStudentId(1), true)
  assert.equal(store.activeStudentId.value, 1)
})

test('A→C and C→A work; continuous round-trips do not stick', () => {
  store.clearActiveStudent()
  const list = [
    { id: 10, display_name: 'A' },
    { id: 20, display_name: 'B' },
    { id: 30, display_name: 'C' },
  ]
  store.syncStudentsAndActive(list, 10)
  const seq = [20, 10, 30, 10, 20, 30, 20, 10, 30, 20, 10, 30, 10, 20, 30, 10, 20, 30, 10, 20]
  for (const id of seq) {
    assert.equal(store.setActiveStudentId(id), true)
    assert.equal(store.activeStudentId.value, id)
  }
  assert.equal(store.activeStudentId.value, 20)
})

test('rapid A→B→A discards stale B response', async () => {
  store.clearActiveStudent()
  store.syncStudentsAndActive([
    { id: 1, display_name: 'A' },
    { id: 2, display_name: 'B' },
  ], 1)

  let resolveB
  const slowB = new Promise((resolve) => { resolveB = resolve })
  const pB = store.loadForActiveStudent(2, async () => {
    await slowB
    return { id: 2, profile: { basic_info: { chinese_name: 'B' }, goals: { targets: [{ university_name: '清华大学', major: '计算机' }] } } }
  })
  const pA = store.loadForActiveStudent(1, async () => ({
    id: 1,
    profile: { basic_info: { chinese_name: '兰恩' }, goals: { targets: [{ university_name: '浙江大学', major: '经济' }] } },
  }))
  const a = await pA
  assert.equal(a.ok, true)
  assert.equal(a.data.profile.basic_info.chinese_name, '兰恩')
  resolveB()
  const b = await pB
  assert.equal(b.ok, false)
  assert.equal(b.reason, 'stale')
  assert.equal(store.activeStudentId.value, 1)
})

test('refresh persistence keeps last student; invalid id falls back', () => {
  const storage = memoryStorage({ smp_active_student_id: '2' })
  const list = [
    { id: 1, display_name: 'A' },
    { id: 2, display_name: 'B' },
  ]
  const preferred = store.readPersistedStudentId(storage)
  assert.equal(preferred, 2)
  assert.equal(store.resolveActiveStudentId(preferred, list), 2)
  assert.equal(store.resolveActiveStudentId(999, list), 1)
  assert.equal(store.resolveActiveStudentId('兰恩', list), 1)
  store.persistActiveStudentId(2, storage)
  assert.equal(storage.getItem('smp_active_student_id'), '2')
  assert.equal(storage.getItem('smp_student_id'), '2')
})

test('home and profile share the same activeStudentId module state', () => {
  store.clearActiveStudent()
  store.syncStudentsAndActive([
    { id: 5, display_name: 'HomeA' },
    { id: 6, display_name: 'ProfileB' },
  ], 5)
  // Simulate home switch
  store.setActiveStudentId(6)
  assert.equal(store.activeStudentId.value, 6)
  // Simulate profile reading the same store
  assert.equal(store.activeStudentId.value, 6)
  store.setActiveStudentId(5)
  assert.equal(store.activeStudentId.value, 5)
})

test('isolation maps: different student payloads never merge by name', async () => {
  store.clearActiveStudent()
  store.syncStudentsAndActive([
    { id: 101, display_name: 'Student A' },
    { id: 102, display_name: 'Student B' },
  ], 101)
  const cache = new Map()
  async function fetchById(id) {
    if (id === 101) {
      return {
        id: 101,
        profile: { goals: { targets: [{ university_name: '浙江大学', major: '经济' }] } },
        portrait: { basic: { chinese_name: 'A' } },
        eligibility: { international: 'A' },
        timeline: [{ title: 'A-deadline' }],
      }
    }
    return {
      id: 102,
      profile: { goals: { targets: [{ university_name: '清华大学', major: '计算机' }] } },
      portrait: { basic: { chinese_name: 'B' } },
      eligibility: { international: 'B' },
      timeline: [{ title: 'B-deadline' }],
    }
  }
  for (const id of [101, 102, 101, 102, 101]) {
    const r = await store.loadForActiveStudent(id, fetchById)
    assert.equal(r.ok, true)
    cache.set(id, r.data)
  }
  assert.equal(cache.get(101).profile.goals.targets[0].university_name, '浙江大学')
  assert.equal(cache.get(102).profile.goals.targets[0].university_name, '清华大学')
  assert.equal(cache.get(101).portrait.basic.chinese_name, 'A')
  assert.equal(cache.get(102).portrait.basic.chinese_name, 'B')
  assert.equal(cache.get(101).eligibility.international, 'A')
  assert.equal(cache.get(102).timeline[0].title, 'B-deadline')
})

test('foreign student_id cannot be selected when list is known', () => {
  store.clearActiveStudent()
  store.syncStudentsAndActive([{ id: 1, display_name: 'Mine' }], 1)
  assert.equal(store.setActiveStudentId(999), false)
  assert.equal(store.activeStudentId.value, 1)
})

test('TEST_1–5: bidirectional switch preserves full student list and active id', () => {
  store.clearActiveStudent()
  const list = [
    { id: 1, display_name: '兰恩' },
    { id: 2, display_name: 'Student B' },
  ]
  store.syncStudentsAndActive(list, 1)
  assert.equal(store.activeStudentId.value, 1)
  assert.equal(store.accessibleStudents.value.length, 2)

  // TEST_1 A→B
  assert.equal(store.switchActiveStudent(2), true)
  assert.equal(store.activeStudentId.value, 2)
  assert.equal(store.accessibleStudents.value.length, 2)

  // TEST_2 after B, A still in list / switchable
  const switchableOnB = store.switchableStudents.value.map((s) => s.id)
  assert.deepEqual(switchableOnB, [1])
  assert.ok(store.accessibleStudents.value.some((s) => s.id === 1))

  // TEST_3 B→A
  assert.equal(store.switchActiveStudent(1), true)
  assert.equal(store.activeStudentId.value, 1)

  // TEST_4 A→B→A
  assert.equal(store.switchActiveStudent(2), true)
  assert.equal(store.switchActiveStudent(1), true)
  assert.equal(store.activeStudentId.value, 1)
  assert.equal(store.studentLabel(store.accessibleStudents.value, 1), '兰恩')

  // TEST_5 count always 2
  assert.equal(store.accessibleStudents.value.length, 2)
})

test('TEST_6: refresh restores persisted activeStudentId', () => {
  const storage = memoryStorage({ smp_active_student_id: '2' })
  const list = [
    { id: 1, display_name: '兰恩' },
    { id: 2, display_name: 'Student B' },
  ]
  const preferred = store.readPersistedStudentId(storage)
  assert.equal(preferred, 2)
  store.clearActiveStudent()
  const resolved = store.syncStudentsAndActive(list, preferred)
  assert.equal(resolved, 2)
  assert.equal(store.activeStudentId.value, 2)
})

test('TEST_7: switch reloads context by student_id (eligibility/timeline keyed by id)', async () => {
  store.clearActiveStudent()
  store.syncStudentsAndActive([
    { id: 1, display_name: '兰恩' },
    { id: 2, display_name: 'Student B' },
  ], 1)
  const payloads = {
    1: { id: 1, eligibility: { international: 'A-elig' }, timeline: [{ title: 'A-tl' }], profile: { basic_info: { chinese_name: '兰恩' } } },
    2: { id: 2, eligibility: { international: 'B-elig' }, timeline: [{ title: 'B-tl' }], profile: { basic_info: { chinese_name: 'Student B' } } },
  }
  const rB = await store.loadForActiveStudent(2, async (id) => payloads[id])
  assert.equal(rB.ok, true)
  assert.equal(rB.studentId, 2)
  assert.equal(rB.data.eligibility.international, 'B-elig')
  assert.equal(rB.data.timeline[0].title, 'B-tl')

  const rA = await store.loadForActiveStudent(1, async (id) => payloads[id])
  assert.equal(rA.ok, true)
  assert.equal(rA.studentId, 1)
  assert.equal(rA.data.eligibility.international, 'A-elig')
  assert.equal(rA.data.profile.basic_info.chinese_name, '兰恩')
})

test('switch never replaces accessibleStudents with only the selected student', () => {
  store.clearActiveStudent()
  store.syncStudentsAndActive([
    { id: 1, display_name: '兰恩' },
    { id: 2, display_name: 'Student B' },
  ], 1)
  store.switchActiveStudent(2)
  store.switchActiveStudent(1)
  store.switchActiveStudent(2)
  assert.equal(store.accessibleStudents.value.length, 2)
  assert.deepEqual(store.accessibleStudents.value.map((s) => s.id).sort(), [1, 2])
})

