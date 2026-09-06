<template>
  <div class="m-page">
    <header class="m-hd">
      <h1>通知</h1>
      <p class="gq-muted">待办提醒 · 审核 · 学生风险</p>
    </header>

    <div class="filters">
      <button
        v-for="f in filters"
        :key="f.key"
        type="button"
        :class="{ active: filter === f.key }"
        @click="filter = f.key"
      >
        {{ f.label }}
      </button>
    </div>

    <div v-if="loading" class="gq-muted pad">加载中…</div>
    <div v-else-if="!filtered.length" class="gq-muted empty">暂无通知</div>
    <article
      v-for="n in filtered"
      :key="n.id"
      class="card"
      :class="{ unread: n.unread, crit: n.priority === 'CRITICAL', high: n.priority === 'HIGH' }"
      @click="openItem(n)"
    >
      <div class="row">
        <strong>{{ n.title }}</strong>
        <span class="prio">{{ n.priority }}</span>
      </div>
      <p class="body">{{ n.body }}</p>
      <p class="gq-muted meta">{{ n.event_type }} · {{ n.created_at || '—' }}</p>
    </article>
    <p v-if="error" class="err">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const error = ref('')
const filter = ref('all')

const filters = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待处理' },
  { key: 'high', label: '高优先级' },
  { key: 'read', label: '已读' },
]

const filtered = computed(() => {
  const list = items.value || []
  if (filter.value === 'pending') return list.filter((n) => n.unread)
  if (filter.value === 'high') return list.filter((n) => n.priority === 'HIGH' || n.priority === 'CRITICAL')
  if (filter.value === 'read') return list.filter((n) => !n.unread)
  return list
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.notifications()
    items.value = data.items || []
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function openItem(n) {
  try {
    if (n.unread) await api.notificationRead(n.id)
  } catch {
    /* ignore */
  }
  const url = n.action_url || ''
  if (url.includes('/m/ai/') || url.includes('/ai/')) {
    const sid = n.student_id
    if (sid) router.push(`/m/ai/${sid}`)
    else router.push('/m/ai')
  } else if (n.student_id) {
    router.push(`/m/students/${n.student_id}`)
  } else if (url.startsWith('/m/')) {
    router.push(url)
  }
  await load()
}

onMounted(load)
</script>

<style scoped>
.m-page { padding: 12px 14px 8px; }
.m-hd h1 { margin: 0; font-size: 22px; }
.m-hd p { margin: 4px 0 12px; }
.filters { display: flex; gap: 6px; overflow-x: auto; margin-bottom: 12px; }
.filters button {
  border: 1px solid var(--gq-border); background: #fff; border-radius: 999px;
  padding: 6px 12px; font-size: 13px; white-space: nowrap; color: #64748b;
}
.filters button.active { background: var(--gq-sea); color: #fff; border-color: var(--gq-sea); }
.card {
  border: 1px solid var(--gq-border); border-radius: 12px; padding: 12px;
  margin-bottom: 10px; background: #fff; text-align: left; width: 100%;
}
.card.unread { border-color: var(--gq-sea); }
.card.high { border-left: 3px solid var(--gq-warn); }
.card.crit { border-left: 3px solid #dc2626; }
.row { display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; }
.prio { font-size: 11px; color: #64748b; }
.body { margin: 6px 0; font-size: 14px; color: #334155; }
.meta { margin: 0; font-size: 12px; }
.empty, .pad { padding: 16px 0; }
.err { color: #dc2626; }
</style>
