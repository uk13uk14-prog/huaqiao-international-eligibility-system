<template>
  <div class="m-page">
    <header class="m-hd">
      <h1>我的</h1>
      <p class="gq-muted">当前管理员 · 会话</p>
    </header>

    <section class="gq-panel block" v-if="me">
      <p><strong>邮箱</strong></p>
      <p>{{ me.email || '—' }}</p>
      <p style="margin-top:12px"><strong>角色</strong></p>
      <p>{{ me.console_role || me.role || '—' }}</p>
      <p style="margin-top:12px"><strong>用户 ID</strong></p>
      <p>{{ me.id || me.user_id || '—' }}</p>
    </section>
    <p v-else class="gq-muted">{{ error || '加载中…' }}</p>

    <section class="gq-panel block">
      <p><strong>API</strong></p>
      <p class="mono">{{ api.apiBase }}</p>
      <p class="gq-muted" style="margin-top:8px">App 仅保存登录 JWT，不含 JWT_SECRET / VAULT / DB 密码。</p>
    </section>

    <el-button type="danger" style="width:100%" @click="logout">退出登录</el-button>

    <section class="links">
      <el-button text type="primary" @click="$router.push('/m/published')">已发布报告</el-button>
      <el-button text @click="$router.push('/dashboard')">切换桌面版（宽屏）</el-button>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, clearToken } from '../api/client'

const router = useRouter()
const me = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    me.value = await api.me()
  } catch (e) {
    error.value = e.message || '无法获取管理员信息'
  }
})

function logout() {
  clearToken()
  router.replace('/login')
}
</script>

<style scoped>
.m-page { padding: 12px 14px; }
.m-hd h1 { margin: 0; font-size: 22px; }
.m-hd p { margin: 4px 0 12px; }
.block { margin-bottom: 12px; }
.block p { margin: 4px 0; }
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px; word-break: break-all;
}
.links { margin-top: 16px; display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
</style>
