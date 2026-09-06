<template>
  <div v-if="data" class="m-page">
    <header class="m-hd">
      <button type="button" class="back" @click="$router.back()">‹ 返回</button>
      <h1>{{ displayName }}</h1>
      <p class="gq-muted">#{{ data.student_id }} · {{ human(owner.email) }}</p>
      <div class="ops-banner">
        <div class="hi"><span class="k">姓名</span><span class="v">{{ displayName }}</span></div>
        <div class="hi"><span class="k">Student ID</span><span class="v">{{ data.student_id }}</span></div>
        <div class="hi"><span class="k">身份路线</span><span class="v">{{ human(crm.identity_track || identityRoute) }}</span></div>
        <div class="hi"><span class="k">阶段</span><span class="v">{{ human(crm.crm_stage_label || ops.crm_stage_label, EMPTY.unassigned) }}</span></div>
        <div class="hi"><span class="k">负责人</span><span class="v">{{ human(crm.assignee_label || ops.assignee_label, EMPTY.unassigned) }}</span></div>
        <div class="hi"><span class="k">风险</span><span class="v"><el-tag size="small" :type="riskTagType(crm.risk_level)">{{ riskLabel(crm.risk_level) }}</el-tag></span></div>
        <div class="hi"><span class="k">下一步</span><span class="v">{{ human(crm.next_action || ops.next_action, EMPTY.unset) }}</span></div>
        <div class="hi"><span class="k">下次跟进</span><span class="v">{{ humanDateTime(crm.next_follow_up_at || ops.next_follow_up_at, EMPTY.unset) }}</span></div>
        <div><span class="k">套餐</span><span class="v">{{ planLabel }}</span></div>
      </div>
      <div class="quick">
        <button type="button" @click="tab = 'follow'">记跟进</button>
        <button type="button" @click="$router.push(`/m/ai/${studentId}`)">AI建议</button>
        <button type="button" @click="tab = 'timeline'">时间线</button>
        <button type="button" @click="tab = 'consult'">专家规划</button>
      </div>
    </header>

    <el-tabs v-model="tab" class="tabs">
      <el-tab-pane label="概览" name="overview">
        <section class="gq-panel block">
          <h3>学生概览</h3>
          <dl class="dl">
            <div><dt>姓名</dt><dd>{{ displayName }}</dd></div>
            <div><dt>身份路线</dt><dd>{{ human(crm.identity_track || identityRoute) }}</dd></div>
            <div><dt>所属账号</dt><dd>{{ human(owner.email || owner.name) }}</dd></div>
            <div><dt>最后更新</dt><dd>{{ humanDateTime(meta.updated_at) }}</dd></div>
          </dl>
        </section>
        <section class="gq-panel block">
          <h3>资格</h3>
          <div class="elig-row">
            <span>国际生</span>
            <el-tag size="small" :type="eligIntl.type">{{ eligIntl.label }}</el-tag>
          </div>
          <div class="elig-row">
            <span>华侨生</span>
            <el-tag size="small" :type="eligHq.type">{{ eligHq.label }}</el-tag>
          </div>
        </section>
        <section class="gq-panel block">
          <h3>CSCA</h3>
          <dl class="dl">
            <div><dt>状态</dt><dd>{{ cscaStatusLabel(csca.csca_status, csca.csca_status_label) }}</dd></div>
            <div><dt>考试日期</dt><dd>{{ humanDate(csca.csca_exam_date, EMPTY.official) }}</dd></div>
            <div><dt>成绩</dt><dd>{{ human(csca.csca_score) }}</dd></div>
          </dl>
        </section>
        <section class="gq-panel block">
          <h3>下一步 / 风险</h3>
          <p><strong>下一步：</strong>{{ human(crm.next_action || ops.next_action) }}</p>
          <p><strong>时间线：</strong>{{ timelineRiskHint }}</p>
          <p><strong>最近跟进：</strong>{{ human(latestFollowHint, EMPTY.none) }}</p>
        </section>
        <el-button type="primary" style="width:100%" @click="$router.push(`/m/ai/${studentId}`)">
          打开 AI 专家
        </el-button>
      </el-tab-pane>

      <el-tab-pane label="档案" name="profile">
        <section class="gq-panel block">
          <h3>基本资料</h3>
          <p v-if="canEditProfile" class="gq-muted">仅超级管理员可修改并保存学生姓名与基本资料。</p>
          <div v-if="canEditProfile" class="basic-edit">
            <el-input v-model="basicForm.chinese_name" maxlength="80" placeholder="中文姓名" />
            <el-input v-model="basicForm.english_name" maxlength="80" placeholder="英文名" />
            <el-input v-model="basicForm.birth_date" maxlength="10" placeholder="出生日期 YYYY-MM-DD" />
            <el-select v-model="basicForm.gender" clearable placeholder="性别">
              <el-option label="男" value="男" />
              <el-option label="女" value="女" />
              <el-option label="其他" value="其他" />
              <el-option label="未说明" value="未说明" />
            </el-select>
            <el-input v-model="basicForm.current_country" maxlength="80" placeholder="当前国家" />
            <el-input v-model="basicForm.current_city" maxlength="80" placeholder="当前城市" />
            <el-input v-model="basicForm.contact" maxlength="80" placeholder="联系方式" />
            <el-input v-model="basicForm.intended_entry_year" maxlength="4" placeholder="入学年份" />
            <el-button type="primary" :loading="basicSaving" style="width:100%" @click="saveBasic">保存基本资料</el-button>
          </div>
          <dl class="dl">
            <div><dt>学生姓名</dt><dd>{{ human(basic.chinese_name || displayName) }}</dd></div>
            <div><dt>英文名</dt><dd>{{ human(basic.english_name) }}</dd></div>
            <div><dt>出生日期</dt><dd>{{ humanDate(basic.birth_date) }}</dd></div>
            <div><dt>性别</dt><dd>{{ human(basic.gender) }}</dd></div>
            <div><dt>国家 / 城市</dt><dd>{{ human(basic.current_country) }} / {{ human(basic.current_city) }}</dd></div>
            <div><dt>联系方式</dt><dd>{{ human(basic.contact) }}</dd></div>
            <div><dt>入学年份</dt><dd>{{ human(basic.intended_entry_year) }}</dd></div>
            <div><dt>所属用户</dt><dd>{{ human(owner.name) }} · {{ human(owner.email) }}</dd></div>
            <div><dt>套餐 / Trial</dt><dd>{{ planLabel }} · {{ trialLabel }}</dd></div>
          </dl>
        </section>

        <section class="gq-panel block">
          <h3>身份 / 国籍</h3>
          <dl class="dl">
            <div><dt>出生国家</dt><dd>{{ human(identity.birth_country) }}</dd></div>
            <div><dt>当前国籍</dt><dd>{{ human(identity.current_nationality) }}</dd></div>
            <div><dt>曾用国籍</dt><dd>{{ human(identity.former_nationalities) }}</dd></div>
            <div><dt>曾有中国国籍</dt><dd>{{ humanBool(identity.had_chinese_nationality) }}</dd></div>
            <div><dt>中国户籍</dt><dd>{{ humanBool(identity.has_chinese_hukou) }}</dd></div>
            <div><dt>国际生状态</dt><dd>{{ human(identity.international?.status || identity.international?.conclusion, EMPTY.judge) }}</dd></div>
            <div><dt>华侨生状态</dt><dd>{{ human(identity.huaqiao?.status || identity.huaqiao?.conclusion, EMPTY.judge) }}</dd></div>
          </dl>
        </section>

        <section class="gq-panel block">
          <h3>教育背景</h3>
          <dl class="dl">
            <div><dt>当前学校</dt><dd>{{ human(currentSchool.school_name || currentSchool.name) }}</dd></div>
            <div><dt>课程体系</dt><dd>{{ human(pick(currentSchool.curriculum, currentSchool.school_type)) }}</dd></div>
            <div><dt>年级</dt><dd>{{ human(currentSchool.current_grade || currentSchool.grade) }}</dd></div>
            <div><dt>预计毕业</dt><dd>{{ humanDate(currentSchool.end_date || currentSchool.expected_graduation) }}</dd></div>
          </dl>
        </section>

        <section class="gq-panel block">
          <h3>语言成绩</h3>
          <article v-for="(row, i) in languageRows" :key="i" class="mini-card">
            <strong>{{ human(row.exam_type || row.exam) }}</strong>
            <p>{{ human(row.overall_score || row.score) }} · {{ human(row.level || row.band, '—') }} · {{ human(row.status, '已取得') }}</p>
          </article>
          <p v-if="!languageRows.length" class="gq-muted">{{ EMPTY.none }}</p>
        </section>

        <section class="gq-panel block">
          <h3>CSCA 考试</h3>
          <dl class="dl">
            <div><dt>状态</dt><dd>{{ cscaStatusLabel(csca.csca_status, csca.csca_status_label) }}</dd></div>
            <div><dt>报名截止</dt><dd>{{ humanDate(csca.csca_registration_deadline, EMPTY.official) }}</dd></div>
            <div><dt>考试日期</dt><dd>{{ humanDate(csca.csca_exam_date, EMPTY.official) }}</dd></div>
            <div><dt>成绩发布</dt><dd>{{ humanDate(csca.csca_result_date, EMPTY.official) }}</dd></div>
            <div><dt>成绩 / 等级</dt><dd>{{ human(csca.csca_score) }} / {{ human(csca.csca_level) }}</dd></div>
            <div><dt>备注</dt><dd>{{ human(csca.csca_notes, EMPTY.none) }}</dd></div>
          </dl>
        </section>

        <section class="gq-panel block">
          <h3>目标大学 / 专业</h3>
          <article v-for="(row, i) in targetRows" :key="i" class="mini-card">
            <strong>{{ human(row.university_name || row.university) }}</strong>
            <p>{{ human(row.major || row.college) }} · {{ targetPriorityLabel(row.priority_level || row.priority) }} · {{ human(row.status || row.application_route, '—') }}</p>
          </article>
          <p v-if="!targetRows.length" class="gq-muted">{{ EMPTY.noTargets }}</p>
        </section>
      </el-tab-pane>

      <el-tab-pane label="时间线" name="timeline">
        <article v-for="(t, i) in timelineRows" :key="i" class="tl">
          <strong>{{ human(t.title || t.name) }}</strong>
          <p class="gq-muted">
            {{ humanDate(t.deadline || t.target_date) }}
            · {{ timelineStatusLabel(t.status) }}
            · {{ daysRemainingLabel(t.deadline || t.target_date) }}
          </p>
        </article>
        <p v-if="!timelineRows.length" class="gq-muted">{{ EMPTY.none }}</p>
      </el-tab-pane>

      <el-tab-pane label="跟进" name="follow">
        <div class="follow-form">
          <el-input v-model="followContent" type="textarea" :rows="3" placeholder="人工跟进内容" />
          <el-input v-model="followNext" placeholder="下一步" style="margin-top:8px" />
          <el-button type="primary" style="width:100%;margin-top:8px" @click="saveFollowUp">保存人工跟进</el-button>
        </div>
        <article v-for="(row, i) in followRows" :key="i" class="tl">
          <div class="row">
            <strong>{{ humanDateTime(row.created_at) }}</strong>
            <el-tag size="small" :type="followSourceTag(row.source)">{{ followSourceLabel(row.source) }}</el-tag>
          </div>
          <p>{{ human(row.summary || row.content) }}</p>
          <p class="gq-muted">下一步：{{ human(row.next_action, '—') }} · {{ human(row.operator_label || row.operator_name, '—') }}</p>
        </article>
        <p v-if="!followRows.length" class="gq-muted">{{ EMPTY.none }}</p>
      </el-tab-pane>

      <el-tab-pane label="咨询" name="consult">
        <section class="gq-panel block ai-ctx">
          <h3>AI 上下文摘要</h3>
          <ul>
            <li>学生：{{ displayName }}</li>
            <li>目标：{{ human(goalHint, EMPTY.noTargets) }}</li>
            <li>资格：国际生 {{ eligIntl.label }} · 华侨生 {{ eligHq.label }}</li>
            <li>CSCA：{{ cscaStatusLabel(csca.csca_status, csca.csca_status_label) }}</li>
            <li>时间线风险：{{ timelineRiskHint }}</li>
            <li>下一步：{{ human(crm.next_action || ops.next_action) }}</li>
          </ul>
        </section>
        <article
          v-for="d in history"
          :key="d.id"
          class="tl"
          role="button"
          @click="openDraft(d)"
        >
          <div class="row">
            <strong>{{ kindLabel(d.report_kind) }}</strong>
            <el-tag size="small" :type="statusType(d.status)">{{ d.status }}</el-tag>
          </div>
          <p class="gq-muted">#{{ d.id }} · {{ humanDateTime(d.updated_at || d.created_at) }}</p>
        </article>
        <p v-if="!history.length" class="gq-muted">{{ EMPTY.none }}</p>
      </el-tab-pane>
    </el-tabs>

    <MobileBottomSheet v-model="sheetOpen" :title="sheetTitle">
      <div class="sheet-body">{{ sheetBody }}</div>
    </MobileBottomSheet>
  </div>
  <div v-else class="pad gq-muted">{{ error || '加载中…' }}</div>
