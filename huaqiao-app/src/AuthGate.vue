<template>
  <section class="auth-gate" :class="darkMode ? 'dark' : 'light'">
    <div class="auth-gate-inner">
      <header class="auth-hero">
        <p class="auth-brand">国侨升学</p>
        <h1>国际生 / 华侨生升学规划</h1>
        <p class="auth-sub">新用户注册即享 7 天 Pro 完整体验</p>
      </header>

      <div v-if="mode === 'gate'" class="auth-actions">
        <van-button block round type="primary" @click="mode = 'login'">登录</van-button>
        <van-button block round plain type="primary" @click="mode = 'register'">免费注册</van-button>
      </div>

      <van-form v-else-if="mode === 'login'" class="auth-form" @submit="onLogin">
        <van-cell-group inset>
          <van-field v-model="email" type="email" label="邮箱" placeholder="注册邮箱" autocomplete="username" />
          <van-field
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            label="密码"
            placeholder="密码"
            autocomplete="current-password"
          >
            <template #right-icon>
              <span class="pwd-toggle" @click="showPassword = !showPassword">{{ showPassword ? '隐藏' : '显示' }}</span>
            </template>
          </van-field>
        </van-cell-group>
        <p v-if="errorText" class="auth-error">{{ errorText }}</p>
        <div class="auth-form-actions">
          <van-button block round type="primary" native-type="submit" :loading="busy">登录</van-button>
          <van-button block round plain native-type="button" @click="mode = 'register'">没有账号？免费注册</van-button>
          <van-button block round plain type="default" native-type="button" @click="mode = 'gate'">返回</van-button>
        </div>
      </van-form>

      <van-form v-else class="auth-form" @submit="onRegister">
        <van-cell-group inset>
          <van-field v-model="name" label="姓名" placeholder="学生或家长姓名" autocomplete="name" />
          <van-field v-model="email" type="email" label="邮箱" placeholder="注册邮箱" autocomplete="username" />
          <van-field
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            label="密码"
            placeholder="至少 6 位"
            autocomplete="new-password"
          >
            <template #right-icon>
              <span class="pwd-toggle" @click="showPassword = !showPassword">{{ showPassword ? '隐藏' : '显示' }}</span>
            </template>
          </van-field>
          <van-field
            v-model="passwordConfirm"
            :type="showPassword ? 'text' : 'password'"
            label="确认密码"
            placeholder="再次输入密码"
            autocomplete="new-password"
          />
        </van-cell-group>
        <p class="auth-hint">注册成功后自动登录，并开通 7 天 Pro 试用（完整大学库与规划能力）。</p>
        <p v-if="errorText" class="auth-error">{{ errorText }}</p>
        <div class="auth-form-actions">
          <van-button block round type="primary" native-type="submit" :loading="busy">注册并开始试用</van-button>
          <van-button block round plain native-type="button" @click="mode = 'login'">已有账号？去登录</van-button>
          <van-button block round plain type="default" native-type="button" @click="mode = 'gate'">返回</van-button>
        </div>
      </van-form>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'
import { saasApi, setSaasToken } from './saasApi'
import {
  buildRegisterPayload,
  mapAuthError,
  normalizeSaasUser,
  validateLoginForm,
  validateRegisterForm,
} from './authSession.js'

defineProps({
  darkMode: { type: Boolean, default: false },
})

const emit = defineEmits(['authenticated'])

const mode = ref('gate')
const name = ref('')
const email = ref('')
const password = ref('')
const passwordConfirm = ref('')
const showPassword = ref(false)
const busy = ref(false)
const errorText = ref('')

async function onLogin() {
  errorText.value = ''
  const v = validateLoginForm({ email: email.value, password: password.value })
  if (v) {
    errorText.value = v
    showFailToast(v)
    return
  }
  busy.value = true
  try {
    const r = await saasApi.login(email.value.trim(), password.value)
    setSaasToken(r.token)
    const user = normalizeSaasUser(r.user)
    showSuccessToast('登录成功')
    emit('authenticated', user)
  } catch (error) {
    const msg = mapAuthError(error)
    errorText.value = msg
    showFailToast(msg)
  } finally {
    busy.value = false
  }
}

async function onRegister() {
  errorText.value = ''
  const v = validateRegisterForm({
    name: name.value,
    email: email.value,
    password: password.value,
    passwordConfirm: passwordConfirm.value,
  })
  if (v) {
    errorText.value = v
    showFailToast(v)
    return
  }
  busy.value = true
  try {
    const payload = buildRegisterPayload({
      name: name.value,
      email: email.value,
      password: password.value,
    })
    const r = await saasApi.register(payload)
    setSaasToken(r.token)
    const user = normalizeSaasUser(r.user)
    const days = user?.trial_days_remaining ?? 7
    showSuccessToast(`注册成功 · 7天 Pro 试用（剩余 ${days} 天）`)
    emit('authenticated', user)
  } catch (error) {
    const msg = mapAuthError(error)
    errorText.value = msg
    showFailToast(msg)
  } finally {
    busy.value = false
  }
}
</script>
