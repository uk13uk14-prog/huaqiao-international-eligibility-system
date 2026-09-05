<template>
  <div>
    <h1 class="page-title">学生 CRM</h1>
    <p class="page-sub gq-muted">点击姓名或整行进入 Student 360 · 不展示证件明文 / cipher</p>

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
        <el-option v-for="r in riskLevels" :key="r" :label="r" :value="r" />
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

    <el-table :data="students" @row-click="go" style="cursor:pointer" empty-text="暂无学生">
      <el-table-column label="学生姓名" min-width="140">
        <template #default="{ row }">
          <a class="name-link" @click.stop="go(row)">{{ row.display_name || '待补姓名' }}</a>
          <el-tag v-if="row.display_name_needs_repair" size="small" type="warning" style="margin-left:6px">待补姓名</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="所属账号" min-width="160">
        <template #default="{ row }">{{ row.owner?.email || row.user_id }}</template>
      </el-table-column>
      <el-table-column label="身份路线" width="110">
        <template #default="{ row }">{{ identityLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="目标大学" min-width="140">
        <template #default="{ row }">{{ (row.target_universities || []).join('、') || row.goal_hint || '—' }}</template>
      </el-table-column>
      <el-table-column label="入学年份" width="90">
        <template #default="{ row }">{{ row.intended_entry_year || '—' }}</template>
      </el-table-column>
      <el-table-column label="当前阶段" width="110">
        <template #default="{ row }">{{ row.crm_stage_label || row.crm_stage || '—' }}</template>
      </el-table-column>
      <el-table-column label="负责人" width="120">
        <template #default="{ row }">{{ row.assignee_label || '未分配' }}</template>
      </el-table-column>
      <el-table-column label="风险" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="riskType(row.risk_level)">{{ row.risk_level || 'NONE' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最近跟进" width="160">
        <template #default="{ row }">{{ row.last_follow_up_at || '—' }}</template>
      </el-table-column>
      <el-table-column label="下一步" min-width="160">
        <template #default="{ row }">{{ row.next_action || '—' }}</template>
      </el-table-column>
      <el-table-column label="最后更新" width="160">
        <template #default="{ row }">{{ row.updated_at || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="go(row)">查看画像</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'

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
const riskLevels = ['NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

function identityLabel(row) {
  const track = row.identity_track
  if (track) return track
  const intl = row.summary?.international_status
  const hq = row.summary?.huaqiao_status
  if (intl && intl !== 'NOT_ASSESSED') return `国际生:${intl}`
  if (hq && hq !== 'NOT_ASSESSED') return `华侨生:${hq}`
  return '—'
}
function riskType(r) {
  if (r === 'CRITICAL' || r === 'HIGH') return 'danger'
  if (r === 'MEDIUM') return 'warning'
  return 'info'
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
  stageLabels.value = data.stage_labels || {}
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
