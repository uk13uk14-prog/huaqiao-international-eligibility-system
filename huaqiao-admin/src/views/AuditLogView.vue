<template>
  <div>
    <h1 class="page-title">操作日志</h1>
    <p class="page-sub gq-muted">不展示密码 / token / cipher / 完整敏感 payload</p>
    <el-table :data="rows" empty-text="暂无记录">
      <el-table-column label="时间" width="180" prop="created_at" />
      <el-table-column label="操作人" width="140" prop="actor_label" />
      <el-table-column label="动作" width="200" prop="action" />
      <el-table-column label="对象" width="160">
        <template #default="{ row }">{{ row.resource_type }} #{{ row.resource_id || '—' }}</template>
      </el-table-column>
      <el-table-column label="结果" width="80" prop="result" />
      <el-table-column label="摘要" min-width="200" prop="summary" />
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'

const rows = ref([])
onMounted(async () => {
  rows.value = (await api.auditEvents()).events || []
})
</script>
