<template>
  <div class="m-page">
    <header class="m-hd">
      <h1>待审核</h1>
      <p class="gq-muted">DRAFT / REVIEWED / APPROVED · 一键进入</p>
    </header>

    <div class="filters">
      <button
        v-for="s in statuses"
        :key="s"
        type="button"
        :class="{ on: status === s }"
        @click="status = s"
      >{{ s }}</button>
    </div>

    <div v-if="loading" class="gq-muted pad">汇总审核队列中…</div>
    <div v-else-if="!filtered.length" class="gq-muted pad">当前状态无待办</div>

    <article
      v-for="item in filtered"
      :key="`${item.student_id}-${item.id}`"
      class="card"
      @click="open(item)"
    >
      <div class="row">
        <strong>{{ item.student_name || `学生 #${item.student_id}` }}</strong>
        <el-tag size="small" :type="tagType(item.status)">{{ item.status }}</el-tag>
      </div>
      <p class="gq-muted">{{ kindLabel(item.report_kind) }} · 草稿 #{{ item.id }}</p>
      <p class="meta">{{ item.updated_at || item.created_at || '' }}</p>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { DEFAULT_REPORT_KINDS } from '../composables/useStudentAi'

const router = useRouter()
const statuses = ['DRAFT', 'REVIEWED', 'APPROVED']
const status = ref('DRAFT')
const items = ref([])
const loading = ref(true)

const filtered = computed(() => items.value.filter((x) => x.status === status.value))

function tagType(s) {
  if (s === 'APPROVED') return 'warning'
  if (s === 'REVIEWED') return 'info'
  return ''
}
function kindLabel(k) {
  return DEFAULT_REPORT_KINDS[k] || k
}
function open(item) {
  router.push({ path: `/m/ai/${item.student_id}`, query: { draft: String(item.id) } })
}

onMounted(async () => {
  loading.value = true
  try {
    const list = await api.students('')
    const students = (list.students || []).slice(0, 40)
    const chunks = await Promise.all(
      students.map(async (s) => {
        try {
          const d = await api.aiDrafts(s.id)
          return (d.drafts || [])
            .filter((x) => statuses.includes(x.status))
            .map((x) => ({
              ...x,
              student_id: s.id,
              student_name: s.display_name,
            }))
        } catch {
          return []
        }
      }),
    )
    items.value = chunks.flat().sort((a, b) =>
      String(b.updated_at || '').localeCompare(String(a.updated_at || '')),
    )
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.m-page { padding: 12px 14px; }
.m-hd h1 { margin: 0; font-size: 22px; }
.m-hd p { margin: 4px 0 12px; }
.filters { display: flex; gap: 8px; margin-bottom: 12px; overflow-x: auto; }
.filters button {
  border: 1px solid var(--gq-border); background: #fff; border-radius: 999px;
  padding: 6px 12px; font-size: 12px; white-space: nowrap;
}
.filters button.on { background: var(--gq-sea); color: #fff; border-color: var(--gq-sea); }
.card {
  border: 1px solid var(--gq-border); border-radius: 12px; padding: 12px;
  background: #fff; margin-bottom: 8px;
}
.row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.meta { margin: 6px 0 0; font-size: 12px; color: #94a3b8; }
.pad { padding: 16px 0; }
</style>
