<template>
  <div v-if="data" class="gq-grid-2">
    <div>
      <h1 class="page-title">Student 360 · #{{ data.student_id }}</h1>
      <p class="page-sub gq-muted">
        {{ data.meta?.display_name }} · 所属用户 {{ data.owner?.email }} · 查询键 student_id={{ data.student_id }}
      </p>

      <section class="gq-panel block">
        <h3>1. 基本资料</h3>
        <pre class="gq-pre">{{ pretty(data.sections.basic_info) }}</pre>
      </section>
      <section class="gq-panel block">
        <h3>2. 所属用户</h3>
        <pre class="gq-pre">{{ pretty(data.owner) }}</pre>
      </section>
      <section class="gq-panel block">
        <h3>3–7. 档案 / 身份 / 教育 / 语言 / 目标</h3>
        <el-tabs>
          <el-tab-pane label="身份/国籍"><pre class="gq-pre">{{ pretty(data.sections.identity) }}</pre></el-tab-pane>
          <el-tab-pane label="教育背景"><pre class="gq-pre">{{ pretty(data.sections.education) }}</pre></el-tab-pane>
          <el-tab-pane label="语言成绩"><pre class="gq-pre">{{ pretty(data.sections.language_exams) }}</pre></el-tab-pane>
          <el-tab-pane label="目标大学/专业"><pre class="gq-pre">{{ pretty(data.sections.goals) }}</pre></el-tab-pane>
        </el-tabs>
        <p class="gq-muted">敏感证件默认掩码：{{ data.privacy?.note || 'masked' }}</p>
      </section>
      <section class="gq-panel block">
        <h3>8–9. 资格结果</h3>
        <el-alert
          v-if="data.eligibility?.mapping_status === 'UNRESOLVED'"
          type="warning"
          :closable="false"
          title="历史资格记录尚未绑定到具体学生"
          :description="data.eligibility.message"
          style="margin-bottom:10px"
        />
        <el-tag>{{ data.eligibility?.mapping_status }}</el-tag>
        <div style="margin-top:8px">
          <strong>国际生：</strong>
          <span>{{ data.eligibility?.international?.conclusion || '—' }}</span>
        </div>
        <div>
          <strong>华侨生：</strong>
          <span>{{ data.eligibility?.huaqiao?.conclusion || '—' }}</span>
        </div>
      </section>
      <section class="gq-panel block">
        <h3>10. 时间线</h3>
        <el-table :data="data.timeline || []" size="small">
          <el-table-column prop="title" label="事项" />
          <el-table-column prop="deadline" label="截止" width="120" />
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="university_name" label="院校" />
        </el-table>
      </section>
      <section class="gq-panel block">
        <h3>11. 历史咨询</h3>
        <el-tag>{{ data.consultations?.mapping_status }}</el-tag>
        <el-table :data="data.consultations?.db_consultations || []" size="small" style="margin-top:8px">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="title" label="标题" />
          <el-table-column prop="status" label="状态" width="120" />
        </el-table>
      </section>
      <section class="gq-panel block">
        <h3>12. 顾问备注</h3>
        <p class="gq-muted">{{ data.consultant_notes?.message }}</p>
      </section>
    </div>

    <!-- AI Expert Workspace -->
    <aside class="gq-panel ai-panel">
      <h2 style="margin-top:0">AI 专家工作台</h2>
      <p class="gq-muted">仅读取 student_id={{ data.student_id }} · 输出强制 DRAFT</p>
      <el-tag type="warning">{{ data.ai_provider?.AI_PROVIDER || 'LOCAL_TEMPLATE' }}</el-tag>
      <div style="margin:12px 0;display:flex;flex-wrap:wrap;gap:8px">
        <el-button
          v-for="(label, kind) in kinds"
          :key="kind"
          size="small"
          :loading="generating === kind"
          @click="generate(kind)"
        >{{ label }}</el-button>
      </div>
      <div class="flow gq-muted">流程：AI Generate → Draft → Edit → Approve → Publish</div>
      <div v-if="activeDraft" style="margin-top:12px">
        <span class="gq-draft-tag">{{ activeDraft.status }}</span>
        <span class="gq-muted" style="margin-left:8px">{{ activeDraft.title }} · {{ activeDraft.ai_provider }}</span>
        <el-input
          v-model="editContent"
          type="textarea"
          :rows="14"
          style="margin-top:8px"
        />
        <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">
          <el-button size="small" @click="saveEdit">保存编辑</el-button>
          <el-button size="small" type="success" @click="approve">批准</el-button>
          <el-button size="small" type="danger" @click="publish">尝试发布</el-button>
        </div>
        <p v-if="msg" class="gq-muted" style="margin-top:8px">{{ msg }}</p>
      </div>
      <div style="margin-top:16px">
        <h4>本学生草稿</h4>
        <el-table :data="drafts" size="small" @row-click="selectDraft" style="cursor:pointer">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="report_kind" label="类型" />
          <el-table-column prop="status" label="状态" width="100" />
        </el-table>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
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

function pretty(v) {
  return JSON.stringify(v ?? {}, null, 2)
}

async function load() {
  data.value = await api.student360(props.studentId)
  const k = await api.aiKinds(props.studentId)
  kinds.value = k.report_kinds || {}
  await refreshDrafts()
}

async function refreshDrafts() {
  const d = await api.aiDrafts(props.studentId)
  drafts.value = d.drafts || []
}

async function generate(kind) {
  generating.value = kind
  msg.value = ''
  try {
    const res = await api.aiGenerate(props.studentId, kind)
    activeDraft.value = res.draft
    editContent.value = res.draft.content
    ElMessage.success('已生成 DRAFT（未发布）')
    await refreshDrafts()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    generating.value = ''
  }
}

function selectDraft(row) {
  activeDraft.value = row
  editContent.value = row.content
}

async function saveEdit() {
  const res = await api.aiEdit(props.studentId, activeDraft.value.id, editContent.value)
  activeDraft.value = res.draft
  msg.value = '已保存编辑（仍为 DRAFT）'
  await refreshDrafts()
}

async function approve() {
  const res = await api.aiApprove(props.studentId, activeDraft.value.id)
  activeDraft.value = res.draft
  msg.value = '已批准（仍未发布给学生）'
  await refreshDrafts()
}

async function publish() {
  try {
    await api.aiPublish(props.studentId, activeDraft.value.id)
  } catch (e) {
    msg.value = e.message
    ElMessage.warning('发布已拦截（缺 student_id 迁移 / V1 禁止生产写入）')
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
