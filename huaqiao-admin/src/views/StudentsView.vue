<template>
  <div>
    <h1 class="page-title">学生 CRM</h1>
    <p class="page-sub gq-muted">点击姓名或整行进入 Student 360 · 不展示证件明文 / cipher / raw JSON</p>

    <div class="filters">
      <el-input v-model="q" placeholder="搜索姓名 / 所属邮箱 / Student ID" clearable style="max-width:280px" @keyup.enter="load" />
      <el-select v-model="assigneeUserId" clearable placeholder="负责人" style="width:160px" @change="load">
        <el-option label="未分配" :value="0" />
        <el-option v-for="s in staff" :key="s.id" :label="s.label" :value="s.id" />
      </el-select>
      <el-select v-model="crmStage" clearable placeholder="阶段" style="width:140px" @change="load">
        <el-option v-for="(label, key) in stageLabels" :key="key" :label="label" :value="key" />
      </el-select>
      <el-select v-model="riskLevel" clearable placeholder="风险" style="width:120px" @change="load">
        <el-option v-for="r in riskOptions" :key="r.value" :label="r.label" :value="r.value" />
      </el-select>
      <el-select v-model="plan" clearable placeholder="Trial/Paid" style="width:120px" @change="load">
        <el-option label="Trial" value="trial" />
        <el-option label="Paid" value="paid" />
      </el-select>
      <el-select v-model="sort" style="width:150px" @change="load">
        <el-option label="最近更新" value="updated_at" />
        <el-option label="最近跟进" value="last_follow_up" />
        <el-option label="下次跟进" value="next_follow_up" />
        <el-option label="创建时间" value="created_at" />
      </el-select>
      <el-button type="primary" @click="load">搜索</el-button>
    </div>

    <el-table :data="students" @row-click="go" style="cursor:pointer" empty-text="暂无记录">
      <el-table-column label="学生姓名" min-width="140">
        <template #default="{ row }">
          <a class="name-link" @click.stop="go(row)">{{ displayName(row) }}</a>
          <el-tag v-if="needsName(row)" size="small" type="warning" style="margin-left:6px">待补姓名</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="身份路线" width="120">
        <template #default="{ row }">{{ identityLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="目标入学年份" width="110">
        <template #default="{ row }">{{ human(row.intended_entry_year, EMPTY.unset) }}</template>
      </el-table-column>
      <el-table-column label="CRM 阶段" width="110">
        <template #default="{ row }">{{ human(row.crm_stage_label || row.crm_stage, EMPTY.unassigned) }}</template>
      </el-table-column>
      <el-table-column label="负责人" width="120">
        <template #default="{ row }">{{ human(row.assignee_label, EMPTY.unassigned) }}</template>
      </el-table-column>
      <el-table-column label="风险等级" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="riskTagType(row.risk_level)">{{ riskLabel(row.risk_level) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="下一步" min-width="160">
        <template #default="{ row }">{{ human(row.next_action, EMPTY.unset) }}</template>
      </el-table-column>
      <el-table-column label="下次跟进时间" width="160">
        <template #default="{ row }">{{ humanDateTime(row.next_follow_up_at, EMPTY.unset) }}</template>
      </el-table-column>
      <el-table-column label="最近更新时间" width="160">
        <template #default="{ row }">{{ humanDateTime(row.updated_at, EMPTY.none) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="go(row)">进入360</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import {
  EMPTY,
  human,
  humanDateTime,
  riskLabel,
  riskTagType,
} from '../utils/opsDisplay'

const router = useRouter()
const students = ref([])
const staff = ref([])
const stageLabels = ref({})
const q = ref('')
const assigneeUserId = ref()
const crmStage = ref()
const riskLevel = ref()
const plan = ref()
const sort = ref('updated_at')
const riskOptions = [
  { value: 'NONE', label: '无' },
  { value: 'LOW', label: '低' },
  { value: 'MEDIUM', label: '中' },
  { value: 'HIGH', label: '高' },
  { value: 'CRITICAL', label: '严重' },
]

function displayName(row) {
  const n = row.display_name
  if (!n || n === '未命名学生' || n === '待补姓名') return '待补姓名'
  // Never fall back to email as the student name
  if (String(n).includes('@')) return '待补姓名'
  return n
}
function needsName(row) {
  return displayName(row) === '待补姓名' || row.display_name_needs_repair
}
function identityLabel(row) {
  const track = row.identity_track || row.identity_route
  if (track) return human(track)
  const intl = row.summary?.international_status
  const hq = row.summary?.huaqiao_status
  if (intl && intl !== 'NOT_ASSESSED') return `国际生:${intl}`
  if (hq && hq !== 'NOT_ASSESSED') return `华侨生:${hq}`
  return EMPTY.pending
}
function go(row) { router.push(`/students/${row.id}`) }
async function load() {
  const data = await api.students({
    q: q.value || undefined,
    assignee_user_id: assigneeUserId.value,
    crm_stage: crmStage.value || undefined,
    risk_level: riskLevel.value || undefined,
    plan: plan.value || undefined,
    sort: sort.value,
  })
  students.value = data.students || []
  stageLabels.value = data.stage_labels || data.crm_stages || {}
}
onMounted(async () => {
  try { staff.value = (await api.staff()).staff || [] } catch { staff.value = [] }
  await load()
})
</script>

<style scoped>
.filters { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; align-items:center; }
.name-link { color:#1d4ed8; font-weight:600; }
</style>
