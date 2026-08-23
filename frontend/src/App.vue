<template>
  <div :class="['app-shell', darkMode ? 'dark' : 'light']">
    <header class="hero">
      <div>
        <p class="eyebrow">Education Eligibility Intelligence</p>
        <h1>华侨生国际生资格智能判定系统</h1>
        <p class="subtitle">基于《中华人民共和国国籍法》条款、居住记录与高校招生要求，完成资格初判、依据解释与院校查询。</p>
      </div>
      <div class="hero-actions">
        <el-switch v-model="darkMode" active-text="深色" inactive-text="浅色" @change="persistTheme" />
        <el-button type="primary" plain @click="loadAll">刷新数据</el-button>
      </div>
    </header>

    <main class="container">
      <el-steps :active="step" finish-status="success" simple class="steps">
        <el-step title="填写信息" />
        <el-step title="系统判定" />
        <el-step title="查看结果" />
        <el-step title="查询大学" />
      </el-steps>

      <el-tabs v-model="activeTab" class="main-tabs" @tab-change="onTabChange">
        <el-tab-pane label="华侨生判定" name="huaqiao">
          <JudgeForm title="华侨生资格自动判定" type="huaqiao" :loading="loading" @submit="submitJudge" />
        </el-tab-pane>
        <el-tab-pane label="国际生判定" name="international">
          <JudgeForm title="国际生资格自动判定" type="international" :loading="loading" @submit="submitJudge" />
        </el-tab-pane>
        <el-tab-pane label="判定结果" name="result">
          <ResultPanel :result="result" @copy="copyResult" @print="printPage" />
        </el-tab-pane>
        <el-tab-pane label="国籍法条款" name="law">
          <section class="card">
            <div class="section-head">
              <div><h2>国籍法与教外函政策依据</h2><p>统一展示《中华人民共和国国籍法》与教外函〔2020〕12号，作为国际生/华侨生资格初判依据。</p></div>
              <el-input v-model="lawKeyword" placeholder="搜索条款关键词" clearable class="search" @input="loadLaws" />
            </div>
            <div class="law-grid">
              <article v-for="law in laws" :key="law.number" class="law-card">
                <strong>第{{ law.number }}条：{{ law.title }}</strong>
                <p v-html="highlight(law.text)"></p>
                <el-alert :title="law.explanation" type="info" :closable="false" />
              </article>
            </div><h3 class="policy-title">教外函〔2020〕12号政策依据</h3><div class="policy-list"><article v-for="doc in policies" :key="doc.id" class="law-card"><strong>{{ doc.title }}</strong><p class="muted">{{ doc.authority }} · {{ doc.code }}</p><p>{{ doc.summary }}</p><el-alert :title="doc.focus" type="warning" :closable="false" /><section v-for="section in doc.sections" :key="section.heading" class="policy-section"><b>{{ section.heading }}</b><p>{{ section.text }}</p></section></article></div>
          </section>
        </el-tab-pane>
        <el-tab-pane label="大学库" name="universities">
          <UniversityPanel :target="activeTarget" :universities="universities" @reload="loadUniversities" />
        </el-tab-pane>
        <el-tab-pane label="招生时间" name="schedule">
          <SchedulePanel :target="activeTarget" :schedules="schedules" @reload="loadSchedules" />
        </el-tab-pane>
        <el-tab-pane label="历史记录" name="history">
          <HistoryPanel :records="records" @reload="loadRecords" />
        </el-tab-pane>
      </el-tabs>
    </main>

    <footer class="privacy-footer">
      <p class="privacy-notice">
        <strong>隐私声明：</strong>本系统严格遵守《个人信息保护法》。您提交的护照信息、身份证件、居住记录等敏感数据均使用 Fernet 加密存储，日志中自动脱敏处理。
        管理员访问敏感数据将被审计记录。您有权要求删除全部个人数据（GDPR 删除权）。
        <a href="#" @click.prevent="showPrivacyDetail = !showPrivacyDetail">了解更多</a>
      </p>
      <div v-if="showPrivacyDetail" class="privacy-detail">
        <ul>
          <li>数据传输全程 HTTPS 加密</li>
          <li>敏感字段（护照号、身份证号）使用 Fernet 对称加密存储</li>
          <li>日志系统自动脱敏处理，不会记录明文敏感信息</li>
          <li>管理员访问敏感数据需通过 RBAC 权限控制，所有操作记录审计日志</li>
          <li>数据保留策略：活跃案件保留至结案后 3 年，支付记录保留 5 年</li>
          <li>您有权随时要求删除全部个人数据，请联系管理员处理</li>
        </ul>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElEmpty, ElForm, ElFormItem, ElInput, ElInputNumber, ElOption, ElSelect, ElSwitch, ElTable, ElTableColumn, ElMessage } from 'element-plus'
