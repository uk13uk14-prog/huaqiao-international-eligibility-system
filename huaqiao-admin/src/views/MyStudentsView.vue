<template>
  <div>
    <h1 class="page-title">我的学生</h1>
    <p class="page-sub gq-muted">仅显示分配给我的学生 · 后端隔离</p>
    <el-table :data="students" empty-text="暂无记录" @row-click="go" style="cursor:pointer">
      <el-table-column label="学生姓名" min-width="140">
        <template #default="{ row }">{{ displayName(row) }}</template>
      </el-table-column>
      <el-table-column label="身份路线" width="120"><template #default="{ row }">{{ row.identity_track || '待补充' }}</template></el-table-column>
      <el-table-column label="目标院校" min-width="140"><template #default="{ row }">{{ (row.target_universities || []).join('、') || '尚未添加目标大学' }}</template></el-table-column>
      <el-table-column label="CRM阶段" width="110"><template #default="{ row }">{{ row.crm_stage_label || '未分配' }}</template></el-table-column>
      <el-table-column label="风险" width="90"><template #default="{ row }">{{ riskLabel(row.risk_level) }}</template></el-table-column>
      <el-table-column label="下一步" min-width="140"><template #default="{ row }">{{ row.next_action || '未设置' }}</template></el-table-column>
      <el-table-column label="下次跟进" width="160"><template #default="{ row }">{{ row.next_follow_up_at || '未设置' }}</template></el-table-column>
      <el-table-column label="最后跟进" width="160"><template #default="{ row }">{{ row.last_follow_up_at || '暂无记录' }}</template></el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { useAdminSession } from '../composables/useAdminSession'
import { riskLabel } from '../utils/opsDisplay'

const router = useRouter()
const { refresh, user, role } = useAdminSession()
const students = ref([])

function displayName(row) {
  const n = row.display_name
  if (!n || n === '未命名学生' || String(n).includes('@')) return '待补姓名'
  return n
}
function go(row) { router.push(`/students/${row.id}`) }

onMounted(async () => {
  await refresh()
  const params = role.value === 'consultant' ? {} : { assignee_user_id: user.value.id }
  const data = await api.students(params)
  students.value = data.students || []
})
</script>