</template>

<script setup>
import { computed, onMounted, ref, toRef } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import { useAdminSession } from '../composables/useAdminSession'
import { useStudentAi } from '../composables/useStudentAi'
import MobileBottomSheet from './MobileBottomSheet.vue'
import {
  EMPTY,
  human,
  humanBool,
  humanDate,
  humanDateTime,
  pick,
  cscaStatusLabel,
  riskLabel,
  riskTagType,
  eligibilityBadge,
  followSourceLabel,
  followSourceTag,
  timelineStatusLabel,
  daysRemaining,
  daysRemainingLabel,
  targetPriorityLabel,
} from '../utils/opsDisplay'

const props = defineProps({ studentId: { type: [String, Number], required: true } })
const { can } = useAdminSession()
const canEditProfile = computed(() => can('student360.profile.write'))
const basicSaving = ref(false)
const basicForm = ref({
  chinese_name: '',
  english_name: '',
  birth_date: '',
  gender: '',
  current_country: '',
  current_city: '',
  contact: '',
  intended_entry_year: '',
})
const data = ref(null)
const error = ref('')
const tab = ref('overview')
const sheetOpen = ref(false)
const sheetTitle = ref('')
const sheetBody = ref('')
const followContent = ref('')
const followNext = ref('')

const { history, kindLabel, statusType, bootstrap } = useStudentAi(toRef(props, 'studentId'))

