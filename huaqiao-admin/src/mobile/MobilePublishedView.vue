<template>
  <div class="m-page">
    <header class="m-hd">
      <h1>已发布</h1>
      <p class="gq-muted">Published consultations · 只读查看</p>
    </header>

    <div v-if="loading" class="gq-muted pad">加载中…</div>
    <div v-else-if="!items.length" class="gq-muted pad">暂无已发布报告</div>

    <article
      v-for="item in items"
      :key="`${item.student_id}-${item.id}`"
      class="card"
      @click="open(item)"
    >
      <div class="row">
        <strong>{{ item.student_name || `学生 #${item.student_id}` }}</strong>
        <el-tag size="small" type="success">PUBLISHED</el-tag>
      </div>
      <p class="gq-muted">{{ kindLabel(item.report_kind) }} · #{{ item.id }}</p>
      <p class="meta">{{ item.updated_at || item.published_at || item.created_at }}</p>
    </article>

    <MobileBottomSheet v-model="sheetOpen" :title="sheetTitle">
      <pre class="gq-pre">{{ sheetBody }}</pre>
    </MobileBottomSheet>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'
import { DEFAULT_REPORT_KINDS } from '../composables/useStudentAi'
import MobileBottomSheet from './MobileBottomSheet.vue'

const items = ref([])
const loading = ref(true)
const sheetOpen = ref(false)
const sheetTitle = ref('')
const sheetBody = ref('')

function kindLabel(k) {
  return DEFAULT_REPORT_KINDS[k] || k
}
function open(item) {
  sheetTitle.value = `${kindLabel(item.report_kind)} · PUBLISHED`
  sheetBody.value = item.final_report || item.raw_draft || item.content || '(空)'
  sheetOpen.value = true
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
            .filter((x) => x.status === 'PUBLISHED')
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
.card {
  border: 1px solid var(--gq-border); border-radius: 12px; padding: 12px;
  background: #fff; margin-bottom: 8px;
}
.row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.meta { margin: 6px 0 0; font-size: 12px; color: #94a3b8; }
.pad { padding: 16px 0; }
.gq-pre {
  white-space: pre-wrap; font-size: 12px; background: #0f172a; color: #e2e8f0;
  padding: 10px; border-radius: 8px; max-height: 55vh; overflow: auto;
}
</style>
