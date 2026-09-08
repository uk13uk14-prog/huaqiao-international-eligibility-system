/**
 * Map formal student master profile → eligibility form fields.
 * Priority (applied by mergeEligibilityForm):
 *   formal student profile > caller/legal draft prefills > defaultForm blanks
 * Does not invent a second student. Does not treat random local form cache as profile.
 */

const FIELD_KEYWORDS = [
  [['体育', 'sport'], '体育'],
  [['音乐', 'music', '钢琴', 'piano'], '音乐'],
  [['美术', '绘画', 'fine art', 'fineart'], '美术'],
  [['设计', 'design'], '设计'],
  [['医', '药', '临床', '护理', 'dent'], '医药'],
  [['计算机', '软件', '电子', '工程', '理工', '物理', '化学', '数学', 'computer', 'engineer'], '理工'],
  [['文史', '历史', '文学', '哲学', '法学', '新闻'], '文史'],
]

function asObj(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

function asList(v) {
  return Array.isArray(v) ? v : []
}

function pickStr(...vals) {
  for (const v of vals) {
    if (v == null) continue
    const s = String(v).trim()
    if (s) return s
  }
  return undefined
}

function pickNum(v) {
  if (v == null || v === '') return undefined
  const n = Number(v)
  if (!Number.isFinite(n)) return undefined
  return n
}

function looksLikeCountry(s) {
  const t = String(s || '').trim()
  if (!t) return false
  if (/^(是|否|有|无|true|false|yes|no)$/i.test(t)) return false
  return t.length >= 2 && t.length <= 64
}

function mapIntendedField(majorOrField) {
  const raw = String(majorOrField || '').trim()
  if (!raw) return undefined
  const hay = raw.toLowerCase()
  for (const [keys, field] of FIELD_KEYWORDS) {
    if (keys.some((k) => hay.includes(String(k).toLowerCase()))) return field
  }
  const allowed = ['综合', '理工', '文史', '医药', '体育', '音乐', '美术', '设计']
  if (allowed.includes(raw)) return raw
  return undefined
}

function parseResidenceMonths(text) {
  const s = String(text || '')
  const last4 = s.match(/近\s*4\s*年[^0-9]{0,12}(\d{1,3})\s*个?月/)
  const last2 = s.match(/近\s*2\s*年[^0-9]{0,12}(\d{1,3})\s*个?月/)
  const annual = s.match(/(单年|每年|一年|年度)[^0-9]{0,12}(\d{1,3})\s*个?月/)
  const any = s.match(/(\d{1,3})\s*个?月/)
  return {
    last4: last4 ? Number(last4[1]) : undefined,
    last2: last2 ? Number(last2[1]) : undefined,
    annual: annual ? Number(annual[2]) : undefined,
    any: any ? Number(any[1]) : undefined,
  }
}

function firstNumericScore(profile) {
  const courses = asObj(profile.courses)
  for (const g of asList(courses.grades)) {
    const n = pickNum(g?.score) ?? pickNum(g?.grade) ?? pickNum(g?.gpa)
    if (n != null && n > 0) return n
  }
  for (const exam of asList(courses.language_exams)) {
    const n = pickNum(exam?.overall_score) ?? pickNum(exam?.score)
    if (n != null && n > 0) return n
  }
  for (const exam of asList(courses.other_exams)) {
    const n = pickNum(exam?.score) ?? pickNum(exam?.overall_score)
    if (n != null && n > 0) return n
  }
  const csca = asObj(profile.csca)
  const cscaScore = pickNum(csca.csca_score)
  if (cscaScore != null && cscaScore > 0) return cscaScore
  return undefined
}

/**
 * Only defined keys — empty strings / missing facts are omitted
 * so defaultForm values are not wiped by an empty profile.
 */
export function mapStudentToEligibilityPrefills(student) {
  const root = asObj(student)
  const profile = asObj(root.profile)
  const basic = asObj(profile.basic_info)
  const identity = asObj(profile.identity)
  const goals = asObj(profile.goals)
  const planning = asObj(profile.planning)
  const apiPrefills = asObj(root.judge_prefills)
  const firstTarget = asList(goals.targets)[0] || {}
  const overseas = identity.overseas_residence_info
  const overseasText = typeof overseas === 'string' ? overseas : pickStr(asObj(overseas).note, asObj(overseas).text)

  const out = {}

  const name = pickStr(apiPrefills.name, basic.chinese_name, basic.english_name, root.display_name)
  if (name) out.name = name

  const birth = pickStr(apiPrefills.birth_date, basic.birth_date)
  if (birth) out.birth_date = birth

  const nationality = pickStr(apiPrefills.current_nationality, identity.current_nationality)
  if (nationality) out.current_nationality = nationality

  const acquired = pickStr(apiPrefills.foreign_nationality_acquired_date, identity.foreign_nationality_acquired_date)
  if (acquired) out.foreign_nationality_acquired_date = acquired

  const passport = pickStr(apiPrefills.passport_info, identity.passport_info)
  if (passport) out.passport_info = passport

  if (typeof identity.has_foreign_nationality === 'boolean') {
    out.has_foreign_nationality = identity.has_foreign_nationality
  } else if (typeof apiPrefills.has_foreign_nationality === 'boolean' && identity.current_nationality) {
    out.has_foreign_nationality = apiPrefills.has_foreign_nationality
  }

  if (typeof identity.has_chinese_nationality === 'boolean') {
    out.has_chinese_nationality = identity.has_chinese_nationality
  } else if (typeof apiPrefills.has_chinese_nationality === 'boolean' && identity.current_nationality) {
    out.has_chinese_nationality = apiPrefills.has_chinese_nationality
  }

  if (identity.has_chinese_hukou === true || identity.hukou_cancelled === true) {
    out.has_mainland_household = Boolean(identity.has_chinese_hukou) && !Boolean(identity.hukou_cancelled)
  } else if (typeof apiPrefills.has_mainland_household === 'boolean' && identity.has_chinese_hukou != null) {
    out.has_mainland_household = apiPrefills.has_mainland_household
  }

  const birthCountry = pickStr(identity.birth_country)
  if (birthCountry) {
    out.born_abroad = !['中国', '中国大陆', 'CN', 'China', 'PRC'].includes(birthCountry)
  } else if (typeof apiPrefills.born_abroad === 'boolean' && apiPrefills.born_abroad) {
    out.born_abroad = true
  }

  const residenceCountry = (
    looksLikeCountry(identity.foreign_permanent_residence)
      ? pickStr(identity.foreign_permanent_residence)
      : undefined
  ) || pickStr(basic.current_country, asObj(overseas).current_residence_country)
  if (residenceCountry) out.permanent_residence_country = residenceCountry
  else if (looksLikeCountry(overseasText) && !/\d/.test(overseasText)) {
    out.permanent_residence_country = overseasText.trim()
  }

  const months = parseResidenceMonths(overseasText)
  const years = pickNum(asObj(overseas).residence_years)
  if (months.last2 != null) out.overseas_residence_months_last_2y = months.last2
  if (months.last4 != null) out.overseas_residence_months_last_4y = months.last4
  if (months.annual != null) out.annual_months_overseas = months.annual
  if (years != null && years > 0) {
    const approx = Math.round(years * 12)
    if (out.overseas_residence_months_last_4y == null) out.overseas_residence_months_last_4y = Math.min(approx, 48)
    if (out.overseas_residence_months_last_2y == null) out.overseas_residence_months_last_2y = Math.min(approx, 24)
  }
  if (months.any != null) {
    if (out.overseas_residence_months_last_4y == null) out.overseas_residence_months_last_4y = months.any
    if (out.overseas_residence_months_last_2y == null) out.overseas_residence_months_last_2y = months.any
  }

  const field = mapIntendedField(
    pickStr(firstTarget.major, firstTarget.field, planning.target_major, planning.intended_field),
  )
  if (field) out.intended_field = field

  const score = firstNumericScore(profile)
  if (score != null) out.score = score

  const father = pickStr(identity.father_nationality)
  const mother = pickStr(identity.mother_nationality)
  if (father || mother) {
    const blob = `${father || ''} ${mother || ''}`
    if (/中国|chinese/i.test(blob)) out.parent_chinese_citizen = true
  }

  return out
}

function omitEmpty(obj) {
  const out = {}
  if (!obj || typeof obj !== 'object') return out
  for (const [k, v] of Object.entries(obj)) {
    if (v == null) continue
    if (typeof v === 'string' && !v.trim()) continue
    out[k] = v
  }
  return out
}

/**
 * @param {object} defaults from defaultForm(type)
 * @param {{ draft?: object, profile?: object }} layers
 */
export function mergeEligibilityForm(defaults, { draft, profile } = {}) {
  return {
    ...(defaults || {}),
    ...omitEmpty(draft),
    ...omitEmpty(profile),
  }
}
