import { computed, ref, unref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

export const DEFAULT_REPORT_KINDS = {
  student_portrait: '学生画像',
  risk_analysis: '风险分析',
  school_advice: '选校建议',
  material_gaps: '材料缺口',
  parent_report: '家长沟通报告',
  one_on_one_plan: '一对一规划',
}

/** Shared AI Expert + approval flow for desktop Student360 and mobile AI/Approval. */
export function useStudentAi(studentIdSource) {
  const drafts = ref([])
  const kinds = ref({ ...DEFAULT_REPORT_KINDS })
  const activeDraft = ref(null)
  const editContent = ref('')
  const generating = ref('')
  const msg = ref('')
  const loading = ref(false)

  const history = computed(() => drafts.value || [])
  const canEdit = computed(() => ['DRAFT', 'REVIEWED'].includes(activeDraft.value?.status))
  const canApprove = computed(() => ['DRAFT', 'REVIEWED'].includes(activeDraft.value?.status))
  const canPublish = computed(() => activeDraft.value?.status === 'APPROVED')

  function sid() {
    return unref(studentIdSource)
  }

  function statusType(s) {
    if (s === 'PUBLISHED') return 'success'
    if (s === 'APPROVED') return 'warning'
    if (s === 'REVIEWED') return 'info'
    return ''
  }

  function kindLabel(k) {
    return kinds.value?.[k] || DEFAULT_REPORT_KINDS[k] || k
  }

  async function refreshDrafts() {
    const id = sid()
    if (id == null || id === '') return
    const d = await api.aiDrafts(id)
    drafts.value = d.drafts || []
    if (d.report_kinds && Object.keys(d.report_kinds).length) {
      kinds.value = d.report_kinds
    }
  }

  async function bootstrap(reportKindsFrom360) {
    loading.value = true
    try {
      if (reportKindsFrom360 && Object.keys(reportKindsFrom360).length) {
        kinds.value = reportKindsFrom360
      }
      await refreshDrafts()
    } finally {
      loading.value = false
    }
  }

  async function generate(kind) {
    generating.value = kind
    msg.value = ''
    try {
      const res = await api.aiGenerate(sid(), kind, false)
      activeDraft.value = res.draft
      editContent.value = res.draft.raw_draft || res.draft.content || ''
      ElMessage.success('已生成并持久化 DRAFT（未发布）')
      await refreshDrafts()
    } catch (e) {
      ElMessage.error(e.message || '生成失败')
    } finally {
      generating.value = ''
    }
  }

  function selectDraft(row) {
    activeDraft.value = row
    editContent.value = row.raw_draft || row.final_report || row.content || ''
    msg.value =
      row.status === 'PUBLISHED' ? 'PUBLISHED 只读；如需修改请重新「生成」新版本' : ''
  }

  async function saveEdit() {
    if (!canEdit.value) return
    const res = await api.aiEdit(sid(), activeDraft.value.id, editContent.value, true)
    activeDraft.value = res.draft
    msg.value = `已保存 → ${res.draft.status}`
    await refreshDrafts()
  }

  async function approve() {
    if (!canApprove.value) return
    const res = await api.aiApprove(sid(), activeDraft.value.id)
    activeDraft.value = res.draft
    msg.value = '已批准 APPROVED（学生仍不可见）'
    await refreshDrafts()
  }

  async function publish() {
    if (!canPublish.value) return
    try {
      const res = await api.aiPublish(sid(), activeDraft.value.id)
      activeDraft.value = res.draft
      msg.value = '已发布 PUBLISHED（学生端可读）'
      ElMessage.success('已发布')
      await refreshDrafts()
    } catch (e) {
      msg.value = e.message
      ElMessage.warning(e.message)
    }
  }

  watch(
    () => unref(studentIdSource),
    () => {
      activeDraft.value = null
      editContent.value = ''
      drafts.value = []
    },
  )

  return {
    drafts,
    kinds,
    activeDraft,
    editContent,
    generating,
    msg,
    loading,
    history,
    canEdit,
    canApprove,
    canPublish,
    statusType,
    kindLabel,
    refreshDrafts,
    bootstrap,
    generate,
    selectDraft,
    saveEdit,
    approve,
    publish,
  }
}
