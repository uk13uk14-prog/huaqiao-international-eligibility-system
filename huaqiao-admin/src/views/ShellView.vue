<template>
  <el-container class="shell">
    <el-aside width="220px" class="aside">
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
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="gq-muted">desktop-first · SaaS JWT · 不写生产</span>
        <el-button text type="danger" @click="logout">退出</el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { clearToken } from '../api/client'

const route = useRoute()
const router = useRouter()
function logout() {
  clearToken()
  router.replace('/login')
}
</script>

<style scoped>
.shell { min-height: 100vh; }
.aside {
  background: rgba(255,255,255,0.72);
  border-right: 1px solid var(--gq-border);
  padding: 12px 0;
}
.brand-block { padding: 8px 18px 16px; }
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: transparent;
  border-bottom: 1px solid var(--gq-border);
}
</style>
