<template>
  <div class="smp-mobile">
    <van-cell-group inset>
      <van-cell title="当前学生" :value="currentLabel" />
      <van-field
        v-if="students.length > 1"
        label="切换学生"
        is-link
        readonly
        :model-value="currentLabel"
        placeholder="选择学生"
        @click="openStudentPicker"
      />
      <van-cell title="学生档案席位" :value="`${slots.student_profile_used || 0} / ${slots.student_profile_limit || 0}`" />
      <van-cell v-if="canCreate" title="剩余名额" :value="`${slots.student_profile_remaining || 0}`" />
      <div class="consult-actions" style="padding:12px;">
        <van-button block round type="primary" :disabled="!canCreate" @click="createStudent">创建学生</van-button>
        <p v-if="!canCreate" class="confirm-hint" style="margin-top:10px;">{{ limitHint }}</p>
        <van-button v-if="!canCreate" block round plain type="primary" style="margin-top:8px;" @click="emit('goto-member')">升级套餐</van-button>
      </div>
    </van-cell-group>
    <van-popup v-model:show="showPicker" position="bottom" round>
      <van-picker
        v-if="showPicker"
        :key="`profile-picker-${normalizeStudentId(activeStudentId) || 'none'}-${pickerEpoch}`"
        :columns="studentColumns"
        :model-value="profilePickerSelectedValues"
        @confirm="onPickStudent"
        @cancel="showPicker=false"
      />
    </van-popup>

    <template v-if="profile">
      <van-tabs v-model:active="section" shrink sticky>
        <van-tab v-for="sec in sections" :key="sec.key" :title="sec.label" :name="sec.key" />
      </van-tabs>

      <div v-show="section==='basic_info'" class="form-card">
        <van-field v-model="profile.basic_info.chinese_name" label="中文名" />
        <van-field v-model="profile.basic_info.english_name" label="英文名" />
        <van-field v-model="profile.basic_info.birth_date" label="出生日期" placeholder="YYYY-MM-DD" />
        <van-field v-model="profile.basic_info.gender" label="性别" />
        <van-field v-model="profile.basic_info.current_country" label="居住国家" />
        <van-field v-model="profile.basic_info.current_city" label="城市" />
        <van-field v-model="profile.basic_info.contact" label="联系方式" />
        <van-field v-model="profile.basic_info.intended_entry_year" label="入学年份" />
        <van-field v-model="profile.basic_info.basic_info_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('basic_info')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='education'" class="form-card">
        <van-cell title="当前在读学校" :label="currentSchool?.school_name || '未填写'" />
        <van-field v-if="currentSchool" v-model="currentSchool.school_name" label="学校名称" />
        <van-field v-if="currentSchool" v-model="currentSchool.country" label="国家/地区" />
        <van-field v-if="currentSchool" v-model="currentSchool.city" label="城市" />
        <van-field v-if="currentSchool" v-model="currentSchool.school_type" label="学校类型" placeholder="Public / Grammar / International..." />
        <van-field v-if="currentSchool" v-model="currentSchool.start_date" label="开始年月" />
        <van-field v-if="currentSchool" v-model="currentSchool.current_grade" label="当前年级" />
        <van-button block @click="profile.education.history.push(emptySchool())">+ 添加教育经历</van-button>
        <div v-for="(row, idx) in profile.education.history" :key="row.id" class="summary-card">
          <van-field v-model="row.school_name" label="学校" />
          <van-field v-model="row.country" label="国家" />
          <van-field v-model="row.city" label="城市" />
          <van-field v-model="row.school_type" label="类型" />
          <van-field v-model="row.start_date" label="开始" />
          <van-field v-model="row.end_date" label="结束" />
          <van-cell title="当前在读"><template #right-icon><van-switch v-model="row.is_current" size="22" @change="onlyCurrent(idx)" /></template></van-cell>
          <van-button size="small" type="danger" @click="profile.education.history.splice(idx,1)">删除</van-button>
        </div>
        <van-field v-model="profile.education.education_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('education')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='courses'" class="form-card">
        <van-field v-model="curriculaText" label="课程体系" placeholder="A-Level,Custom" @blur="syncCurricula" />
        <van-field v-model="profile.courses.custom_curriculum" label="自定义体系" />
        <van-button block @click="addMathBundle">+ 添加 Mathematics / FM / Physics 示例</van-button>
        <van-button block @click="profile.courses.items.push(emptyCourse())">+ 添加课程</van-button>
        <div v-for="c in profile.courses.items" :key="c.id" class="summary-card">
          <van-field v-model="c.subject" label="科目" />
          <van-field v-model="c.qualification" label="资格" placeholder="A-Level" />
          <van-field v-model="c.level" label="Level" placeholder="AS / A2" />
          <van-field v-model="c.exam_board" label="Exam board" />
          <van-field v-model="c.start_year" label="开始年" />
          <van-field v-model="c.end_year" label="结束年" />
          <van-button size="small" @click="addGrade(c)">+ 添加成绩</van-button>
          <div v-for="g in gradesFor(c.id)" :key="g.id">
            <van-field v-model="g.exam_session" label="场次" placeholder="AS / A2 / GCSE" />
            <van-field v-model="g.grade_type" label="类型" placeholder="Actual / Predicted" />
            <van-field v-model="g.grade" label="成绩" />
          </div>
        </div>
        <van-button block @click="profile.courses.language_exams.push(emptyLang({ exam_type: 'HSK', overall_score: '6' }))">+ 添加 HSK / 语言成绩</van-button>
        <div v-for="(ex, idx) in profile.courses.language_exams" :key="ex.id" class="summary-card">
          <van-field v-model="ex.exam_type" label="考试" />
          <van-field v-model="ex.overall_score" label="成绩" />
          <van-field v-model="ex.exam_date" label="日期" />
          <van-button size="small" type="danger" @click="profile.courses.language_exams.splice(idx,1)">删除</van-button>
        </div>
        <van-button block @click="profile.courses.other_exams.push(emptyOther())">+ 其他考试/资格</van-button>
        <div v-for="(ex, idx) in profile.courses.other_exams" :key="ex.id" class="summary-card">
          <van-field v-model="ex.exam_type" label="类型" placeholder="CSCA / SAT / 竞赛" />
          <van-field v-model="ex.score" label="成绩" />
          <van-button size="small" type="danger" @click="profile.courses.other_exams.splice(idx,1)">删除</van-button>
        </div>
        <van-field v-model="profile.courses.courses_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('courses')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='goals'" class="form-card">
        <van-button block type="primary" @click="profile.goals.targets.push(emptyTarget())">+ 添加目标大学</van-button>
        <div v-for="level in priorityLevels" :key="level.value">
          <h3 style="padding:12px 16px 0;color:#123c69;">{{ level.label }}</h3>
          <div v-for="t in targetsBy(level.value)" :key="t.id" class="summary-card">
            <van-field v-model="t.university_name" label="大学" />
            <van-field v-model="t.major" label="专业" />
            <van-field v-model="t.entry_year" label="入学年" />
            <van-field v-model="t.priority_level" label="分类" placeholder="reach/target/match/safety" />
            <van-button size="small" type="danger" @click="profile.goals.targets = profile.goals.targets.filter(x=>x.id!==t.id)">删除</van-button>
          </div>
        </div>
        <van-field v-model="profile.goals.goals_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('goals')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='identity'" class="form-card">
        <p class="confirm-hint">外国国籍 / 中国国籍仅为事实字段，不能自行设定“我是国际生/华侨生”。</p>
        <van-field v-model="profile.identity.birth_country" label="出生国家" />
        <van-field v-model="profile.identity.current_nationality" label="当前国籍" />
        <van-field v-model="profile.identity.former_nationalities" label="曾经国籍" />
        <van-cell title="持有外国国籍（事实）"><template #right-icon><van-switch v-model="profile.identity.has_foreign_nationality" size="22" /></template></van-cell>
        <van-cell title="持有中国国籍（事实）"><template #right-icon><van-switch v-model="profile.identity.has_chinese_nationality" size="22" /></template></van-cell>
        <van-cell title="曾拥有中国国籍"><template #right-icon><van-switch v-model="profile.identity.had_chinese_nationality" size="22" /></template></van-cell>
        <van-cell title="有中国户籍"><template #right-icon><van-switch v-model="profile.identity.has_chinese_hukou" size="22" /></template></van-cell>
        <van-cell title="已注销中国户籍"><template #right-icon><van-switch v-model="profile.identity.hukou_cancelled" size="22" /></template></van-cell>
        <van-field v-model="profile.identity.foreign_nationality_acquired_date" label="取得外国国籍日" />
        <van-field v-model="profile.identity.passport_info" label="护照信息" />
        <van-field v-model="profile.identity.father_nationality" label="父亲国籍" />
        <van-field v-model="profile.identity.mother_nationality" label="母亲国籍" />
        <van-field v-model="profile.identity.parents_overseas_settlement" label="父母海外定居" type="textarea" rows="2" />
        <van-field v-model="profile.identity.overseas_residence_info" label="海外居住信息" type="textarea" rows="2" />
        <div class="summary-card">
          <h3>国际生资格</h3>
          <p>{{ profile.identity.international.status === 'NOT_ASSESSED' ? '国际生资格尚未判定' : statusLabel[profile.identity.international.status] }}</p>
          <p class="muted" v-if="profile.identity.international.assessed_at">{{ profile.identity.international.assessed_at }} · {{ profile.identity.international.policy_version }} · {{ profile.identity.international.confirmed ? '已确认写入' : '未确认写入' }}</p>
          <van-button block type="primary" @click="goJudge('international')">前往国际生判定</van-button>
          <van-button v-if="profile.identity.international.engine_result && !profile.identity.international.confirmed" block @click="confirmWB('international')">确认写入学生档案</van-button>
        </div>
        <div class="summary-card">
          <h3>华侨生资格</h3>
          <p>{{ profile.identity.huaqiao.status === 'NOT_ASSESSED' ? '华侨生资格尚未判定' : statusLabel[profile.identity.huaqiao.status] }}</p>
          <van-button block type="primary" @click="goJudge('huaqiao')">前往华侨生判定</van-button>
          <van-button v-if="profile.identity.huaqiao.engine_result && !profile.identity.huaqiao.confirmed" block @click="confirmWB('huaqiao')">确认写入学生档案</van-button>
        </div>
        <van-field v-model="profile.identity.identity_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('identity')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='planning'" class="form-card">
        <van-cell title="入学年份" :value="profile.basic_info.intended_entry_year || '—'" />
        <van-field v-model="profile.planning.current_education_stage" label="教育阶段" />
        <van-cell title="国际生状态" :value="statusLabel[profile.identity.international.status]" />
        <van-cell title="华侨生状态" :value="statusLabel[profile.identity.huaqiao.status]" />
        <van-cell title="目标大学" :label="profile.goals.targets.map(t=>t.university_name).filter(Boolean).join('、') || '—'" />
        <van-cell title="冲刺/主申/稳妥/保底" :value="`${countPri('reach')}/${countPri('target')}/${countPri('match')}/${countPri('safety')}`" />
        <van-button block @click="loadTimeline">读取匹配招生时间线</van-button>
        <div v-for="(s,i) in timeline" :key="i" class="summary-card">
          <b>{{ s.university_name }} {{ s.year }}-{{ s.month }}</b>
          <p>报名 {{ s.registration_time }}</p>
        </div>
        <van-field v-model="profile.planning.planning_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('planning')">{{ saveLabel }}</van-button></div>
      </div>

      <div v-show="section==='summary'" class="form-card">
        <div class="hero-card">
          <h1>申请准备度 {{ readinessScore }}%</h1>
          <p class="hero-lead">档案完整度 {{ completeness.percent || 0 }}% · 非录取概率</p>
        </div>
        <van-cell title="姓名" :value="(portrait?.basic?.chinese_name || profile.basic_info.chinese_name || '') + ' ' + (portrait?.basic?.english_name || '')" is-link @click="section='portrait'" />
        <van-cell title="学校/年级" :label="(portrait?.basic?.current_school || currentSchool?.school_name || '—') + ' · ' + (portrait?.basic?.current_grade || '—')" />
        <van-cell title="国际生" :value="statusLabel[portrait?.identity?.international?.status || profile.identity.international.status]" />
        <van-cell title="华侨生" :value="statusLabel[portrait?.identity?.huaqiao?.status || profile.identity.huaqiao.status]" />
        <van-cell title="语言" :value="portrait?.language?.summary || '语言成绩缺失'" />
        <van-cell title="目标结构" :value="`冲${targetCounts.reach||0}/主${targetCounts.target||0}/稳${targetCounts.match||0}/保${targetCounts.safety||0}`" />
        <van-cell title="未来30天" :value="`${timelineSummary.next_30_count||0} 项`" is-link @click="goSection('my_timeline')" />
        <van-cell title="未来90天" :value="`${timelineSummary.next_90_count||0} 项`" is-link @click="goSection('my_timeline')" />
        <van-cell title="逾期" :value="`${timelineSummary.overdue_count||0} 项`" is-link @click="goSection('my_timeline')" />
        <van-cell v-for="r in (portrait?.risk_flags||[]).slice(0,4)" :key="r" :title="r" />
        <van-cell v-for="a in (portrait?.next_actions||[]).slice(0,5)" :key="a.code" :title="a.label" is-link @click="runAction(a)" />
        <van-field v-model="profile.summary.summary_notes" label="备注" type="textarea" rows="2" autosize />
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('summary')">{{ saveLabel }}</van-button></div>
      </div>


      <div v-show="section==='csca'" class="form-card">
        <h3 class="block-title">CSCA 考试</h3>
        <van-field label="状态" is-link readonly :model-value="cscaStatusLabel" placeholder="选择状态" @click="showCscaStatus = true" />
        <van-field v-model="profile.csca.csca_registration_deadline" label="报名截止" placeholder="YYYY-MM-DD，无则留空" />
        <van-field v-model="profile.csca.csca_exam_date" label="考试日期" placeholder="YYYY-MM-DD，无则留空" />
        <van-field v-model="profile.csca.csca_result_date" label="成绩发布" placeholder="YYYY-MM-DD，无则留空" />
        <van-field v-model="profile.csca.csca_score" label="成绩" placeholder="可选" />
        <van-field v-model="profile.csca.csca_level" label="等级" placeholder="可选" />
        <van-field v-model="profile.csca.csca_notes" label="备注" type="textarea" rows="2" autosize />
        <p class="confirm-hint">日期须真实录入；留空则显示「待官方公布」，系统不会编造日期。</p>
        <div class="quick-actions">
          <van-button size="small" round @click="setCscaStatus('PLANNED')">计划参加</van-button>
          <van-button size="small" round @click="setCscaStatus('REGISTERED')">已报名</van-button>
          <van-button size="small" round @click="setCscaStatus('TAKEN')">已考试</van-button>
          <van-button size="small" round type="primary" @click="focusCscaScore">录入成绩</van-button>
        </div>
        <div class="flow-actions"><van-button type="primary" block round :loading="saving" @click="save('csca')">{{ saveLabel }}</van-button></div>
        <van-popup v-model:show="showCscaStatus" position="bottom" round>
          <van-picker :columns="cscaStatusColumns" @confirm="onPickCscaStatus" @cancel="showCscaStatus=false" />
        </van-popup>
      </div>

      <div v-show="section==='portrait'" class="form-card">
        <div class="consult-actions" style="padding:8px 12px;"><van-button block round @click="refreshPortrait">刷新画像</van-button></div>
        <p class="confirm-hint">自动从档案生成 · v{{ portrait?.portrait_version || '—' }}</p>
        <van-cell title="年龄" :value="portrait?.basic?.age ?? '—'" />
        <van-cell title="国家" :value="portrait?.basic?.current_country || '—'" />
        <van-cell title="课程体系" :value="(portrait?.basic?.curricula||[]).join('/') || '—'" />
        <van-cell title="学术优势" :label="(portrait?.academic?.academic_strengths||[]).join('；') || '暂无'" />
        <van-cell title="需关注" :label="(portrait?.academic?.academic_weaknesses||[]).join('；') || '暂无'" />
        <van-cell v-for="ex in (portrait?.language?.exams||[])" :key="ex.exam_type+ex.exam_date" :title="ex.exam_type" :value="`${ex.overall_score||'—'} · ${ex.status}`" />
        <div class="summary-card">
          <h3>国际生资格</h3>
          <p>{{ statusLabel[portrait?.identity?.international?.status] || '尚未判定' }}</p>
          <p class="muted" v-if="portrait?.identity?.international?.prompt">{{ portrait.identity.international.prompt }}</p>
          <van-button block type="primary" @click="goJudge('international')">前往国际生判定</van-button>
        </div>
        <div class="summary-card">
          <h3>华侨生资格</h3>
          <p>{{ statusLabel[portrait?.identity?.huaqiao?.status] || '尚未判定' }}</p>
          <p class="muted" v-if="portrait?.identity?.huaqiao?.prompt">{{ portrait.identity.huaqiao.prompt }}</p>
          <van-button block type="primary" @click="goJudge('huaqiao')">前往华侨生判定</van-button>
        </div>
        <van-cell title="申请准备度" :value="`${readinessScore}%`" />
        <van-cell v-for="(v,k) in (portrait?.application_readiness?.components||{})" :key="k" :title="k" :value="`${v}%`" />
        <van-cell title="时间轴" :value="`30天${timelineSummary.next_30_count||0} / 90天${timelineSummary.next_90_count||0} / 逾期${timelineSummary.overdue_count||0}`" is-link @click="goSection('my_timeline')" />
      </div>

      <div v-show="section==='my_timeline'" class="form-card">
        <div class="consult-actions" style="padding:8px 12px;display:flex;flex-direction:column;gap:8px;">
          <van-button block round type="primary" :loading="timelineBusy" @click="regenerateTimeline">重新生成个人时间轴</van-button>
          <van-button block round @click="showManual=true">+ 自定义事项</van-button>
        </div>
        <div v-for="group in timelineGroupsUI" :key="group.key">
          <h3 style="padding:12px 16px 0;color:#123c69;">{{ group.label }}（{{ (timelineGroups[group.key]||[]).length }}）</h3>
          <div v-for="it in (timelineGroups[group.key]||[])" :key="it.id" class="summary-card">
            <b>{{ it.title }}</b>
            <p>{{ it.deadline || it.start_date || '日期待确认' }} · {{ timelineStatusLabel[it.status] || it.status }}</p>
            <p class="muted">{{ it.university_name || '—' }} · {{ it.application_route || '路线待确认' }}</p>
            <p v-if="it.has_precise_deadline && it.days_until_deadline!=null" class="muted">距离 Deadline {{ it.days_until_deadline }} 天</p>
            <p v-else class="muted">无精确截止日期</p>
            <p v-if="it.student_note">备注：{{ it.student_note }}</p>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">
              <van-button size="small" @click="patchItem(it,'IN_PROGRESS')">开始</van-button>
              <van-button size="small" type="primary" @click="patchItem(it,'COMPLETED')">完成</van-button>
              <van-button size="small" @click="patchItem(it,'NOT_STARTED')">恢复</van-button>
              <van-button size="small" @click="patchItem(it,'NOT_APPLICABLE')">不适用</van-button>
              <van-button size="small" @click="editNote(it)">备注</van-button>
            </div>
          </div>
        </div>
        <van-dialog v-model:show="showManual" title="自定义事项" show-cancel-button @confirm="createManual">
          <van-field v-model="manualForm.title" label="标题" />
          <van-field v-model="manualForm.deadline" label="截止" placeholder="YYYY-MM-DD" />
          <van-field v-model="manualForm.university_name" label="学校" />
          <van-field v-model="manualForm.student_note" label="备注" type="textarea" rows="2" />
        </van-dialog>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'