import { api } from './api'

const activeTab = ref('huaqiao')
/** 与当前华侨生/国际生流程一致：离开判定页签后仍能正确驱动大学库、招生时间筛选 */
const eligibilityContext = ref('huaqiao')
watch(activeTab, (name) => {
  if (name === 'huaqiao') eligibilityContext.value = 'huaqiao'
  else if (name === 'international') eligibilityContext.value = 'international'
})
const activeTarget = computed(() => {
  if (activeTab.value === 'international') return 'international'
  if (activeTab.value === 'huaqiao') return 'huaqiao'
  return eligibilityContext.value
})
const step = computed(() => activeTab.value === 'result' ? 2 : ['universities', 'schedule'].includes(activeTab.value) ? 3 : ['huaqiao', 'international'].includes(activeTab.value) ? 0 : 1)
const loading = ref(false)
const darkMode = ref(localStorage.getItem('theme') === 'dark')
const showPrivacyDetail = ref(false)
const result = ref(null)
const laws = ref([])
const policies = ref([])
const lawKeyword = ref('')
const universities = ref([])
const schedules = ref([])
const records = ref([])

function syncHtmlDark() {
  document.documentElement.classList.toggle('dark', darkMode.value)
}
function persistTheme() {
  localStorage.setItem('theme', darkMode.value ? 'dark' : 'light')
  syncHtmlDark()
}
function onTabChange() {
  if (activeTab.value === 'law') loadLaws()
  if (activeTab.value === 'universities') loadUniversities(activeTarget.value)
  if (activeTab.value === 'schedule') loadSchedules({ target: activeTarget.value })
  if (activeTab.value === 'history') loadRecords()
}
async function submitJudge(type, payload) {
  loading.value = true
  try {
    eligibilityContext.value = type
    result.value = type === 'huaqiao' ? await api.judgeHuaqiao(payload) : await api.judgeInternational(payload)
    activeTab.value = 'result'
    await loadRecords()
    ElMessage.success('判定完成，记录已保存')
  } catch (error) { ElMessage.error(error.message) } finally { loading.value = false }
}
async function loadLaws() { laws.value = await api.laws(lawKeyword.value); policies.value = await api.policies(lawKeyword.value) }
async function loadUniversities(target = '', keyword = '', filters = {}) { universities.value = await api.universities(target, keyword, filters) }
async function loadSchedules({ target = '', month = '', filters = {} } = {}) { schedules.value = await api.schedules(target, month, filters) }
async function loadRecords(kind = '') { records.value = await api.records(kind) }
async function loadAll() { await Promise.all([loadLaws(), loadUniversities(), loadSchedules(), loadRecords()]); ElMessage.success('数据已刷新') }
function highlight(text) {
  if (!lawKeyword.value) return text
  return text.replaceAll(lawKeyword.value, `<mark>${lawKeyword.value}</mark>`)
}
async function copyResult() {
  if (!result.value) return
  await navigator.clipboard.writeText(JSON.stringify(result.value, null, 2))
  ElMessage.success('结果已复制')
}
function printPage() { window.print() }
onMounted(() => {
  syncHtmlDark()
  loadAll()
})

