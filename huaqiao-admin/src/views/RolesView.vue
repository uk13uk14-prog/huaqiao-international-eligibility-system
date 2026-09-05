<template>
  <div>
    <h1 class="page-title">角色管理</h1>
    <p class="page-sub gq-muted">角色 = 权限；职位 = 业务称谓。权限由后端强制执行。</p>
    <div class="role-grid">
      <article v-for="r in roles" :key="r.key" class="gq-panel">
        <h3>{{ r.label }}</h3>
        <p class="gq-muted">{{ r.key }}</p>
        <ul>
          <li v-for="c in (r.capabilities || [])" :key="c">{{ label(c) }}</li>
        </ul>
      </article>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'
import { capabilityLabel } from '../utils/opsDisplay'

const roles = ref([])
function label(c) { return capabilityLabel(c) }
onMounted(async () => {
  const data = await api.rbacCatalog()
  roles.value = data.roles || []
})
</script>

<style scoped>
.role-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:12px; }
ul { padding-left: 18px; font-size: 13px; line-height: 1.6; }
</style>
