<template>
  <div class="smp-mobile">
    <van-cell-group inset>
      <van-field label="学生" is-link readonly :model-value="currentLabel" @click="showPicker = true" />
      <div class="consult-actions" style="padding:12px;">
        <van-button block round type="primary" @click="createStudent">创建学生</van-button>
      </div>
    </van-cell-group>
    <van-popup v-model:show="showPicker" position="bottom">
      <van-picker :columns="studentColumns" @confirm="onPickStudent" @cancel="showPicker=false" />
    </van-popup>

    <template v-if="profile">
      <van-tabs v-model:active="section" shrink sticky>
        <van-tab v-for="sec in sections" :key="sec.key" :title="sec.label" :name="sec.key" />
      </van-tabs>

      <div v-show="section==='basic_info'" class="form-card">
        <van-field v-model="profile.basic_info.chinese_name" label="中文名" />
        <van-field v-model="profile.basic_info.english_name" label="英文名" />
        <van-field v-model="profile.basic_info.birth_date" label="出生日期" placeholder="YYYY-MM-DD" />
        <van-field v-model="profile.basic_info.gender" label="性别" />
        <van-field v-model="profile.basic_info.current_country" label="居住国家" />
        <van-field v-model="profile.basic_info.current_city" label="城市" />
        <van-field v-model="profile.basic_info.contact" label="联系方式" />
        <van-field v-model="profile.basic_info.intended_entry_year" label="入学年份" />
        <van-field v-model="profile.basic_info.basic_info_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('basic_info')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='education'" class="form-card">
        <van-cell title="当前在读学校" :label="currentSchool?.school_name || '未填写'" />
        <van-field v-if="currentSchool" v-model="currentSchool.school_name" label="学校名称" />
        <van-field v-if="currentSchool" v-model="currentSchool.country" label="国家/地区" />
        <van-field v-if="currentSchool" v-model="currentSchool.city" label="城市" />
        <van-field v-if="currentSchool" v-model="currentSchool.school_type" label="学校类型" placeholder="Public / Grammar / International..." />
        <van-field v-if="currentSchool" v-model="currentSchool.start_date" label="开始年月" />
        <van-field v-if="currentSchool" v-model="currentSchool.current_grade" label="当前年级" />
        <van-button block @click="profile.education.history.push(emptySchool())">+ 添加教育经历</van-button>
        <div v-for="(row, idx) in profile.education.history" :key="row.id" class="summary-card">
          <van-field v-model="row.school_name" label="学校" />
          <van-field v-model="row.country" label="国家" />
          <van-field v-model="row.city" label="城市" />
          <van-field v-model="row.school_type" label="类型" />
          <van-field v-model="row.start_date" label="开始" />
          <van-field v-model="row.end_date" label="结束" />
          <van-cell title="当前在读"><template #right-icon><van-switch v-model="row.is_current" size="22" @change="onlyCurrent(idx)" /></template></van-cell>
          <van-button size="small" type="danger" @click="profile.education.history.splice(idx,1)">删除</van-button>
        </div>
        <van-field v-model="profile.education.education_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('education')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='courses'" class="form-card">
        <van-field v-model="curriculaText" label="课程体系" placeholder="A-Level,Custom" @blur="syncCurricula" />
        <van-field v-model="profile.courses.custom_curriculum" label="自定义体系" />
        <van-button block @click="addMathBundle">+ 添加 Mathematics / FM / Physics 示例</van-button>
        <van-button block @click="profile.courses.items.push(emptyCourse())">+ 添加课程</van-button>
        <div v-for="c in profile.courses.items" :key="c.id" class="summary-card">
          <van-field v-model="c.subject" label="科目" />
          <van-field v-model="c.qualification" label="资格" placeholder="A-Level" />
          <van-field v-model="c.level" label="Level" placeholder="AS / A2" />
          <van-field v-model="c.exam_board" label="Exam board" />
          <van-field v-model="c.start_year" label="开始年" />
          <van-field v-model="c.end_year" label="结束年" />
          <van-button size="small" @click="addGrade(c)">+ 添加成绩</van-button>
          <div v-for="g in gradesFor(c.id)" :key="g.id">
            <van-field v-model="g.exam_session" label="场次" placeholder="AS / A2 / GCSE" />
            <van-field v-model="g.grade_type" label="类型" placeholder="Actual / Predicted" />
            <van-field v-model="g.grade" label="成绩" />
          </div>
        </div>
        <van-button block @click="profile.courses.language_exams.push(emptyLang({ exam_type: 'HSK', overall_score: '6' }))">+ 添加 HSK / 语言成绩</van-button>
        <div v-for="(ex, idx) in profile.courses.language_exams" :key="ex.id" class="summary-card">
          <van-field v-model="ex.exam_type" label="考试" />
          <van-field v-model="ex.overall_score" label="成绩" />
          <van-field v-model="ex.exam_date" label="日期" />
          <van-button size="small" type="danger" @click="profile.courses.language_exams.splice(idx,1)">删除</van-button>
        </div>
        <van-button block @click="profile.courses.other_exams.push(emptyOther())">+ 其他考试/资格</van-button>
        <div v-for="(ex, idx) in profile.courses.other_exams" :key="ex.id" class="summary-card">
          <van-field v-model="ex.exam_type" label="类型" placeholder="CSCA / SAT / 竞赛" />
          <van-field v-model="ex.score" label="成绩" />
          <van-button size="small" type="danger" @click="profile.courses.other_exams.splice(idx,1)">删除</van-button>
        </div>
        <van-field v-model="profile.courses.courses_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('courses')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='goals'" class="form-card">
        <van-button block type="primary" @click="profile.goals.targets.push(emptyTarget())">+ 添加目标大学</van-button>
        <div v-for="level in priorityLevels" :key="level.value">
          <h3 style="padding:12px 16px 0;color:#123c69;">{{ level.label }}</h3>
          <div v-for="t in targetsBy(level.value)" :key="t.id" class="summary-card">
            <van-field v-model="t.university_name" label="大学" />
            <van-field v-model="t.major" label="专业" />
            <van-field v-model="t.entry_year" label="入学年" />
            <van-field v-model="t.priority_level" label="分类" placeholder="reach/target/match/safety" />
            <van-button size="small" type="danger" @click="profile.goals.targets = profile.goals.targets.filter(x=>x.id!==t.id)">删除</van-button>
          </div>
        </div>
        <van-field v-model="profile.goals.goals_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('goals')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='identity'" class="form-card">
        <p class="confirm-hint">外国国籍 / 中国国籍仅为事实字段，不能自行设定“我是国际生/华侨生”。</p>
        <van-field v-model="profile.identity.birth_country" label="出生国家" />
        <van-field v-model="profile.identity.current_nationality" label="当前国籍" />
        <van-field v-model="profile.identity.former_nationalities" label="曾经国籍" />
        <van-cell title="持有外国国籍（事实）"><template #right-icon><van-switch v-model="profile.identity.has_foreign_nationality" size="22" /></template></van-cell>
        <van-cell title="持有中国国籍（事实）"><template #right-icon><van-switch v-model="profile.identity.has_chinese_nationality" size="22" /></template></van-cell>
        <van-cell title="曾拥有中国国籍"><template #right-icon><van-switch v-model="profile.identity.had_chinese_nationality" size="22" /></template></van-cell>
        <van-cell title="有中国户籍"><template #right-icon><van-switch v-model="profile.identity.has_chinese_hukou" size="22" /></template></van-cell>
        <van-cell title="已注销中国户籍"><template #right-icon><van-switch v-model="profile.identity.hukou_cancelled" size="22" /></template></van-cell>
        <van-field v-model="profile.identity.foreign_nationality_acquired_date" label="取得外国国籍日" />
        <van-field v-model="profile.identity.passport_info" label="护照信息" />
        <van-field v-model="profile.identity.father_nationality" label="父亲国籍" />
        <van-field v-model="profile.identity.mother_nationality" label="母亲国籍" />
        <van-field v-model="profile.identity.parents_overseas_settlement" label="父母海外定居" type="textarea" rows="2" />
        <van-field v-model="profile.identity.overseas_residence_info" label="海外居住信息" type="textarea" rows="2" />
        <div class="summary-card">
          <h3>国际生资格</h3>
          <p>{{ profile.identity.international.status === 'NOT_ASSESSED' ? '国际生资格尚未判定' : statusLabel[profile.identity.international.status] }}</p>
          <p class="muted" v-if="profile.identity.international.assessed_at">{{ profile.identity.international.assessed_at }} · {{ profile.identity.international.policy_version }} · {{ profile.identity.international.confirmed ? '已确认写入' : '未确认写入' }}</p>
          <van-button block type="primary" @click="goJudge('international')">前往国际生判定</van-button>
          <van-button v-if="profile.identity.international.engine_result && !profile.identity.international.confirmed" block @click="confirmWB('international')">确认写入学生档案</van-button>
        </div>
        <div class="summary-card">
          <h3>华侨生资格</h3>
          <p>{{ profile.identity.huaqiao.status === 'NOT_ASSESSED' ? '华侨生资格尚未判定' : statusLabel[profile.identity.huaqiao.status] }}</p>
          <van-button block type="primary" @click="goJudge('huaqiao')">前往华侨生判定</van-button>
          <van-button v-if="profile.identity.huaqiao.engine_result && !profile.identity.huaqiao.confirmed" block @click="confirmWB('huaqiao')">确认写入学生档案</van-button>
        </div>
        <van-field v-model="profile.identity.identity_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('identity')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='planning'" class="form-card">
        <van-cell title="入学年份" :value="profile.basic_info.intended_entry_year || '—'" />
        <van-field v-model="profile.planning.current_education_stage" label="教育阶段" />
        <van-cell title="国际生状态" :value="statusLabel[profile.identity.international.status]" />
        <van-cell title="华侨生状态" :value="statusLabel[profile.identity.huaqiao.status]" />
        <van-cell title="目标大学" :label="profile.goals.targets.map(t=>t.university_name).filter(Boolean).join('、') || '—'" />
        <van-cell title="冲刺/主申/稳妥/保底" :value="`${countPri('reach')}/${countPri('target')}/${countPri('match')}/${countPri('safety')}`" />
        <van-button block @click="loadTimeline">读取匹配招生时间线</van-button>
        <div v-for="(s,i) in timeline" :key="i" class="summary-card">
          <b>{{ s.university_name }} {{ s.year }}-{{ s.month }}</b>
          <p>报名 {{ s.registration_time }}</p>
        </div>
        <van-field v-model="profile.planning.planning_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('planning')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='summary'" class="form-card">
        <div class="hero-card"><h1>档案完整度 {{ completeness.percent || 0 }}%</h1><p class="hero-lead">缺失只提示，不强制一次填完</p></div>
        <van-cell v-for="m in completeness.missing || []" :key="m" :title="m" />
        <van-cell title="姓名" :value="(profile.basic_info.chinese_name||'')+' '+(profile.basic_info.english_name||'')" />
        <van-cell title="当前学校" :value="currentSchool?.school_name || '—'" />
        <van-cell title="课程体系" :value="(profile.courses.curricula||[]).join('/') || '—'" />
        <van-field v-model="profile.summary.summary_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('summary')">{{ saveLabel }}</van-button></div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'