import {
  activeStudentId,
  loadForActiveStudent,
  normalizeStudentId,
  studentLabel,
  switchActiveStudent,
  syncStudentsAndActive,
} from './activeStudent'
import { getSaasToken, saasApi } from './saasApi'
import { CSCA_STATUS_OPTIONS, PRIORITY_LEVELS, SECTIONS, STATUS_LABEL, TIMELINE_STATUS_LABEL, WIZARD_SECTIONS, emptyCourse, emptyCsca, emptyGrade, emptyLang, emptyOther, emptySchool, emptyTarget } from './studentProfileLib'

const emit = defineEmits(['goto-judge', 'goto-member'])
const sections = SECTIONS
const wizardSections = WIZARD_SECTIONS
const priorityLevels = PRIORITY_LEVELS
const statusLabel = STATUS_LABEL
const timelineStatusLabel = TIMELINE_STATUS_LABEL
const timelineGroupsUI = [
  { key: 'overdue', label: '已逾期' },
  { key: 'next_30', label: '未来30天' },
  { key: 'next_90', label: '未来90天' },
  { key: 'later', label: '以后' },
  { key: 'completed', label: '已完成' },
]
const students = ref([])
const loadedStudentId = ref(null)
const profile = ref(null)
const portrait = ref(null)
const slots = ref({
  student_profile_limit: 1,
  student_profile_used: 0,
  student_profile_remaining: 1,
  student_profile_over_quota: 0,
  can_create_student: true,
})
const showCscaStatus = ref(false)
const cscaStatusColumns = CSCA_STATUS_OPTIONS.map(o => ({ text: o.label, value: o.value }))
const cscaStatusLabel = computed(() => {
  const v = profile.value?.csca?.csca_status || 'NOT_PLANNED'
  return CSCA_STATUS_OPTIONS.find(o => o.value === v)?.label || v
})
const section = ref('summary')
const saving = ref(false)
const completeness = ref({ percent: 0, missing: [] })
const showPicker = ref(false)
const pickerEpoch = ref(0)
const timeline = ref([])
const timelineGroups = ref({ overdue: [], next_30: [], next_90: [], later: [], completed: [] })
const timelineSummary = ref({ overdue_count: 0, next_30_count: 0, next_90_count: 0, next_30: [], next_90: [] })
const timelineBusy = ref(false)
const showManual = ref(false)
const manualForm = ref({ title: '', deadline: '', university_name: '', student_note: '' })
const curriculaText = ref('')

