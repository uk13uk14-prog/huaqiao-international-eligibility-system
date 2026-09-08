<template>
  <div class="coop-admin">
    <h1 class="page-title">合作管理</h1>
    <p class="page-sub gq-muted">前台「合作中心」内容由本页维护，不写死在 H5</p>

    <section class="gq-panel" style="margin-bottom:20px">
      <h2 class="block-title">合作信息</h2>
      <el-form label-position="top" class="coop-form">
        <el-form-item label="页面标题">
          <el-input v-model="settings.page_title" :disabled="!canWrite" maxlength="40" />
        </el-form-item>
        <el-form-item label="合作介绍">
          <el-input v-model="settings.intro" type="textarea" :rows="4" :disabled="!canWrite" />
        </el-form-item>
        <div class="field-row">
          <el-form-item label="联系人">
            <el-input v-model="settings.contact_name" :disabled="!canWrite" />
          </el-form-item>
          <el-switch v-model="settings.show_contact_name" :disabled="!canWrite" active-text="前台展示" />
        </div>
        <div class="field-row">
          <el-form-item label="微信">
            <el-input v-model="settings.wechat" :disabled="!canWrite" />
          </el-form-item>
          <el-switch v-model="settings.show_wechat" :disabled="!canWrite" active-text="前台展示" />
        </div>
        <div class="field-row">
          <el-form-item label="电话">
            <el-input v-model="settings.phone" :disabled="!canWrite" />
          </el-form-item>
          <el-switch v-model="settings.show_phone" :disabled="!canWrite" active-text="前台展示" />
        </div>
        <div class="field-row">
          <el-form-item label="Email">
            <el-input v-model="settings.email" :disabled="!canWrite" />
          </el-form-item>
          <el-switch v-model="settings.show_email" :disabled="!canWrite" active-text="前台展示" />
        </div>
        <div class="field-row">
          <el-form-item label="联系说明">
            <el-input v-model="settings.contact_note" type="textarea" :rows="2" :disabled="!canWrite" />
          </el-form-item>
          <el-switch v-model="settings.show_contact_note" :disabled="!canWrite" active-text="前台展示" />
        </div>
        <div class="field-row">
          <el-form-item label="联系二维码">
            <div class="qr-box">
              <img v-if="settings.qr_image_url" :src="mediaUrl(settings.qr_image_url)" alt="二维码预览" class="qr-preview" />
              <el-upload
                v-if="canWrite"
                :show-file-list="false"
                accept="image/png,image/jpeg,image/webp,image/gif"
                :http-request="uploadQr"
              >
                <el-button>上传二维码</el-button>
              </el-upload>
            </div>
          </el-form-item>
          <el-switch v-model="settings.show_qr" :disabled="!canWrite" active-text="前台展示" />
        </div>
        <el-button v-if="canWrite" type="primary" :loading="saving" @click="saveSettings">保存合作信息</el-button>
      </el-form>
    </section>

    <section class="gq-panel">
      <div class="brand-head">
        <h2 class="block-title">品牌背书</h2>
        <el-button v-if="canWrite" type="success" @click="openCreate">+ 新增品牌</el-button>
      </div>
      <el-table :data="brands" empty-text="暂无品牌">
        <el-table-column label="排序" width="80" prop="sort_order" />
        <el-table-column label="Logo" width="88">
          <template #default="{ row }">
            <img v-if="row.logo_url" :src="mediaUrl(row.logo_url)" alt="" class="logo-thumb" />
            <span v-else class="gq-muted">无</span>
          </template>
        </el-table-column>
        <el-table-column label="品牌" min-width="140" prop="brand_name" />
        <el-table-column label="说明" min-width="180" prop="description" />
        <el-table-column label="链接" min-width="160" prop="link" />
        <el-table-column label="展示" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="canWrite" label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="edit(row)">编辑</el-button>
            <el-button link @click="move(row, -1)">上移</el-button>
            <el-button link @click="move(row, 1)">下移</el-button>
            <el-button link @click="toggle(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="dlg" :title="form.id ? '编辑品牌' : '新增品牌'" width="480px">
      <el-form label-position="top">
        <el-form-item label="品牌/机构名称">
          <el-input v-model="form.brand_name" />
        </el-form-item>
        <el-form-item label="Logo">
          <img v-if="form.logo_url" :src="mediaUrl(form.logo_url)" alt="" class="logo-thumb" />
          <el-upload :show-file-list="false" accept="image/png,image/jpeg,image/webp,image/gif" :http-request="uploadLogo">
            <el-button>上传 Logo</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="简短说明">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="链接（可选）">
          <el-input v-model="form.link" placeholder="https://" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :step="10" />
        </el-form-item>
        <el-form-item label="前台展示">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" @click="saveBrand">保存</el-button>
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
const saving = ref(false)
const brands = ref([])
const dlg = ref(false)
const settings = ref(emptySettings())
const form = ref(emptyBrand())

