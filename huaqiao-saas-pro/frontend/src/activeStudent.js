/**
 * Single source of truth for active student selection.
 * Identity is always numeric student_id — never name / index / profile object.
 *
 * Priority for restore:
 *   valid persisted id belonging to current account's student list
 *   > first accessible student
 *   > null
 */
import { computed, ref } from 'vue'

export const ACTIVE_STUDENT_STORAGE_KEY = 'smp_active_student_id'
/** Legacy key used for judge writeback; keep in sync for compatibility. */
export const LEGACY_STUDENT_STORAGE_KEY = 'smp_student_id'

/** @type {import('vue').Ref<number|null>} */
export const activeStudentId = ref(null)
/** @type {import('vue').Ref<Array<{id:number, display_name?:string}>>} */
export const accessibleStudents = ref([])

let loadSeq = 0

export function normalizeStudentId(value) {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return null
  return Math.trunc(n)
}

export function readPersistedStudentId(storage = globalThis.localStorage) {
  if (!storage) return null
  const raw = storage.getItem(ACTIVE_STUDENT_STORAGE_KEY) || storage.getItem(LEGACY_STUDENT_STORAGE_KEY)
  return normalizeStudentId(raw)
}

export function persistActiveStudentId(id, storage = globalThis.localStorage) {
  if (!storage) return
  const nid = normalizeStudentId(id)
  if (nid == null) {
    storage.removeItem(ACTIVE_STUDENT_STORAGE_KEY)
    storage.removeItem(LEGACY_STUDENT_STORAGE_KEY)
    return
  }
  storage.setItem(ACTIVE_STUDENT_STORAGE_KEY, String(nid))
  storage.setItem(LEGACY_STUDENT_STORAGE_KEY, String(nid))
}

/**
 * Pick a valid active id from the account's accessible list.
 * Invalid / foreign ids never win.
 */
export function resolveActiveStudentId(preferredId, students) {
  const list = Array.isArray(students) ? students : []
  const ids = new Set(list.map((s) => normalizeStudentId(s?.id)).filter((x) => x != null))
  const preferred = normalizeStudentId(preferredId)
  if (preferred != null && ids.has(preferred)) return preferred
  if (list.length) return normalizeStudentId(list[0].id)
  return null
}

export function studentLabel(students, id) {
  const nid = normalizeStudentId(id)
  const hit = (students || []).find((s) => normalizeStudentId(s.id) === nid)
  return hit?.display_name || (nid != null ? `学生 #${nid}` : '未选择学生')
}

export function setAccessibleStudents(list) {
  accessibleStudents.value = Array.isArray(list) ? list.slice() : []
}

/**
 * Set active student by id. Does not fetch profile data.
 * Returns true if the id is accepted (belongs to accessible list, or list empty and id forced).
 */
export function setActiveStudentId(id, { allowUnknown = false } = {}) {
  const nid = normalizeStudentId(id)
  if (nid == null) {
    activeStudentId.value = null
    persistActiveStudentId(null)
    return false
  }
  const ids = accessibleStudents.value.map((s) => normalizeStudentId(s.id))
  if (!allowUnknown && ids.length && !ids.includes(nid)) {
    return false
  }
  activeStudentId.value = nid
  persistActiveStudentId(nid)
  return true
}

/**
 * Sync list + resolve active id (persisted or preferred).
 * Falls back to first accessible student when persisted id is invalid.
 */
export function syncStudentsAndActive(list, preferredId = undefined) {
  setAccessibleStudents(list)
  const preferred = preferredId !== undefined ? preferredId : (activeStudentId.value ?? readPersistedStudentId())
  const resolved = resolveActiveStudentId(preferred, accessibleStudents.value)
  activeStudentId.value = resolved
  persistActiveStudentId(resolved)
  return resolved
}

/** Bump request token; returns token for stale-response guards. */
export function beginStudentLoad(id) {
  const nid = normalizeStudentId(id)
  if (nid != null) {
    activeStudentId.value = nid
    persistActiveStudentId(nid)
  }
  loadSeq += 1
  return { token: loadSeq, studentId: nid }
}

/** True if this response still matches the latest selection. */
export function isStudentLoadCurrent(token, studentId) {
  return token === loadSeq && normalizeStudentId(studentId) === normalizeStudentId(activeStudentId.value)
}

/**
 * Race-safe loader: late responses for a previous student are discarded.
 * @template T
 * @param {number|string} id
 * @param {(id:number) => Promise<T>} loader
 * @returns {Promise<{ok:true, data:T, studentId:number}|{ok:false, reason:'stale'|'invalid'|'error', error?:any}>}
 */
export async function loadForActiveStudent(id, loader) {
  const { token, studentId } = beginStudentLoad(id)
  if (studentId == null) return { ok: false, reason: 'invalid' }
  try {
    const data = await loader(studentId)
    if (!isStudentLoadCurrent(token, studentId)) {
      return { ok: false, reason: 'stale' }
    }
    return { ok: true, data, studentId }
  } catch (error) {
    if (!isStudentLoadCurrent(token, studentId)) {
      return { ok: false, reason: 'stale', error }
    }
    return { ok: false, reason: 'error', error }
  }
}

export function clearActiveStudent() {
  loadSeq += 1
  activeStudentId.value = null
  accessibleStudents.value = []
  persistActiveStudentId(null)
}

export const activeStudentLabel = computed(() => studentLabel(accessibleStudents.value, activeStudentId.value))
export const hasMultipleStudents = computed(() => accessibleStudents.value.length > 1)

export function useActiveStudent() {
  return {
    activeStudentId,
    accessibleStudents,
    activeStudentLabel,
    hasMultipleStudents,
    setAccessibleStudents,
    setActiveStudentId,
    syncStudentsAndActive,
    loadForActiveStudent,
    beginStudentLoad,
    isStudentLoadCurrent,
    clearActiveStudent,
    normalizeStudentId,
    resolveActiveStudentId,
    readPersistedStudentId,
    persistActiveStudentId,
  }
}
