<template>
  <div class="login-wrap">
    <div class="login-card gq-panel">
      <div class="gq-brand">国侨升学运营后台</div>
      <p class="gq-muted">国侨升学运营后台 V2</p>
      <p class="gq-muted">API：{{ apiBaseLabel }}</p>
      <el-form @submit.prevent="onLogin" label-position="top" style="margin-top:16px">
        <el-form-item label="邮箱">
          <el-input v-model="email" autocomplete="username" :disabled="loading" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            autocomplete="current-password"
            :disabled="loading"
          />
        </el-form-item>
        <el-button
          type="primary"
          native-type="submit"
          :loading="loading"
          :disabled="loading || !email || !password"
          style="width:100%"
        >
          {{ loading ? '登录中…' : '登录' }}
        </el-button>
      </el-form>
      <p v-if="error" class="login-error" role="alert">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError, setToken, clearToken } from '../api/client'
import { isMobileViewport } from '../composables/useIsMobile'

const router = useRouter()
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const apiBaseLabel = computed(() => api.apiBase)

async function onLogin() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.login(email.value.trim(), password.value)
    if (!data?.token) throw new ApiError('登录响应异常：缺少 token', { status: 0, code: 'bad_response' })
    setToken(data.token)
    const me = await api.me()
    if (!me?.console_role) {
      clearToken()
      throw new ApiError('当前账号无权进入运营后台', { status: 403, code: 'no_console_role' })
    }
    await router.replace(isMobileViewport() ? '/m/home' : '/dashboard')
  } catch (e) {
    clearToken()
    if (e instanceof ApiError) {
      error.value = e.message
    } else if (e?.name === 'TypeError' || /Failed to fetch|NetworkError/i.test(String(e?.message || e))) {
      error.value = '无法连接服务器，请稍后重试'
    } else {
      error.value = e?.message || `登录失败：${String(e)}`
    }
    console.error('[admin-login]', e)
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
.login-error {
  color: #b91c1c;
  margin-top: 12px;
  font-size: 14px;
  line-height: 1.45;
}
</style>