const wizardMode = computed(() => profile.value && !profile.value.wizard_completed)
const saveLabel = computed(() => wizardMode.value ? '保存并继续' : '保存修改')
const currentLabel = computed(() => studentLabel(students.value, activeStudentId.value))
const studentColumns = computed(() => students.value.map(s => ({ text: s.display_name || `学生 #${s.id}`, value: normalizeStudentId(s.id) })))
const profilePickerSelectedValues = computed(() => {
  const id = normalizeStudentId(activeStudentId.value)
  return id != null ? [id] : []
})
const currentSchool = computed(() => {
  const list = profile.value?.education?.history || []
  return list.find(s => s.is_current) || list[0]
})
const readinessScore = computed(() => portrait.value?.application_readiness?.score ?? 0)
const targetCounts = computed(() => portrait.value?.targets?.counts || { reach: 0, target: 0, match: 0, safety: 0 })
const canCreate = computed(() => !!slots.value.can_create_student)
const limitHint = computed(() => {
  const lim = slots.value.student_profile_limit || 0
  const used = slots.value.student_profile_used || 0
  return `当前套餐最多可建立 ${lim} 个学生档案，已使用 ${used}/${lim}。如需管理更多学生，请升级套餐。`
})

function targetsBy(level) { return (profile.value?.goals?.targets || []).filter(t => t.priority_level === level) }
function countPri(level) { return targetsBy(level).length }
function gradesFor(id) { return (profile.value?.courses?.grades || []).filter(g => g.course_id === id) }
function onlyCurrent(idx) { profile.value.education.history.forEach((row, i) => { row.is_current = i === idx }) }
function addGrade(c) { profile.value.courses.grades.push(emptyGrade({ course_id: c.id, subject: c.subject, is_predicted: false })) }
function syncCurricula() { profile.value.courses.curricula = curriculaText.value.split(/[,，]/).map(s => s.trim()).filter(Boolean) }
function addMathBundle() {
  if (!profile.value.courses.curricula.includes('A-Level')) profile.value.courses.curricula.push('A-Level')
  curriculaText.value = profile.value.courses.curricula.join(',')
  const math = emptyCourse({ subject: 'Mathematics', qualification: 'A-Level', level: 'AS', exam_board: 'CCEA', start_year: '2025', end_year: '2027' })
  profile.value.courses.items.push(math, emptyCourse({ subject: 'Further Mathematics', qualification: 'A-Level' }), emptyCourse({ subject: 'Physics', qualification: 'A-Level' }))
  profile.value.courses.grades.push(
    emptyGrade({ course_id: math.id, subject: 'Mathematics', exam_session: 'AS', grade_type: 'Actual', grade: 'A' }),
    emptyGrade({ course_id: math.id, subject: 'Mathematics', exam_session: 'A2', grade_type: 'Predicted', grade: 'A*', is_predicted: true }),
  )
}