const sections = computed(() => data.value?.sections || {})
const basic = computed(() => sections.value.basic_info || {})
const identity = computed(() => sections.value.identity || {})
const education = computed(() => sections.value.education || {})
const goals = computed(() => sections.value.goals || {})
const owner = computed(() => data.value?.owner || {})
const meta = computed(() => data.value?.meta || {})
const crm = computed(() => data.value?.crm || {})
const ops = computed(() => data.value?.ops_header || {})
const csca = computed(() => data.value?.csca_card || sections.value.csca || {})
const currentSchool = computed(() => education.value.current_school || {})
const languageRows = computed(() => (Array.isArray(sections.value.language_exams) ? sections.value.language_exams : []))
const targetRows = computed(() => (Array.isArray(goals.value.targets) ? goals.value.targets : []))
const timelineRows = computed(() => (Array.isArray(data.value?.timeline) ? data.value.timeline : []))
const followRows = computed(() => (Array.isArray(data.value?.follow_ups) ? data.value.follow_ups : []))

const displayName = computed(() => {
  const raw = pick(ops.value.display_name, crm.value.display_name, meta.value.display_name, basic.value.chinese_name, basic.value.english_name)
  if (!raw || String(raw).includes('@')) return EMPTY.name
  return human(raw, EMPTY.name)
})
const planLabel = computed(() => {
  const code = owner.value.plan_code
  if (!code) return EMPTY.pending
  if (owner.value.is_paid && !String(code).toLowerCase().includes('trial')) return `${code}（付费）`
  return String(code)
})
const trialLabel = computed(() => {
  const t = owner.value.trial || {}
  if (t.trial_active) return '试用中'
  if (t.trial_expired) return '试用已结束'
  if (owner.value.is_paid) return '非试用 / 付费'
  return EMPTY.pending
})
const identityRoute = computed(() => {
  const intl = identity.value.international?.status
  const hq = identity.value.huaqiao?.status
  if (intl || hq) return [intl && `国际生:${intl}`, hq && `华侨生:${hq}`].filter(Boolean).join(' · ')
  return null
})
const eligIntl = computed(() => eligibilityBadge(data.value?.eligibility?.international?.conclusion, data.value?.eligibility?.international?.qualified))
const eligHq = computed(() => eligibilityBadge(data.value?.eligibility?.huaqiao?.conclusion, data.value?.eligibility?.huaqiao?.qualified))
const goalHint = computed(() => {
  if (!targetRows.value.length) return goals.value.goals_notes || null
  return targetRows.value.slice(0, 3).map((t) => `${t.university_name || t.university || ''} ${t.major || ''}`.trim()).filter(Boolean).join('；')
})
const timelineRiskHint = computed(() => {
  const rows = timelineRows.value
  if (!rows.length) return EMPTY.none
  const overdue = rows.filter((r) => {
    const n = daysRemaining(r.deadline || r.target_date)
    return n != null && n < 0 && !/DONE|COMPLETED/i.test(String(r.status || ''))
  })
  const soon = rows.filter((r) => {
    const n = daysRemaining(r.deadline || r.target_date)
    return n != null && n >= 0 && n <= 7 && !/DONE|COMPLETED/i.test(String(r.status || ''))
  })
  if (overdue.length) return `${overdue.length} 项逾期`
  if (soon.length) return `${soon.length} 项 7 日内到期`
  return '暂无紧急项'
})
const latestFollowHint = computed(() => {
  const row = followRows.value[0]
  if (!row) return null
  return `${humanDateTime(row.created_at, '')} ${row.summary || row.content || ''}`.trim()
})

