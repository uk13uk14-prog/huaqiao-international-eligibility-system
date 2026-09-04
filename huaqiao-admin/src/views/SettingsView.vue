<template>
  <div>
    <h1 class="page-title">设置</h1>
    <div class="gq-panel" v-if="data">
      <p><strong>Admin Domain:</strong> {{ data.admin_domain }}</p>
      <p><strong>API Base (frontend):</strong> {{ apiBase }}</p>
      <p><strong>AI Provider:</strong> {{ data.ai_provider?.AI_PROVIDER }}</p>
      <p><strong>Migration applied:</strong> {{ data.migration_status?.applied }}</p>
      <p class="gq-muted">{{ data.migration_status?.draft_file }}</p>
      <h3>RBAC Proposal</h3>
      <pre class="gq-pre">{{ JSON.stringify(data.rbac, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'

const data = ref(null)
const apiBase = api.apiBase
onMounted(async () => { data.value = await api.settings() })
</script>
