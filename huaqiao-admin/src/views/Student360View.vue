<template>
  <div v-if="data" class="s360">
    <!-- Top ops summary -->
    <header class="gq-panel ops-summary">
      <div>
        <h1 class="page-title">{{ displayName }}</h1>
        <p class="page-sub gq-muted">Student 360 运营工作台 · ID {{ data.student_id }}</p>
      </div>
      <div class="ops-grid">
        <div class="ops-cell hi"><span class="k">学生姓名</span><span class="v">{{ displayName }}</span></div>
        <div class="ops-cell hi"><span class="k">Student ID</span><span class="v">{{ data.student_id }}</span></div>
        <div class="ops-cell hi"><span class="k">身份路线</span><span class="v">{{ human(crm.identity_track || identityRoute) }}</span></div>
        <div class="ops-cell hi"><span class="k">CRM 阶段</span><span class="v"><el-tag size="small">{{ human(crm.crm_stage_label || ops.crm_stage_label, EMPTY.unassigned) }}</el-tag></span></div>
        <div class="ops-cell hi"><span class="k">负责人</span><span class="v">{{ human(crm.assignee_label || ops.assignee_label, EMPTY.unassigned) }}</span></div>
        <div class="ops-cell hi"><span class="k">风险</span><span class="v"><el-tag size="small" :type="riskTagType(crm.risk_level)" effect="dark">{{ riskLabel(crm.risk_level) }}</el-tag></span></div>
        <div class="ops-cell hi"><span class="k">下一步</span><span class="v">{{ human(crm.next_action || ops.next_action, EMPTY.unset) }}</span></div>
        <div class="ops-cell hi"><span class="k">下次跟进</span><span class="v">{{ humanDateTime(crm.next_follow_up_at || ops.next_follow_up_at, EMPTY.unset) }}</span></div>
        <div class="ops-cell"><span class="k">所属账号</span><span class="v">{{ human(owner.email || owner.name) }}</span></div>
        <div class="ops-cell"><span class="k">当前套餐</span><span class="v">{{ planLabel }}</span></div>
        <div class="ops-cell"><span class="k">最后更新</span><span class="v">{{ humanDateTime(meta.updated_at) }}</span></div>
      </div>
      <div class="ops-actions">
        <el-select v-model="assignTo" clearable placeholder="分配负责人" style="width:180px">
          <el-option label="未分配" :value="0" />
          <el-option v-for="s in staff" :key="s.id" :label="s.label" :value="s.id" />
        </el-select>
        <el-button size="small" type="primary" @click="doAssign">分配负责人</el-button>
        <el-select v-model="stageEdit" placeholder="阶段" style="width:140px">
          <el-option v-for="(label, key) in stageLabels" :key="key" :label="label" :value="key" />
        </el-select>
        <el-button size="small" @click="saveStage">更新阶段</el-button>
      </div>
    </header>

    <div class="gq-grid-2">
      <div>
        <!-- Basic -->
        <section class="gq-panel block">
          <h3>基本资料 / 所属用户</h3>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="学生姓名">{{ human(basic.chinese_name || displayName) }}</el-descriptions-item>
            <el-descriptions-item label="英文名">{{ human(basic.english_name) }}</el-descriptions-item>
            <el-descriptions-item label="出生日期">{{ humanDate(basic.birth_date) }}</el-descriptions-item>
            <el-descriptions-item label="性别">{{ human(basic.gender) }}</el-descriptions-item>
            <el-descriptions-item label="当前国家">{{ human(basic.current_country) }}</el-descriptions-item>
            <el-descriptions-item label="当前城市">{{ human(basic.current_city) }}</el-descriptions-item>
            <el-descriptions-item label="联系方式">{{ human(basic.contact) }}</el-descriptions-item>
            <el-descriptions-item label="入学年份">{{ human(basic.intended_entry_year) }}</el-descriptions-item>
            <el-descriptions-item label="Student ID">{{ data.student_id }}</el-descriptions-item>
            <el-descriptions-item label="所属用户">{{ human(owner.email) }}</el-descriptions-item>
            <el-descriptions-item label="用户姓名">{{ human(owner.name) }}</el-descriptions-item>
            <el-descriptions-item label="用户邮箱">{{ human(owner.email) }}</el-descriptions-item>
            <el-descriptions-item label="当前套餐">{{ planLabel }}</el-descriptions-item>
            <el-descriptions-item label="Trial 状态">{{ trialLabel }}</el-descriptions-item>
            <el-descriptions-item label="会员到期">{{ humanDateTime(owner.membership_until) }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ humanDateTime(meta.created_at) }}</el-descriptions-item>
          </el-descriptions>
        </section>

        <section class="gq-panel block">
          <h3>档案分节</h3>
          <el-tabs>
            <el-tab-pane label="身份/国籍">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="出生国家">{{ human(identity.birth_country) }}</el-descriptions-item>
                <el-descriptions-item label="当前国籍">{{ human(identity.current_nationality) }}</el-descriptions-item>
                <el-descriptions-item label="曾用国籍">{{ human(identity.former_nationalities) }}</el-descriptions-item>
                <el-descriptions-item label="是否曾有中国国籍">{{ humanBool(identity.had_chinese_nationality) }}</el-descriptions-item>
                <el-descriptions-item label="是否有中国户籍">{{ humanBool(identity.has_chinese_hukou) }}</el-descriptions-item>
                <el-descriptions-item label="户籍是否已注销">{{ humanBool(identity.hukou_cancelled) }}</el-descriptions-item>
                <el-descriptions-item label="国际生身份状态">{{ human(identity.international?.status || identity.international?.conclusion, EMPTY.judge) }}</el-descriptions-item>
                <el-descriptions-item label="华侨生身份状态">{{ human(identity.huaqiao?.status || identity.huaqiao?.conclusion, EMPTY.judge) }}</el-descriptions-item>
                <el-descriptions-item label="风险提示" :span="2">{{ human(identity.identity_notes || identityRiskHint, EMPTY.none) }}</el-descriptions-item>
              </el-descriptions>
            </el-tab-pane>

            <el-tab-pane label="教育背景">
              <el-descriptions :column="2" border size="small" class="mb">
                <el-descriptions-item label="当前学校">{{ human(currentSchool.school_name || currentSchool.name) }}</el-descriptions-item>
                <el-descriptions-item label="课程体系">{{ human(pick(currentSchool.curriculum, currentSchool.school_type, educationCurriculum)) }}</el-descriptions-item>
                <el-descriptions-item label="年级">{{ human(currentSchool.current_grade || currentSchool.grade) }}</el-descriptions-item>
                <el-descriptions-item label="学历">{{ human(currentSchool.qualification || education.degree_level) }}</el-descriptions-item>
                <el-descriptions-item label="预计毕业时间">{{ humanDate(currentSchool.end_date || currentSchool.expected_graduation) }}</el-descriptions-item>
                <el-descriptions-item label="所在城市">{{ human(pick(currentSchool.city, currentSchool.country)) }}</el-descriptions-item>
                <el-descriptions-item label="主要科目" :span="2">{{ human(mainSubjects) }}</el-descriptions-item>
                <el-descriptions-item label="成绩摘要" :span="2">{{ human(gradesSummary) }}</el-descriptions-item>
              </el-descriptions>
              <h4 class="sub-h">教育经历</h4>
              <el-table v-if="educationHistory.length" :data="educationHistory" size="small" stripe>
                <el-table-column label="学校" min-width="160">
                  <template #default="{ row }">{{ human(row.school_name || row.name) }}</template>
                </el-table-column>
                <el-table-column label="起止" width="180">
                  <template #default="{ row }">{{ humanDate(row.start_date, '—') }} → {{ humanDate(row.end_date, '—') }}</template>
                </el-table-column>
                <el-table-column label="年级/体系" width="140">
                  <template #default="{ row }">{{ human(pick(row.current_grade, row.curriculum, row.school_type), '—') }}</template>
                </el-table-column>
                <el-table-column label="备注" min-width="120">
                  <template #default="{ row }">{{ human(row.notes, '—') }}</template>
                </el-table-column>
              </el-table>
              <p v-else class="gq-muted empty">{{ EMPTY.none }}</p>
            </el-tab-pane>

            <el-tab-pane label="语言成绩">
              <el-table v-if="languageRows.length" :data="languageRows" size="small" stripe>
                <el-table-column label="考试" width="120"><template #default="{ row }">{{ human(row.exam_type || row.exam) }}</template></el-table-column>
                <el-table-column label="成绩" width="100"><template #default="{ row }">{{ human(row.overall_score || row.score) }}</template></el-table-column>
                <el-table-column label="等级" width="100"><template #default="{ row }">{{ human(row.level || row.band) }}</template></el-table-column>
                <el-table-column label="考试日期" width="120"><template #default="{ row }">{{ humanDate(row.exam_date) }}</template></el-table-column>
                <el-table-column label="有效期" width="120"><template #default="{ row }">{{ humanDate(row.valid_until || row.expiry_date) }}</template></el-table-column>
                <el-table-column label="状态" width="100"><template #default="{ row }">{{ human(row.status, '已取得') }}</template></el-table-column>
              </el-table>
              <p v-else class="gq-muted empty">{{ EMPTY.none }}</p>
            </el-tab-pane>

            <el-tab-pane label="CSCA考试">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="状态"><el-tag size="small">{{ cscaStatusLabel(csca.csca_status, csca.csca_status_label) }}</el-tag></el-descriptions-item>
                <el-descriptions-item label="成绩">{{ human(csca.csca_score) }}</el-descriptions-item>
                <el-descriptions-item label="报名截止">{{ humanDate(csca.csca_registration_deadline, EMPTY.official) }}</el-descriptions-item>
                <el-descriptions-item label="考试日期">{{ humanDate(csca.csca_exam_date, EMPTY.official) }}</el-descriptions-item>
                <el-descriptions-item label="成绩发布日期">{{ humanDate(csca.csca_result_date, EMPTY.official) }}</el-descriptions-item>
                <el-descriptions-item label="等级">{{ human(csca.csca_level) }}</el-descriptions-item>
                <el-descriptions-item label="日期来源" :span="2">
                  报名={{ human(csca.registration_deadline_source, '—') }}
                  · 考试={{ human(csca.exam_date_source, '—') }}
                  · 成绩={{ human(csca.result_date_source, '—') }}
                </el-descriptions-item>
                <el-descriptions-item label="备注" :span="2">{{ human(csca.csca_notes, EMPTY.none) }}</el-descriptions-item>
              </el-descriptions>
            </el-tab-pane>

            <el-tab-pane label="目标大学/专业">
              <el-table v-if="targetRows.length" :data="targetRows" size="small" stripe>
                <el-table-column label="大学" min-width="160"><template #default="{ row }">{{ human(row.university_name || row.university) }}</template></el-table-column>
                <el-table-column label="地区" width="100"><template #default="{ row }">{{ human(row.country || row.region) }}</template></el-table-column>
                <el-table-column label="院校层次" width="110"><template #default="{ row }">{{ human(row.tier || row.university_tier) }}</template></el-table-column>
                <el-table-column label="目标专业" min-width="140"><template #default="{ row }">{{ human(row.major || row.college) }}</template></el-table-column>
                <el-table-column label="冲稳保" width="90"><template #default="{ row }">{{ targetPriorityLabel(row.priority_level || row.priority) }}</template></el-table-column>
                <el-table-column label="当前状态" width="110"><template #default="{ row }">{{ human(row.status || row.application_route) }}</template></el-table-column>
                <el-table-column label="备注" min-width="120"><template #default="{ row }">{{ human(row.notes, '—') }}</template></el-table-column>
              </el-table>
              <p v-else class="gq-muted empty">{{ EMPTY.noTargets }}</p>
            </el-tab-pane>
          </el-tabs>
        </section>

        <section class="gq-panel block">
          <h3>CSCA 协助更新</h3>
          <div class="row-edit">
            <el-select v-model="cscaForm.csca_status" placeholder="状态" style="width:160px">
              <el-option v-for="o in cscaStatuses" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-input v-model="cscaForm.csca_registration_deadline" placeholder="报名截止 YYYY-MM-DD" style="width:180px" />
            <el-input v-model="cscaForm.csca_exam_date" placeholder="考试日期 YYYY-MM-DD" style="width:180px" />
            <el-input v-model="cscaForm.csca_result_date" placeholder="成绩发布 YYYY-MM-DD" style="width:180px" />
            <el-input v-model="cscaForm.csca_score" placeholder="成绩" style="width:120px" />
            <el-input v-model="cscaForm.csca_level" placeholder="等级" style="width:120px" />
            <el-input v-model="cscaForm.csca_notes" placeholder="备注" style="width:200px" />
            <el-button type="primary" size="small" :loading="cscaSaving" @click="saveCsca">保存（审计）</el-button>
          </div>
          <p class="gq-muted" style="margin-top:6px">仅可填写真实日期；留空表示待官方公布。</p>
        </section>

        <section class="gq-panel block">
          <h3>资格判定</h3>
          <el-alert
            v-if="data.eligibility?.mapping_status === 'UNRESOLVED'"
            type="warning"
            :closable="false"
            title="历史资格记录尚未绑定到具体学生"
            :description="data.eligibility.message"
            style="margin-bottom:10px"
          />
          <div class="elig-grid">
            <div class="elig-card">
              <div class="elig-h"><strong>国际生</strong><el-tag size="small" :type="eligIntl.type">{{ eligIntl.label }}</el-tag></div>
              <p><span class="k">关键依据</span>{{ human(eligIntlReasons) }}</p>
              <p><span class="k">风险点</span>{{ human(data.eligibility?.international?.risks || data.eligibility?.international?.warnings, EMPTY.none) }}</p>
              <p><span class="k">最近判定</span>{{ humanDateTime(data.eligibility?.international?.created_at || data.eligibility?.international?.assessed_at, EMPTY.judge) }}</p>
            </div>
            <div class="elig-card">
              <div class="elig-h"><strong>华侨生</strong><el-tag size="small" :type="eligHq.type">{{ eligHq.label }}</el-tag></div>
              <p><span class="k">关键依据</span>{{ human(eligHqReasons) }}</p>
              <p><span class="k">风险点</span>{{ human(data.eligibility?.huaqiao?.risks || data.eligibility?.huaqiao?.warnings, EMPTY.none) }}</p>
              <p><span class="k">最近判定</span>{{ humanDateTime(data.eligibility?.huaqiao?.created_at || data.eligibility?.huaqiao?.assessed_at, EMPTY.judge) }}</p>
            </div>
          </div>
        </section>

        <section class="gq-panel block">
          <h3>个人时间线</h3>
          <el-table v-if="timelineRows.length" :data="timelineRows" size="small" stripe>
            <el-table-column label="事项" min-width="160"><template #default="{ row }">{{ human(row.title || row.name) }}</template></el-table-column>
            <el-table-column label="类型" width="100"><template #default="{ row }">{{ human(row.type || row.category, '—') }}</template></el-table-column>
            <el-table-column label="目标日期" width="120"><template #default="{ row }">{{ humanDate(row.deadline || row.target_date) }}</template></el-table-column>
            <el-table-column label="剩余天数" width="110"><template #default="{ row }">{{ daysRemainingLabel(row.deadline || row.target_date) }}</template></el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }"><el-tag size="small" :type="timelineTag(row)">{{ timelineStatusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="优先级" width="90"><template #default="{ row }">{{ human(row.priority, '—') }}</template></el-table-column>
            <el-table-column label="来源" width="100"><template #default="{ row }">{{ human(row.source, '—') }}</template></el-table-column>
          </el-table>
          <p v-else class="gq-muted empty">{{ EMPTY.none }}</p>
        </section>
      </div>

      <aside class="gq-panel ai-panel">
        <h2 style="margin-top:0">AI 专家工作台</h2>
        <p class="gq-muted">输出默认 DRAFT · 人工审核后才可发布 · 禁止自动发送</p>
        <div class="ai-ctx">
          <h4 class="sub-h">上下文摘要</h4>
          <ul>
            <li><b>学生</b>：{{ displayName }}（#{{ data.student_id }}）</li>
            <li><b>目标</b>：{{ human(goalHint, EMPTY.noTargets) }}</li>
            <li><b>资格</b>：国际生 {{ eligIntl.label }} · 华侨生 {{ eligHq.label }}</li>
            <li><b>CSCA</b>：{{ cscaStatusLabel(csca.csca_status, csca.csca_status_label) }}</li>
            <li><b>时间线风险</b>：{{ timelineRiskHint }}</li>
            <li><b>最近跟进</b>：{{ human(latestFollowHint, EMPTY.none) }}</li>
            <li><b>下一步</b>：{{ human(crm.next_action || ops.next_action) }}</li>
          </ul>
        </div>
        <div class="row-edit" style="margin-top:12px">
          <el-button v-for="(label, kind) in kinds" :key="kind" size="small" :loading="generating === kind" @click="generate(kind)">生成·{{ label }}</el-button>
        </div>
        <div class="gq-muted" style="font-size:12px;margin-top:4px">AI Generate → DRAFT → REVIEWED → APPROVED → PUBLISHED</div>
        <div v-if="activeDraft" style="margin-top:12px">
          <el-tag :type="statusType(activeDraft.status)" effect="dark">{{ activeDraft.status }}</el-tag>
          <span class="gq-muted" style="margin-left:8px">{{ human(activeDraft.report_kind) }} · {{ human(activeDraft.ai_provider, '—') }} · v{{ activeDraft.version_count || 0 }}</span>
          <el-input v-model="editContent" type="textarea" :rows="12" style="margin-top:8px" :disabled="activeDraft.status === 'PUBLISHED'" />
          <div class="row-edit" style="margin-top:8px">
            <el-button v-if="canEdit" size="small" @click="saveEdit">编辑 / 提交审核</el-button>
            <el-button v-if="canApprove" size="small" type="success" @click="approve">批准</el-button>
            <el-button v-if="canPublish" size="small" type="danger" @click="publish">发布</el-button>
            <el-tag v-if="activeDraft.status === 'PUBLISHED'" type="success">已发布 · 只读</el-tag>
          </div>
          <p v-if="msg" class="gq-muted" style="margin-top:8px">{{ msg }}</p>
        </div>
      </aside>
    </div>

    <section class="gq-panel" style="margin-top:16px">
      <h3>跟进记录</h3>
      <div class="row-edit mb">
        <el-input v-model="followContent" type="textarea" :rows="2" placeholder="人工跟进内容" style="flex:1;min-width:240px" />
        <el-input v-model="followNext" placeholder="下一步" style="width:200px" />
        <el-button type="primary" @click="saveFollowUp">记跟进</el-button>
        <el-button @click="loadAiDrafts">AI建议(草稿)</el-button>
      </div>
      <el-alert v-if="aiDrafts.length" type="info" :closable="false" title="AI 建议仅草稿，不会自动发送" style="margin-bottom:8px" />
      <el-table v-if="aiDrafts.length" :data="aiDrafts" size="small" style="margin-bottom:8px">
        <el-table-column prop="action" label="动作" width="140" />
        <el-table-column prop="content" label="草稿内容" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }"><el-button link type="primary" @click="acceptAiDraft(row)">确认为跟进</el-button></template>
        </el-table-column>
      </el-table>
      <el-table :data="followRows" size="small" stripe>
        <el-table-column label="时间" width="170"><template #default="{ row }">{{ humanDateTime(row.created_at) }}</template></el-table-column>
        <el-table-column label="负责人" width="120"><template #default="{ row }">{{ human(row.operator_label || row.operator_name, '—') }}</template></el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }"><el-tag size="small" :type="followSourceTag(row.source)">{{ followSourceLabel(row.source) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="内容摘要" min-width="200"><template #default="{ row }">{{ human(row.summary || row.content) }}</template></el-table-column>
        <el-table-column label="下一步" width="160"><template #default="{ row }">{{ human(row.next_action, '—') }}</template></el-table-column>
        <el-table-column label="下次跟进" width="160"><template #default="{ row }">{{ humanDateTime(row.next_follow_up_at, '—') }}</template></el-table-column>
      </el-table>
      <p v-if="!followRows.length" class="gq-muted empty">{{ EMPTY.none }}</p>
    </section>

    <section class="gq-panel" style="margin-top:16px">
      <h3>专家规划历史</h3>
      <el-table :data="history" size="small" @row-click="selectDraft" style="cursor:pointer" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="类型" width="160"><template #default="{ row }">{{ human(row.report_kind) }}</template></el-table-column>
        <el-table-column label="状态" width="140">
          <template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="模型" min-width="160"><template #default="{ row }">{{ human(row.ai_provider, '—') }}/{{ human(row.ai_model, '—') }}</template></el-table-column>
        <el-table-column label="创建" width="170"><template #default="{ row }">{{ humanDateTime(row.created_at) }}</template></el-table-column>
        <el-table-column label="更新" width="170"><template #default="{ row }">{{ humanDateTime(row.updated_at) }}</template></el-table-column>
        <el-table-column prop="version_count" label="版本" width="80" />
      </el-table>
    </section>

    <details v-if="isDev" class="gq-panel dev-debug">
      <summary>Developer Debug（生产默认隐藏）</summary>
      <p class="gq-muted">仅开发构建可见。不含 cipher / token / password。</p>
      <pre class="safe-pre">{{ debugSafe }}</pre>
    </details>
  </div>
  <div v-else class="gq-muted" style="padding:24px">加载中…</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import {
  EMPTY,
  human,
  humanBool,
  humanDate,
  humanDateTime,
  pick,
  cscaStatusLabel,
  riskLabel,
  riskTagType,
  eligibilityBadge,
  followSourceLabel,
  followSourceTag,
  timelineStatusLabel,
  daysRemaining,
  daysRemainingLabel,
  targetPriorityLabel,
} from '../utils/opsDisplay'

