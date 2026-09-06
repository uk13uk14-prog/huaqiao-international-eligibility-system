<template>
  <div v-if="data">
    <h1 class="page-title">用户详情 #{{ data.user.id }}</h1>
    <p class="page-sub gq-muted">{{ data.user.email }} · {{ planCodeLabel(data.user.plan_code, { isPaid: data.user.is_paid }) }} · {{ human(data.user.trial?.trial_status, '—') }}</p>
    <div class="gq-panel">
      <h3>名下学生</h3>
      <el-table :data="data.students" @row-click="goStudent" style="cursor:pointer">
        <el-table-column prop="id" label="学生 ID" width="90" />
        <el-table-column label="姓名">
          <template #default="{ row }">{{ studentName(row) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="updated_at" label="更新时间" width="180" />
        <el-table-column v-if="canEditName" label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openName(row)">改姓名</el-button>
            <el-button link type="primary" @click.stop="goStudent(row)">进入360</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="nameOpen" title="修改学生姓名" width="420px" destroy-on-close>
      <p class="gq-muted" style="margin:0 0 12px">仅超级管理员可保存。勿把邮箱当作学生姓名。</p>
      <el-form :model="nameForm" label-width="88px">
        <el-form-item label="中文姓名">
          <el-input v-model="nameForm.chinese_name" maxlength="80" />
        </el-form-item>
        <el-form-item label="英文名">
          <el-input v-model="nameForm.english_name" maxlength="80" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="nameOpen = false">取消</el-button>
        <el-button type="primary" :loading="nameSaving" @click="saveName">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import { useAdminSession } from '../composables/useAdminSession'
import { human, planCodeLabel } from '../utils/opsDisplay'

const props = defineProps({ userId: { type: [String, Number], required: true } })
const router = useRouter()
const { can } = useAdminSession()
const canEditName = computed(() => can('student360.profile.write'))
const data = ref(null)
const nameOpen = ref(false)
const nameSaving = ref(false)
const nameTarget = ref(null)
const nameForm = ref({ chinese_name: '', english_name: '' })

function studentName(row) {
  const n = row.display_name
  if (!n || n === '未命名学生' || String(n).includes('@')) return '待补姓名'
  return n
}
async function load() { data.value = await api.user(props.userId) }
function goStudent(row) { router.push(`/students/${row.id}`) }
async function openName(row) {
  nameTarget.value = row
  try {
    const d = await api.student360(row.id)
    const b = d.sections?.basic_info || {}
    nameForm.value = { chinese_name: b.chinese_name || '', english_name: b.english_name || '' }
  } catch {
    const shown = studentName(row)
    nameForm.value = { chinese_name: shown === '待补姓名' ? '' : shown, english_name: '' }
  }
  nameOpen.value = true
}
async function saveName() {
  if (!nameTarget.value || !canEditName.value) return
  const cn = String(nameForm.value.chinese_name || '')
  const en = String(nameForm.value.english_name || '')
  if (cn.includes('@') || en.includes('@')) {
    ElMessage.error('姓名不能使用邮箱')
    return
  }
  if (!cn.trim() && !en.trim()) {
    ElMessage.error('请至少填写中文姓名或英文名')
    return
  }
  nameSaving.value = true
  try {
    await api.patchStudentBasic(nameTarget.value.id, {
      chinese_name: cn.trim(),
      english_name: en.trim(),
    })
    ElMessage.success('学生姓名已保存')
    nameOpen.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    nameSaving.value = false
  }
}
onMounted(load)
watch(() => props.userId, load)
</script>