function apply(r) {
  loadedStudentId.value = normalizeStudentId(r.id)
  profile.value = r.profile
  if (!profile.value.csca) profile.value.csca = emptyCsca()
  completeness.value = r.completeness || { percent: 0, missing: [] }
  portrait.value = r.portrait || null
  if (r.slots) slots.value = r.slots
  if (r.dashboard?.timeline_summary) timelineSummary.value = r.dashboard.timeline_summary
  else if (r.portrait?.timeline_summary) timelineSummary.value = r.portrait.timeline_summary
  curriculaText.value = (profile.value.courses.curricula || []).join(',')
}

function goSection(key) {
  section.value = key
  if (key === 'portrait') refreshPortrait()
  if (key === 'my_timeline') loadMyTimeline()
}

async function loadList() {
  if (!getSaasToken()) {
    showFailToast('登录后可云端保存学生档案')
    return
  }
  try {
    const r = await saasApi.students()
    students.value = Array.isArray(r.students) ? r.students.slice() : []
    if (r.slots) slots.value = r.slots
    const resolved = syncStudentsAndActive(students.value)
    if (resolved && loadedStudentId.value !== resolved) await open(resolved)
  } catch (e) {
    showFailToast(e.message || '加载失败')
  }
}
async function createStudent() {
  if (!canCreate.value) {
    showFailToast(limitHint.value)
    return
  }
  try {
    const r = await saasApi.createStudent({ wizard: true, profile: {} })
    switchActiveStudent(r.id, { allowUnknown: true })
    apply(r)
    section.value = 'basic_info'
    await loadList()
    showSuccessToast('已创建学生')
  } catch (e) { showFailToast(e.message || '请先登录') }
}
async function open(id) {
  const nid = normalizeStudentId(id)
  if (!nid) return
  const listCount = students.value.length
  switchActiveStudent(nid, { allowUnknown: true })
  if (listCount > 0 && students.value.length !== listCount) {
    students.value = students.value.slice(0, listCount)
  }
  const result = await loadForActiveStudent(nid, (sid) => saasApi.student(sid))
  if (!result.ok) {
    if (result.reason === 'error') showFailToast(result.error?.message || '加载失败')
    return
  }
  apply(result.data)
  if (section.value === 'portrait') await refreshPortrait()
  if (section.value === 'my_timeline') await loadMyTimeline()
}
function openStudentPicker() {
  pickerEpoch.value += 1
  showPicker.value = true
}
function extractPickerStudentId(payload) {
  if (payload == null) return null
  const fromOpt = payload?.selectedOptions?.[0]
  if (fromOpt && typeof fromOpt === 'object') {
    const id = normalizeStudentId(fromOpt.value ?? fromOpt.id)
    if (id != null) return id
  }
  const fromValuesId = normalizeStudentId(payload?.selectedValues?.[0])
  if (fromValuesId != null) return fromValuesId
  if (Array.isArray(payload)) {
    const first = payload[0]
    if (first && typeof first === 'object') return normalizeStudentId(first.value ?? first.id)
    return normalizeStudentId(first)
  }
  return normalizeStudentId(payload)
}
function onPickStudent(payload) {
  showPicker.value = false
  const id = extractPickerStudentId(payload)
  if (id) open(id)
}