function emptySettings() {
  return {
    page_title: '合作中心',
    intro: '',
    contact_name: '',
    wechat: '',
    phone: '',
    email: '',
    contact_note: '',
    qr_image_url: '',
    show_contact_name: true,
    show_wechat: true,
    show_phone: true,
    show_email: true,
    show_contact_note: true,
    show_qr: true,
  }
}
function emptyBrand() {
  return { id: null, brand_name: '', logo_url: '', description: '', link: '', sort_order: 10, is_active: true }
}
function mediaUrl(u) {
  if (!u) return ''
  if (/^https?:\/\//i.test(u)) return u
  return `${api.apiBase === '(same-origin / vite proxy)' ? '' : api.apiBase}${u}`
}

async function load() {
  const [s, b] = await Promise.all([api.cooperationSettings(), api.cooperationBrands()])
  settings.value = { ...emptySettings(), ...s }
  brands.value = b.brands || []
}
async function saveSettings() {
  saving.value = true
  try {
    settings.value = { ...emptySettings(), ...(await api.patchCooperationSettings(settings.value)) }
    ElMessage.success('合作信息已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}
function openCreate() {
  form.value = emptyBrand()
  dlg.value = true
}
function edit(row) {
  form.value = { ...emptyBrand(), ...row }
  dlg.value = true
}
async function uploadQr({ file }) {
  try {
    const r = await api.uploadCooperationImage(file)
    settings.value.qr_image_url = r.url
    ElMessage.success('二维码已上传')
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  }
}
async function uploadLogo({ file }) {
  try {
    const r = await api.uploadCooperationImage(file)
    form.value.logo_url = r.url
    ElMessage.success('Logo 已上传')
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  }
}
async function saveBrand() {
  try {
    if (form.value.id) {
      await api.patchCooperationBrand(form.value.id, form.value)
    } else {
      await api.createCooperationBrand(form.value)
    }
    ElMessage.success('已保存')
    dlg.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}
async function toggle(row) {
  await api.patchCooperationBrand(row.id, { is_active: !row.is_active })
  await load()
}
async function remove(row) {
  await ElMessageBox.confirm(`删除品牌「${row.brand_name}」？`, '确认', { type: 'warning' })
  await api.deleteCooperationBrand(row.id)
  await load()
}
async function move(row, dir) {
  const list = [...brands.value]
  const idx = list.findIndex((x) => x.id === row.id)
  const next = idx + dir
  if (idx < 0 || next < 0 || next >= list.length) return
  const tmp = list[idx]
  list[idx] = list[next]
  list[next] = tmp
  await api.reorderCooperationBrands(list.map((x) => x.id))
  await load()
}

onMounted(async () => {
  try { await refresh() } catch { /* ignore */ }
  canWrite.value = can('cooperation.write')
  await load()
})
</script>

<style scoped>
.block-title { margin: 0 0 12px; font-size: 16px; }
.coop-form { max-width: 720px; }
.field-row { display: flex; align-items: flex-start; gap: 16px; }
.field-row .el-form-item { flex: 1; }
.brand-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.qr-box, .logo-thumb { display: flex; align-items: center; gap: 10px; }
.qr-preview { width: 96px; height: 96px; object-fit: contain; background: #fff; border: 1px solid #e2e8f0; }
.logo-thumb { width: 40px; height: 40px; object-fit: contain; background: #fff; border: 1px solid #e2e8f0; }
</style>