const props = defineProps({ studentId: { type: [String, Number], required: true } })
const isDev = import.meta.env.DEV

const data = ref(null)
const kinds = ref({})
const drafts = ref([])
const activeDraft = ref(null)
const editContent = ref('')
const generating = ref('')
const msg = ref('')
const staff = ref([])
const assignTo = ref(0)
const stageEdit = ref('')
const stageLabels = ref({})
const followContent = ref('')
const followNext = ref('')
const aiDrafts = ref([])
const cscaSaving = ref(false)
const cscaForm = ref({
  csca_status: 'NOT_PLANNED',
  csca_registration_deadline: '',
  csca_exam_date: '',
  csca_result_date: '',
  csca_score: '',
  csca_level: '',
  csca_notes: '',
})
const cscaStatuses = [
  { value: 'NOT_PLANNED', label: '未计划' },
  { value: 'PLANNED', label: '计划参加' },
  { value: 'REGISTERED', label: '已报名' },
  { value: 'TAKEN', label: '已考试' },
  { value: 'RESULT_AVAILABLE', label: '已出分' },
]

const history = computed(() => drafts.value || [])
const canEdit = computed(() => ['DRAFT', 'REVIEWED'].includes(activeDraft.value?.status))
const canApprove = computed(() => ['DRAFT', 'REVIEWED'].includes(activeDraft.value?.status))
const canPublish = computed(() => activeDraft.value?.status === 'APPROVED')

