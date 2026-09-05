<template>
  <div class="settings-page">
    <h1 class="page-title">设置</h1>
    <p class="page-sub gq-muted">运营权限与系统摘要 · 技术 JSON 不在此展示</p>

    <div v-if="data" class="gq-panel block">
      <h3>系统摘要</h3>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="管理域名">{{ human(data.admin_domain) }}</el-descriptions-item>
        <el-descriptions-item label="前端 API">{{ human(apiBase) }}</el-descriptions-item>
        <el-descriptions-item label="AI 提供商">{{ human(data.ai_provider?.AI_PROVIDER) }}</el-descriptions-item>
        <el-descriptions-item label="迁移状态">{{ migrationLabel }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="gq-panel block">
      <h3>当前角色与权限</h3>
      <p class="gq-muted mb">按运营角色展示能力摘要（非技术提案原文）。</p>
      <div class="role-grid">
        <article v-for="role in roleCards" :key="role.key" class="role-card" :class="{ current: role.isCurrent }">
          <div class="role-hd">
            <h4>{{ role.title }}</h4>
            <el-tag v-if="role.isCurrent" type="success" size="small">当前</el-tag>
          </div>
          <p class="role-blurb">{{ role.blurb }}</p>
          <ul>
            <li v-for="(cap, i) in role.highlights" :key="i">{{ cap }}</li>
          </ul>
          <p v-if="role.denied.length" class="denied">不可：{{ role.denied.join('、') }}</p>
        </article>
      </div>
    </div>

    <details v-if="isDev && data" class="gq-panel block dev-debug">
      <summary>Developer Debug（生产默认隐藏）</summary>
      <p class="gq-muted">仅开发构建可见。不含 secret / token。</p>
      <pre class="safe-pre">{{ debugSafe }}</pre>
    </details>

    <div v-if="!data" class="gq-muted" style="padding:24px">加载中…</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import { EMPTY, human, roleLabel, ROLE_BLURB, capabilityLabel } from '../utils/opsDisplay'

const isDev = import.meta.env.DEV
const data = ref(null)
const apiBase = api.apiBase

/** Ops-facing capability bullets (prefer curated list over raw keys). */
const ROLE_HIGHLIGHTS = {
  super_admin: [
    '查看所有学生',
    '分配顾问',
    'AI 审核',
    '发布报告',
    '查看敏感信息',
    '管理系统设置',
  ],
  consultant: [
    '查看被分配学生',
    '记录跟进',
    '使用 AI 辅助',
    '提交审核',
    '可批准 / 发布报告（按策略）',
  ],
  support: [
    '查看基础资料',
    '记录沟通',
    '查看用户列表',
  ],
}
const ROLE_DENIED = {
  super_admin: [],
  consultant: [],
  support: ['不可发布专家报告', '不可查看完整学生档案写操作', '不可管理系统设置'],
}

const migrationLabel = computed(() => {
  const m = data.value?.migration_status
  if (!m) return EMPTY.pending
  if (m.applied === true) return '已应用'
  if (m.applied === false) return '未应用'
  return human(m.applied)
})

const currentRoleKey = computed(() => {
  // V1: logged-in admin maps to super_admin; API may later expose console_role.
  const map = data.value?.rbac?.v1_mapping || {}
  return map.admin || 'super_admin'
})

const roleCards = computed(() => {
  const caps = data.value?.rbac?.capabilities || {}
  const order = ['super_admin', 'consultant', 'support']
  return order.map((key) => {
    const rawCaps = Array.isArray(caps[key]) ? caps[key] : []
    const highlights = ROLE_HIGHLIGHTS[key] || rawCaps.map(capabilityLabel).slice(0, 8)
    return {
      key,
      title: roleLabel(key),
      blurb: ROLE_BLURB[key] || '',
      highlights,
      denied: ROLE_DENIED[key] || [],
      isCurrent: key === currentRoleKey.value,
    }
  })
})

const debugSafe = computed(() => {
  if (!isDev || !data.value) return ''
  return JSON.stringify({
    admin_domain: data.value.admin_domain,
    ai_provider: data.value.ai_provider?.AI_PROVIDER,
    migration_applied: data.value.migration_status?.applied,
    proposed_roles: data.value.rbac?.proposed_console_roles,
    capability_counts: Object.fromEntries(
      Object.entries(data.value.rbac?.capabilities || {}).map(([k, v]) => [k, Array.isArray(v) ? v.length : 0]),
    ),
  }, null, 2)
})

onMounted(async () => {
  data.value = await api.settings()
})
</script>

<style scoped>
.block { margin-bottom: 14px; }
.mb { margin-bottom: 10px; }
.role-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.role-card {
  background: #fff;
  border: 1px solid #d5dde8;
  border-radius: 10px;
  padding: 14px 16px;
}
.role-card.current {
  border-color: #93c5fd;
  background: #eff6ff;
}
.role-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.role-hd h4 { margin: 0; font-size: 16px; color: #142033; }
.role-blurb { margin: 0 0 10px; font-size: 13px; color: #64748b; line-height: 1.5; }
.role-card ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
  color: #1e293b;
}
.denied {
  margin: 10px 0 0;
  font-size: 12px;
  color: #b45309;
}
.dev-debug summary { cursor: pointer; font-weight: 600; }
.safe-pre {
  white-space: pre-wrap;
  font-size: 12px;
  background: #f1f5f9;
  color: #334155;
  padding: 10px;
  border-radius: 8px;
  max-height: 240px;
  overflow: auto;
}
@media (max-width: 900px) {
  .role-grid { grid-template-columns: 1fr; }
}
</style>
