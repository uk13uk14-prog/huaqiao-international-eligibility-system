<template>
  <div class="m-page">
    <header class="m-hd">
      <h1>学生 CRM</h1>
      <p class="gq-muted">点击卡片进入 Student 360 · 不展示证件明文 / cipher / raw JSON</p>
    </header>
    <form class="search" @submit.prevent="load">
      <el-input v-model="q" clearable placeholder="姓名 / 所属邮箱 / Student ID" />
      <el-button type="primary" :loading="loading" native-type="submit">搜索</el-button>
    </form>
    <div v-if="loading && !students.length" class="gq-muted pad">加载中…</div>
    <div v-else-if="!students.length" class="gq-muted pad">{{ EMPTY.none }}</div>
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
        <strong>{{ displayName(s) }}</strong>
        <el-tag size="small" :type="riskTagType(s.risk_level)">{{ riskLabel(s.risk_level) }}</el-tag>
      </div>
      <p class="meta">
        {{ identityLabel(s) }}
        · {{ human(s.crm_stage_label || s.crm_stage, EMPTY.unassigned) }}
        · {{ human(s.intended_entry_year, EMPTY.unset) }} 入学
      </p>
      <p class="hint">
        负责人：{{ human(s.assignee_label, EMPTY.unassigned) }}
        · 下一步：{{ human(s.next_action, EMPTY.unset) }}
      </p>
      <p class="hint">
        下次跟进：{{ humanDateTime(s.next_follow_up_at, EMPTY.unset) }}
        · 更新：{{ humanDateTime(s.updated_at, EMPTY.none) }}
      </p>
      <div class="go-link">进入 360 ›</div>
    </article>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import {
  EMPTY,
  human,
  humanDateTime,
  riskLabel,
  riskTagType,
} from '../utils/opsDisplay'

const router = useRouter()
const students = ref([])
const q = ref('')
const loading = ref(false)

function displayName(row) {
  const n = row.display_name
  if (!n || n === '未命名学生' || n === '待补姓名') return EMPTY.name
  if (String(n).includes('@')) return EMPTY.name
  return n
}

function identityLabel(row) {
  const track = row.identity_track || row.identity_route
  if (track) return human(track)
  return EMPTY.pending
}

async function load() {
  loading.value = true
  try {
    const data = await api.students(q.value ? { q: q.value } : {})
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
.m-page { padding: 12px 14px; max-width: 100vw; overflow-x: hidden; box-sizing: border-box; }
.m-hd h1 { margin: 0; font-size: 22px; }
.m-hd p { margin: 4px 0 12px; font-size: 13px; }
.search { display: flex; gap: 8px; margin-bottom: 12px; }
.card {
  border: 1px solid var(--gq-border); border-radius: 12px; padding: 12px;
  background: #fff; margin-bottom: 8px; cursor: pointer;
}
.row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.meta { margin: 6px 0 0; font-size: 12px; color: #64748b; }
.hint { margin: 6px 0 0; font-size: 13px; color: #334155; word-break: break-word; }
.go-link { margin-top: 8px; font-size: 13px; color: #1d4ed8; font-weight: 600; }
.pad { padding: 16px 0; }
</style>
