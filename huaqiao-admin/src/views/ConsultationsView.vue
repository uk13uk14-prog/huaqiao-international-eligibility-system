<template>
  <div>
    <h1 class="page-title">咨询列表</h1>
    <p class="page-sub gq-muted">复用既有 /api/admin/expert-consultations（user 级；多学生归属见 Student 360）</p>
    <el-table :data="rows">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="user_id" label="用户" width="90" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'

const rows = ref([])
onMounted(async () => {
  rows.value = await api.consultations()
})
</script>