const provinceOptions = ['', '北京', '上海', '天津', '重庆', '广东', '江苏', '浙江', '湖北', '湖南', '陕西', '四川', '山东', '福建', '辽宁', '吉林', '黑龙江', '安徽', '河南', '河北', '山西', '内蒙古', '江西', '广西', '海南', '贵州', '云南', '西藏', '甘肃', '青海', '宁夏', '新疆']
const tagOptions = ['', 'C9', '双一流', '985', '211']
const featureOptions = ['', '体育', '音乐', '艺术', '师范']
function formatTags(school) {
  const raw = `${school.tags || ''},${school.fields || ''},${school.university_type || ''}`
  return ['C9', '双一流', '985', '211', '体育', '音乐', '艺术', '师范']
    .filter(tag => tag === '211' ? raw.includes('211') || raw.includes('纯211') : tag === '艺术' ? ['艺术', '美术', '设计'].some(x => raw.includes(x)) : raw.includes(tag))
    .join(' / ')
}

function defaultJudgeForm(type) {
  if (type === 'huaqiao') {
    return {
      name: '',
      birth_date: '',
      current_nationality: '',
      has_chinese_nationality: true,
      has_foreign_nationality: false,
      foreign_nationality_acquired_date: '',
      settled_abroad: true,
      permanent_residence_country: '',
      overseas_residence_months_last_2y: 18,
      overseas_residence_months_last_4y: 0,
      annual_months_overseas: 0,
      has_mainland_household: false,
      parent_chinese_citizen: false,
      parent_settled_abroad_at_birth: false,
      born_abroad: false,
      passport_info: '',
      household_info: '',
      complex_situation: '',
      intended_field: '综合',
      score: null
    }
  }
  return {
    name: '',
    birth_date: '',
    current_nationality: '',
    has_chinese_nationality: false,
    has_foreign_nationality: true,
    foreign_nationality_acquired_date: '',
    settled_abroad: true,
    permanent_residence_country: '',
    overseas_residence_months_last_2y: 0,
    overseas_residence_months_last_4y: 24,
    annual_months_overseas: 9,
    has_mainland_household: false,
    parent_chinese_citizen: false,
    parent_settled_abroad_at_birth: false,
    born_abroad: false,
    passport_info: '',
    household_info: '',
    complex_situation: '',
    intended_field: '综合',
    score: null
  }
}

