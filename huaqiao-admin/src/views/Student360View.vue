<template>
  <div v-if="data">
    <div class="gq-grid-2">
      <div>
        <h1 class="page-title">Student 360 · #{{ data.student_id }}</h1>
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
            <el-tab-pane label="目标大学/专业"><pre class="gq-pre">{{ pretty(data.sections.goals) }}</pre></el-tab-pane>
          </el-tabs>
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

async function load() {
  data.value = await api.student360(props.studentId)
  kinds.value = data.value.report_kinds || {}
  await refreshDrafts()
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
