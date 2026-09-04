<template>
  <div class="m-page">
    <header class="m-hd">
      <h1>运营首页</h1>
      <p class="gq-muted">今日概览 · 快捷入口</p>
    </header>

    <div v-if="loading" class="gq-muted pad">加载中…</div>
    <template v-else-if="data">
      <div class="kpi-grid">
        <button type="button" class="kpi accent" @click="$router.push('/m/notifications')">
          <span class="k">新消息</span>
          <strong>{{ unreadNotif ?? '—' }}</strong>
        </button>
        <button type="button" class="kpi" @click="$router.push('/m/students')">
          <span class="k">总用户</span>
          <strong>{{ data.total_users ?? '—' }}</strong>
        </button>
        <button type="button" class="kpi warn" @click="$router.push('/m/students')">
          <span class="k">Trial 将到期</span>
          <strong>{{ data.trial_expiring_soon ?? '—' }}</strong>
        </button>
        <button type="button" class="kpi accent" @click="$router.push('/m/approval')">
          <span class="k">待审核</span>
          <strong>{{ data.pending_human_review ?? '—' }}</strong>
        </button>
        <button type="button" class="kpi" @click="$router.push('/m/students')">
          <span class="k">学生档案</span>
          <strong>{{ data.student_profiles ?? '—' }}</strong>
        </button>
      </div>

      <section class="block">
        <h2>快捷入口</h2>
        <div class="shortcuts">
          <button type="button" @click="$router.push('/m/students')">学生搜索</button>
          <button type="button" @click="$router.push('/m/approval')">审核队列</button>
          <button type="button" @click="$router.push('/m/ai')">AI 专家</button>
          <button type="button" @click="$router.push('/m/published')">已发布</button>
          <button type="button" @click="$router.push('/m/notifications')">通知中心</button>
        </div>
      </section>

      <section class="block">
        <div class="sec-hd">
          <h2>最近咨询</h2>
          <button type="button" class="link" @click="$router.push('/m/published')">全部</button>
        </div>
        <div v-if="!(data.recent_consultations || []).length" class="gq-muted empty">暂无咨询</div>
        <article v-for="c in (data.recent_consultations || []).slice(0, 8)" :key="c.id" class="card">
          <div class="row">
            <strong>#{{ c.id }} {{ c.title || '咨询' }}</strong>
            <el-tag size="small">{{ c.status }}</el-tag>
          </div>
          <p class="gq-muted meta">用户 {{ c.user_id }} · {{ c.created_at || '—' }}</p>
        </article>
      </section>
    </template>
    <p v-if="error" class="err">{{ error }}</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'

const data = ref(null)
const loading = ref(true)
const error = ref('')
const unreadNotif = ref(null)

onMounted(async () => {
  try {
    data.value = await api.dashboard()
    try {
      const n = await api.notifications({ unread_only: true })
      unreadNotif.value = n.unread_count ?? (n.items || []).length
    } catch {
      unreadNotif.value = null
    }
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.m-page { padding: 12px 14px 8px; }
.m-hd h1 { margin: 0; font-size: 22px; }
.m-hd p { margin: 4px 0 12px; }
.kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.kpi {
  text-align: left; border: 1px solid var(--gq-border); background: var(--gq-panel);
  border-radius: 12px; padding: 12px;
}
.kpi strong { display: block; font-size: 26px; color: var(--gq-sea); margin: 4px 0; }
.kpi .k { font-size: 12px; color: #64748b; }
.kpi.warn strong { color: var(--gq-warn); }
.kpi.accent strong { color: var(--gq-accent); }
.block { margin-top: 18px; }
.block h2, .sec-hd h2 { margin: 0 0 8px; font-size: 16px; }
.sec-hd { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.shortcuts { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.shortcuts button, .link {
  border: 1px solid var(--gq-border); background: #fff; border-radius: 10px;
  padding: 12px; font-size: 14px; color: var(--gq-sea);
}
.link { border: 0; background: transparent; padding: 0; }
.card {
  border: 1px solid var(--gq-border); border-radius: 12px; padding: 12px;
  background: #fff; margin-bottom: 8px;
}
.row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.meta { margin: 6px 0 0; font-size: 12px; }
.empty, .pad { padding: 12px 0; }
.err { color: #b91c1c; }
</style>
