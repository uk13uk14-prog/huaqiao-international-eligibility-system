<template>
  <div class="m-page">
    <header class="m-hd">
      <button v-if="studentId" type="button" class="back" @click="$router.back()">‹ 返回</button>
      <h1>AI 专家</h1>
      <p class="gq-muted">画像 · 风险 · 选校 · 材料 · 家长报告 · 规划</p>
    </header>

    <section v-if="!studentId" class="gq-panel block">
      <h3>先选择学生</h3>
      <form class="search" @submit.prevent="search">
        <el-input v-model="q" clearable placeholder="搜索学生" />
        <el-button type="primary" :loading="searching" native-type="submit">搜索</el-button>
      </form>
      <article
        v-for="s in students"
        :key="s.id"
        class="pick"
        role="button"
        @click="$router.push(`/m/ai/${s.id}`)"
      >
        <strong>{{ s.display_name || `#${s.id}` }}</strong>
        <span class="gq-muted">{{ s.owner?.email || s.user_id }}</span>
      </article>
    </section>

    <template v-else>
      <section class="gq-panel block" v-if="profile">
        <strong>{{ profile.meta?.display_name || `学生 #${studentId}` }}</strong>
        <p class="gq-muted">#{{ studentId }} · {{ profile.owner?.email }}</p>
        <el-button text type="primary" @click="$router.push(`/m/students/${studentId}`)">
          查看 Student 360
        </el-button>
      </section>

      <section class="block">
        <h3>生成报告</h3>
        <div class="kinds">
          <el-button
            v-for="(label, kind) in kinds"
            :key="kind"
            size="small"
            :loading="generating === kind"
            @click="generate(kind)"
          >{{ label }}</el-button>
        </div>
      </section>

      <section class="block" v-if="activeDraft">
        <div class="row">
          <el-tag :type="statusType(activeDraft.status)" effect="dark">{{ activeDraft.status }}</el-tag>
          <span class="gq-muted">{{ kindLabel(activeDraft.report_kind) }} · #{{ activeDraft.id }}</span>
        </div>
        <el-input
          v-model="editContent"
          type="textarea"
          :rows="12"
          style="margin-top:8px"
          :disabled="activeDraft.status === 'PUBLISHED'"
        />
        <div class="actions">
          <el-button v-if="canEdit" size="small" @click="saveEdit">编辑 / 提交审核</el-button>
          <el-button v-if="canApprove" size="small" type="success" @click="approve">批准</el-button>
          <el-button v-if="canPublish" size="small" type="danger" @click="publish">发布</el-button>
        </div>
        <p v-if="msg" class="gq-muted">{{ msg }}</p>
      </section>

      <section class="block">
        <h3>历史草稿</h3>
        <article v-for="d in history" :key="d.id" class="pick" @click="selectDraft(d)">
          <div class="row">
            <strong>{{ kindLabel(d.report_kind) }}</strong>
            <el-tag size="small" :type="statusType(d.status)">{{ d.status }}</el-tag>
          </div>
          <span class="gq-muted">#{{ d.id }} · {{ d.updated_at || d.created_at }}</span>
        </article>
        <p v-if="!history.length" class="gq-muted">暂无草稿</p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref, toRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import { useStudentAi } from '../composables/useStudentAi'

const props = defineProps({
  studentId: { type: [String, Number], default: '' },
})

const route = useRoute()
const q = ref('')
const students = ref([])
const searching = ref(false)
const profile = ref(null)

const {
  kinds,
  activeDraft,
  editContent,
  generating,
  msg,
  history,
  canEdit,
  canApprove,
  canPublish,
  statusType,
  kindLabel,
  bootstrap,
  generate,
  selectDraft,
  saveEdit,
  approve,
  publish,
} = useStudentAi(toRef(props, 'studentId'))

async function search() {
  searching.value = true
  try {
    const data = await api.students(q.value)
    students.value = data.students || []
  } finally {
    searching.value = false
  }
}

async function loadStudent() {
  if (!props.studentId) {
    profile.value = null
    return
  }
  profile.value = await api.student360(props.studentId)
  await bootstrap(profile.value.report_kinds)
  const draftId = route.query.draft
  if (draftId) {
    const hit = history.value.find((d) => String(d.id) === String(draftId))
    if (hit) selectDraft(hit)
  }
}

onMounted(async () => {
  if (!props.studentId) await search()
  else await loadStudent()
})
watch(() => props.studentId, loadStudent)
</script>

<style scoped>
.m-page { padding: 12px 14px; }
.m-hd h1 { margin: 4px 0 0; font-size: 22px; }
.m-hd p { margin: 4px 0 10px; }
.back { border: 0; background: transparent; color: var(--gq-sea); padding: 0; }
.block { margin-bottom: 14px; }
.block h3 { margin: 0 0 8px; font-size: 15px; }
.search { display: flex; gap: 8px; margin-bottom: 10px; }
.kinds { display: flex; flex-wrap: wrap; gap: 8px; }
.pick {
  border: 1px solid var(--gq-border); border-radius: 10px; padding: 10px 12px;
  background: #fff; margin-bottom: 8px; display: flex; flex-direction: column; gap: 4px;
}
.row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
</style>
