<template>
  <div class="smp">
    <div class="smp-head">
      <div>
        <p class="smp-eyebrow">国侨升学 · Student Master Profile</p>
        <h2>学生档案 <span class="smp-slot">{{ slots.student_profile_used || 0 }} / {{ slots.student_profile_limit || 0 }}</span></h2>
        <p class="muted">档案是升学规划数据中心。每页独立保存，判定结果需确认后才写入身份状态。</p>
      </div>
      <div class="smp-head-actions">
        <el-button @click="loadList">刷新</el-button>
        <el-button type="primary" :disabled="!canCreate" @click="createStudent">创建学生</el-button>
        <span v-if="canCreate" class="muted">剩余 {{ slots.student_profile_remaining || 0 }} 个名额</span>
      </div>
    </div>

    <el-alert
      v-if="!canCreate"
      class="smp-limit-alert"
      type="warning"
      :closable="false"
      :title="limitHint"
    >
      <template #default>
        <p>{{ limitHint }}</p>
        <el-button type="primary" link @click="emit('goto-member')">升级套餐</el-button>
      </template>
    </el-alert>

    <div class="smp-student-bar">
      <el-select v-model="studentId" placeholder="选择学生" filterable style="min-width:240px" @change="openStudent">
        <el-option v-for="s in students" :key="s.id" :label="`${s.display_name}（完整度 ${s.completeness?.percent || 0}%）`" :value="s.id" />
      </el-select>
      <el-tag v-if="profile" type="info">{{ wizardMode ? '建档向导' : '档案管理' }}</el-tag>
      <el-tag v-if="slots.student_profile_over_quota" type="warning">超额 {{ slots.student_profile_over_quota }}（已有档案可继续查看编辑）</el-tag>
    </div>

    <template v-if="profile">
      <el-steps v-if="wizardMode" :active="wizardIndex" finish-status="success" class="smp-steps" align-center>
        <el-step v-for="sec in wizardSections" :key="sec.key" :title="sec.label" @click="section = sec.key" />
      </el-steps>
      <div class="smp-layout">
        <aside class="smp-nav">
          <button v-for="sec in sections" :key="sec.key" :class="{active: section===sec.key}" type="button" @click="goSection(sec.key)">{{ sec.label }}</button>
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
            <h3>档案总览 · Dashboard</h3>
            <div class="smp-complete">
              <el-progress type="circle" :percentage="completeness.percent || 0" />
              <div>
                <p>档案完整度 {{ completeness.percent || 0 }}%</p>
                <p>申请准备度 {{ readinessScore }}%</p>
                <p class="muted">由档案事实透明汇总，非录取概率。</p>
              </div>
            </div>
            <div class="smp-dash-grid">
              <div class="smp-dash-block">
                <h4>核心信息</h4>
                <p>{{ portrait?.basic?.chinese_name || profile.basic_info.chinese_name }} {{ portrait?.basic?.english_name || '' }}</p>
                <p class="muted">{{ portrait?.basic?.current_school || '—' }} · {{ portrait?.basic?.current_grade || '—' }} · 入学 {{ portrait?.basic?.intended_entry_year || '—' }}</p>
                <el-button link type="primary" @click="section='portrait'">查看学生画像</el-button>
              </div>
              <div class="smp-dash-block">
                <h4>身份状态</h4>
                <p>国际生：{{ statusLabel[portrait?.identity?.international?.status || profile.identity.international.status] }}</p>
                <p>华侨生：{{ statusLabel[portrait?.identity?.huaqiao?.status || profile.identity.huaqiao.status] }}</p>
                <el-button link type="primary" @click="section='identity'">身份与国籍</el-button>
              </div>
              <div class="smp-dash-block">
                <h4>学术 / 语言</h4>
                <p>{{ (portrait?.academic?.curricula || profile.courses.curricula || []).join(' / ') || '—' }}</p>
                <p class="muted">{{ portrait?.language?.summary || '语言成绩缺失' }}</p>
                <el-button link type="primary" @click="section='courses'">课程与成绩</el-button>
              </div>
              <div class="smp-dash-block">
                <h4>目标结构</h4>
                <p>冲刺 {{ targetCounts.reach || 0 }} · 主申 {{ targetCounts.target || 0 }} · 稳妥 {{ targetCounts.match || 0 }} · 保底 {{ targetCounts.safety || 0 }}</p>
                <el-button link type="primary" @click="section='goals'">升学目标</el-button>
              </div>
            </div>
            <div class="smp-dash-grid">
              <div class="smp-dash-block">
                <h4>风险提示</h4>
                <ul><li v-for="r in (portrait?.risk_flags || [])" :key="r">{{ r }}</li></ul>
                <p v-if="!(portrait?.risk_flags||[]).length" class="muted">暂无结构风险提示</p>
              </div>
              <div class="smp-dash-block">
                <h4>下一步行动</h4>
                <ul>
                  <li v-for="a in (portrait?.next_actions || [])" :key="a.code">
                    <el-button link type="primary" @click="runAction(a)">{{ a.label }}</el-button>
                  </li>
                </ul>
              </div>
              <div class="smp-dash-block">
                <h4>未来 30 天</h4>
                <p>共 {{ timelineSummary.next_30_count || 0 }} 项</p>
                <ul><li v-for="it in (timelineSummary.next_30 || [])" :key="it.id">{{ it.deadline || '日期待确认' }} · {{ it.title }}</li></ul>
                <el-button link type="primary" @click="goSection('my_timeline')">进入升学时间轴</el-button>
              </div>
              <div class="smp-dash-block">
                <h4>未来 90 天 / 逾期</h4>
                <p>未来90天 {{ timelineSummary.next_90_count || 0 }} · 逾期 {{ timelineSummary.overdue_count || 0 }}</p>
                <ul><li v-for="it in (timelineSummary.next_90 || [])" :key="it.id">{{ it.deadline || '日期待确认' }} · {{ it.title }}</li></ul>
              </div>
            </div>
            <el-form-item class="mt" label="备注"><el-input v-model="profile.summary.summary_notes" type="textarea" :rows="3" /></el-form-item>
            <div class="smp-save"><el-button type="primary" :loading="saving" @click="saveSection('summary')">{{ saveLabel }}</el-button></div>
          </section>

          <section v-show="section==='portrait'" class="smp-card">
            <div class="smp-save" style="margin-top:0">
              <h3 style="margin:0;flex:1">学生画像</h3>
              <el-button @click="refreshPortrait">刷新画像</el-button>
            </div>
            <p class="muted">由 Student Master Profile 自动生成（v{{ portrait?.portrait_version || '—' }} · {{ portrait?.portrait_generated_at || '—' }}），不覆盖资格判定引擎结果。</p>
            <h4>基础画像</h4>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="姓名">{{ portrait?.basic?.chinese_name }} {{ portrait?.basic?.english_name }}</el-descriptions-item>
              <el-descriptions-item label="年龄">{{ portrait?.basic?.age ?? '—' }}</el-descriptions-item>
              <el-descriptions-item label="当前国家">{{ portrait?.basic?.current_country || '—' }}</el-descriptions-item>
              <el-descriptions-item label="当前学校">{{ portrait?.basic?.current_school || '—' }}</el-descriptions-item>
              <el-descriptions-item label="年级">{{ portrait?.basic?.current_grade || '—' }}</el-descriptions-item>
              <el-descriptions-item label="课程体系">{{ (portrait?.basic?.curricula||[]).join(' / ') || '—' }}</el-descriptions-item>
              <el-descriptions-item label="预计入学">{{ portrait?.basic?.intended_entry_year || '—' }}</el-descriptions-item>
            </el-descriptions>
            <h4>学术画像</h4>
            <p>优势：{{ (portrait?.academic?.academic_strengths||[]).join('；') || '暂无' }}</p>
            <p>关注：{{ (portrait?.academic?.academic_weaknesses||[]).join('；') || '暂无' }}</p>
            <p class="muted">{{ portrait?.academic?.grade_trend }} · {{ portrait?.academic?.curriculum_rigor }}</p>
            <p class="muted">缺失：{{ (portrait?.academic?.missing_academic_data||[]).join('、') || '无' }}</p>
            <h4>语言画像</h4>
            <ul>
              <li v-for="ex in (portrait?.language?.exams||[])" :key="ex.exam_type + ex.exam_date">{{ ex.exam_type }} {{ ex.overall_score || '—' }} · {{ ex.status }}</li>
            </ul>
            <h4>身份画像</h4>
            <div class="smp-verdicts">
              <el-card>
                <h4>International Student Eligibility</h4>
                <p>{{ statusLabel[portrait?.identity?.international?.status] || '尚未判定' }}</p>
                <p v-if="portrait?.identity?.international?.prompt" class="muted">{{ portrait.identity.international.prompt }}</p>
                <el-button type="primary" @click="goJudge('international')">前往国际生判定</el-button>
              </el-card>
              <el-card>
                <h4>Huaqiao Eligibility</h4>
                <p>{{ statusLabel[portrait?.identity?.huaqiao?.status] || '尚未判定' }}</p>
                <p v-if="portrait?.identity?.huaqiao?.prompt" class="muted">{{ portrait.identity.huaqiao.prompt }}</p>
                <el-button type="primary" @click="goJudge('huaqiao')">前往华侨生判定</el-button>
              </el-card>
            </div>
            <h4>目标画像</h4>
            <p>冲刺 {{ targetCounts.reach||0 }} · 主申 {{ targetCounts.target||0 }} · 稳妥 {{ targetCounts.match||0 }} · 保底 {{ targetCounts.safety||0 }}</p>
            <p class="muted">结构提示：{{ (portrait?.targets?.structure_flags||[]).join('、') || '无' }}</p>
            <h4>申请准备度 {{ readinessScore }}%</h4>
            <ul>
              <li v-for="(v,k) in (portrait?.application_readiness?.components||{})" :key="k">{{ k }}：{{ v }}%</li>
            </ul>
            <p class="muted">缺失项：{{ (portrait?.application_readiness?.missing||[]).join('、') || '无' }}</p>
            <h4>风险与下一步</h4>
            <ul><li v-for="r in (portrait?.risk_flags||[])" :key="'r'+r">{{ r }}</li></ul>
            <ul>
              <li v-for="a in (portrait?.next_actions||[])" :key="a.code"><el-button link type="primary" @click="runAction(a)">{{ a.label }}</el-button></li>
            </ul>
            <p>未来30天 {{ timelineSummary.next_30_count||0 }} 项 · 未来90天 {{ timelineSummary.next_90_count||0 }} 项 · 逾期 {{ timelineSummary.overdue_count||0 }} 项
              <el-button link type="primary" @click="goSection('my_timeline')">打开时间轴</el-button>
            </p>
          </section>

          <section v-show="section==='my_timeline'" class="smp-card">
            <div class="smp-save" style="margin-top:0">
              <h3 style="margin:0;flex:1">我的升学时间轴</h3>
              <el-button type="primary" :loading="timelineBusy" @click="regenerateTimeline">重新生成</el-button>
              <el-button @click="showManual=true">+ 自定义事项</el-button>
            </div>
            <p class="muted">公共招生时间线只读匹配；完成状态/备注/手工事项保存在学生个人时间轴。</p>
            <div v-for="group in timelineGroupsUI" :key="group.key" class="smp-priority">
              <h4>{{ group.label }}（{{ (timelineGroups[group.key]||[]).length }}）</h4>
              <article v-for="it in (timelineGroups[group.key]||[])" :key="it.id" class="smp-item">
                <header>
                  <strong>{{ it.title }}</strong>
                  <el-tag size="small">{{ timelineStatusLabel[it.status] || it.status }}</el-tag>
                </header>
                <p>{{ it.deadline || it.start_date || '日期待确认' }} · {{ it.university_name || '—' }} · {{ it.application_route || '路线待确认' }}</p>
                <p v-if="it.has_precise_deadline && it.days_until_deadline!=null" class="muted">距离 Deadline {{ it.days_until_deadline }} 天</p>
                <p v-else class="muted">无精确截止日期，不显示倒计时</p>
                <p v-if="it.needs_confirmation" class="muted">需确认：字段匹配不完全，请人工核实官方简章</p>
                <p v-if="it.student_note">备注：{{ it.student_note }}</p>
                <div class="smp-save">
                  <el-button size="small" @click="patchItem(it,'IN_PROGRESS')">开始</el-button>
                  <el-button size="small" type="success" @click="patchItem(it,'COMPLETED')">完成</el-button>
                  <el-button size="small" @click="patchItem(it,'NOT_STARTED')">恢复</el-button>
                  <el-button size="small" @click="patchItem(it,'NOT_APPLICABLE')">标记不适用</el-button>
                  <el-button size="small" @click="editNote(it)">添加备注</el-button>
                </div>
              </article>
              <p v-if="!(timelineGroups[group.key]||[]).length" class="muted">暂无</p>
            </div>
            <el-dialog v-model="showManual" title="添加自定义事项" width="480px">
              <el-form label-width="90px">
                <el-form-item label="标题"><el-input v-model="manualForm.title" /></el-form-item>
                <el-form-item label="截止日期"><el-input v-model="manualForm.deadline" placeholder="YYYY-MM-DD" /></el-form-item>
                <el-form-item label="学校"><el-input v-model="manualForm.university_name" /></el-form-item>
                <el-form-item label="备注"><el-input v-model="manualForm.student_note" type="textarea" /></el-form-item>
              </el-form>
              <template #footer>
                <el-button @click="showManual=false">取消</el-button>
                <el-button type="primary" @click="createManual">保存</el-button>
              </template>
            </el-dialog>
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
import { CURRICULUMS, GRADE_TYPES, LANGUAGE_EXAMS, OTHER_EXAM_TYPES, PRIORITY_LEVELS, SCHOOL_TYPES, SECTIONS, STATUS_LABEL, TIMELINE_STATUS_LABEL, WIZARD_SECTIONS, emptyCourse, emptyGrade, emptyLang, emptyOther, emptySchool, emptyTarget } from './studentProfileLib'

