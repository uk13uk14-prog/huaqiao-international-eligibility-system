<template>
  <div>
    <h1 class="page-title">用户管理</h1>
    <div style="margin-bottom:12px;display:flex;gap:8px">
      <el-input v-model="q" placeholder="搜索姓名/邮箱/ID" clearable style="max-width:280px" @keyup.enter="load" />
      <el-button type="primary" @click="load">搜索</el-button>
    </div>
    <el-table :data="users" @row-click="go" style="cursor:pointer">
      <el-table-column prop="id" label="用户 ID" width="90" />
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column prop="email" label="邮箱" />
      <el-table-column label="套餐" width="140">
        <template #default="{ row }">{{ planCodeLabel(row.plan_code, { isPaid: row.is_paid }) }}</template>
      </el-table-column>
      <el-table-column label="Trial" width="100">
        <template #default="{ row }">{{ human(row.trial?.trial_status, '—') }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" width="180" />
      <el-table-column prop="membership_until" label="会员到期" width="180" />
      <el-table-column prop="student_count" label="学生数" width="90" />
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { human, planCodeLabel } from '../utils/opsDisplay'

const router = useRouter()
const users = ref([])
const q = ref('')
async function load() {
  const data = await api.users(q.value)
  users.value = data.users || []
}
function go(row) { router.push(`/users/${row.id}`) }
onMounted(load)
</script>
