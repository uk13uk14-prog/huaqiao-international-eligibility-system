<template>
  <div v-if="data">
    <h1 class="page-title">{{ data.consultant.name || '待补充' }}</h1>
    <p class="page-sub gq-muted">顾问 360 · {{ data.consultant.role_label }} · {{ data.consultant.status_label }}</p>
    <div class="stat-row">
      <div class="gq-panel stat-card"><h3>负责学生</h3><p>{{ data.workload.assigned }}</p></div>
      <div class="gq-panel stat-card"><h3>今日待办</h3><p>{{ data.workload.today }}</p></div>
      <div class="gq-panel stat-card"><h3>逾期</h3><p>{{ data.workload.overdue }}</p></div>
    </div>
    <section class="gq-panel" style="margin-top:16px">
      <h3>基本资料</h3>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="邮箱">{{ data.consultant.email }}</el-descriptions-item>
        <el-descriptions-item label="职位">{{ data.consultant.job_title || '未设置' }}</el-descriptions-item>
        <el-descriptions-item label="最后登录">{{ data.consultant.last_login_at || '未设置' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ data.consultant.status_label }}</el-descriptions-item>
      </el-descriptions>
    </section>
    <section class="gq-panel" style="margin-top:16px">
      <h3>负责学生</h3>
      <el-table :data="data.students" empty-text="暂无记录" @row-click="goStu" style="cursor:pointer">
        <el-table-column label="学生" min-width="140"><template #default="{ row }">{{ row.display_name }}</template></el-table-column>
        <el-table-column label="阶段" width="110"><template #default="{ row }">{{ row.crm_stage_label }}</template></el-table-column>
        <el-table-column label="风险" width="90" prop="risk_level" />
        <el-table-column label="下一步" min-width="160"><template #default="{ row }">{{ row.next_action || '未设置' }}</template></el-table-column>
      </el-table>
    </section>
    <section class="gq-panel" style="margin-top:16px">
      <h3>最近跟进</h3>
      <el-table :data="data.recent_follow_ups" empty-text="暂无记录">
        <el-table-column label="时间" width="170" prop="created_at" />
        <el-table-column label="学生" width="90" prop="student_id" />
        <el-table-column label="摘要" min-width="200" prop="summary" />
      </el-table>
    </section>
    <p class="gq-muted" style="margin-top:12px">AI 顾问摘要 / 遗漏提醒：仅预留入口，禁止自动发送</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'

const props = defineProps({ consultantId: { type: [String, Number], required: true } })
const router = useRouter()
const data = ref(null)
onMounted(async () => { data.value = await api.consultant360(props.consultantId) })
function goStu(row) { router.push(`/students/${row.id}`) }
</script>
