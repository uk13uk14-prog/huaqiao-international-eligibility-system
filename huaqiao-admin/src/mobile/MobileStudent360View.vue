<template>
  <div v-if="data" class="m-page">
    <header class="m-hd">
      <button type="button" class="back" @click="$router.back()">‹ 返回</button>
      <h1>{{ data.ops_header?.display_name || data.meta?.display_name || `学生 #${data.student_id}` }}</h1>
      <p class="gq-muted">#{{ data.student_id }} · {{ data.owner?.email || '—' }}</p>
      <div class="ops-banner">
        <div>负责人：{{ data.ops_header?.assignee_label || data.crm?.assignee_label || '未分配' }}</div>
        <div>阶段：{{ data.ops_header?.crm_stage_label || data.crm?.crm_stage_label || '—' }}</div>
        <div>下一步：{{ data.ops_header?.next_action || data.crm?.next_action || '—' }}</div>
        <div>跟进：{{ data.ops_header?.next_follow_up_at || data.crm?.next_follow_up_at || '—' }}</div>
      </div>
      <div class="quick">
        <button type="button" @click="tab='follow'">记跟进</button>
        <button type="button" @click="$router.push(`/m/ai/${studentId}`)">AI建议</button>
        <button type="button" @click="tab='timeline'">时间线</button>
        <button type="button" @click="tab='consult'">专家规划</button>
      </div>
    </header>

    <el-tabs v-model="tab" class="tabs">
      <el-tab-pane label="概览" name="overview">
        <section class="gq-panel block">
          <h3>资格</h3>
          <el-tag>{{ data.eligibility?.mapping_status || '—' }}</el-tag>
          <p><strong>国际生：</strong>{{ data.eligibility?.international?.conclusion || '—' }}</p>
          <p><strong>华侨生：</strong>{{ data.eligibility?.huaqiao?.conclusion || '—' }}</p>
        </section>
        <section class="gq-panel block">
          <h3>目标提示</h3>
          <p>{{ data.meta?.goal_hint || '—' }}</p>
        </section>
        <el-button type="primary" style="width:100%" @click="$router.push(`/m/ai/${studentId}`)">
          打开 AI 专家
        </el-button>
      </el-tab-pane>

      <el-tab-pane label="档案" name="profile">
        <details v-for="sec in profileSections" :key="sec.key" class="fold" :open="sec.open">
          <summary>{{ sec.label }}</summary>
          <pre class="gq-pre">{{ pretty(sec.value) }}</pre>
        </details>
      </el-tab-pane>

      <el-tab-pane label="时间线" name="timeline">
        <article v-for="(t, i) in (data.timeline || [])" :key="i" class="tl">
          <strong>{{ t.title || '事项' }}</strong>
          <p class="gq-muted">{{ t.deadline || '—' }} · {{ t.status || '—' }}</p>
        </article>
        <p v-if="!(data.timeline || []).length" class="gq-muted">暂无时间线</p>
      </el-tab-pane>

      <el-tab-pane label="咨询" name="consult">
        <article
          v-for="d in history"
          :key="d.id"
          class="tl"
          role="button"
          @click="openDraft(d)"
        >
          <div class="row">
            <strong>{{ kindLabel(d.report_kind) }}</strong>
            <el-tag size="small" :type="statusType(d.status)">{{ d.status }}</el-tag>
          </div>
          <p class="gq-muted">#{{ d.id }} · {{ d.updated_at || d.created_at }}</p>
        </article>
        <p v-if="!history.length" class="gq-muted">暂无 AI 草稿</p>
      </el-tab-pane>
    </el-tabs>

    <MobileBottomSheet v-model="sheetOpen" :title="sheetTitle">
      <pre class="gq-pre sheet-pre">{{ sheetBody }}</pre>
    </MobileBottomSheet>
  </div>
  <div v-else class="pad gq-muted">{{ error || '加载中…' }}</div>
</template>

<script setup>
import { computed, onMounted, ref, toRef } from 'vue'
import { api } from '../api/client'
import { useStudentAi } from '../composables/useStudentAi'
import MobileBottomSheet from './MobileBottomSheet.vue'

const props = defineProps({ studentId: { type: [String, Number], required: true } })
const data = ref(null)
const error = ref('')
const tab = ref('overview')
const sheetOpen = ref(false)
const sheetTitle = ref('')
const sheetBody = ref('')

const { history, kindLabel, statusType, bootstrap } = useStudentAi(toRef(props, 'studentId'))

const profileSections = computed(() => {
  const s = data.value?.sections || {}
  return [
    { key: 'basic', label: '基本资料 / 所属用户', value: { basic: s.basic_info, owner: data.value?.owner }, open: true },
    { key: 'identity', label: '身份 / 国籍', value: s.identity, open: false },
    { key: 'education', label: '教育背景', value: s.education, open: false },
    { key: 'language', label: '语言成绩', value: s.language_exams, open: false },
    { key: 'csca', label: 'CSCA考试', value: data.value?.csca_card || s.csca, open: true },
    { key: 'goals', label: '目标大学 / 专业', value: s.goals, open: false },
  ]
})

function pretty(v) {
  return JSON.stringify(v ?? {}, null, 2)
}
function openDraft(d) {
  sheetTitle.value = `${kindLabel(d.report_kind)} · ${d.status}`
  sheetBody.value = d.final_report || d.raw_draft || d.content || '(空)'
  sheetOpen.value = true
}

onMounted(async () => {
  try {
    data.value = await api.student360(props.studentId)
    await bootstrap(data.value.report_kinds)
  } catch (e) {
    error.value = e.message || '加载失败'
  }
})
</script>

<style scoped>
.m-page { padding: 8px 14px 12px; }
.m-hd h1 { margin: 4px 0 0; font-size: 20px; }
.m-hd p { margin: 4px 0 8px; }
.back { border: 0; background: transparent; color: var(--gq-sea); font-size: 15px; padding: 0; }
.block { margin-bottom: 10px; }
.fold {
  border: 1px solid var(--gq-border); border-radius: 10px; background: #fff;
  margin-bottom: 8px; padding: 8px 10px;
}
.fold summary { cursor: pointer; font-weight: 600; }
.tl {
  border: 1px solid var(--gq-border); border-radius: 10px; padding: 10px;
  background: #fff; margin-bottom: 8px;
}
.row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.pad { padding: 24px 14px; }
.sheet-pre { max-height: 55vh; }
.gq-pre {
  white-space: pre-wrap; font-size: 12px; background: #0f172a; color: #e2e8f0;
  padding: 10px; border-radius: 8px; overflow: auto; max-height: 240px;
}
</style>

<style scoped>
.ops-banner{background:#eff6ff;border-radius:10px;padding:10px;margin:8px 0;font-size:13px;display:grid;gap:4px}
.quick{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0 12px}
.quick button{border:1px solid #cbd5e1;border-radius:10px;padding:10px;background:#fff}
</style>
