<template>
  <div class="smp">
    <div class="smp-head">
      <div>
        <p class="smp-eyebrow">国侨升学 · Student Master Profile</p>
        <h2>学生档案</h2>
        <p class="muted">档案是升学规划数据中心。每页独立保存，判定结果需确认后才写入身份状态。</p>
      </div>
      <div class="smp-head-actions">
        <el-button @click="loadList">刷新</el-button>
        <el-button type="primary" @click="createStudent">创建学生</el-button>
      </div>
    </div>

    <div class="smp-student-bar">
      <el-select v-model="studentId" placeholder="选择学生" filterable style="min-width:240px" @change="openStudent">
        <el-option v-for="s in students" :key="s.id" :label="`${s.display_name}（完整度 ${s.completeness?.percent || 0}%）`" :value="s.id" />
      </el-select>
      <el-tag v-if="profile" type="info">{{ wizardMode ? '建档向导' : '档案管理' }}</el-tag>
    </div>

    <template v-if="profile">
      <el-steps v-if="wizardMode" :active="wizardIndex" finish-status="success" class="smp-steps" align-center>
        <el-step v-for="sec in sections" :key="sec.key" :title="sec.label" @click="section = sec.key" />
      </el-steps>
      <div class="smp-layout">
        <aside class="smp-nav">
          <button v-for="sec in sections" :key="sec.key" :class="{active: section===sec.key}" type="button" @click="section=sec.key">{{ sec.label }}</button>
        </aside>
        <div class="smp-panel">
          <section v-show="section==='basic_info'" class="smp-card">
            <h3>基本信息</h3>
            <div class="smp-grid">
              <el-form-item label="中文名"><el-input v-model="profile.basic_info.chinese_name" /></el-form-item>
              <el-form-item label="英文名"><el-input v-model="profile.basic_info.english_name" /></el-form-item>
              <el-form-item label="出生日期"><el-input v-model="profile.basic_info.birth_date" placeholder="YYYY-MM-DD" /></el-form-item>
              <el-form-item label="性别"><el-select v-model="profile.basic_info.gender" clearable><el-option label="男" value="男"/><el-option label="女" value="女"/><el-option label="其他" value="其他"/></el-select></el-form-item>
              <el-form-item label="当前居住国家/地区"><el-input v-model="profile.basic_info.current_country" /></el-form-item>
              <el-form-item label="当前城市"><el-input v-model="profile.basic_info.current_city" /></el-form-item>
              <el-form-item label="联系方式"><el-input v-model="profile.basic_info.contact" /></el-form-item>
              <el-form-item label="预计入学年份"><el-input v-model="profile.basic_info.intended_entry_year" placeholder="2027" /></el-form-item>
              <el-form-item label="建档日期"><el-input v-model="profile.basic_info.profile_created_at" disabled /></el-form-item>
            </div>
            <el-form-item label="备注"><el-input v-model="profile.basic_info.basic_info_notes" type="textarea" :rows="3" /></el-form-item>
            <div class="smp-save"><el-button type="primary" :loading="saving" @click="saveSection('basic_info')">{{ saveLabel }}</el-button></div>
          </section>

          <section v-show="section==='education'" class="smp-card">
            <h3>当前在读学校</h3>
            <div class="smp-grid" v-if="currentSchool">
              <el-form-item label="学校名称"><el-input v-model="currentSchool.school_name" @change="markCurrentFromForm" /></el-form-item>
              <el-form-item label="国家/地区"><el-input v-model="currentSchool.country" @change="markCurrentFromForm" /></el-form-item>
              <el-form-item label="城市"><el-input v-model="currentSchool.city" @change="markCurrentFromForm" /></el-form-item>
              <el-form-item label="学校类型"><el-select v-model="currentSchool.school_type" @change="markCurrentFromForm"><el-option v-for="t in schoolTypes" :key="t" :label="t" :value="t"/></el-select></el-form-item>
              <el-form-item label="开始年月"><el-input v-model="currentSchool.start_date" placeholder="YYYY-MM" @change="markCurrentFromForm" /></el-form-item>
              <el-form-item label="当前年级"><el-input v-model="currentSchool.current_grade" @change="markCurrentFromForm" /></el-form-item>
            </div>
            <h3>教育经历</h3>
            <el-button @click="addEducation">+ 添加教育经历</el-button>
            <article v-for="(row, idx) in profile.education.history" :key="row.id" class="smp-item">
              <header>
                <strong>{{ row.school_name || '未命名学校' }}</strong>
                <div>
                  <el-button size="small" @click="moveEdu(idx,-1)">上移</el-button>
                  <el-button size="small" @click="moveEdu(idx,1)">下移</el-button>
                  <el-button size="small" type="danger" @click="removeEdu(idx)">删除</el-button>
                </div>
              </header>
              <div class="smp-grid">
                <el-form-item label="学校名称"><el-input v-model="row.school_name" /></el-form-item>
                <el-form-item label="国家/地区"><el-input v-model="row.country" /></el-form-item>
                <el-form-item label="城市"><el-input v-model="row.city" /></el-form-item>
                <el-form-item label="学校类型"><el-select v-model="row.school_type"><el-option v-for="t in schoolTypes" :key="t" :label="t" :value="t"/></el-select></el-form-item>
                <el-form-item label="开始年月"><el-input v-model="row.start_date" /></el-form-item>
                <el-form-item label="结束年月"><el-input v-model="row.end_date" /></el-form-item>
                <el-form-item label="年级/阶段"><el-input v-model="row.current_grade" /></el-form-item>
                <el-form-item label="当前在读"><el-switch v-model="row.is_current" @change="() => onlyOneCurrent(idx)" /></el-form-item>
                <el-form-item label="本条备注"><el-input v-model="row.notes" /></el-form-item>
              </div>
            </article>
            <el-form-item label="备注"><el-input v-model="profile.education.education_notes" type="textarea" :rows="3" /></el-form-item>
            <div class="smp-save"><el-button type="primary" :loading="saving" @click="saveSection('education')">{{ saveLabel }}</el-button></div>
          </section>

          <section v-show="section==='courses'" class="smp-card">
            <h3>课程体系</h3>
            <el-select v-model="profile.courses.curricula" multiple filterable allow-create default-first-option placeholder="选择或自定义">
              <el-option v-for="c in curriculums" :key="c" :label="c" :value="c" />
            </el-select>
            <el-form-item v-if="profile.courses.curricula.includes('Custom') || profile.courses.curricula.includes('Other')" label="自定义课程体系" class="mt"><el-input v-model="profile.courses.custom_curriculum" /></el-form-item>
            <h3>课程</h3>
            <el-button @click="profile.courses.items.push(emptyCourse({ qualification: (profile.courses.curricula[0]||'A-Level') }))">+ 添加课程</el-button>
            <article v-for="(c, idx) in profile.courses.items" :key="c.id" class="smp-item">
              <header><strong>{{ c.subject || '未命名课程' }}</strong><el-button size="small" type="danger" @click="profile.courses.items.splice(idx,1)">删除</el-button></header>
              <div class="smp-grid">
                <el-form-item label="科目"><el-input v-model="c.subject" /></el-form-item>
                <el-form-item label="资格"><el-input v-model="c.qualification" placeholder="A-Level / IB ..." /></el-form-item>
                <el-form-item label="Level"><el-input v-model="c.level" placeholder="AS / A2 / HL" /></el-form-item>
                <el-form-item label="Exam board"><el-input v-model="c.exam_board" placeholder="CCEA / AQA" /></el-form-item>
                <el-form-item label="开始年"><el-input v-model="c.start_year" /></el-form-item>
                <el-form-item label="结束年"><el-input v-model="c.end_year" /></el-form-item>
                <el-form-item label="在读"><el-switch v-model="c.is_current" /></el-form-item>
                <el-form-item label="备注"><el-input v-model="c.notes" /></el-form-item>
              </div>
              <p class="muted">本课程成绩（可多年、Actual + Predicted 并存）</p>
              <el-button size="small" @click="addGrade(c)">+ 添加成绩</el-button>
              <div v-for="(g, gidx) in gradesFor(c.id)" :key="g.id" class="smp-grade">
                <el-input v-model="g.academic_year" placeholder="学年" />
                <el-input v-model="g.exam_session" placeholder="GCSE/AS/A2" />
                <el-select v-model="g.grade_type" @change="g.is_predicted = g.grade_type==='Predicted'"><el-option v-for="t in gradeTypes" :key="t" :label="t" :value="t"/></el-select>
                <el-input v-model="g.grade" placeholder="等级" />
                <el-input v-model="g.score" placeholder="分数" />
                <el-input v-model="g.exam_board" placeholder="局" />
                <el-button size="small" type="danger" @click="removeGrade(gidx, g.id)">删</el-button>
              </div>
            </article>
            <h3>语言成绩</h3>
            <el-button @click="profile.courses.language_exams.push(emptyLang())">+ 添加语言考试</el-button>
            <article v-for="(ex, idx) in profile.courses.language_exams" :key="ex.id" class="smp-item">
              <div class="smp-grid">
                <el-form-item label="考试"><el-select v-model="ex.exam_type"><el-option v-for="t in languageExams" :key="t" :label="t" :value="t"/></el-select></el-form-item>
                <el-form-item label="日期"><el-input v-model="ex.exam_date" /></el-form-item>
                <el-form-item label="总分/等级"><el-input v-model="ex.overall_score" placeholder="HSK 6 / IELTS 7.0" /></el-form-item>
                <el-form-item label="证书号"><el-input v-model="ex.certificate_no" /></el-form-item>
                <el-form-item label="分项"><el-input v-model="ex.notes" placeholder="听/说/读/写可写在备注" /></el-form-item>
              </div>
              <el-button size="small" type="danger" @click="profile.courses.language_exams.splice(idx,1)">删除</el-button>
            </article>
            <h3>其他考试 / 资格</h3>
            <el-button @click="profile.courses.other_exams.push(emptyOther())">+ 添加资格</el-button>
            <article v-for="(ex, idx) in profile.courses.other_exams" :key="ex.id" class="smp-item">
              <div class="smp-grid">
                <el-form-item label="类型"><el-select v-model="ex.exam_type" allow-create filterable><el-option v-for="t in otherExams" :key="t" :label="t" :value="t"/></el-select></el-form-item>
                <el-form-item label="自定义"><el-input v-model="ex.custom_type" /></el-form-item>
                <el-form-item label="日期"><el-input v-model="ex.exam_date" /></el-form-item>
                <el-form-item label="成绩"><el-input v-model="ex.score" /></el-form-item>
                <el-form-item label="备注"><el-input v-model="ex.notes" /></el-form-item>
              </div>
              <el-button size="small" type="danger" @click="profile.courses.other_exams.splice(idx,1)">删除</el-button>
            </article>
            <el-form-item label="备注"><el-input v-model="profile.courses.courses_notes" type="textarea" :rows="3" /></el-form-item>
            <div class="smp-save"><el-button type="primary" :loading="saving" @click="saveSection('courses')">{{ saveLabel }}</el-button></div>
          </section>

          <section v-show="section==='goals'" class="smp-card">
            <h3>目标大学列表</h3>
            <el-button type="primary" plain @click="profile.goals.targets.push(emptyTarget())">+ 添加目标大学</el-button>
            <div v-for="level in priorityLevels" :key="level.value" class="smp-priority">
              <h4>{{ level.label }}</h4>
              <article v-for="(t, idx) in targetsBy(level.value)" :key="t.id" class="smp-item">
                <div class="smp-grid">
                  <el-form-item label="国家"><el-input v-model="t.country" /></el-form-item>
                  <el-form-item label="大学"><el-select v-model="t.university_name" filterable allow-create default-first-option @change="onUniPick(t)">
                    <el-option v-for="u in universityOptions" :key="u.id" :label="u.name" :value="u.name" />
                  </el-select></el-form-item>
                  <el-form-item label="专业"><el-input v-model="t.major" /></el-form-item>
                  <el-form-item label="学院"><el-input v-model="t.college" /></el-form-item>
                  <el-form-item label="入学年"><el-input v-model="t.entry_year" /></el-form-item>
                  <el-form-item label="申请通道"><el-input v-model="t.application_route" placeholder="国际生 / 联招" /></el-form-item>
                  <el-form-item label="分类"><el-select v-model="t.priority_level"><el-option v-for="p in priorityLevels" :key="p.value" :label="p.label" :value="p.value"/></el-select></el-form-item>
                  <el-form-item label="备注"><el-input v-model="t.notes" /></el-form-item>
                </div>
                <el-button size="small" type="danger" @click="removeTarget(t.id)">删除</el-button>
              </article>
            </div>
            <el-form-item label="备注"><el-input v-model="profile.goals.goals_notes" type="textarea" :rows="3" /></el-form-item>
            <div class="smp-save"><el-button type="primary" :loading="saving" @click="saveSection('goals')">{{ saveLabel }}</el-button></div>
          </section>

          <section v-show="section==='identity'" class="smp-card">
            <el-alert type="info" :closable="false" title="以下为事实字段，不能自行勾选“我是国际生/华侨生”。资格只能由判定模块写入。" />
            <div class="smp-grid mt">
              <el-form-item label="出生国家"><el-input v-model="profile.identity.birth_country" /></el-form-item>
              <el-form-item label="当前国籍"><el-input v-model="profile.identity.current_nationality" /></el-form-item>
              <el-form-item label="曾经国籍"><el-input v-model="profile.identity.former_nationalities" /></el-form-item>
              <el-form-item label="取得外国国籍日期"><el-input v-model="profile.identity.foreign_nationality_acquired_date" /></el-form-item>
              <el-form-item label="外国永久居留"><el-input v-model="profile.identity.foreign_permanent_residence" /></el-form-item>
              <el-form-item label="护照信息"><el-input v-model="profile.identity.passport_info" /></el-form-item>
              <el-form-item label="父亲国籍"><el-input v-model="profile.identity.father_nationality" /></el-form-item>
              <el-form-item label="母亲国籍"><el-input v-model="profile.identity.mother_nationality" /></el-form-item>
            </div>
            <div class="smp-switches">
              <el-switch v-model="profile.identity.has_foreign_nationality" active-text="持有外国国籍（事实）" />
              <el-switch v-model="profile.identity.has_chinese_nationality" active-text="持有中国国籍（事实）" />
              <el-switch v-model="profile.identity.had_chinese_nationality" active-text="曾拥有中国国籍" />
              <el-switch v-model="profile.identity.has_chinese_hukou" active-text="有中国户籍" />
              <el-switch v-model="profile.identity.hukou_cancelled" active-text="已注销中国户籍" />
            </div>
            <el-form-item label="父母海外定居信息"><el-input v-model="profile.identity.parents_overseas_settlement" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="海外居住信息"><el-input v-model="profile.identity.overseas_residence_info" type="textarea" :rows="2" /></el-form-item>
            <div class="smp-verdicts">
              <el-card>
                <h4>国际生资格</h4>
                <p v-if="profile.identity.international.status==='NOT_ASSESSED'">国际生资格尚未判定</p>
                <p v-else>{{ statusLabel[profile.identity.international.status] }} · {{ profile.identity.international.conclusion || '—' }}</p>
                <p class="muted" v-if="profile.identity.international.assessed_at">判定时间 {{ profile.identity.international.assessed_at }} · 依据 {{ profile.identity.international.policy_version || '—' }}</p>
                <p class="muted">{{ profile.identity.international.confirmed ? '已确认写入档案' : '尚未确认写入档案' }}</p>
                <el-button type="primary" @click="goJudge('international')">前往国际生判定</el-button>
                <el-button v-if="profile.identity.international.engine_result && !profile.identity.international.confirmed" @click="confirmWriteback('international')">确认写入学生档案</el-button>
              </el-card>
              <el-card>
                <h4>华侨生资格</h4>
                <p v-if="profile.identity.huaqiao.status==='NOT_ASSESSED'">华侨生资格尚未判定</p>
                <p v-else>{{ statusLabel[profile.identity.huaqiao.status] }} · {{ profile.identity.huaqiao.conclusion || '—' }}</p>
                <p class="muted" v-if="profile.identity.huaqiao.assessed_at">判定时间 {{ profile.identity.huaqiao.assessed_at }} · 依据 {{ profile.identity.huaqiao.policy_version || '—' }}</p>
                <p class="muted">{{ profile.identity.huaqiao.confirmed ? '已确认写入档案' : '尚未确认写入档案' }}</p>
                <el-button type="primary" @click="goJudge('huaqiao')">前往华侨生判定</el-button>
                <el-button v-if="profile.identity.huaqiao.engine_result && !profile.identity.huaqiao.confirmed" @click="confirmWriteback('huaqiao')">确认写入学生档案</el-button>
              </el-card>
            </div>
            <el-form-item label="备注"><el-input v-model="profile.identity.identity_notes" type="textarea" :rows="3" /></el-form-item>
            <div class="smp-save"><el-button type="primary" :loading="saving" @click="saveSection('identity')">{{ saveLabel }}</el-button></div>
          </section>

          <section v-show="section==='planning'" class="smp-card">
            <h3>申请与规划</h3>
            <div class="smp-grid">
              <el-form-item label="预计入学年份"><el-input v-model="profile.basic_info.intended_entry_year" disabled /></el-form-item>
              <el-form-item label="当前教育阶段"><el-input v-model="profile.planning.current_education_stage" /></el-form-item>
              <el-form-item label="目标国家"><el-input v-model="profile.planning.target_countries" /></el-form-item>
            </div>
            <ul class="smp-facts">
              <li>当前学校：{{ profile.education.current_school.school_name || '—' }}</li>
              <li>国际生状态：{{ statusLabel[profile.identity.international.status] }}</li>
              <li>华侨生状态：{{ statusLabel[profile.identity.huaqiao.status] }}</li>
              <li>目标大学：{{ profile.goals.targets.map(t=>t.university_name).filter(Boolean).join('、') || '—' }}</li>
              <li>目标专业：{{ profile.goals.targets.map(t=>t.major).filter(Boolean).join('、') || '—' }}</li>
              <li>冲刺/主申/稳妥/保底：{{ countPri('reach') }} / {{ countPri('target') }} / {{ countPri('match') }} / {{ countPri('safety') }}</li>
              <li>已完成考试：{{ doneExams || '—' }}</li>
              <li>待完成考试：课程中标记在读且尚无 Actual 成绩的科目</li>
            </ul>
            <h4>匹配招生时间线（只读）</h4>
            <el-button size="small" @click="loadTimeline">读取匹配结果</el-button>
            <el-timeline v-if="timeline.length">
              <el-timeline-item v-for="(s,i) in timeline" :key="i" :timestamp="`${s.year}年${s.month}月`">
                <b>{{ s.university_name }}</b>
                <p>报名：{{ s.registration_time }}；材料：{{ s.material_deadline }}；考试：{{ s.exam_time }}</p>
              </el-timeline-item>
            </el-timeline>
            <p v-else class="muted">保存目标大学后可匹配现有招生时间轴，不会改写原始时间线数据。</p>
            <el-form-item label="备注"><el-input v-model="profile.planning.planning_notes" type="textarea" :rows="3" /></el-form-item>
            <div class="smp-save"><el-button type="primary" :loading="saving" @click="saveSection('planning')">{{ saveLabel }}</el-button></div>
          </section>

          <section v-show="section==='summary'" class="smp-card">
            <h3>档案总览</h3>
            <div class="smp-complete">
              <el-progress type="circle" :percentage="completeness.percent || 0" />
              <div>
                <p>PROFILE COMPLETENESS {{ completeness.percent || 0 }}%</p>
                <p class="muted">缺失只做提示，不强制一次填完。</p>
                <ul>
                  <li v-for="m in completeness.missing || []" :key="m">{{ m }}</li>
                </ul>
              </div>
            </div>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="姓名">{{ profile.basic_info.chinese_name }} {{ profile.basic_info.english_name }}</el-descriptions-item>
              <el-descriptions-item label="出生日期">{{ profile.basic_info.birth_date || '—' }}</el-descriptions-item>
              <el-descriptions-item label="当前学校">{{ profile.education.current_school.school_name || '—' }}</el-descriptions-item>
              <el-descriptions-item label="课程体系">{{ (profile.courses.curricula||[]).join(' / ') || '—' }}</el-descriptions-item>
              <el-descriptions-item label="主要课程">{{ (profile.courses.items||[]).map(c=>c.subject).filter(Boolean).join('、') || '—' }}</el-descriptions-item>
              <el-descriptions-item label="语言成绩">{{ (profile.courses.language_exams||[]).map(e=>`${e.exam_type} ${e.overall_score}`).join('、') || '—' }}</el-descriptions-item>
              <el-descriptions-item label="国际生">{{ statusLabel[profile.identity.international.status] }}</el-descriptions-item>
              <el-descriptions-item label="华侨生">{{ statusLabel[profile.identity.huaqiao.status] }}</el-descriptions-item>
              <el-descriptions-item label="预计入学">{{ profile.basic_info.intended_entry_year || '—' }}</el-descriptions-item>
              <el-descriptions-item label="目标大学">{{ profile.goals.targets.map(t=>`${t.university_name}（${priorityLabel(t.priority_level)}）`).join('、') || '—' }}</el-descriptions-item>
            </el-descriptions>
            <el-form-item class="mt" label="备注"><el-input v-model="profile.summary.summary_notes" type="textarea" :rows="3" /></el-form-item>
            <div class="smp-save"><el-button type="primary" :loading="saving" @click="saveSection('summary')">{{ saveLabel }}</el-button></div>
          </section>
        </div>
      </div>
    </template>
    <el-empty v-else description="请创建或选择学生，进入长期可维护的主档案" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from './api'