const emit = defineEmits(['goto-judge', 'goto-member'])

const sections = SECTIONS
const wizardSections = WIZARD_SECTIONS
const schoolTypes = SCHOOL_TYPES
const curriculums = CURRICULUMS
const gradeTypes = GRADE_TYPES
const languageExams = LANGUAGE_EXAMS
const otherExams = OTHER_EXAM_TYPES
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
const studentId = ref(null)
const profile = ref(null)
const portrait = ref(null)
const dashboard = ref(null)
const slots = ref({
  student_profile_limit: 1,
  student_profile_used: 0,
  student_profile_remaining: 1,
  student_profile_over_quota: 0,
  can_create_student: true,
})
const section = ref('summary')
const saving = ref(false)
const completeness = ref({ percent: 0, missing: [] })
const universityOptions = ref([])
const timeline = ref([])
const timelineGroups = ref({ overdue: [], next_30: [], next_90: [], later: [], completed: [] })
const timelineSummary = ref({ overdue_count: 0, next_30_count: 0, next_90_count: 0, next_30: [], next_90: [] })
const timelineBusy = ref(false)
const showManual = ref(false)
const manualForm = ref({ title: '', deadline: '', university_name: '', student_note: '' })

const wizardMode = computed(() => profile.value && !profile.value.wizard_completed)
const wizardIndex = computed(() => Math.max(0, wizardSections.findIndex(s => s.key === section.value)))
const saveLabel = computed(() => wizardMode.value ? '保存并继续' : '保存修改')
const readinessScore = computed(() => portrait.value?.application_readiness?.score ?? dashboard.value?.application_readiness?.score ?? 0)
const targetCounts = computed(() => portrait.value?.targets?.counts || dashboard.value?.targets || { reach: 0, target: 0, match: 0, safety: 0 })
const canCreate = computed(() => !!slots.value.can_create_student)
const limitHint = computed(() => {
  const lim = slots.value.student_profile_limit || 0
  const used = slots.value.student_profile_used || 0
  return `当前套餐最多可建立 ${lim} 个学生档案，已使用 ${used}/${lim}。如需管理更多学生，请升级套餐。`
})
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
function goSection(key) {
  section.value = key
  if (key === 'portrait') refreshPortrait()
  if (key === 'my_timeline') loadMyTimeline()
  if (key === 'summary' && studentId.value) openStudent(studentId.value)
}

