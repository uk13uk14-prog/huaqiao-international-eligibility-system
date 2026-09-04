<template>
  <div class="shell" :class="{ mobile: isMobile }">
    <!-- Desktop sidebar — hidden on mobile / native -->
    <aside v-if="!isMobile" class="aside">
      <div class="brand-block">
        <div class="gq-brand">国侨运营后台</div>
        <div class="gq-muted">Admin Console V1</div>
      </div>
      <el-menu :default-active="route.path" router>
        <el-menu-item index="/dashboard">Dashboard</el-menu-item>
        <el-menu-item index="/users">用户管理</el-menu-item>
        <el-menu-item index="/students">学生管理</el-menu-item>
        <el-menu-item index="/consultations">咨询列表</el-menu-item>
        <el-menu-item index="/settings">设置</el-menu-item>
      </el-menu>
    </aside>

    <div class="main-col">
      <header v-if="!isMobile" class="header">
        <span class="gq-muted">desktop-first · SaaS JWT · 不写生产</span>
        <el-button text type="danger" @click="logout">退出</el-button>
      </header>
      <main class="content" :class="{ 'with-tabbar': isMobile && showTabbar }">
        <router-view />
      </main>
      <MobileTabBar v-if="isMobile && showTabbar" />
    </div>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearToken } from '../api/client'
import { useIsMobile } from '../composables/useIsMobile'
import MobileTabBar from '../mobile/MobileTabBar.vue'

const route = useRoute()
const router = useRouter()
const { isMobile } = useIsMobile()

const showTabbar = computed(() => route.meta.mobileTab !== false)

function logout() {
  clearToken()
  router.replace('/login')
}

/** Auto-route: wide → desktop dashboard; narrow → mobile home (once per switch). */
watch(
  isMobile,
  (mobile) => {
    const p = route.path
    if (mobile && (p === '/' || p === '/dashboard')) {
      router.replace('/m/home')
    } else if (!mobile && p.startsWith('/m/')) {
      router.replace('/dashboard')
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.shell {
  min-height: 100vh;
  display: flex;
  background: transparent;
}
.aside {
  width: 220px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.72);
  border-right: 1px solid var(--gq-border);
  padding: 12px 0;
}
.brand-block { padding: 8px 18px 16px; }
.main-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 16px;
  border-bottom: 1px solid var(--gq-border);
  background: transparent;
}
.content {
  flex: 1;
  padding: 16px 20px 24px;
  overflow: auto;
}
.shell.mobile .content {
  padding: 0;
}
.shell.mobile .content.with-tabbar {
  padding-bottom: calc(56px + env(safe-area-inset-bottom, 0px));
}
</style>