import { CURRICULUMS, GRADE_TYPES, LANGUAGE_EXAMS, OTHER_EXAM_TYPES, PRIORITY_LEVELS, SCHOOL_TYPES, SECTIONS, STATUS_LABEL, emptyCourse, emptyGrade, emptyLang, emptyOther, emptySchool, emptyTarget } from './studentProfileLib'

const emit = defineEmits(['goto-judge'])

const sections = SECTIONS
const schoolTypes = SCHOOL_TYPES
const curriculums = CURRICULUMS
const gradeTypes = GRADE_TYPES
const languageExams = LANGUAGE_EXAMS
const otherExams = OTHER_EXAM_TYPES
const priorityLevels = PRIORITY_LEVELS
const statusLabel = STATUS_LABEL

const students = ref([])
const studentId = ref(null)
const profile = ref(null)
const section = ref('basic_info')
const saving = ref(false)
const completeness = ref({ percent: 0, missing: [] })
const universityOptions = ref([])
const timeline = ref([])

const wizardMode = computed(() => profile.value && !profile.value.wizard_completed)
const wizardIndex = computed(() => Math.max(0, sections.findIndex(s => s.key === section.value)))
const saveLabel = computed(() => wizardMode.value ? '保存并继续' : '保存修改')
const currentSchool = computed(() => {
  const list = profile.value?.education?.history || []
  return list.find(s => s.is_current) || list[0]
})
const doneExams = computed(() => {
  const langs = (profile.value?.courses?.language_exams || []).map(e => e.exam_type).filter(Boolean)
  const actual = (profile.value?.courses?.grades || []).filter(g => g.grade_type === 'Actual').map(g => g.subject)
  return [...langs, ...actual].join('、')
})