const JudgeForm = defineComponent({
  props: { title: String, type: String, loading: Boolean },
  emits: ['submit'],
  setup(props, { emit }) {
    const form = ref(defaultJudgeForm(props.type))
    const submit = () => emit('submit', props.type, form.value)
    const fieldOpts = ['综合', '理工', '文史', '医药', '体育', '音乐', '美术', '设计'].map(item => h(ElOption, { label: item, value: item }))
    return () => {
      const isHq = props.type === 'huaqiao'
      const head = h('div', { class: 'section-head' }, [h('div', [h('h2', props.title), h('p', isHq ? '与 SaaS Pro 一致：华侨生表单独立、字段更简单，重点核验中国国籍、海外定居、近两年海外居住与内地户籍状态。' : '国际生模块独立判定外国国籍、中国国籍状态与居住连续性。')])])
      if (isHq) {
        return h('section', { class: 'card' }, [
          head,
          h(ElForm, { model: form.value, labelPosition: 'top' }, () => [
            h(ElAlert, { type: 'success', closable: false, title: '华侨生表格：比国际生更简单，重点核验中国国籍、海外定居、近两年居住和户籍状态。' }),
            h('div', { class: 'form-grid' }, [
              h(ElFormItem, { label: '姓名' }, () => h(ElInput, { modelValue: form.value.name, 'onUpdate:modelValue': v => form.value.name = v, placeholder: '请输入姓名' })),
              h(ElFormItem, { label: '出生日期' }, () => h(ElInput, { modelValue: form.value.birth_date, 'onUpdate:modelValue': v => form.value.birth_date = v, placeholder: 'YYYY-MM-DD' })),
              h(ElFormItem, { label: '当前国籍' }, () => h(ElInput, { modelValue: form.value.current_nationality, 'onUpdate:modelValue': v => form.value.current_nationality = v, placeholder: '如：中国' })),
              h(ElFormItem, { label: '永久/长期居留地' }, () => h(ElInput, { modelValue: form.value.permanent_residence_country, 'onUpdate:modelValue': v => form.value.permanent_residence_country = v, placeholder: '国家或地区' })),
              h(ElFormItem, { label: '近2年海外居住月份' }, () => h(ElInputNumber, { modelValue: form.value.overseas_residence_months_last_2y, 'onUpdate:modelValue': v => form.value.overseas_residence_months_last_2y = v || 0, min: 0, max: 24 })),
              h(ElFormItem, { label: '意向专业领域' }, () => h(ElSelect, { modelValue: form.value.intended_field, 'onUpdate:modelValue': v => form.value.intended_field = v, placeholder: '选择推荐方向' }, () => fieldOpts)),
              h(ElFormItem, { label: '分数/成绩（可选）' }, () => h(ElInputNumber, { modelValue: form.value.score, 'onUpdate:modelValue': v => form.value.score = v, min: 0, max: 750, placeholder: '可选' }))
            ]),
            h('div', { class: 'switch-grid' }, [
              ['has_chinese_nationality', '具有中国国籍'],
              ['has_foreign_nationality', '具有外国国籍'],
              ['settled_abroad', '已定居国外'],
              ['has_mainland_household', '仍有内地户籍']
            ].map(([key, label]) => h(ElSwitch, { modelValue: form.value[key], 'onUpdate:modelValue': v => form.value[key] = v, activeText: label }))),
            h(ElFormItem, { label: '复杂情况说明' }, () => h(ElInput, { type: 'textarea', rows: 4, modelValue: form.value.complex_situation, 'onUpdate:modelValue': v => form.value.complex_situation = v, placeholder: '出入境记录、定居证明、户籍状态等补充说明' })),
            h(ElButton, { type: 'primary', size: 'large', loading: props.loading, onClick: submit }, () => '开始判定')
          ])
        ])
      }
      return h('section', { class: 'card' }, [
        head,
        h(ElForm, { model: form.value, labelPosition: 'top' }, () => [
          h('div', { class: 'form-grid' }, [
            h(ElFormItem, { label: '姓名' }, () => h(ElInput, { modelValue: form.value.name, 'onUpdate:modelValue': v => form.value.name = v, placeholder: '请输入姓名' })),
            h(ElFormItem, { label: '出生日期' }, () => h(ElInput, { modelValue: form.value.birth_date, 'onUpdate:modelValue': v => form.value.birth_date = v, placeholder: 'YYYY-MM-DD' })),
            h(ElFormItem, { label: '当前国籍' }, () => h(ElInput, { modelValue: form.value.current_nationality, 'onUpdate:modelValue': v => form.value.current_nationality = v })),
            h(ElFormItem, { label: '永久/长期居留国家或地区' }, () => h(ElInput, { modelValue: form.value.permanent_residence_country, 'onUpdate:modelValue': v => form.value.permanent_residence_country = v })),
            h(ElFormItem, { label: '近两年海外居住月份' }, () => h(ElInputNumber, { modelValue: form.value.overseas_residence_months_last_2y, 'onUpdate:modelValue': v => form.value.overseas_residence_months_last_2y = v || 0, min: 0, max: 24 })),
            h(ElFormItem, { label: '近四年海外居住月份' }, () => h(ElInputNumber, { modelValue: form.value.overseas_residence_months_last_4y, 'onUpdate:modelValue': v => form.value.overseas_residence_months_last_4y = v || 0, min: 0, max: 48 })),
            h(ElFormItem, { label: '单年最高海外居住月份' }, () => h(ElInputNumber, { modelValue: form.value.annual_months_overseas, 'onUpdate:modelValue': v => form.value.annual_months_overseas = v || 0, min: 0, max: 12 })),
            h(ElFormItem, { label: '取得外国国籍日期' }, () => h(ElInput, { modelValue: form.value.foreign_nationality_acquired_date, 'onUpdate:modelValue': v => form.value.foreign_nationality_acquired_date = v, placeholder: '如适用' })),
            h(ElFormItem, { label: '意向专业领域' }, () => h(ElSelect, { modelValue: form.value.intended_field, 'onUpdate:modelValue': v => form.value.intended_field = v, placeholder: '选择推荐方向' }, () => fieldOpts)),
            h(ElFormItem, { label: '分数/成绩（可选）' }, () => h(ElInputNumber, { modelValue: form.value.score, 'onUpdate:modelValue': v => form.value.score = v, min: 0, max: 750, placeholder: '可选' }))
          ]),
          h('div', { class: 'switch-grid' }, [
            ['has_chinese_nationality', '具有中国国籍'],
            ['has_foreign_nationality', '具有外国国籍'],
            ['settled_abroad', '已定居国外'],
            ['has_mainland_household', '仍有内地户籍'],
            ['born_abroad', '出生在外国'],
            ['parent_chinese_citizen', '父母一方为中国公民'],
            ['parent_settled_abroad_at_birth', '出生时父母一方已定居外国']
          ].map(([key, label]) => h(ElSwitch, { modelValue: form.value[key], 'onUpdate:modelValue': v => form.value[key] = v, activeText: label }))),
          h(ElFormItem, { label: '护照/户籍/复杂情况说明' }, () => h(ElInput, { type: 'textarea', rows: 4, modelValue: form.value.complex_situation, 'onUpdate:modelValue': v => form.value.complex_situation = v, placeholder: '可填写护照、户籍、父母国籍、出入境记录等复杂情况' })),
          h(ElButton, { type: 'primary', size: 'large', loading: props.loading, onClick: submit }, () => '开始判定')
        ])
      ])
    }
  }
})

