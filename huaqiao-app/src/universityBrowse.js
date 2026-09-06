/**
 * Client-side university browse helpers (search / sort / A-Z index).
 * Does not change entitlement or API limits — only filters already-returned rows.
 */

const PINYIN_BOUNDARIES = [
  ['A', '阿'], ['B', '八'], ['C', '嚓'], ['D', '哒'], ['E', '娥'], ['F', '发'],
  ['G', '噶'], ['H', '哈'], ['J', '讥'], ['K', '咔'], ['L', '垃'], ['M', '妈'],
  ['N', '拿'], ['O', '哦'], ['P', '啪'], ['Q', '期'], ['R', '然'], ['S', '撒'],
  ['T', '塌'], ['W', '挖'], ['X', '昔'], ['Y', '压'], ['Z', '匝'],
]

export function pinyinInitial(name) {
  const s = String(name || '').trim()
  if (!s) return '#'
  const ch = s[0]
  if (/[A-Za-z]/.test(ch)) return ch.toUpperCase()
  if (/[0-9]/.test(ch)) return '#'
  let best = '#'
  for (const [letter, rep] of PINYIN_BOUNDARIES) {
    if (ch.localeCompare(rep, 'zh-CN') >= 0) best = letter
    else break
  }
  return best
}

export function matchesUniversityQuery(school, query) {
  const q = String(query || '').trim().toLowerCase()
  if (!q) return true
  const hay = [
    school.name,
    school.province,
    school.fields,
    school.advantage_majors,
    school.tags,
    school.university_type,
    school.description,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return hay.includes(q)
}

export function sortUniversities(list, mode) {
  const rows = Array.isArray(list) ? [...list] : []
  if (mode === 'az') {
    rows.sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'zh-CN'))
    return rows
  }
  if (mode === 'region') {
    rows.sort((a, b) => {
      const p = String(a.province || '').localeCompare(String(b.province || ''), 'zh-CN')
      if (p !== 0) return p
      return (a.ranking ?? 9999) - (b.ranking ?? 9999)
    })
    return rows
  }
  if (mode === 'tier') {
    const tierScore = (s) => {
      const t = String(s.tags || '')
      if (t.includes('C9') || t.includes('九校')) return 0
      if (t.includes('985')) return 1
      if (t.includes('211')) return 2
      return 3
    }
    rows.sort((a, b) => {
      const d = tierScore(a) - tierScore(b)
      if (d !== 0) return d
      return (a.ranking ?? 9999) - (b.ranking ?? 9999)
    })
    return rows
  }
  // recommend (default): ranking asc
  rows.sort((a, b) => (a.ranking ?? 9999) - (b.ranking ?? 9999))
  return rows
}

export function browseUniversities(list, { query = '', sort = 'recommend' } = {}) {
  const filtered = (Array.isArray(list) ? list : []).filter((s) => matchesUniversityQuery(s, query))
  const sorted = sortUniversities(filtered, sort)
  const groups = {}
  for (const s of sorted) {
    const letter = pinyinInitial(s.name)
    if (!groups[letter]) groups[letter] = []
    groups[letter].push(s)
  }
  const letters = Object.keys(groups).sort((a, b) => {
    if (a === '#') return 1
    if (b === '#') return -1
    return a.localeCompare(b)
  })
  return { items: sorted, groups, letters }
}

export const SORT_OPTIONS = [
  { text: '推荐', value: 'recommend' },
  { text: 'A-Z', value: 'az' },
  { text: '地区', value: 'region' },
  { text: '院校层次', value: 'tier' },
]
