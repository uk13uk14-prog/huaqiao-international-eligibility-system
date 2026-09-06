<template>
  <div class="shell" :class="{ mobile: isMobile }">
    <aside v-if="!isMobile" class="aside">
      <div class="brand-block">
        <div class="gq-brand">国侨运营后台</div>
        <div class="gq-muted">运营后台 V2 · {{ roleLabel }}</div>
      </div>
      <el-menu :default-active="activePath" router>
        <el-sub-menu v-for="g in groupedMenu" :key="g.title" :index="g.title">
          <template #title>{{ g.title }}</template>
          <el-menu-item v-for="it in g.items" :key="it.path" :index="it.path">{{ it.title }}</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </aside>

    <div class="main-col">
      <header v-if="!isMobile" class="header">
        <span class="gq-muted">{{ user.email }} · {{ roleLabel }}</span>
        <el-button text type="danger" @click="logout">退出</el-button>
      </header>
      <el-alert
        v-if="mustChange"
        title="首次登录请修改临时密码"
        type="warning"
        :closable="false"
        style="margin:8px 16px 0"
      />
      <main class="content" :class="{ 'with-tabbar': isMobile && showTabbar }">
        <router-view />
      </main>
      <MobileTabBar v-if="isMobile && showTabbar" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearToken } from '../api/client'
import { useIsMobile } from '../composables/useIsMobile'
import { useAdminSession } from '../composables/useAdminSession'
import MobileTabBar from '../mobile/MobileTabBar.vue'
import { useNotificationPopups } from '../composables/useNotificationPopups'
import { ROLE_ZH } from '../utils/opsDisplay'

const route = useRoute()
const router = useRouter()
const { isMobile } = useIsMobile()
const { groupedMenu, role, user, mustChange, refresh } = useAdminSession()
useNotificationPopups()

const showTabbar = computed(() => route.meta.mobileTab !== false)
const roleLabel = computed(() => ROLE_ZH[role.value] || '运营')
const activePath = computed(() => route.path)

function logout() {
  clearToken()
  router.replace('/login')
}

onMounted(async () => {
  try { await refresh() } catch { /* session guard handles */ }
})

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
  width: 228px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.72);
  border-right: 1px solid var(--gq-border);
  padding: 12px 0;
  overflow: auto;
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
.shell.mobile .content { padding: 0; }
.shell.mobile .content.with-tabbar {
  padding-bottom: calc(56px + env(safe-area-inset-bottom, 0px));
}
</style>
