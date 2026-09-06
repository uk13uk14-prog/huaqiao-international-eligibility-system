<template>
  <div>
    <h1 class="page-title">顾问管理</h1>
    <p class="page-sub gq-muted">顾问是真实员工账号，不是角色说明卡片</p>
    <el-table :data="rows" empty-text="暂无记录" @row-click="go" style="cursor:pointer">
      <el-table-column label="姓名" min-width="140"><template #default="{ row }">{{ row.name || '待补充' }}</template></el-table-column>
      <el-table-column label="职位" width="140"><template #default="{ row }">{{ row.job_title || '升学顾问' }}</template></el-table-column>
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column label="状态" width="90"><template #default="{ row }">{{ row.status_label }}</template></el-table-column>
      <el-table-column label="当前学生" width="100" prop="assigned_student_count" />
      <el-table-column label="待跟进" width="90" prop="due_today_count" />
      <el-table-column label="逾期" width="80" prop="overdue_count" />
      <el-table-column label="最近活动" width="170"><template #default="{ row }">{{ row.last_activity_at || '未设置' }}</template></el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }"><el-button link type="primary" @click.stop="go(row)">顾问360</el-button></template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'

const router = useRouter()
const rows = ref([])
onMounted(async () => {
  rows.value = (await api.consultants()).consultants || []
})
function go(row) { router.push(`/consultants/${row.id}`) }
</script>
