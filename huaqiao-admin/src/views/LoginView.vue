<template>
  <div class="login-wrap">
    <div class="login-card gq-panel">
      <div class="gq-brand">国侨升学运营后台</div>
      <p class="gq-muted">GUOQIAO ADMIN + AI EXPERT CONSOLE V1 · Staging/Dev</p>
      <p class="gq-muted">目标域名：admin.guoqiaoplan.com（本轮不部署生产）</p>
      <el-form @submit.prevent="onLogin" label-position="top" style="margin-top:16px">
        <el-form-item label="邮箱">
          <el-input v-model="email" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width:100%">登录</el-button>
      </el-form>
      <p v-if="error" style="color:#b91c1c;margin-top:12px">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api/client'

const router = useRouter()
const email = ref('admin@example.com')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function onLogin() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.login(email.value, password.value)
    setToken(data.token)
    const me = await api.me()
    if (!me.console_role) throw new Error('当前账号无权进入运营后台')
    router.replace('/dashboard')
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}
.login-card { width: min(420px, 100%); }
.gq-brand { font-size: 28px; margin-bottom: 6px; }
</style>
