<template>
  <div>
    <h1 class="page-title">员工管理</h1>
    <p class="page-sub gq-muted">员工账号与客户账号严格分离 · 停用保留历史跟进</p>
    <div class="filters">
      <el-input v-model="q" placeholder="姓名 / 邮箱" clearable style="max-width:240px" @keyup.enter="load" />
      <el-select v-model="role" clearable placeholder="角色" style="width:160px" @change="load">
        <el-option label="超级管理员" value="super_admin" />
        <el-option label="运营管理员" value="operations_admin" />
        <el-option label="顾问" value="consultant" />
        <el-option label="客服" value="support" />
      </el-select>
      <el-button type="primary" @click="load">搜索</el-button>
      <el-button v-if="canWrite" type="success" @click="openCreate">+ 新增员工</el-button>
    </div>
    <el-table :data="rows" empty-text="暂无记录">
      <el-table-column label="姓名" min-width="120"><template #default="{ row }">{{ row.name || '待补充' }}</template></el-table-column>
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column label="角色" width="120"><template #default="{ row }">{{ row.role_label }}</template></el-table-column>
      <el-table-column label="职位" width="130"><template #default="{ row }">{{ row.job_title || '未设置' }}</template></el-table-column>
      <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="row.status === 'ACTIVE' ? 'success' : 'info'">{{ row.status_label }}</el-tag></template></el-table-column>
      <el-table-column label="负责学生数" width="110" prop="assigned_student_count" />
      <el-table-column label="最后登录" width="170"><template #default="{ row }">{{ row.last_login_at || '未设置' }}</template></el-table-column>
      <el-table-column label="创建时间" width="170"><template #default="{ row }">{{ row.created_at || '暂无记录' }}</template></el-table-column>
      <el-table-column v-if="canWrite" label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="edit(row)">编辑</el-button>
          <el-button link @click="resetPw(row)">重置密码</el-button>
          <el-button v-if="row.status === 'ACTIVE'" link type="danger" @click="toggle(row, false)">停用</el-button>
          <el-button v-else link type="success" @click="toggle(row, true)">启用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dlg" :title="form.id ? '编辑员工' : '新增员工'" width="480px">
      <el-form label-position="top">
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" :disabled="!!form.id" /></el-form-item>
        <el-form-item label="职位">
          <el-select v-model="form.job_title" allow-create filterable placeholder="职位">
            <el-option v-for="t in titles" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role">
            <el-option label="超级管理员" value="super_admin" />
            <el-option label="运营管理员" value="operations_admin" />
            <el-option label="顾问" value="consultant" />
            <el-option label="客服" value="support" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!form.id" label="临时密码"><el-input v-model="form.password" show-password /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api/client'
import { useAdminSession } from '../composables/useAdminSession'

const { can, refresh } = useAdminSession()
const canWrite = ref(false)
const rows = ref([])
const q = ref('')
const role = ref()
const dlg = ref(false)
const titles = ['升学顾问', '高级升学顾问', '客服', '运营', '管理员']
const form = ref({ name: '', email: '', role: 'consultant', job_title: '升学顾问', password: '', id: null })

async function load() {
  const data = await api.employees({ q: q.value, role: role.value })
  rows.value = data.employees || []
}
function openCreate() {
  form.value = { name: '', email: '', role: 'consultant', job_title: '升学顾问', password: '', id: null }
  dlg.value = true
}
function edit(row) {
  form.value = { id: row.id, name: row.name, email: row.email, role: row.role, job_title: row.job_title, password: '' }
  dlg.value = true
}
async function save() {
  try {
    if (form.value.id) {
      await api.patchEmployee(form.value.id, { name: form.value.name, role: form.value.role, job_title: form.value.job_title })
    } else {
      await api.createEmployee({
        name: form.value.name,
        email: form.value.email,
        role: form.value.role,
        job_title: form.value.job_title,
        password: form.value.password,
        status: 'ACTIVE',
      })
    }
    ElMessage.success('已保存')
    dlg.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}
async function toggle(row, enable) {
  await ElMessageBox.confirm(enable ? '启用该员工？' : '停用后立即无法登录，历史跟进将保留。', '确认', { type: 'warning' })
  if (enable) await api.enableEmployee(row.id)
  else await api.disableEmployee(row.id)
  await load()
}
async function resetPw(row) {
  const { value } = await ElMessageBox.prompt('输入一次性临时密码（不少于 8 位）', '重置密码', { inputType: 'password' })
  await api.resetEmployeePassword(row.id, value)
  ElMessage.success('已重置，员工下次登录需改密')
}
onMounted(async () => {
  try { await refresh() } catch { /* ignore */ }
  canWrite.value = can('employees.write')
  await load()
})
</script>

<style scoped>
.filters { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
</style>
