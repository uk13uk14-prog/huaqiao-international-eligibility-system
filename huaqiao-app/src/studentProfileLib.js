export const SCHOOL_TYPES = ['Public School','Private School','Grammar School','International School','Chinese High School','College','University','Other']
export const CURRICULUMS = ['A-Level','GCSE','IGCSE','IB','AP','SAT','ACT','Canadian High School','Australian Curriculum','Chinese High School','HK Curriculum','Other','Custom']
export const GRADE_TYPES = ['Actual','Predicted','Mock','School Assessment','Other']
export const LANGUAGE_EXAMS = ['HSK','IELTS','TOEFL','Duolingo','Other']
export const OTHER_EXAM_TYPES = ['CSCA','SAT','ACT','AP','竞赛','其他资格']
export const CSCA_STATUS_OPTIONS = [
  { value: 'NOT_PLANNED', label: '未计划' },
  { value: 'PLANNED', label: '计划参加' },
  { value: 'REGISTERED', label: '已报名' },
  { value: 'TAKEN', label: '已考试' },
  { value: 'RESULT_AVAILABLE', label: '成绩已出' },
]
export function emptyCsca(extra = {}) {
  return {
    csca_status: 'NOT_PLANNED',
    csca_exam_date: '',
    csca_registration_deadline: '',
    csca_result_date: '',
    csca_score: '',
    csca_level: '',
    csca_notes: '',
    registration_deadline_source: '',
    exam_date_source: '',
    result_date_source: '',
    updated_at: '',
    ...extra,
  }
}
export const PRIORITY_LEVELS = [
  { value: 'reach', label: '冲刺' },
  { value: 'target', label: '主申' },
  { value: 'match', label: '稳妥' },
  { value: 'safety', label: '保底' },
]
export const SECTIONS = [
  { key: 'summary', label: '档案总览' },
  { key: 'basic_info', label: '基本信息' },
  { key: 'education', label: '教育与学校' },
  { key: 'courses', label: '课程与成绩' },
  { key: 'goals', label: '升学目标' },
  { key: 'identity', label: '身份与国籍' },
  { key: 'portrait', label: '学生画像' },
  { key: 'my_timeline', label: '升学时间轴' },
  { key: 'planning', label: '申请与规划' },
  { key: 'csca', label: 'CSCA考试' },
]
export const WIZARD_SECTIONS = [
  { key: 'basic_info', label: '基本信息' },
  { key: 'education', label: '教育与学校' },
  { key: 'courses', label: '课程与成绩' },
  { key: 'goals', label: '升学目标' },
  { key: 'identity', label: '身份与国籍' },
  { key: 'planning', label: '申请与规划' },
  { key: 'summary', label: '档案总览' },
]
export const DERIVED_SECTIONS = new Set(['portrait', 'my_timeline'])
export const STATUS_LABEL = {
  NOT_ASSESSED: '尚未判定',
  IN_PROGRESS: '判定进行中',
  ELIGIBLE: '符合',
  LIKELY_ELIGIBLE: '初步符合',
  NOT_ELIGIBLE: '初步不符合',
  NEED_MORE_INFO: '需补充材料',
}
export const TIMELINE_STATUS_LABEL = {
  NOT_STARTED: '未开始',
  IN_PROGRESS: '进行中',
  COMPLETED: '已完成',
  OVERDUE: '已逾期',
  NOT_APPLICABLE: '不适用',
}

export function nid() {
  return typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '') : `id${Date.now()}${Math.random().toString(16).slice(2)}`
}

export function emptySchool(extra = {}) {
  return { id: nid(), school_name: '', country: '', city: '', school_type: '', start_date: '', end_date: '', current_grade: '', is_current: false, sort_order: 0, notes: '', ...extra }
}
export function emptyCourse(extra = {}) {
  return { id: nid(), subject: '', qualification: '', level: '', exam_board: '', start_year: '', end_year: '', is_current: false, notes: '', ...extra }
}
export function emptyGrade(extra = {}) {
  return { id: nid(), course_id: '', subject: '', academic_year: '', exam_session: '', grade_type: 'Actual', grade: '', score: '', max_score: '', exam_board: '', is_predicted: false, notes: '', ...extra }
}
export function emptyLang(extra = {}) {
  return { id: nid(), exam_type: '', exam_date: '', overall_score: '', sub_scores: {}, certificate_no: '', notes: '', ...extra }
}
export function emptyOther(extra = {}) {
  return { id: nid(), exam_type: '', custom_type: '', exam_date: '', score: '', notes: '', ...extra }
}
export function emptyTarget(extra = {}) {
  return { id: nid(), country: '中国', university_id: null, university_name: '', major: '', college: '', entry_year: '', application_route: '', priority_level: 'target', notes: '', sort_order: 0, ...extra }
}

export function emptyProfile() {
  const current = emptySchool({ is_current: true })
  return {
    schema_version: 2,
    wizard_completed: false,
    basic_info: { chinese_name: '', english_name: '', birth_date: '', gender: '', current_country: '', current_city: '', contact: '', intended_entry_year: '', profile_created_at: '', basic_info_notes: '' },
    education: { current_school: current, history: [JSON.parse(JSON.stringify(current))], education_notes: '' },
    courses: { curricula: [], custom_curriculum: '', items: [], grades: [], language_exams: [], other_exams: [], courses_notes: '' },
    goals: { targets: [], goals_notes: '' },
    identity: {
      birth_country: '', current_nationality: '', former_nationalities: '', had_chinese_nationality: false, has_chinese_hukou: false, hukou_cancelled: false,
      foreign_nationality_acquired_date: '', foreign_permanent_residence: '', passport_info: '', father_nationality: '', mother_nationality: '',
      parents_overseas_settlement: '', overseas_residence_info: '', has_foreign_nationality: false, has_chinese_nationality: false,
      international: { status: 'NOT_ASSESSED', engine_result: '', conclusion: '', assessed_at: '', policy_version: '', record_id: null, confirmed: false, confirmed_at: '' },
      huaqiao: { status: 'NOT_ASSESSED', engine_result: '', conclusion: '', assessed_at: '', policy_version: '', record_id: null, confirmed: false, confirmed_at: '' },
      identity_notes: '',
    },
    planning: { current_education_stage: '', target_countries: '', planning_notes: '' },
    summary: { summary_notes: '' },
    csca: emptyCsca(),
    legacy: {},
  }
}
