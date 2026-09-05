<template>
  <nav class="m-tabbar" aria-label="手机底部导航">
    <button
      v-for="item in items"
      :key="item.to"
      type="button"
      class="m-tab"
      :class="{ active: isActive(item) }"
      @click="go(item.to)"
    >
      <span class="ico">{{ item.icon }}</span>
      <span class="lab">{{ item.label }}</span>
    </button>
  </nav>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const items = [
  { to: '/m/home', label: '首页', icon: '⌂', match: ['/m/home'] },
  { to: '/m/students', label: '学生', icon: '学', match: ['/m/students'] },
  { to: '/follow-ups', label: '待跟进', icon: '跟', match: ['/follow-ups', '/tasks'] },
  { to: '/m/notifications', label: '通知', icon: '铃', match: ['/m/notifications'] },
  { to: '/m/me', label: '我的', icon: '我', match: ['/m/me'] },
]

function isActive(item) {
  return item.match.some((p) => route.path === p || route.path.startsWith(`${p}/`))
}
function go(to) {
  if (route.path !== to) router.push(to)
}
</script>

<style scoped>
.m-tabbar {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 50;
  display: grid; grid-template-columns: repeat(5, 1fr);
  height: calc(56px + env(safe-area-inset-bottom, 0px));
  padding-bottom: env(safe-area-inset-bottom, 0px);
  background: rgba(255, 255, 255, 0.94);
  border-top: 1px solid var(--gq-border);
  backdrop-filter: blur(10px);
}
.m-tab {
  border: 0; background: transparent;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 2px; color: #64748b; font-size: 11px; padding: 6px 0 4px;
}
.m-tab.active { color: var(--gq-sea); font-weight: 700; }
.ico { font-size: 16px; line-height: 1.1; }
.lab { line-height: 1.2; }
</style>
