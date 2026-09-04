<template>
  <div>
    <h1 class="page-title">Dashboard</h1>
    <p class="page-sub gq-muted">运营概览（非复杂 BI）</p>
    <div class="stat-row" v-if="data">
      <div class="gq-panel stat-card" v-for="s in stats" :key="s.label">
        <h3>{{ s.label }}</h3>
        <p>{{ s.value }}</p>
      </div>
    </div>
    <div class="gq-panel" style="margin-top:16px" v-if="data">
      <h3>最近咨询</h3>
      <el-table :data="data.recent_consultations || []" size="small">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="user_id" label="用户" width="90" />
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="created_at" label="时间" width="180" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'

const data = ref(null)
onMounted(async () => { data.value = await api.dashboard() })
const stats = computed(() => {
  const d = data.value || {}
  return [
    { label: '总用户数', value: d.total_users ?? '—' },
    { label: 'Trial 用户', value: d.trial_users ?? '—' },
    { label: '付费用户', value: d.paid_users ?? '—' },
    { label: 'Trial 即将到期', value: d.trial_expiring_soon ?? '—' },
    { label: '学生档案', value: d.student_profiles ?? '—' },
    { label: '待人工审核', value: d.pending_human_review ?? '—' },
  ]
})
</script>
