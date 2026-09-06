<template>
  <div>
    <h1 class="page-title">{{ title }}</h1>
    <p class="page-sub gq-muted">点击进入对应 Student 360 · AI 不自动发送</p>
    <el-radio-group v-model="bucket" @change="load" style="margin-bottom:12px">
      <el-radio-button value="today">今天</el-radio-button>
      <el-radio-button value="upcoming">即将到期</el-radio-button>
      <el-radio-button value="overdue">已逾期</el-radio-button>
      <el-radio-button value="done">已完成</el-radio-button>
    </el-radio-group>
    <el-table :data="items" empty-text="暂无记录" @row-click="go" style="cursor:pointer">
      <el-table-column label="学生" min-width="140"><template #default="{ row }">{{ row.display_name }}</template></el-table-column>
      <el-table-column label="阶段" width="110" prop="crm_stage_label" />
      <el-table-column label="风险" width="90" prop="risk_level" />
      <el-table-column label="下一步" min-width="160"><template #default="{ row }">{{ row.next_action || '未设置' }}</template></el-table-column>
      <el-table-column label="下次跟进" width="170"><template #default="{ row }">{{ row.next_follow_up_at || '未设置' }}</template></el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'

const route = useRoute()
const router = useRouter()
const bucket = ref(route.meta.bucket || 'today')
const items = ref([])
const title = computed(() => ({
  today: '今日任务',
  upcoming: '待跟进',
  overdue: '逾期任务',
  done: '已完成',
}[bucket.value] || '待办中心'))

async function load() {
  items.value = (await api.followUpCenter(bucket.value)).items || []
}
function go(row) { router.push(`/students/${row.id}`) }
onMounted(load)
</script>
