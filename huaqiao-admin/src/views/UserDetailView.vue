<template>
  <div v-if="data">
    <h1 class="page-title">用户详情 #{{ data.user.id }}</h1>
    <p class="page-sub gq-muted">{{ data.user.email }} · {{ data.user.plan_code }} · Trial {{ data.user.trial?.trial_status }}</p>
    <div class="gq-panel">
      <h3>名下学生</h3>
      <el-table :data="data.students" @row-click="goStudent" style="cursor:pointer">
        <el-table-column prop="id" label="学生 ID" width="90" />
        <el-table-column prop="display_name" label="姓名" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="updated_at" label="更新时间" width="180" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'

const props = defineProps({ userId: { type: [String, Number], required: true } })
const router = useRouter()
const data = ref(null)
async function load() { data.value = await api.user(props.userId) }
function goStudent(row) { router.push(`/students/${row.id}`) }
onMounted(load)
watch(() => props.userId, load)
</script>