import { getSaasToken, saasApi } from './saasApi'
import { PRIORITY_LEVELS, SECTIONS, STATUS_LABEL, emptyCourse, emptyGrade, emptyLang, emptyOther, emptySchool, emptyTarget } from './studentProfileLib'

const emit = defineEmits(['goto-judge'])
const sections = SECTIONS
const priorityLevels = PRIORITY_LEVELS
const statusLabel = STATUS_LABEL
const students = ref([])
const studentId = ref(null)
const profile = ref(null)
const section = ref('basic_info')
const saving = ref(false)
const completeness = ref({ percent: 0, missing: [] })
const showPicker = ref(false)
const timeline = ref([])
const curriculaText = ref('')

const wizardMode = computed(() => profile.value && !profile.value.wizard_completed)
const saveLabel = computed(() => wizardMode.value ? '保存并继续' : '保存修改')
const currentLabel = computed(() => students.value.find(s => s.id === studentId.value)?.display_name || '请选择学生')
const studentColumns = computed(() => students.value.map(s => ({ text: s.display_name, value: s.id })))
const currentSchool = computed(() => {
  const list = profile.value?.education?.history || []
  return list.find(s => s.is_current) || list[0]
})

function targetsBy(level) { return (profile.value?.goals?.targets || []).filter(t => t.priority_level === level) }
function countPri(level) { return targetsBy(level).length }
function gradesFor(id) { return (profile.value?.courses?.grades || []).filter(g => g.course_id === id) }
function onlyCurrent(idx) { profile.value.education.history.forEach((row, i) => { row.is_current = i === idx }) }
function addGrade(c) { profile.value.courses.grades.push(emptyGrade({ course_id: c.id, subject: c.subject, is_predicted: false })) }
function syncCurricula() { profile.value.courses.curricula = curriculaText.value.split(/[,，]/).map(s => s.trim()).filter(Boolean) }
function addMathBundle() {
  if (!profile.value.courses.curricula.includes('A-Level')) profile.value.courses.curricula.push('A-Level')
  curriculaText.value = profile.value.courses.curricula.join(',')
  const math = emptyCourse({ subject: 'Mathematics', qualification: 'A-Level', level: 'AS', exam_board: 'CCEA', start_year: '2025', end_year: '2027' })
  profile.value.courses.items.push(math, emptyCourse({ subject: 'Further Mathematics', qualification: 'A-Level' }), emptyCourse({ subject: 'Physics', qualification: 'A-Level' }))
  profile.value.courses.grades.push(
    emptyGrade({ course_id: math.id, subject: 'Mathematics', exam_session: 'AS', grade_type: 'Actual', grade: 'A' }),
    emptyGrade({ course_id: math.id, subject: 'Mathematics', exam_session: 'A2', grade_type: 'Predicted', grade: 'A*', is_predicted: true }),
  )
}

