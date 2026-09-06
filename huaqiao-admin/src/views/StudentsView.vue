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
      <el-table-column label="操作" width="170" fixed="right">
        <template #default="{ row }">
          <el-button v-if="canEditName" link type="primary" @click.stop="openName(row)">改姓名</el-button>
          <el-button link type="primary" @click.stop="go(row)">进入360</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="nameOpen" title="修改学生姓名" width="420px" destroy-on-close>
      <p class="gq-muted" style="margin:0 0 12px">仅超级管理员可保存。勿把邮箱当作学生姓名。</p>
      <el-form :model="nameForm" label-width="88px">
        <el-form-item label="中文姓名">
          <el-input v-model="nameForm.chinese_name" maxlength="80" />
        </el-form-item>
        <el-form-item label="英文名">
          <el-input v-model="nameForm.english_name" maxlength="80" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="nameOpen = false">取消</el-button>
        <el-button type="primary" :loading="nameSaving" @click="saveName">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import { useAdminSession } from '../composables/useAdminSession'
import {
  EMPTY,
  human,
  humanDateTime,
  riskLabel,
  riskTagType,
} from '../utils/opsDisplay'

const router = useRouter()
const { can } = useAdminSession()
const canEditName = computed(() => can('student360.profile.write'))
const nameOpen = ref(false)
const nameSaving = ref(false)
const nameTarget = ref(null)
const nameForm = ref({ chinese_name: '', english_name: '' })
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
async function openName(row) {
  nameTarget.value = row
  nameSaving.value = false
  try {
    const d = await api.student360(row.id)
    const b = d.sections?.basic_info || {}
    nameForm.value = { chinese_name: b.chinese_name || '', english_name: b.english_name || '' }
  } catch {
    const shown = displayName(row)
    nameForm.value = { chinese_name: shown === '待补姓名' ? '' : shown, english_name: '' }
  }
  nameOpen.value = true
}
async function saveName() {
  if (!nameTarget.value || !canEditName.value) return
  const cn = String(nameForm.value.chinese_name || '')
  const en = String(nameForm.value.english_name || '')
  if (cn.includes('@') || en.includes('@')) {
    ElMessage.error('姓名不能使用邮箱')
    return
  }
  if (!cn.trim() && !en.trim()) {
    ElMessage.error('请至少填写中文姓名或英文名')
    return
  }
  nameSaving.value = true
  try {
    await api.patchStudentBasic(nameTarget.value.id, {
      chinese_name: cn.trim(),
      english_name: en.trim(),
    })
    ElMessage.success('学生姓名已保存')
    nameOpen.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    nameSaving.value = false
  }
}
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