const sections = computed(() => data.value?.sections || {})
const basic = computed(() => sections.value.basic_info || {})
const identity = computed(() => sections.value.identity || {})
const education = computed(() => sections.value.education || {})
const goals = computed(() => sections.value.goals || {})
const owner = computed(() => data.value?.owner || {})
const meta = computed(() => data.value?.meta || {})
const crm = computed(() => data.value?.crm || {})
const ops = computed(() => data.value?.ops_header || {})
const csca = computed(() => data.value?.csca_card || sections.value.csca || {})

const displayName = computed(() => {
  const raw = pick(ops.value.display_name, crm.value.display_name, meta.value.display_name, basic.value.chinese_name, basic.value.english_name)
  if (!raw || String(raw).includes('@')) return EMPTY.name
  return human(raw, EMPTY.name)
})
const planLabel = computed(() => {
  const code = owner.value.plan_code
  if (!code) return EMPTY.pending
  if (owner.value.is_paid && !String(code).toLowerCase().includes('trial')) return `${code}（付费）`
  return String(code)
})
const trialLabel = computed(() => {
  const t = owner.value.trial || {}
  if (t.trial_active) return '试用中'
  if (t.trial_expired) return '试用已结束'
  if (owner.value.is_paid) return '非试用 / 付费'
  return EMPTY.pending
})
const identityRoute = computed(() => {
  const intl = identity.value.international?.status
  const hq = identity.value.huaqiao?.status
  if (intl || hq) return [intl && `国际生:${intl}`, hq && `华侨生:${hq}`].filter(Boolean).join(' · ')
  return null
})
const identityRiskHint = computed(() => {
  const bits = []
  if (identity.value.had_chinese_nationality && identity.value.has_foreign_nationality) bits.push('曾有中国国籍且现有外国国籍，需核验材料')
  if (identity.value.has_chinese_hukou && !identity.value.hukou_cancelled) bits.push('仍有中国户籍')
  return bits.join('；') || null
})
const currentSchool = computed(() => education.value.current_school || {})
const educationHistory = computed(() => (Array.isArray(education.value.history) ? education.value.history : []))
const educationCurriculum = computed(() => {
  const curricula = sections.value.courses?.curricula || []
  if (Array.isArray(curricula) && curricula.length) return curricula.map((c) => c.name || c).filter(Boolean).join('、')
  return null
})
const mainSubjects = computed(() => {
  const items = sections.value.courses?.items || []
  if (!Array.isArray(items) || !items.length) return null
  return items.map((i) => i.subject || i.name).filter(Boolean).slice(0, 8).join('、')
})
const gradesSummary = computed(() => {
  const grades = sections.value.courses?.grades || []
  if (!Array.isArray(grades) || !grades.length) return education.value.education_notes || null
  return grades.slice(0, 6).map((g) => `${g.subject || ''}:${g.grade || g.score || ''}`.replace(/^:/, '')).filter(Boolean).join('；')
})
const languageRows = computed(() => (Array.isArray(sections.value.language_exams) ? sections.value.language_exams : []))
const targetRows = computed(() => (Array.isArray(goals.value.targets) ? goals.value.targets : []))
const goalHint = computed(() => {
  if (!targetRows.value.length) return goals.value.goals_notes || null
  return targetRows.value.slice(0, 3).map((t) => `${t.university_name || t.university || ''} ${t.major || ''}`.trim()).filter(Boolean).join('；')
})
const timelineRows = computed(() => (Array.isArray(data.value?.timeline) ? data.value.timeline : []))
const followRows = computed(() => (Array.isArray(data.value?.follow_ups) ? data.value.follow_ups : []))
const eligIntl = computed(() => eligibilityBadge(data.value?.eligibility?.international?.conclusion, data.value?.eligibility?.international?.qualified))
const eligHq = computed(() => eligibilityBadge(data.value?.eligibility?.huaqiao?.conclusion, data.value?.eligibility?.huaqiao?.qualified))
const eligIntlReasons = computed(() => {
  const r = data.value?.eligibility?.international?.reasons
  return Array.isArray(r) ? r.filter(Boolean).join('；') : r
})
const eligHqReasons = computed(() => {
  const r = data.value?.eligibility?.huaqiao?.reasons
  return Array.isArray(r) ? r.filter(Boolean).join('；') : r
})
const timelineRiskHint = computed(() => {
  const rows = timelineRows.value
  if (!rows.length) return EMPTY.none
  const overdue = rows.filter((r) => {
    const n = daysRemaining(r.deadline || r.target_date)
    return n != null && n < 0 && !/DONE|COMPLETED/i.test(String(r.status || ''))
  })
  const soon = rows.filter((r) => {
    const n = daysRemaining(r.deadline || r.target_date)
    return n != null && n >= 0 && n <= 7 && !/DONE|COMPLETED/i.test(String(r.status || ''))
  })
  if (overdue.length) return `${overdue.length} 项逾期`
  if (soon.length) return `${soon.length} 项 7 日内到期`
  return '暂无紧急项'
})
const latestFollowHint = computed(() => {
  const row = followRows.value[0]
  if (!row) return null
  return `${humanDateTime(row.created_at, '')} ${row.summary || row.content || ''}`.trim()
})
const debugSafe = computed(() => {
  if (!isDev || !data.value) return ''
  return JSON.stringify({
    student_id: data.value.student_id,
    meta: data.value.meta,
    owner: { id: owner.value.id, email: owner.value.email, plan_code: owner.value.plan_code },
    crm: { assignee_user_id: crm.value.assignee_user_id, crm_stage: crm.value.crm_stage, risk_level: crm.value.risk_level },
    section_keys: Object.keys(sections.value),
    timeline_count: timelineRows.value.length,
    follow_up_count: followRows.value.length,
  }, null, 2)
})