const ResultPanel = defineComponent({
  props: { result: Object }, emits: ['copy', 'print'],
  setup(props, { emit }) { return () => h('section', { class: 'card result-card' }, props.result ? [
    h('div', { class: ['result-banner', (props.result.result === 'PRELIMINARY_ELIGIBLE' || props.result.qualified) ? 'pass' : (props.result.result === 'MANUAL_REVIEW_REQUIRED' ? 'review' : 'fail')] }, [h('span', props.result.result === 'PRELIMINARY_ELIGIBLE' ? '初步符合条件' : (props.result.result === 'MANUAL_REVIEW_REQUIRED' ? '需人工复核' : (props.result.qualified ? '合格' : '不合格'))), h('strong', props.result.conclusion)]),
    h('h3', '详细判定理由'), h('ul', props.result.reasons.map(r => h('li', r))),
    h('h3', '对应国籍法条款原文'), props.result.basis_articles.map(a => h('article', { class: 'law-card' }, [h('strong', `依据《中华人民共和国国籍法》第${a.number}条：${a.title}`), h('p', a.text), h('small', `解释：${a.explanation}`)])),
    props.result.suggestions.length ? h(ElAlert, { title: props.result.suggestions.join('；'), type: 'warning', closable: false }) : null,
    props.result.result === 'MANUAL_REVIEW_REQUIRED' ? h(ElAlert, { title: '本结果需要人工复核。部分条件无法仅凭当前信息做出确定性判断，建议联系联招办或目标高校招生办确认。', type: 'info', closable: false, style: 'margin-top:12px' }) : null,
    h(ElAlert, { title: '本结果为基于当前政策与用户提供信息生成的初步资格评估，不替代教育主管部门、联招办或高校的最终资格审核。', type: 'info', closable: false, style: 'margin-top:12px' }),
    h('h3', '匹配大学推荐'),
    props.result.recommendations?.length ? h('div', { class: 'recommend-grid' }, props.result.recommendations.map(u => h('article', { class: 'recommend-card' }, [
      h('div', { class: 'recommend-title' }, [h('strong', `#${u.ranking} ${u.name}`), h('span', u.province)]),
      h('p', [h('b', '标签：'), formatTags(u)]),
      h('p', [h('b', '领域：'), u.fields]),
      h('p', [h('b', '优势专业：'), u.advantage_majors]),
      h('p', [h('b', '招生时间：'), u.admission_timeline]),
      h('p', [h('b', '招生办公室：'), u.admissions_office || '以学校官方发布为准']),
      h('p', [h('b', '招生邮箱：'), u.admission_email || '以学校官方发布为准']),
      h(ElAlert, { title: u.match_reason, type: 'success', closable: false }),
      h('a', { href: u.admission_url || u.official_url, target: '_blank' }, '查看官方报考链接')
    ]))) : h(ElEmpty, { description: '暂无匹配推荐，请补充意向专业领域或成绩后重新判定' }),
    h('div', { class: 'actions' }, [h(ElButton, { onClick: () => emit('copy') }, () => '复制结果'), h(ElButton, { type: 'primary', onClick: () => emit('print') }, () => '打印结果')])
  ] : [h(ElEmpty, { description: '请先完成一次资格判定' })]) }
})

