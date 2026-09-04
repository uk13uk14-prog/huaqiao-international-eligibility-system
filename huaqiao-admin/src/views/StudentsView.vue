<template>
  <div>
    <h1 class="page-title">学生管理</h1>
    <div style="margin-bottom:12px;display:flex;gap:8px">
      <el-input v-model="q" placeholder="搜索 display_name / 所属用户" clearable style="max-width:320px" @keyup.enter="load" />
      <el-button type="primary" @click="load">搜索</el-button>
    </div>
    <el-table :data="students" @row-click="go" style="cursor:pointer">
      <el-table-column prop="id" label="学生 ID" width="90" />
      <el-table-column prop="display_name" label="display_name" />
      <el-table-column label="所属用户">
        <template #default="{ row }">{{ row.owner?.email || row.user_id }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="goal_hint" label="目标提示" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column prop="updated_at" label="最后更新" width="180" />
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'

const router = useRouter()
const students = ref([])
const q = ref('')
async function load() {
  const data = await api.students(q.value)
  students.value = data.students || []
}
function go(row) { router.push(`/students/${row.id}`) }
onMounted(load)
</script>