function timelineTag(row) {
  const st = String(row.status || '').toUpperCase()
  const n = daysRemaining(row.deadline || row.target_date)
  if (st === 'DONE' || st === 'COMPLETED') return 'success'
  if (st === 'OVERDUE' || (n != null && n < 0)) return 'danger'
  if (n != null && n <= 7) return 'warning'
  return 'info'
}
function statusType(s) {
  if (s === 'PUBLISHED') return 'success'
  if (s === 'APPROVED') return 'warning'
  if (s === 'REVIEWED') return 'info'
  return ''
}

function syncCscaForm() {
  const c = data.value?.sections?.csca || data.value?.csca_card || {}
  cscaForm.value = {
    csca_status: c.csca_status || 'NOT_PLANNED',
    csca_registration_deadline: c.csca_registration_deadline_raw || '',
    csca_exam_date: c.csca_exam_date_raw || '',
    csca_result_date: c.csca_result_date_raw || '',
    csca_score: c.csca_score || '',
    csca_level: c.csca_level || '',
    csca_notes: c.csca_notes || '',
  }
  for (const k of ['csca_registration_deadline', 'csca_exam_date', 'csca_result_date']) {
    if (cscaForm.value[k] === '待官方公布') cscaForm.value[k] = ''
  }
}

async function saveCsca() {
  cscaSaving.value = true
  try {
    const payload = {}
    for (const [k, v] of Object.entries(cscaForm.value)) {
      if (v !== '' && v != null) payload[k] = v
    }
    const res = await api.patchStudentCsca(props.studentId, payload)
    ElMessage.success('CSCA 已协助更新（已记审计）')
    data.value = { ...data.value, sections: { ...(data.value.sections || {}), csca: res.csca }, csca_card: res.csca_card }
    syncCscaForm()
  } catch (e) {
    ElMessage.error(e.message || 'CSCA 更新失败')
  } finally {
    cscaSaving.value = false
  }
}

