<template>
  <div class="m-page">
    <header class="m-hd">
      <h1>学生</h1>
      <p class="gq-muted">搜索并进入 Student 360</p>
    </header>
    <form class="search" @submit.prevent="load">
      <el-input v-model="q" clearable placeholder="display_name / 所属用户" />
      <el-button type="primary" :loading="loading" native-type="submit">搜索</el-button>
    </form>
    <div v-if="loading && !students.length" class="gq-muted pad">加载中…</div>
    <div v-else-if="!students.length" class="gq-muted pad">无匹配学生</div>
    <article
      v-for="s in students"
      :key="s.id"
      class="card"
      role="button"
      tabindex="0"
      @click="go(s.id)"
      @keyup.enter="go(s.id)"
    >
      <div class="row">
        <strong>{{ s.display_name || `学生 #${s.id}` }}</strong>
        <el-tag size="small" type="info">#{{ s.id }}</el-tag>
      </div>
      <p class="gq-muted meta">{{ s.owner?.email || s.user_id }} · {{ s.status || '—' }}</p>
      <p class="hint">{{ s.goal_hint || '暂无目标提示' }}</p>
    </article>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'

const router = useRouter()
const students = ref([])
const q = ref('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await api.students(q.value)
    students.value = data.students || []
  } finally {
    loading.value = false
  }
}
function go(id) {
  router.push(`/m/students/${id}`)
}
onMounted(load)
</script>

<style scoped>
.m-page { padding: 12px 14px; }
.m-hd h1 { margin: 0; font-size: 22px; }
.m-hd p { margin: 4px 0 12px; }
.search { display: flex; gap: 8px; margin-bottom: 12px; }
.card {
  border: 1px solid var(--gq-border); border-radius: 12px; padding: 12px;
  background: #fff; margin-bottom: 8px;
}
.row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.meta { margin: 6px 0 0; font-size: 12px; }
.hint { margin: 8px 0 0; font-size: 13px; color: #334155; }
.pad { padding: 16px 0; }
</style>
