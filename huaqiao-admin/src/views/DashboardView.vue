<template>
  <div>
    <h1 class="page-title">工作台</h1>
    <p class="page-sub gq-muted">{{ subtitle }}</p>
    <div class="stat-row" v-if="data">
      <div class="gq-panel stat-card" v-for="s in stats" :key="s.label" @click="s.to && $router.push(s.to)" :style="s.to ? 'cursor:pointer' : ''">
        <h3>{{ s.label }}</h3>
        <p>{{ s.value }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import { useAdminSession } from '../composables/useAdminSession'

const { role, refresh } = useAdminSession()
const data = ref(null)
onMounted(async () => {
  try { await refresh() } catch { /* ignore */ }
  data.value = await api.dashboard()
})

const subtitle = computed(() => {
  if (role.value === 'consultant') return '我的学生与今日待办'
  if (role.value === 'support') return '咨询与用户沟通'
  return '全站运营概览'
})

const stats = computed(() => {
  const d = data.value || {}
  const c = d.crm_todos?.counts || {}
  if (role.value === 'consultant') {
    return [
      { label: '我的学生', value: d.student_profiles ?? '—', to: '/my-students' },
      { label: '今日待跟进', value: c.due_today ?? '—', to: '/tasks/today' },
      { label: '逾期', value: c.overdue ?? '—', to: '/tasks/overdue' },
      { label: '高风险', value: c.high_risk ?? '—', to: '/my-students' },
    ]
  }
  if (role.value === 'support') {
    return [
      { label: '待处理咨询', value: d.pending_human_review ?? '—', to: '/consultations' },
      { label: '总用户', value: d.total_users ?? '—', to: '/users' },
    ]
  }
  return [
    { label: '今日新增用户', value: d.total_users ?? '—' },
    { label: 'Trial 用户', value: d.trial_users ?? '—' },
    { label: '付费用户', value: d.paid_users ?? '—' },
    { label: '待分配学生', value: c.unassigned ?? '—', to: '/students' },
    { label: '今日待跟进', value: c.due_today ?? '—', to: '/tasks/today' },
    { label: '逾期跟进', value: c.overdue ?? '—', to: '/tasks/overdue' },
    { label: '高风险学生', value: c.high_risk ?? '—' },
    { label: '咨询待处理', value: d.pending_human_review ?? '—', to: '/consultations' },
  ]
})
</script>