async function doAssign() {
  await api.assignStudent(props.studentId, assignTo.value === 0 ? null : assignTo.value)
  ElMessage.success('负责人已更新')
  await load()
}
async function saveStage() {
  if (!stageEdit.value) return
  await api.patchStudentCrm(props.studentId, { crm_stage: stageEdit.value })
  ElMessage.success('阶段已更新')
  await load()
}
async function saveFollowUp() {
  if (!followContent.value.trim()) return
  await api.createFollowUp(props.studentId, { content: followContent.value, next_action: followNext.value || null, source: 'HUMAN' })
  followContent.value = ''
  followNext.value = ''
  ElMessage.success('跟进已保存')
  await load()
}
async function loadAiDrafts() {
  aiDrafts.value = (await api.aiFollowUpDrafts(props.studentId)).drafts || []
}
async function acceptAiDraft(row) {
  await api.createFollowUp(props.studentId, { content: row.content, summary: row.action, source: 'AI_ASSISTED', type: 'AI_SUGGESTION' })
  ElMessage.success('已保存为 AI 辅助跟进（未自动发送）')
  aiDrafts.value = []
  await load()
}

async function load() {
  data.value = await api.student360(props.studentId)
  kinds.value = data.value.report_kinds || {}
  stageEdit.value = data.value.crm?.crm_stage || ''
  stageLabels.value = data.value.crm_stage_labels || {
    UNASSIGNED: '未分配', NEW: '新学生', CONTACTED: '已联系', PLANNING: '规划中',
    WAITING_STUDENT: '等待学生', WAITING_DOCUMENTS: '等待材料', APPLICATION: '申请中',
    FOLLOW_UP: '持续跟进', COMPLETED: '已完成', PAUSED: '暂停',
  }
  assignTo.value = data.value.crm?.assignee_user_id || 0
  syncCscaForm()
  await refreshDrafts()
  try { staff.value = (await api.staff()).staff || [] } catch { staff.value = [] }
}