const UniversityPanel = defineComponent({
  props: { target: String, universities: Array }, emits: ['reload'],
  setup(props, { emit }) {
    const target = ref(props.target), keyword = ref(''), province = ref(''), tag = ref(''), feature = ref('')
    watch(() => props.target, (v) => { if (v) target.value = v })
    const reload = () => emit('reload', target.value, keyword.value, { province: province.value, tag: tag.value, feature: feature.value })
    return () => h('section', { class: 'card' }, [
      h('div', { class: 'section-head' }, [h('div', [h('h2', '国内高校信息库'), h('p', '完整覆盖 39 所 985、115 所 211，可按地区、C9/双一流/985/211、体育/音乐/艺术/师范筛选。')])]),
      h('div', { class: 'filter-panel' }, [
        h(ElInput, { modelValue: keyword.value, 'onUpdate:modelValue': v => keyword.value = v, placeholder: '搜索学校名称', clearable: true }),
        h(ElSelect, { modelValue: target.value, 'onUpdate:modelValue': v => target.value = v, placeholder: '招生对象' }, () => [h(ElOption, { label: '华侨生', value: 'huaqiao' }), h(ElOption, { label: '国际生', value: 'international' })]),
        h(ElSelect, { modelValue: province.value, 'onUpdate:modelValue': v => province.value = v, placeholder: '地区', clearable: true }, () => provinceOptions.map(x => h(ElOption, { label: x || '全部地区', value: x }))),
        h(ElSelect, { modelValue: tag.value, 'onUpdate:modelValue': v => tag.value = v, placeholder: '院校层级', clearable: true }, () => tagOptions.map(x => h(ElOption, { label: x || '全部层级', value: x }))),
        h(ElSelect, { modelValue: feature.value, 'onUpdate:modelValue': v => feature.value = v, placeholder: '特色类型', clearable: true }, () => featureOptions.map(x => h(ElOption, { label: x || '全部特色', value: x }))),
        h(ElButton, { type: 'primary', onClick: reload }, () => '筛选')
      ]),
      h('p', { class: 'muted' }, `当前共 ${props.universities.length} 所学校`),
      h('div', { class: 'uni-grid' }, props.universities.map(u => h('article', { class: 'uni-card' }, [h('h3', `#${u.ranking} ${u.name}`), h('p', `${u.province} · ${u.university_type}`), h('p', `标签：${formatTags(u)}`), h('p', `领域：${u.fields}`), h('p', `优势专业：${u.advantage_majors}`), h('p', u.description), h('p', `招生办公室：${u.admissions_office || '以学校官方发布为准'}`), h('p', `招生邮箱：${u.admission_email || '以学校官方发布为准'}`), h('p', `招生电话：${u.admission_phone || '以学校官方发布为准'}`), h(ElAlert, { title: u.requirements, type: 'success', closable: false }), h('a', { href: u.admission_url || u.official_url, target: '_blank' }, '访问官方报考链接')])) )
    ])
  }
})

