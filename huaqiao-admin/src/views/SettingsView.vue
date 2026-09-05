<template>
  <div class="settings-page">
    <h1 class="page-title">系统设置</h1>
    <p class="page-sub gq-muted">按权限展示 · 技术信息仅超级管理员可见</p>
    <el-tabs v-model="tab">
      <el-tab-pane label="账号与安全" name="account">
        <section class="gq-panel">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="当前账号">{{ user.email || '未设置' }}</el-descriptions-item>
            <el-descriptions-item label="角色">{{ roleLabel }}</el-descriptions-item>
            <el-descriptions-item label="职位">{{ user.job_title || '未设置' }}</el-descriptions-item>
          </el-descriptions>
          <div style="margin-top:12px;max-width:360px">
            <el-input v-model="newPw" type="password" show-password placeholder="新密码（不少于 8 位）" />
            <el-button type="primary" style="margin-top:8px" @click="changePw">修改密码</el-button>
          </div>
        </section>
      </el-tab-pane>
      <el-tab-pane v-if="can('employees.read')" label="员工与角色" name="staff">
        <p><el-button type="primary" @click="$router.push('/employees')">打开员工管理</el-button>
        <el-button @click="$router.push('/roles')">打开角色管理</el-button></p>
      </el-tab-pane>
      <el-tab-pane v-if="can('roles.read')" label="权限" name="perms">
        <p class="gq-muted">权限由后端强制校验，前端仅隐藏菜单。</p>
        <ul>
          <li v-for="p in permissions" :key="p">{{ cap(p) }}</li>
        </ul>
      </el-tab-pane>
      <el-tab-pane label="通知" name="notif">
        <p class="gq-muted">通知中心已接入。规则配置保持现有通知模块，本页不展示技术 JSON。</p>
        <el-button @click="$router.push('/m/notifications')">打开通知</el-button>
      </el-tab-pane>
      <el-tab-pane label="AI 配置" name="ai">
        <p>提供商：{{ human(data?.ai_provider?.AI_PROVIDER) }}</p>
        <p class="gq-muted">AI 输出默认草稿，必须人工审核。禁止自动发送。</p>
      </el-tab-pane>
      <el-tab-pane v-if="can('settings.write')" label="系统信息" name="tech">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="管理域名">{{ human(data?.admin_domain) }}</el-descriptions-item>
          <el-descriptions-item label="API">{{ api.apiBase }}</el-descriptions-item>
          <el-descriptions-item label="代码迁移头">{{ data?.migration_status?.alembic_head_code || '待补充' }}</el-descriptions-item>
          <el-descriptions-item label="生产库预期">{{ data?.migration_status?.production_expected || '010_student_crm_v1' }}</el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import { useAdminSession } from '../composables/useAdminSession'
import { capabilityLabel, human, ROLE_ZH } from '../utils/opsDisplay'

const { user, role, permissions, can, refresh } = useAdminSession()
const tab = ref('account')
const data = ref(null)
const newPw = ref('')
const roleLabel = computed(() => ROLE_ZH[role.value] || '未分配角色')
function cap(p) { return capabilityLabel(p) }

async function changePw() {
  try {
    await api.changeOwnPassword(newPw.value)
    ElMessage.success('密码已更新')
    newPw.value = ''
    await refresh()
  } catch (e) {
    ElMessage.error(e.message || '更新失败')
  }
}
onMounted(async () => {
  try { await refresh() } catch { /* ignore */ }
  try { data.value = await api.settings() } catch { data.value = {} }
})
</script>