function targetsBy(level) {
  return (profile.value?.goals?.targets || []).filter(t => t.priority_level === level)
}
function countPri(level) {
  return targetsBy(level).length
}
function priorityLabel(v) {
  return priorityLevels.find(p => p.value === v)?.label || v
}
function gradesFor(courseId) {
  return (profile.value?.courses?.grades || []).filter(g => g.course_id === courseId)
}

async function loadList() {
  const r = await api.students()
  students.value = r.students || []
  if (!studentId.value && students.value[0]) {
    studentId.value = students.value[0].id
    await openStudent(studentId.value)
  }
}
async function createStudent() {
  const r = await api.createStudent({ wizard: true, profile: {} })
  studentId.value = r.id
  applyPayload(r)
  section.value = 'basic_info'
  await loadList()
  ElMessage.success('已创建学生，可开始建档向导')
}
async function openStudent(id) {
  if (!id) return
  const r = await api.student(id)
  applyPayload(r)
}
function applyPayload(r) {
  profile.value = r.profile
  completeness.value = r.completeness || { percent: 0, missing: [] }
  if (profile.value?.wizard_completed) {
    /* stay on current section */
  }
}

async function saveSection(key) {
  if (!studentId.value || !profile.value) return
  saving.value = true
  try {
    const r = await api.patchStudentSection(studentId.value, key, profile.value[key])
    applyPayload(r)
    ElMessage.success('已保存')
    if (wizardMode.value) {
      const idx = sections.findIndex(s => s.key === key)
      if (idx >= 0 && idx < sections.length - 1) section.value = sections[idx + 1].key
      if (key === 'summary') {
        await api.completeStudentWizard(studentId.value)
        await openStudent(studentId.value)
      }
    }
    await loadList()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function addEducation() {
  profile.value.education.history.push(emptySchool())
}
function removeEdu(idx) {
  profile.value.education.history.splice(idx, 1)
}
function moveEdu(idx, dir) {
  const arr = profile.value.education.history
  const next = idx + dir
  if (next < 0 || next >= arr.length) return
  const [row] = arr.splice(idx, 1)
  arr.splice(next, 0, row)
}
function onlyOneCurrent(idx) {
  profile.value.education.history.forEach((row, i) => { row.is_current = i === idx })
}
function markCurrentFromForm() {
  const cur = currentSchool.value
  if (!cur) return
  cur.is_current = true
}
function addGrade(course) {
  profile.value.courses.grades.push(emptyGrade({ course_id: course.id, subject: course.subject, exam_board: course.exam_board }))
}
function removeGrade(_gidx, id) {
  profile.value.courses.grades = profile.value.courses.grades.filter(g => g.id !== id)
}
function removeTarget(id) {
  profile.value.goals.targets = profile.value.goals.targets.filter(t => t.id !== id)
}
function onUniPick(t) {
  const u = universityOptions.value.find(x => x.name === t.university_name)
  t.university_id = u ? u.id : null
}

function goJudge(kind) {
  emit('goto-judge', { kind, studentId: studentId.value, prefills: {
    name: profile.value.basic_info.chinese_name || profile.value.basic_info.english_name,
    birth_date: profile.value.basic_info.birth_date,
    current_nationality: profile.value.identity.current_nationality,
    has_foreign_nationality: profile.value.identity.has_foreign_nationality,
    has_chinese_nationality: profile.value.identity.has_chinese_nationality,
    foreign_nationality_acquired_date: profile.value.identity.foreign_nationality_acquired_date,
    passport_info: profile.value.identity.passport_info,
    has_mainland_household: profile.value.identity.has_chinese_hukou && !profile.value.identity.hukou_cancelled,
  }})
}
async function confirmWriteback(kind) {
  const card = profile.value.identity[kind]
  const r = await api.studentWriteback(studentId.value, { kind, result: card.engine_result, conclusion: card.conclusion, record_id: card.record_id, policy_version: card.policy_version || 'R4.2', confirm: true })
  applyPayload(r)
  ElMessage.success('已确认写入学生档案')
}
async function loadTimeline() {
  if (!studentId.value) return
  try {
    const r = await api.studentTimeline(studentId.value)
    timeline.value = r.matches || []
  } catch (e) {
    ElMessage.error(e.message || '读取时间线失败')
  }
}

onMounted(async () => {
  try {
    universityOptions.value = await api.universities('international', '')
  } catch { universityOptions.value = [] }
  await loadList()
})

watch(section, () => { window.scrollTo({ top: 0, behavior: 'smooth' }) })

defineExpose({ openStudent, loadList, applyWriteback: async (kind, result) => {
  if (!studentId.value || !result) return
  const r = await api.studentWriteback(studentId.value, {
    kind,
    result: result.result,
    conclusion: result.conclusion || result.explanation,
    record_id: result.record_id,
    policy_version: 'R4.2',
    confirm: false,
  })
  applyPayload(r)
}})
</script>
