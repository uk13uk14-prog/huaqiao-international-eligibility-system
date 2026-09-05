<template>
  <div v-if="data">
    <div class="gq-grid-2">
      <div>
        <h1 class="page-title">Student 360 · {{ data.ops_header?.display_name || data.meta?.display_name || ('#' + data.student_id) }}</h1>
        <div class="ops-banner" v-if="data.crm || data.ops_header">
          <div><b>负责人</b>：{{ data.ops_header?.assignee_label || data.crm?.assignee_label || '未分配' }}</div>
          <div><b>阶段</b>：{{ data.ops_header?.crm_stage_label || data.crm?.crm_stage_label || '—' }}</div>
          <div><b>下一步</b>：{{ data.ops_header?.next_action || data.crm?.next_action || '—' }}</div>
          <div><b>下次跟进</b>：{{ data.ops_header?.next_follow_up_at || data.crm?.next_follow_up_at || '—' }}</div>
        </div>
        <div class="ops-actions">
          <el-select v-model="assignTo" clearable placeholder="分配负责人" style="width:180px">
            <el-option label="未分配" :value="0" />
            <el-option v-for="s in staff" :key="s.id" :label="s.label" :value="s.id" />
          </el-select>
          <el-button size="small" type="primary" @click="doAssign">分配负责人</el-button>
          <el-select v-model="stageEdit" placeholder="阶段" style="width:140px">
            <el-option v-for="(label, key) in stageLabels" :key="key" :label="label" :value="key" />
          </el-select>
          <el-button size="small" @click="saveStage">更新阶段</el-button>
        </div>
        <p class="page-sub gq-muted">
          {{ data.meta?.display_name }} · 所属用户 {{ data.owner?.email }} · student_id={{ data.student_id }}
        </p>

        <section class="gq-panel block">
          <h3>基本资料 / 所属用户</h3>
          <pre class="gq-pre">{{ pretty({ basic: data.sections.basic_info, owner: data.owner }) }}</pre>
        </section>
        <section class="gq-panel block">
          <h3>档案分节</h3>
          <el-tabs>
            <el-tab-pane label="身份/国籍"><pre class="gq-pre">{{ pretty(data.sections.identity) }}</pre></el-tab-pane>
            <el-tab-pane label="教育背景"><pre class="gq-pre">{{ pretty(data.sections.education) }}</pre></el-tab-pane>
            <el-tab-pane label="语言成绩"><pre class="gq-pre">{{ pretty(data.sections.language_exams) }}</pre></el-tab-pane>
            <el-tab-pane label="CSCA考试"><pre class="gq-pre">{{ pretty(data.csca_card || data.sections.csca) }}</pre></el-tab-pane>
            <el-tab-pane label="目标大学/专业"><pre class="gq-pre">{{ pretty(data.sections.goals) }}</pre></el-tab-pane>
          </el-tabs>
        </section>
        
        <section class="gq-panel block" v-if="data.csca_card || data.sections?.csca">
          <h3>CSCA 考试</h3>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="状态">{{ data.csca_card?.csca_status_label || data.sections?.csca?.csca_status || '—' }}</el-descriptions-item>
            <el-descriptions-item label="报名截止">{{ data.csca_card?.csca_registration_deadline || '待官方公布' }}</el-descriptions-item>
            <el-descriptions-item label="考试日期">{{ data.csca_card?.csca_exam_date || '待官方公布' }}</el-descriptions-item>
            <el-descriptions-item label="成绩发布">{{ data.csca_card?.csca_result_date || '待官方公布' }}</el-descriptions-item>
            <el-descriptions-item label="成绩">{{ data.csca_card?.csca_score || '—' }}</el-descriptions-item>
            <el-descriptions-item label="等级">{{ data.csca_card?.csca_level || data.sections?.csca?.csca_level || '—' }}</el-descriptions-item>
            <el-descriptions-item label="备注">{{ data.csca_card?.csca_notes || data.sections?.csca?.csca_notes || '—' }}</el-descriptions-item>
            <el-descriptions-item label="日期来源">
              报名={{ data.csca_card?.registration_deadline_source || data.sections?.csca?.registration_deadline_source || '—' }}
              · 考试={{ data.csca_card?.exam_date_source || data.sections?.csca?.exam_date_source || '—' }}
              · 成绩={{ data.csca_card?.result_date_source || data.sections?.csca?.result_date_source || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="最近更新">{{ data.csca_card?.updated_at || data.sections?.csca?.updated_at || '—' }}</el-descriptions-item>
          </el-descriptions>
          <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
            <el-select v-model="cscaForm.csca_status" placeholder="状态" style="width:160px">
              <el-option v-for="o in cscaStatuses" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-input v-model="cscaForm.csca_registration_deadline" placeholder="报名截止 YYYY-MM-DD" style="width:180px" />
            <el-input v-model="cscaForm.csca_exam_date" placeholder="考试日期 YYYY-MM-DD" style="width:180px" />
            <el-input v-model="cscaForm.csca_result_date" placeholder="成绩发布 YYYY-MM-DD" style="width:180px" />
            <el-input v-model="cscaForm.csca_score" placeholder="成绩" style="width:120px" />
            <el-input v-model="cscaForm.csca_level" placeholder="等级" style="width:120px" />
            <el-input v-model="cscaForm.csca_notes" placeholder="备注" style="width:200px" />
            <el-button type="primary" size="small" :loading="cscaSaving" @click="saveCsca">协助更新（审计）</el-button>
          </div>
          <p class="gq-muted" style="margin-top:6px">仅可填写真实日期；留空表示待官方公布。禁止编造。</p>
        </section>

        <section class="gq-panel block">
          <h3>资格结果</h3>
          <el-alert
            v-if="data.eligibility?.mapping_status === 'UNRESOLVED'"
            type="warning"
            :closable="false"
            title="历史资格记录尚未绑定到具体学生"
            :description="data.eligibility.message"
            style="margin-bottom:10px"
          />
          <el-tag>{{ data.eligibility?.mapping_status }}</el-tag>
          <div style="margin-top:8px"><strong>国际生：</strong>{{ data.eligibility?.international?.conclusion || '—' }}</div>
          <div><strong>华侨生：</strong>{{ data.eligibility?.huaqiao?.conclusion || '—' }}</div>
        </section>
        <section class="gq-panel block">
          <h3>时间线</h3>
          <el-table :data="data.timeline || []" size="small">
            <el-table-column prop="title" label="事项" />
            <el-table-column prop="deadline" label="截止" width="120" />
            <el-table-column prop="status" label="状态" width="120" />
          </el-table>
        </section>
      </div>

      <aside class="gq-panel ai-panel">
        <h2 style="margin-top:0">AI 专家工作台</h2>
        <p class="gq-muted">student_id={{ data.student_id }} · {{ data.ai_provider?.AI_PROVIDER }}</p>
        <div style="margin:12px 0;display:flex;flex-wrap:wrap;gap:8px">
          <el-button
            v-for="(label, kind) in kinds"
            :key="kind"
            size="small"
            :loading="generating === kind"
            @click="generate(kind)"
          >生成·{{ label }}</el-button>
        </div>
        <div class="flow gq-muted">AI Generate → DRAFT → REVIEWED → APPROVED → PUBLISHED</div>
        <div v-if="activeDraft" style="margin-top:12px">
          <el-tag :type="statusType(activeDraft.status)" effect="dark">{{ activeDraft.status }}</el-tag>
          <span class="gq-muted" style="margin-left:8px">
            {{ activeDraft.report_kind }} · {{ activeDraft.ai_provider }}/{{ activeDraft.ai_model }}
            · v{{ activeDraft.version_count || 0 }}
          </span>
          <el-input
            v-model="editContent"
            type="textarea"
            :rows="12"
            style="margin-top:8px"
            :disabled="activeDraft.status === 'PUBLISHED'"
          />
          <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">
            <el-button
              v-if="canEdit"
              size="small"
              @click="saveEdit"
            >编辑 / 提交审核</el-button>
            <el-button
              v-if="canApprove"
              size="small"
              type="success"
              @click="approve"
            >批准</el-button>
            <el-button
              v-if="canPublish"
              size="small"
              type="danger"
              @click="publish"
            >发布</el-button>
            <el-tag v-if="activeDraft.status === 'PUBLISHED'" type="success">已发布 · 只读（请新建新版本）</el-tag>
          </div>
          <p v-if="msg" class="gq-muted" style="margin-top:8px">{{ msg }}</p>
        </div>
      </aside>
    </div>

    <section class="gq-panel" style="margin-top:16px">
      <h3>跟进记录</h3>
      <div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap">
        <el-input v-model="followContent" type="textarea" :rows="2" placeholder="人工跟进内容" style="flex:1;min-width:240px" />
        <el-input v-model="followNext" placeholder="下一步" style="width:200px" />
        <el-button type="primary" @click="saveFollowUp">记跟进</el-button>
        <el-button @click="loadAiDrafts">AI建议(草稿)</el-button>
      </div>
      <el-alert v-if="aiDrafts.length" type="info" :closable="false" title="AI 建议仅草稿，不会自动发送" style="margin-bottom:8px" />
      <el-table :data="aiDrafts" size="small" v-if="aiDrafts.length" style="margin-bottom:8px">
        <el-table-column prop="action" label="动作" width="140" />
        <el-table-column prop="content" label="草稿内容" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="acceptAiDraft(row)">确认为跟进</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-table :data="data.follow_ups || []" size="small">
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="operator_label" label="操作人" width="120" />
        <el-table-column prop="source" label="来源" width="110" />
        <el-table-column prop="content" label="内容" />
        <el-table-column prop="next_action" label="下一步" width="160" />
      </el-table>
    </section>

    <section class="gq-panel" style="margin-top:16px">
      <h3>Consultation History</h3>
      <el-table :data="history" size="small" @row-click="selectDraft" style="cursor:pointer">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="report_kind" label="report_kind" width="160" />
        <el-table-column label="status" width="140">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
            <el-tag v-if="row.status === 'PUBLISHED'" type="success" size="small" style="margin-left:4px">已发布</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="provider/model" min-width="180">
          <template #default="{ row }">{{ row.ai_provider }}/{{ row.ai_model }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="created_at" width="170" />
        <el-table-column prop="updated_at" label="updated_at" width="170" />
        <el-table-column prop="version_count" label="versions" width="90" />
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

const props = defineProps({ studentId: { type: [String, Number], required: true } })
const data = ref(null)
const kinds = ref({})
const drafts = ref([])
const activeDraft = ref(null)
const editContent = ref('')
const generating = ref('')
const msg = ref('')
const cscaSaving = ref(false)
const cscaForm = ref({
  csca_status: 'NOT_PLANNED',
  csca_registration_deadline: '',
  csca_exam_date: '',
  csca_result_date: '',
  csca_score: '',
  csca_level: '',
  csca_notes: '',
})
const cscaStatuses = [
  { value: 'NOT_PLANNED', label: '未计划' },
  { value: 'PLANNED', label: '计划参加' },
  { value: 'REGISTERED', label: '已报名' },
  { value: 'TAKEN', label: '已考试' },
  { value: 'RESULT_AVAILABLE', label: '成绩已出' },
]

const history = computed(() => drafts.value || [])
const canEdit = computed(() => ['DRAFT', 'REVIEWED'].includes(activeDraft.value?.status))
const canApprove = computed(() => ['DRAFT', 'REVIEWED'].includes(activeDraft.value?.status))
const canPublish = computed(() => activeDraft.value?.status === 'APPROVED')

function pretty(v) {
  return JSON.stringify(v ?? {}, null, 2)
}
function statusType(s) {
  if (s === 'PUBLISHED') return 'success'
  if (s === 'APPROVED') return 'warning'
  if (s === 'REVIEWED') return 'info'
  return ''
}

function syncCscaFormFromData() {
  const c = data.value?.sections?.csca || data.value?.csca_card || {}
  cscaForm.value = {
    csca_status: c.csca_status || 'NOT_PLANNED',
    csca_registration_deadline: c.csca_registration_deadline_raw || c.csca_registration_deadline || '',
    csca_exam_date: c.csca_exam_date_raw || c.csca_exam_date || '',
    csca_result_date: c.csca_result_date_raw || c.csca_result_date || '',
    csca_score: c.csca_score || '',
    csca_level: c.csca_level || '',
    csca_notes: c.csca_notes || '',
  }
  // Clear pending-official display strings from inputs
  for (const k of ['csca_registration_deadline', 'csca_exam_date', 'csca_result_date']) {
    if (cscaForm.value[k] === '待官方公布') cscaForm.value[k] = ''
  }
}

async function saveCsca() {
  cscaSaving.value = true
  try {
    const payload = {}
    for (const [k, v] of Object.entries(cscaForm.value)) {
      if (v !== '' && v != null) payload[k] = v
    }
    const res = await api.patchStudentCsca(props.studentId, payload)
    ElMessage.success('CSCA 已协助更新（已记审计）')
    data.value = {
      ...data.value,
      sections: { ...(data.value.sections || {}), csca: res.csca },
      csca_card: res.csca_card,
    }
    syncCscaFormFromData()
  } catch (e) {
    ElMessage.error(e.message || 'CSCA 更新失败')
  } finally {
    cscaSaving.value = false
  }
}

const staff = ref([])
const assignTo = ref()
const stageEdit = ref('')
const stageLabels = ref({})
const followContent = ref('')
const followNext = ref('')
const aiDrafts = ref([])

async function doAssign() {
  const id = assignTo.value === 0 ? null : assignTo.value
  await api.assignStudent(props.studentId, id)
  ElMessage.success('负责人已更新')
  await load()
}
async function saveStage() {
  if (!stageEdit.value) return
  await api.patchStudentCrm(props.studentId, { crm_stage: stageEdit.value })
  ElMessage.success('阶段已更新')
  await load()
}
async function saveFollowUp() {
  if (!followContent.value.trim()) return
  await api.createFollowUp(props.studentId, {
    content: followContent.value,
    next_action: followNext.value || null,
    source: 'HUMAN',
  })
  followContent.value = ''
  followNext.value = ''
  ElMessage.success('跟进已保存')
  await load()
}
async function loadAiDrafts() {
  const r = await api.aiFollowUpDrafts(props.studentId)
  aiDrafts.value = r.drafts || []
}
async function acceptAiDraft(row) {
  await api.createFollowUp(props.studentId, {
    content: row.content,
    summary: row.action,
    source: 'AI_ASSISTED',
    type: 'AI_SUGGESTION',
  })
  ElMessage.success('已保存为 AI_ASSISTED 跟进（未自动发送）')
  aiDrafts.value = []
  await load()
}

async function load() {
  data.value = await api.student360(props.studentId)
  kinds.value = data.value.report_kinds || {}
  stageEdit.value = data.value.crm?.crm_stage || ''
  stageLabels.value = data.value.crm_stage_labels || {
    UNASSIGNED:'未分配', NEW:'新学生', CONTACTED:'已联系', PLANNING:'规划中',
    WAITING_STUDENT:'等待学生', WAITING_DOCUMENTS:'等待材料', APPLICATION:'申请中',
    FOLLOW_UP:'持续跟进', COMPLETED:'已完成', PAUSED:'暂停'
  }
  assignTo.value = data.value.crm?.assignee_user_id || 0
  syncCscaFormFromData()
  await refreshDrafts()
  try { staff.value = (await api.staff()).staff || [] } catch { staff.value = [] }
}

async function refreshDrafts() {
  const d = await api.aiDrafts(props.studentId)
  drafts.value = d.drafts || []
  if (!kinds.value || !Object.keys(kinds.value).length) kinds.value = d.report_kinds || {}
}

async function generate(kind) {
  generating.value = kind
  msg.value = ''
  try {
    const res = await api.aiGenerate(props.studentId, kind, false)
    activeDraft.value = res.draft
    editContent.value = res.draft.raw_draft || res.draft.content || ''
    ElMessage.success('已生成并持久化 DRAFT（未发布）')
    await refreshDrafts()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    generating.value = ''
  }
}

function selectDraft(row) {
  activeDraft.value = row
  editContent.value = row.raw_draft || row.final_report || ''
  msg.value = row.status === 'PUBLISHED' ? 'PUBLISHED 只读；如需修改请重新「生成」新版本' : ''
}

async function saveEdit() {
  if (!canEdit.value) return
  const res = await api.aiEdit(props.studentId, activeDraft.value.id, editContent.value, true)
  activeDraft.value = res.draft
  msg.value = `已保存 → ${res.draft.status}`
  await refreshDrafts()
}

async function approve() {
  if (!canApprove.value) return
  const res = await api.aiApprove(props.studentId, activeDraft.value.id)
  activeDraft.value = res.draft
  msg.value = '已批准 APPROVED（学生仍不可见）'
  await refreshDrafts()
}

async function publish() {
  if (!canPublish.value) return
  try {
    const res = await api.aiPublish(props.studentId, activeDraft.value.id)
    activeDraft.value = res.draft
    msg.value = '已发布 PUBLISHED（学生端可读）'
    ElMessage.success('已发布')
    await refreshDrafts()
  } catch (e) {
    msg.value = e.message
    ElMessage.warning(e.message)
  }
}

onMounted(load)
watch(() => props.studentId, load)
</script>

<style scoped>
.block { margin-bottom: 12px; }
.ai-panel {
  position: sticky;
  top: 12px;
  align-self: start;
  max-height: calc(100vh - 40px);
  overflow: auto;
}
.flow { font-size: 12px; margin-top: 4px; }
</style>

<style scoped>
.ops-banner{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:10px 12px;margin:8px 0 12px;font-size:14px}
.ops-actions{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
@media(max-width:900px){.ops-banner{grid-template-columns:1fr 1fr}}
</style>