function apply(r) {
  profile.value = r.profile
  completeness.value = r.completeness || { percent: 0, missing: [] }
  curriculaText.value = (profile.value.courses.curricula || []).join(',')
  studentId.value = r.id
}

async function loadList() {
  if (!getSaasToken()) {
    showFailToast('登录后可云端保存学生档案')
    return
  }
  try {
    const r = await saasApi.students()
    students.value = r.students || []
    if (students.value[0] && !studentId.value) await open(students.value[0].id)
  } catch (e) {
    showFailToast(e.message || '加载失败')
  }
}
async function createStudent() {
  try {
    const r = await saasApi.createStudent({ wizard: true, profile: {} })
    apply(r)
    section.value = 'basic_info'
    await loadList()
    showSuccessToast('已创建学生')
  } catch (e) { showFailToast(e.message || '请先登录') }
}
async function open(id) {
  const r = await saasApi.student(id)
  apply(r)
}
function onPickStudent({ selectedOptions }) {
  showPicker.value = false
  const id = selectedOptions?.[0]?.value
  if (id) open(id)
}
async function save(key) {
  if (!studentId.value) return
  if (key === 'courses') syncCurricula()
  saving.value = true
  try {
    const r = await saasApi.patchStudentSection(studentId.value, key, profile.value[key])
    apply(r)
    showSuccessToast('已保存')
    if (wizardMode.value) {
      const idx = sections.findIndex(s => s.key === key)
      if (idx >= 0 && idx < sections.length - 1) section.value = sections[idx + 1].key
      if (key === 'summary') await saasApi.completeStudentWizard(studentId.value)
    }
    await loadList()
  } catch (e) { showFailToast(e.message || '保存失败') }
  finally { saving.value = false }
}
function goJudge(kind) {
  emit('goto-judge', {
    kind,
    studentId: studentId.value,
    prefills: {
      name: profile.value.basic_info.chinese_name || profile.value.basic_info.english_name,
      birth_date: profile.value.basic_info.birth_date,
      current_nationality: profile.value.identity.current_nationality,
      has_foreign_nationality: profile.value.identity.has_foreign_nationality,
      has_chinese_nationality: profile.value.identity.has_chinese_nationality,
      foreign_nationality_acquired_date: profile.value.identity.foreign_nationality_acquired_date,
      passport_info: profile.value.identity.passport_info,
    },
  })
}
async function confirmWB(kind) {
  const card = profile.value.identity[kind]
  const r = await saasApi.studentWriteback(studentId.value, { kind, result: card.engine_result, conclusion: card.conclusion, record_id: card.record_id, policy_version: card.policy_version || 'R4.2', confirm: true })
  apply(r)
  showSuccessToast('已确认写入学生档案')
}
async function loadTimeline() {
  const r = await saasApi.studentTimeline(studentId.value)
  timeline.value = r.matches || []
}
onMounted(loadList)
defineExpose({ loadList })
</script>