function ensureCsca() {
  if (!profile.value) return
  if (!profile.value.csca) profile.value.csca = emptyCsca()
}
function setCscaStatus(status) {
  ensureCsca()
  profile.value.csca.csca_status = status
}
function focusCscaScore() {
  ensureCsca()
  const cur = profile.value.csca.csca_status
  if (cur === 'NOT_PLANNED' || cur === 'PLANNED' || cur === 'REGISTERED') {
    profile.value.csca.csca_status = 'TAKEN'
  } else {
    profile.value.csca.csca_status = 'RESULT_AVAILABLE'
  }
}
function onPickCscaStatus({ selectedOptions }) {
  ensureCsca()
  const opt = selectedOptions?.[0]
  if (opt) profile.value.csca.csca_status = opt.value
  showCscaStatus.value = false
}

async function save(key) {
  if (!activeStudentId.value) return
  if (key === 'portrait' || key === 'my_timeline') return
  if (key === 'courses') syncCurricula()
  saving.value = true
  const sid = activeStudentId.value
  try {
    const r = await saasApi.patchStudentSection(sid, key, profile.value[key])
    if (normalizeStudentId(r.id) !== normalizeStudentId(activeStudentId.value)) return
    apply(r)
    showSuccessToast('已保存')
    if (wizardMode.value) {
      const idx = wizardSections.findIndex(s => s.key === key)
      if (idx >= 0 && idx < wizardSections.length - 1) section.value = wizardSections[idx + 1].key
      if (key === 'summary') await saasApi.completeStudentWizard(sid)
    }
    await loadList()
  } catch (e) { showFailToast(e.message || '保存失败') }
  finally { saving.value = false }
}
function goJudge(kind) {
  emit('goto-judge', {
    kind,
    studentId: activeStudentId.value,
    prefills: {
      name: profile.value.basic_info.chinese_name || profile.value.basic_info.english_name,
      birth_date: profile.value.basic_info.birth_date,
      current_nationality: profile.value.identity.current_nationality,
      has_foreign_nationality: profile.value.identity.has_foreign_nationality,
      has_chinese_nationality: profile.value.identity.has_chinese_nationality,
      foreign_nationality_acquired_date: profile.value.identity.foreign_nationality_acquired_date,
      passport_info: profile.value.identity.passport_info,
    },
  })
}
async function confirmWB(kind) {
  const sid = activeStudentId.value
  if (!sid) return
  const card = profile.value.identity[kind]
  const r = await saasApi.studentWriteback(sid, { kind, result: card.engine_result, conclusion: card.conclusion, record_id: card.record_id, policy_version: card.policy_version || 'R4.2', confirm: true })
  if (normalizeStudentId(r.id) !== normalizeStudentId(activeStudentId.value)) return
  apply(r)
  showSuccessToast('已确认写入学生档案')
}
async function loadTimeline() {
  const sid = activeStudentId.value
  if (!sid) return
  const r = await saasApi.studentTimeline(sid)
  if (normalizeStudentId(activeStudentId.value) !== sid) return
  timeline.value = r.matches || []
}
async function refreshPortrait() {
  const sid = activeStudentId.value
  if (!sid) return
  try {
    const r = await saasApi.studentPortrait(sid)
    if (normalizeStudentId(activeStudentId.value) !== sid) return
    portrait.value = r.portrait
    if (r.portrait?.timeline_summary) timelineSummary.value = r.portrait.timeline_summary
  } catch (e) { showFailToast(e.message || '刷新失败') }
}
async function loadMyTimeline() {
  const sid = activeStudentId.value
  if (!sid) return
  try {
    const r = await saasApi.studentTimelineItems(sid)
    if (normalizeStudentId(activeStudentId.value) !== sid) return
    timelineGroups.value = r.groups || timelineGroups.value
    timelineSummary.value = r.summary || timelineSummary.value
  } catch (e) { showFailToast(e.message || '加载时间轴失败') }
}
async function regenerateTimeline() {
  const sid = activeStudentId.value
  if (!sid) return
  timelineBusy.value = true
  try {
    const r = await saasApi.regenerateStudentTimeline(sid)
    if (normalizeStudentId(activeStudentId.value) !== sid) return
    timelineGroups.value = r.groups || {}
    timelineSummary.value = r.summary || timelineSummary.value
    if (r.portrait) portrait.value = r.portrait
    showSuccessToast('已重新生成')
  } catch (e) { showFailToast(e.message || '生成失败') }
  finally { timelineBusy.value = false }
}
async function patchItem(it, status) {
  const sid = activeStudentId.value
  if (!sid) return
  try {
    await saasApi.patchTimelineItem(sid, it.id, { status })
    if (normalizeStudentId(activeStudentId.value) !== sid) return
    await loadMyTimeline()
    await refreshPortrait()
  } catch (e) { showFailToast(e.message || '更新失败') }
}
async function editNote(it) {
  const sid = activeStudentId.value
  if (!sid) return
  const note = window.prompt('学生备注', it.student_note || '')
  if (note === null) return
  try {
    await saasApi.patchTimelineItem(sid, it.id, { student_note: note })
    if (normalizeStudentId(activeStudentId.value) !== sid) return
    await loadMyTimeline()
  } catch (e) { showFailToast(e.message || '备注失败') }
}
async function createManual() {
  const sid = activeStudentId.value
  if (!sid) return
  if (!manualForm.value.title.trim()) {
    showFailToast('请填写标题')
    return
  }
  try {
    await saasApi.createManualTimeline(sid, { ...manualForm.value })
    if (normalizeStudentId(activeStudentId.value) !== sid) return
    showManual.value = false
    manualForm.value = { title: '', deadline: '', university_name: '', student_note: '' }
    await loadMyTimeline()
    showSuccessToast('已添加')
  } catch (e) { showFailToast(e.message || '添加失败') }
}
function runAction(a) {
  const map = {
    ASSESS_INTERNATIONAL: () => goJudge('international'),
    ASSESS_HUAQIAO: () => goJudge('huaqiao'),
    ADD_PREDICTED: () => { section.value = 'courses' },
    ADD_LANGUAGE: () => { section.value = 'courses' },
    ADD_SAFETY: () => { section.value = 'goals' },
    ADD_ENTRY_YEAR: () => { section.value = 'basic_info' },
    ADD_TARGETS: () => { section.value = 'goals' },
    OPEN_TIMELINE_OVERDUE: () => goSection('my_timeline'),
    OPEN_TIMELINE_30: () => goSection('my_timeline'),
    OPEN_TIMELINE_90: () => goSection('my_timeline'),
    GENERATE_TIMELINE: () => { goSection('my_timeline'); regenerateTimeline() },
  }
  const fn = map[a.code]
  if (fn) fn()
  else if (a.section === 'timeline') goSection('my_timeline')
  else if (a.section) section.value = a.section
}
watch(section, (key) => {
  if (key === 'portrait') refreshPortrait()
  if (key === 'my_timeline') loadMyTimeline()
})
watch(activeStudentId, (id) => {
  const nid = normalizeStudentId(id)
  if (!nid || nid === loadedStudentId.value) return
  open(nid)
})
onMounted(loadList)
defineExpose({ loadList, openStudent: open })
</script>