async function loadList() {
  const r = await api.students()
  students.value = r.students || []
  if (r.slots) slots.value = r.slots
  if (!studentId.value && students.value[0]) {
    studentId.value = students.value[0].id
    await openStudent(studentId.value)
  }
}
async function createStudent() {
  if (!canCreate.value) {
    ElMessage.warning(limitHint.value)
    return
  }
  try {
    const r = await api.createStudent({ wizard: true, profile: {} })
    studentId.value = r.id
    applyPayload(r)
    if (r.slots) slots.value = r.slots
    section.value = 'basic_info'
    await loadList()
    ElMessage.success('已创建学生，可开始建档向导')
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  }
}
async function openStudent(id) {
  if (!id) return
  const r = await api.student(id)
  applyPayload(r)
}
function applyPayload(r) {
  profile.value = r.profile
  completeness.value = r.completeness || { percent: 0, missing: [] }
  portrait.value = r.portrait || null
  dashboard.value = r.dashboard || null
  if (r.slots) slots.value = r.slots
  if (r.dashboard?.timeline_summary) timelineSummary.value = r.dashboard.timeline_summary
  else if (r.portrait?.timeline_summary) timelineSummary.value = r.portrait.timeline_summary
}

async function saveSection(key) {
  if (!studentId.value || !profile.value) return
  if (key === 'portrait' || key === 'my_timeline') return
  saving.value = true
  try {
    const r = await api.patchStudentSection(studentId.value, key, profile.value[key])
    applyPayload(r)
    ElMessage.success('已保存')
    if (wizardMode.value) {
      const idx = wizardSections.findIndex(s => s.key === key)
      if (idx >= 0 && idx < wizardSections.length - 1) section.value = wizardSections[idx + 1].key
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
async function refreshPortrait() {
  if (!studentId.value) return
  try {
    const r = await api.studentPortrait(studentId.value)
    portrait.value = r.portrait
    if (r.portrait?.timeline_summary) timelineSummary.value = r.portrait.timeline_summary
  } catch (e) {
    ElMessage.error(e.message || '刷新画像失败')
  }
}
async function loadMyTimeline() {
  if (!studentId.value) return
  try {
    const r = await api.studentTimelineItems(studentId.value)
    timelineGroups.value = r.groups || timelineGroups.value
    timelineSummary.value = r.summary || timelineSummary.value
  } catch (e) {
    ElMessage.error(e.message || '加载时间轴失败')
  }
}
async function regenerateTimeline() {
  if (!studentId.value) return
  timelineBusy.value = true
  try {
    const r = await api.regenerateStudentTimeline(studentId.value)
    timelineGroups.value = r.groups || {}
    timelineSummary.value = r.summary || timelineSummary.value
    if (r.portrait) portrait.value = r.portrait
    ElMessage.success('已重新生成个人时间轴（保留完成状态/备注/手工事项）')
  } catch (e) {
    ElMessage.error(e.message || '生成失败')
  } finally {
    timelineBusy.value = false
  }
}
async function patchItem(it, status) {
  try {
    await api.patchTimelineItem(studentId.value, it.id, { status })
    await loadMyTimeline()
    await refreshPortrait()
  } catch (e) {
    ElMessage.error(e.message || '更新失败')
  }
}
async function editNote(it) {
  const note = window.prompt('学生备注', it.student_note || '')
  if (note === null) return
  try {
    await api.patchTimelineItem(studentId.value, it.id, { student_note: note })
    await loadMyTimeline()
  } catch (e) {
    ElMessage.error(e.message || '备注失败')
  }
}
async function createManual() {
  if (!manualForm.value.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  try {
    await api.createManualTimeline(studentId.value, { ...manualForm.value })
    showManual.value = false
    manualForm.value = { title: '', deadline: '', university_name: '', student_note: '' }
    await loadMyTimeline()
    ElMessage.success('已添加自定义事项')
  } catch (e) {
    ElMessage.error(e.message || '添加失败')
  }
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
