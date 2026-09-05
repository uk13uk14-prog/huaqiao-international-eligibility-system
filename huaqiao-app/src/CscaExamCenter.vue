<template>
  <div class="csca-center">
    <div v-if="loading" class="pad muted">加载中…</div>
    <template v-else>
      <section class="form-card">
        <h3 class="block-title">我的状态</h3>
        <van-cell title="CSCA 状态" :value="card.csca_status_label || '未计划'" />
        <van-cell title="成绩" :value="card.csca_score || '—'" />
        <van-cell title="等级" :value="card.csca_level || '—'" />
        <p class="hint">登录 / Trial / 正式会员均可使用，无额外会员门槛。</p>
      </section>

      <section class="form-card">
        <h3 class="block-title">关键时间</h3>
        <van-cell title="报名截止" :value="card.csca_registration_deadline || pending" />
        <van-cell title="考试日期" :value="card.csca_exam_date || pending" />
        <van-cell title="成绩发布" :value="card.csca_result_date || pending" />
        <p class="hint">无官方/后台/本人录入的真实日期时，显示「待官方公布」。系统不会编造日期。</p>
      </section>

      <section class="form-card">
        <h3 class="block-title">成绩状态</h3>
        <van-cell title="是否有成绩" :value="card.csca_score ? '已录入' : '暂无'" />
        <van-cell title="最近更新" :value="card.updated_at || '—'" />
      </section>

      <section class="form-card">
        <h3 class="block-title">准备事项</h3>
        <van-cell v-for="(item, idx) in prepChecklist" :key="idx" :title="`${idx + 1}. ${item}`" />
      </section>

      <section class="form-card">
        <h3 class="block-title">相关提醒</h3>
        <p class="hint">{{ remindersNote }}</p>
        <van-button block round type="primary" @click="$emit('goto-profile')">去档案更新 CSCA</van-button>
        <van-button block round plain type="primary" style="margin-top:8px" @click="$emit('goto-timeline')">查看时间轴</van-button>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { showToast } from 'vant'
import { saasApi } from './saasApi'
import { activeStudentId, normalizeStudentId } from './activeStudent'

defineEmits(['goto-profile', 'goto-timeline'])

const pending = '待官方公布'
const loading = ref(true)
const card = ref({
  csca_status_label: '未计划',
  csca_registration_deadline: pending,
  csca_exam_date: pending,
  csca_result_date: pending,
  csca_score: '',
  csca_level: '',
  updated_at: '',
})
const prepChecklist = ref([
  '确认本人护照/证件信息是否与报名一致',
  '查阅官方报名通道与考场须知（以官方公布为准）',
  '准备考试当日证件与文具',
  '关注成绩发布渠道（仅当官方/后台/本人录入日期后才提醒）',
])
const remindersNote = ref('仅在存在真实日期时，按 T-30/14/7/3/1/0 生成提醒；无真实日期不生成。')

async function load() {
  loading.value = true
  try {
    const sid = normalizeStudentId(activeStudentId.value)
    if (!sid) {
      showToast('请先创建或选择学生档案')
      return
    }
    const r = await saasApi.studentCsca(sid)
    card.value = { ...card.value, ...(r.card || {}) }
    if (Array.isArray(r.prep_checklist) && r.prep_checklist.length) prepChecklist.value = r.prep_checklist
    if (r.related_reminders_note) remindersNote.value = r.related_reminders_note
  } catch (e) {
    showToast(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(activeStudentId, load)
</script>

<style scoped>
.csca-center { padding-bottom: 24px; }
.block-title { margin: 0 0 8px; font-size: 16px; font-weight: 600; }
.hint { margin: 8px 12px 0; color: #6b7280; font-size: 12px; line-height: 1.5; }
.pad { padding: 16px; }
.muted { color: #6b7280; }
</style>