const SchedulePanel = defineComponent({
  props: { target: String, schedules: Array }, emits: ['reload'],
  setup(props, { emit }) {
    const month = ref(''), target = ref(props.target), province = ref(''), tag = ref(''), feature = ref('')
    watch(() => props.target, (v) => { if (v) target.value = v })
    const reload = () => emit('reload', { target: target.value, month: month.value, filters: { province: province.value, tag: tag.value, feature: feature.value } })
    return () => h('section', { class: 'card' }, [
      h('div', { class: 'section-head' }, [h('div', [h('h2', '招生时间管理'), h('p', '按大学库标准筛选招生时间：地区、C9/双一流/985/211、体育/音乐/艺术/师范。')])]),
      h('div', { class: 'filter-panel' }, [
        h(ElSelect, { modelValue: target.value, 'onUpdate:modelValue': v => target.value = v, placeholder: '招生对象' }, () => [h(ElOption, { label: '华侨生', value: 'huaqiao' }), h(ElOption, { label: '国际生', value: 'international' })]),
        h(ElInputNumber, { modelValue: month.value, 'onUpdate:modelValue': v => month.value = v || '', min: 1, max: 12, placeholder: '月份' }),
        h(ElSelect, { modelValue: province.value, 'onUpdate:modelValue': v => province.value = v, placeholder: '地区', clearable: true }, () => provinceOptions.map(x => h(ElOption, { label: x || '全部地区', value: x }))),
        h(ElSelect, { modelValue: tag.value, 'onUpdate:modelValue': v => tag.value = v, placeholder: '院校层级', clearable: true }, () => tagOptions.map(x => h(ElOption, { label: x || '全部层级', value: x }))),
        h(ElSelect, { modelValue: feature.value, 'onUpdate:modelValue': v => feature.value = v, placeholder: '特色类型', clearable: true }, () => featureOptions.map(x => h(ElOption, { label: x || '全部特色', value: x }))),
        h(ElButton, { type: 'primary', onClick: reload }, () => '筛选')
      ]),
      h('p', { class: 'muted' }, `当前共 ${props.schedules.length} 条招生节点`),
      h(ElTable, { data: props.schedules, stripe: true }, () => [h(ElTableColumn, { prop: 'university_name', label: '学校' }), h(ElTableColumn, { prop: 'province', label: '地区', width: 90 }), h(ElTableColumn, { label: '标签', formatter: row => formatTags(row) }), h(ElTableColumn, { prop: 'month', label: '月份', width: 80 }), h(ElTableColumn, { prop: 'registration_time', label: '报名时间' }), h(ElTableColumn, { prop: 'material_deadline', label: '材料截止' }), h(ElTableColumn, { prop: 'exam_time', label: '考试/审核' }), h(ElTableColumn, { prop: 'reminder', label: '提醒' })])
    ])
  }
})

const HistoryPanel = defineComponent({
  props: { records: Array }, emits: ['reload'],
  setup(props, { emit }) { return () => h('section', { class: 'card' }, [h('div', { class: 'section-head' }, [h('div', [h('h2', '永久保存的历史记录'), h('p', '后端 SQLite 保存全部判定历史。')]), h(ElButton, { onClick: () => emit('reload') }, () => '刷新')]), h(ElTable, { data: props.records, stripe: true }, () => [h(ElTableColumn, { prop: 'record_id', label: 'ID', width: 80 }), h(ElTableColumn, { prop: 'eligibility_type', label: '类型', width: 120 }), h(ElTableColumn, { prop: 'conclusion', label: '结论' }), h(ElTableColumn, { label: '结果', width: 100, formatter: row => row.result === 'MANUAL_REVIEW_REQUIRED' ? '需复核' : (row.qualified ? '合格' : '不合格') }), h(ElTableColumn, { prop: 'created_at', label: '时间' })])]) }
})
</script>