async function refreshDrafts() {
  const d = await api.aiDrafts(props.studentId)
  drafts.value = d.drafts || []
  if (!Object.keys(kinds.value || {}).length) kinds.value = d.report_kinds || {}
}

async function generate(kind) {
  generating.value = kind
  msg.value = ''
  try {
    const res = await api.aiGenerate(props.studentId, kind, false)
    activeDraft.value = res.draft
    editContent.value = res.draft.raw_draft || res.draft.content || ''
    ElMessage.success('已生成并持久化 DRAFT（未发布）')
    await refreshDrafts()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    generating.value = ''
  }
}
function selectDraft(row) {
  activeDraft.value = row
  editContent.value = row.raw_draft || row.final_report || ''
  msg.value = row.status === 'PUBLISHED' ? 'PUBLISHED 只读；如需修改请重新「生成」新版本' : ''
}
async function saveEdit() {
  if (!canEdit.value) return
  const res = await api.aiEdit(props.studentId, activeDraft.value.id, editContent.value, true)
  activeDraft.value = res.draft
  msg.value = `已保存 → ${res.draft.status}`
  await refreshDrafts()
}
async function approve() {
  if (!canApprove.value) return
  const res = await api.aiApprove(props.studentId, activeDraft.value.id)
  activeDraft.value = res.draft
  msg.value = '已批准 APPROVED（学生仍不可见）'
  await refreshDrafts()
}
async function publish() {
  if (!canPublish.value) return
  try {
    const res = await api.aiPublish(props.studentId, activeDraft.value.id)
    activeDraft.value = res.draft
    msg.value = '已发布 PUBLISHED（学生端可读）'
    ElMessage.success('已发布')
    await refreshDrafts()
  } catch (e) {
    msg.value = e.message
    ElMessage.warning(e.message)
  }
}