function openDraft(d) {
  sheetTitle.value = `${kindLabel(d.report_kind)} · ${d.status}`
  sheetBody.value = d.final_report || d.raw_draft || d.content || '（空）'
  sheetOpen.value = true
}

function syncBasicForm() {
  const b = data.value?.sections?.basic_info || {}
  basicForm.value = {
    chinese_name: b.chinese_name || '',
    english_name: b.english_name || '',
    birth_date: String(b.birth_date || '').slice(0, 10),
    gender: b.gender || '',
    current_country: b.current_country || '',
    current_city: b.current_city || '',
    contact: b.contact || '',
    intended_entry_year: b.intended_entry_year || '',
  }
}

async function saveBasic() {
  if (!canEditProfile.value) {
    ElMessage.error('仅超级管理员可修改学生姓名与基本资料')
    return
  }
  const cn = String(basicForm.value.chinese_name || '')
  const en = String(basicForm.value.english_name || '')
  if (cn.includes('@') || en.includes('@')) {
    ElMessage.error('姓名不能使用邮箱')
    return
  }
  basicSaving.value = true
  try {
    await api.patchStudentBasic(props.studentId, { ...basicForm.value })
    ElMessage.success('学生基本资料已保存')
    data.value = await api.student360(props.studentId)
    syncBasicForm()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    basicSaving.value = false
  }
}