onMounted(load)
watch(() => props.studentId, load)
</script>

<style scoped>
.block { margin-bottom: 12px; }
.mb { margin-bottom: 12px; }
.sub-h { margin: 8px 0; font-size: 13px; color: #475569; }
.empty { margin: 8px 0; font-size: 13px; }
.ops-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin: 8px 0 12px;
}
.ops-cell {
  background: #fff;
  border: 1px solid #d5dde8;
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 58px;
}
.ops-cell.hi { background: #eff6ff; border-color: #bfdbfe; }
.ops-cell .k { font-size: 12px; color: #64748b; }
.ops-cell .v { font-size: 14px; font-weight: 600; color: #142033; word-break: break-word; }
.ops-actions, .row-edit { display: flex; flex-wrap: wrap; gap: 8px; }
.elig-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.elig-card { border: 1px solid #d5dde8; border-radius: 10px; padding: 12px; background: #fff; }
.elig-h { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.elig-card p { margin: 4px 0; font-size: 13px; }
.elig-card .k { display: inline-block; min-width: 72px; margin-right: 6px; color: #64748b; }
.ai-panel { position: sticky; top: 12px; align-self: start; max-height: calc(100vh - 40px); overflow: auto; }
.ai-ctx { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; margin-top: 8px; }
.ai-ctx ul { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.6; }
.dev-debug { margin-top: 16px; opacity: 0.85; }
.dev-debug summary { cursor: pointer; font-weight: 600; }
.safe-pre {
  white-space: pre-wrap;
  font-size: 12px;
  background: #f1f5f9;
  color: #334155;
  padding: 10px;
  border-radius: 8px;
  max-height: 240px;
  overflow: auto;
}
@media (max-width: 1100px) {
  .ops-grid { grid-template-columns: 1fr 1fr; }
  .elig-grid { grid-template-columns: 1fr; }
}
</style>