async function saveFollowUp() {
  if (!followContent.value.trim()) return
  try {
    await api.createFollowUp(props.studentId, {
      content: followContent.value,
      next_action: followNext.value || null,
      source: 'HUMAN',
    })
    followContent.value = ''
    followNext.value = ''
    ElMessage.success('跟进已保存')
    data.value = await api.student360(props.studentId)
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

onMounted(async () => {
  try {
    data.value = await api.student360(props.studentId)
    syncBasicForm()
    await bootstrap(data.value.report_kinds)
  } catch (e) {
    error.value = e.message || '加载失败'
  }
})
</script>

<style scoped>
.m-page {
  padding: 8px 14px 12px;
  max-width: 100vw;
  overflow-x: hidden;
  box-sizing: border-box;
}
.ops-banner .v { word-break: break-word; }
.m-hd h1 { margin: 4px 0 0; font-size: 20px; }
.m-hd p { margin: 4px 0 8px; }
.back { border: 0; background: transparent; color: var(--gq-sea); font-size: 15px; padding: 0; }
.block { margin-bottom: 10px; }
.block h3 { margin: 0 0 8px; font-size: 15px; }
.ops-banner {
  background: #eff6ff;
  border-radius: 10px;
  padding: 10px;
  margin: 8px 0;
  font-size: 13px;
  display: grid;
  gap: 6px;
}
.ops-banner .k { color: #64748b; margin-right: 6px; }
.ops-banner .v { font-weight: 600; color: #142033; }
.ops-banner .hi .v { color: #1b4f72; }
.quick { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 8px 0 12px; }
.quick button { border: 1px solid #cbd5e1; border-radius: 10px; padding: 10px; background: #fff; }
.dl { margin: 0; display: grid; gap: 6px; }
.dl > div { display: grid; grid-template-columns: 96px 1fr; gap: 8px; font-size: 13px; }
.dl dt { margin: 0; color: #64748b; }
.dl dd { margin: 0; color: #142033; word-break: break-word; }
.elig-row { display: flex; justify-content: space-between; align-items: center; margin: 6px 0; font-size: 13px; }
.mini-card, .tl {
  border: 1px solid var(--gq-border);
  border-radius: 10px;
  padding: 10px;
  background: #fff;
  margin-bottom: 8px;
}
.mini-card p, .tl p { margin: 4px 0 0; font-size: 13px; }
.row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.pad { padding: 24px 14px; }
.ai-ctx ul { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.6; }
.sheet-body {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.55;
  color: #1e293b;
  background: #fff;
  padding: 4px 2px;
  max-height: 55vh;
  overflow: auto;
}
.follow-form { margin-bottom: 12px; }
.basic-edit { display: grid; gap: 8px; margin: 0 0 12px; }
</style>
