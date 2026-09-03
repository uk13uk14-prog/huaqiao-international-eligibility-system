<template>
  <div class="pro-app">
    <section v-if="!user" class="auth-page">
      <div class="auth-theme-bar">
        <el-switch v-model="darkMode" size="small" inline-prompt :active-text="text.themeDark" :inactive-text="text.themeLight" @change="persistSaasTheme" />
      </div>
      <div class="brand-card">
        <img src="/logo.svg" alt="logo" />
        <p class="eyebrow">{{ text.brandEyebrow }}</p>
        <h1>{{ text.systemName }}</h1>
        <p>{{ text.brandIntro }}</p>
        <div class="brand-points"><span>{{ text.tenantIsolation }}</span><span>{{ text.memberPermission }}</span><span>{{ text.universityLibrary }}</span><span>{{ text.assistant }}</span></div>
      </div>
      <el-card class="auth-card">
        <el-tabs v-model="authTab">
          <el-tab-pane :label="text.login" name="login">
            <el-form data-testid="login-form" label-position="top" @submit.prevent="doLogin">
              <el-form-item :label="text.email">
                <el-input v-model="login.email" data-testid="login-email" autocomplete="username" />
              </el-form-item>
              <el-form-item :label="text.password">
                <el-input v-model="login.password" type="password" show-password data-testid="login-password" autocomplete="current-password" />
              </el-form-item>
              <el-button
                type="primary"
                size="large"
                native-type="submit"
                data-testid="login-submit"
                :loading="loading"
                :disabled="loading"
              >{{ text.loginButton }}</el-button>
            </el-form>
          </el-tab-pane>
          <el-tab-pane :label="text.register" name="register">
            <el-form data-testid="register-form" label-position="top" @submit.prevent="doRegister">
              <el-form-item :label="text.tenantName"><el-input v-model="register.tenant_name" /></el-form-item>
              <el-form-item label="邮箱"><el-input v-model="register.email" autocomplete="username" /></el-form-item>
              <el-form-item label="密码"><el-input v-model="register.password" type="password" show-password autocomplete="new-password" /></el-form-item>
              <el-form-item :label="text.accountType"><el-select v-model="register.tenant_type"><el-option :label="text.personal" value="personal"/><el-option :label="text.agency" value="agency"/></el-select></el-form-item>
              <el-button type="primary" size="large" native-type="submit" data-testid="register-submit" :loading="loading" :disabled="loading">{{ text.registerButton }}</el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
        <el-alert class="mt" type="info" :closable="false" :title="text.demoAccount" />
      </el-card>
    </section>

    <template v-else>
      <header class="topbar">
        <div><h1>{{ text.systemName }}</h1><p>{{ user.email }} · {{ planText }}</p></div>
        <div class="top-actions">
          <div v-if="accessibleStudents.length" class="student-switcher" data-testid="home-student-switcher">
            <span class="student-switcher-label">当前学生</span>
            <strong class="student-switcher-name">{{ activeStudentLabel }}</strong>
            <el-dropdown v-if="hasMultipleStudents" trigger="click" @command="onHomeSwitchStudent">
              <el-button size="small" type="primary" plain>切换</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="s in accessibleStudents"
                    :key="s.id"
                    :command="normalizeStudentId(s.id)"
                    :disabled="normalizeStudentId(s.id) === activeStudentId"
                  >
                    <span :class="{ 'is-active-student': normalizeStudentId(s.id) === activeStudentId }">{{ s.display_name }}</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <el-switch v-model="darkMode" class="theme-switch" size="small" inline-prompt :active-text="text.themeDark" :inactive-text="text.themeLight" @change="persistSaasTheme" /><el-button type="primary" plain @click="openConsultDialog">{{ text.consultPlanning }}</el-button><el-segmented v-model="lang" :options="langOptions" size="small"/><el-tag :type="user.features.paid ? 'success' : 'warning'">{{ user.plan_code }}</el-tag><el-button @click="logout">{{ text.logout }}</el-button>
        </div>
      </header>
      <main class="layout">
        <aside class="sidebar">
          <el-menu :default-active="tab" @select="loadTab">
            <el-menu-item index="internationalDashboard">{{ text.internationalDashboard }}</el-menu-item>
            <el-menu-item index="huaqiaoDashboard">{{ text.huaqiaoDashboard }}</el-menu-item>
            <el-menu-item index="judge">{{ text.dualJudge }}</el-menu-item>
            <el-menu-item index="studentProfile">学生档案</el-menu-item>
            <el-menu-item index="laws">{{ text.laws }}</el-menu-item>
            <el-menu-item index="universities">{{ text.universityLibrary }}</el-menu-item>
            <el-menu-item index="schedules">{{ text.schedules }}</el-menu-item>
            <el-menu-item index="assistant">{{ text.assistant }}</el-menu-item>
            <el-menu-item index="history">{{ text.history }}</el-menu-item>
            <el-menu-item index="member">{{ text.memberCenter }}</el-menu-item>
            <el-menu-item v-if="user.role==='admin'" index="admin">{{ text.admin }}</el-menu-item>
          </el-menu>
        </aside>
        <section class="content">
          <section v-if="tab==='internationalDashboard'" class="page">
            <div class="hero-pro international"><div><p class="eyebrow">{{ text.internationalCore }}</p><h2>{{ text.internationalDashboardTitle }}</h2><p>{{ text.internationalDashboardDesc }}</p></div><el-button type="primary" size="large" @click="startJudge('international')">{{ text.startInternational }}</el-button></div>
            <div class="stats-grid"><el-card><h3>{{ text.identityCheck }}</h3><p>{{ text.identityCheckDesc }}</p></el-card><el-card><h3>{{ text.elitePlanning }}</h3><p>{{ user.features.paid ? text.paidEliteOpen : text.freeEliteLocked }}</p></el-card><el-card><h3>{{ text.internationalAssistant }}</h3><p>{{ text.internationalAssistantDesc }}</p></el-card></div>
            <el-card class="mt"><h3>{{ text.entitlementList }}</h3><div class="feature-list"><span v-for="item in featureRows" :key="item.key">{{ item.label }}：{{ item.value }}</span></div></el-card>
          </section>

          <section v-if="tab==='huaqiaoDashboard'" class="page">
            <div class="hero-pro huaqiao"><div><p class="eyebrow">{{ text.huaqiaoAuxiliary }}</p><h2>{{ text.huaqiaoDashboardTitle }}</h2><p>{{ text.huaqiaoDashboardDesc }}</p></div><el-button type="primary" size="large" @click="startJudge('huaqiao')">{{ text.startHuaqiao }}</el-button></div>
            <div class="stats-grid"><el-card><h3>{{ text.huaqiaoIdentity }}</h3><p>{{ text.huaqiaoIdentityDesc }}</p></el-card><el-card><h3>{{ text.residenceEvidence }}</h3><p>{{ text.residenceEvidenceDesc }}</p></el-card><el-card><h3>{{ text.auxiliaryPosition }}</h3><p>{{ text.auxiliaryPositionDesc }}</p></el-card></div>
            <el-card class="mt"><h3>{{ text.huaqiaoScope }}</h3><p>{{ text.huaqiaoScopeDesc }}</p></el-card>
          </section>

          <section v-if="tab==='judge'" class="page">
            <div class="section-head"><div><h2>{{ judgeType==='international' ? text.internationalJudge : text.huaqiaoJudge }}</h2><p>{{ judgeType==='international' ? text.internationalJudgeDesc : text.huaqiaoJudgeDesc }}</p></div><el-radio-group v-model="judgeType"><el-radio-button label="international">{{ text.internationalJudge }}</el-radio-button><el-radio-button label="huaqiao">{{ text.huaqiaoJudge }}</el-radio-button></el-radio-group></div>
            <el-alert v-if="!user.features.full_elite_university_library" type="warning" :closable="false" title="免费版可完成基础判定，但推荐数量、名校库和报告导出受限。" />
            <el-card class="mt"><el-form label-position="top"><template v-if="judgeType==='international'"><el-alert type="info" :closable="false" title="国际生表格：重点核验外国国籍、中国国籍状态、退籍/国籍状态证明、近四年境外居住记录。"/><div class="form-grid"><el-form-item label="姓名"><el-input v-model="form.name"/></el-form-item><el-form-item label="出生日期"><el-input v-model="form.birth_date" placeholder="YYYY-MM-DD"/></el-form-item><el-form-item label="当前外国国籍"><el-input v-model="form.current_nationality"/></el-form-item><el-form-item label="外国国籍取得日期"><el-input v-model="form.foreign_nationality_acquired_date"/></el-form-item><el-form-item label="永久/长期居留地"><el-input v-model="form.permanent_residence_country"/></el-form-item><el-form-item label="意向专业领域"><el-select v-model="form.intended_field"><el-option v-for="f in fields" :key="f" :label="f" :value="f"/></el-select></el-form-item><el-form-item label="分数/成绩"><el-input-number v-model="form.score" :min="0" :max="750"/></el-form-item><el-form-item label="近4年海外月数"><el-input-number v-model="form.overseas_residence_months_last_4y" :min="0" :max="48"/></el-form-item><el-form-item label="单年最高海外月数"><el-input-number v-model="form.annual_months_overseas" :min="0" :max="12"/></el-form-item></div><div class="switches"><el-switch v-model="form.has_foreign_nationality" active-text="具有外国国籍"/><el-switch v-model="form.has_chinese_nationality" active-text="仍具有中国国籍"/><el-switch v-model="form.has_denationalization_certificate" active-text="已有退籍/国籍状态证明"/><el-switch v-model="form.settled_abroad" active-text="已定居国外"/><el-switch v-model="form.born_abroad" active-text="出生在外国"/><el-switch v-model="form.parent_chinese_citizen" active-text="父母一方中国公民"/><el-switch v-model="form.parent_settled_abroad_at_birth" active-text="出生时父母定居外国"/></div><el-form-item label="退籍证明/国籍状态证明说明"><el-input v-model="form.denationalization_certificate_info" type="textarea" rows="2" placeholder="如：户籍注销证明、退出中国国籍证书、使领馆/公安机关国籍状态说明等。国内相关证明通常建议预留约1年办理周期。"/></el-form-item><div class="report-actions"><el-button type="primary" plain @click="openConsultDialog">{{ text.consultPlanning }}</el-button></div></template><template v-else><el-alert type="success" :closable="false" title="华侨生表格：比国际生更简单，重点核验中国国籍、海外定居、近两年居住和户籍状态。"/><div class="form-grid"><el-form-item label="姓名"><el-input v-model="form.name"/></el-form-item><el-form-item label="出生日期"><el-input v-model="form.birth_date" placeholder="YYYY-MM-DD"/></el-form-item><el-form-item label="当前国籍"><el-input v-model="form.current_nationality"/></el-form-item><el-form-item label="永久/长期居留地"><el-input v-model="form.permanent_residence_country"/></el-form-item><el-form-item label="近2年海外月数"><el-input-number v-model="form.overseas_residence_months_last_2y" :min="0" :max="24"/></el-form-item><el-form-item label="意向专业领域"><el-select v-model="form.intended_field"><el-option v-for="f in fields" :key="f" :label="f" :value="f"/></el-select></el-form-item><el-form-item label="分数/成绩"><el-input-number v-model="form.score" :min="0" :max="750"/></el-form-item></div><div class="switches"><el-switch v-model="form.has_chinese_nationality" active-text="具有中国国籍"/><el-switch v-model="form.has_foreign_nationality" active-text="具有外国国籍"/><el-switch v-model="form.settled_abroad" active-text="已定居国外"/><el-switch v-model="form.has_mainland_household" active-text="仍有内地户籍"/></div></template><el-form-item label="复杂情况说明"><el-input v-model="form.complex_situation" type="textarea" rows="3"/></el-form-item><el-button type="primary" size="large" @click="submitJudge">提交判定</el-button></el-form></el-card>
            <ResultPanel v-if="result" :result="result" :paid="user.features.report_export" :can-writeback="!!profileStudentId" @export="exportReport" @unlock="showUnlock" @open-contact="openConsultDialog" @writeback="confirmJudgeWriteback" />
          </section>

          <section v-if="tab==='studentProfile'" class="page smp-page">
            <StudentProfile ref="studentProfileRef" @goto-judge="onGotoJudgeFromProfile" @goto-member="tab='member'" />
          </section>

          <section v-if="tab==='laws'" class="page"><div class="section-head"><div><h2>{{ text.laws }}</h2><p>{{ text.lawsDesc }}</p></div><el-input v-model="lawKeyword" :placeholder="text.searchLaws" clearable @input="loadLaws" /></div><el-tabs v-model="lawView" class="law-tabs"><el-tab-pane :label="text.fullLawText" name="full"><el-card class="law-full"><h2>《中华人民共和国国籍法》</h2><p class="muted">{{ text.fullLawHint }}</p><article v-for="law in allLaws" :key="law.number" class="law-full-item"><h3>第{{law.number}}条</h3><p>{{law.text}}</p></article></el-card></el-tab-pane><el-tab-pane :label="text.moePolicy" name="policies"><div class="policy-list"><el-card v-for="doc in policies" :key="doc.id" class="policy-card"><div class="policy-head"><div><h2>{{doc.title}}</h2><p class="muted">{{doc.authority}} · {{doc.code}}</p></div><el-tag type="primary">{{ text.internationalCore }}</el-tag></div><p>{{doc.summary}}</p><el-alert type="warning" :closable="false" :title="doc.focus"/><article v-for="section in doc.sections" :key="section.heading" class="law-full-item"><h3>{{section.heading}}</h3><p>{{section.text}}</p></article></el-card></div></el-tab-pane><el-tab-pane :label="text.lawExplanation" name="cards"><div class="law-grid"><el-card v-for="law in laws" :key="law.number"><h3>第{{law.number}}条：{{law.title}}</h3><p>{{law.text}}</p><el-alert type="info" :closable="false" :title="law.explanation"/></el-card></div></el-tab-pane></el-tabs></section>

          <section v-if="tab==='universities'" class="page"><div class="section-head"><div><h2>名校库</h2><p>{{ user.features.full_elite_university_library ? '已解锁完整名校库，可按地区、C9/双一流/985/211、体育/音乐/艺术/师范筛选。' : '免费版仅展示基础院校；付费后解锁完整名校库、筛选和招生联系方式。' }}</p></div></div><div class="filter-panel"><el-select v-model="target" placeholder="招生对象"><el-option label="国际生" value="international"/><el-option label="华侨生" value="huaqiao"/></el-select><el-select v-model="provinceFilter" clearable placeholder="地区"><el-option label="全部地区" value=""/><el-option v-for="p in provinces" :key="p" :label="p" :value="p"/></el-select><el-select v-model="tagFilter" clearable placeholder="院校层级"><el-option label="全部层级" value=""/><el-option v-for="t in tagFilters" :key="t" :label="t" :value="t"/></el-select><el-select v-model="featureFilter" clearable placeholder="特色类型"><el-option label="全部特色" value=""/><el-option v-for="f in featureFilters" :key="f" :label="f" :value="f"/></el-select><el-select v-model="field"><el-option label="全部领域" value=""/><el-option v-for="f in fields" :key="f" :label="f" :value="f"/></el-select><el-button type="primary" @click="loadUniversities">筛选</el-button></div><p class="muted">当前共 {{ universities.length }} 所学校</p><el-alert v-if="!user.features.full_elite_university_library" type="warning" :closable="false" title="当前仅展示非核心院校，升级会员后解锁完整名校库。"/><el-alert v-else type="success" :closable="false" title="会员权益已生效：完整名校库已解锁。"/><div class="school-grid"><el-card v-for="u in universities" :key="u.id"><h3>#{{u.ranking}} {{u.name}}</h3><p class="muted">{{u.province}} · {{u.university_type}}</p><p><b>标签：</b>{{ formatTags(u) }}</p><p><b>领域：</b>{{u.fields}}</p><p><b>优势专业：</b>{{u.advantage_majors}}</p><p>{{u.description}}</p><div class="contact-box"><p><b>学校官网：</b><a :href="u.official_url" target="_blank">{{u.official_url}}</a></p><p><b>招生官网：</b><a :href="u.admission_url" target="_blank">{{u.admission_url}}</a></p><p><b>招生邮箱：</b>{{u.admission_email}}</p><p><b>招生电话：</b>{{u.admission_phone}}</p><p><b>招生办公室：</b>{{u.admissions_office}}</p></div><el-tag v-if="u.locked_notice" type="warning">{{u.locked_notice}}</el-tag></el-card></div></section>

          <section v-if="tab==='schedules'" class="page"><div class="section-head"><div><h2>招生时间轴</h2><p>按大学库标准筛选招生时间：地区、C9/双一流/985/211、体育/音乐/艺术/师范。</p></div></div><div class="filter-panel"><el-select v-model="target" placeholder="招生对象"><el-option label="国际生" value="international"/><el-option label="华侨生" value="huaqiao"/></el-select><el-input-number v-model="month" :min="1" :max="12" placeholder="月份"/><el-select v-model="scheduleProvinceFilter" clearable placeholder="地区"><el-option label="全部地区" value=""/><el-option v-for="p in provinces" :key="p" :label="p" :value="p"/></el-select><el-select v-model="scheduleTagFilter" clearable placeholder="院校层级"><el-option label="全部层级" value=""/><el-option v-for="t in tagFilters" :key="t" :label="t" :value="t"/></el-select><el-select v-model="scheduleFeatureFilter" clearable placeholder="特色类型"><el-option label="全部特色" value=""/><el-option v-for="f in featureFilters" :key="f" :label="f" :value="f"/></el-select><el-button type="primary" @click="loadSchedules">筛选</el-button></div><p class="muted">当前共 {{ schedules.length }} 条招生节点</p><el-timeline><el-timeline-item v-for="(s,i) in schedules" :key="i" :timestamp="`${s.year}年${s.month}月`"><h3>#{{s.ranking}} {{s.university_name}}</h3><p class="muted">{{s.province}} · {{ formatTags(s) }} · {{s.fields}}</p><p>报名：{{s.registration_time}}；材料截止：{{s.material_deadline}}；考试/审核：{{s.exam_time}}</p><p class="muted">{{s.reminder}}</p></el-timeline-item></el-timeline></section>

          <section v-if="tab==='assistant'" class="page"><el-card><h2>智能AI助手</h2><p class="muted">用于国际生政策解读、复杂情况辅助分析、材料准备建议。无任何厂商标识。</p><el-input v-model="assistant.context" type="textarea" rows="3" placeholder="背景：国籍、出生地、父母定居、海外居住、目标专业"/><el-input class="mt" v-model="assistant.question" type="textarea" rows="4" placeholder="请输入政策或升学规划问题"/><el-button class="mt" type="primary" @click="ask">智能AI助手分析</el-button><div v-if="assistant.answer" class="answer">{{assistant.answer}}</div></el-card></section>

          <section v-if="tab==='history'" class="page"><div class="section-head"><div><h2>历史记录</h2><p>按租户隔离保存，免费版限制记录数量，付费版永久保存。</p></div><el-button @click="loadRecords">刷新</el-button></div><el-table :data="records"><el-table-column prop="type" label="模块"/><el-table-column prop="conclusion" label="结论"/><el-table-column label="结果"><template #default="s"><el-tag :type="s.row.result==='PRELIMINARY_ELIGIBLE'?'success':s.row.result==='MANUAL_REVIEW_REQUIRED'?'warning':'danger'">{{ s.row.result==='PRELIMINARY_ELIGIBLE'?'初步符合':s.row.result==='MANUAL_REVIEW_REQUIRED'?'需人工复核':'初步不符合' }}</el-tag></template></el-table-column><el-table-column prop="created_at" label="时间"/><el-table-column label="操作"><template #default="s"><el-button size="small" @click="openRecord(s.row.id)">查看</el-button></template></el-table-column></el-table></section>

          <section v-if="tab==='member'" class="page member-page">
            <h2>会员中心</h2>
            <p class="muted">支持微信、支付宝或本地模拟支付；支付成功后自动开通。</p>
            <el-alert class="mt" type="info" :closable="false" title="付费权益总览（仅在此处说明一次）" description="解锁完整 C9/985/211 名校库与筛选、艺术体育专项、智能AI助手不限次、报告导出与更深度的推荐与历史容量。年会员、三年会员与终身版另含完整智能时间轴。一对一深度规划请使用顶部「一对一规划咨询」。" />
            <h3 class="plan-section-title">在售套餐</h3>
            <div class="plan-grid">
              <el-card v-for="p in memberPlansList" :key="p.code">
                <h3>{{ p.name }}</h3>
                <p class="price">¥{{ p.price }}<span v-if="p.duration_days" class="plan-duration"> · {{ formatPlanDuration(p) }}</span></p>
                <p class="plan-desc">{{ p.description }}</p>
                <el-button v-if="p.code !== 'free'" type="primary" @click="openPayment(p)">立即购买</el-button>
                <el-tag v-else type="info">当前基础套餐</el-tag>
              </el-card>
            </div>
            <el-card class="mt"><h3>卡密充值</h3><div class="filters"><el-input v-model="redeemCode" placeholder="输入充值卡密"/><el-button type="primary" @click="redeem">立即开通</el-button></div><el-table :data="orders" class="mt"><el-table-column prop="plan_code" label="套餐"/><el-table-column prop="status" label="状态"/><el-table-column prop="source" label="来源"/><el-table-column prop="created_at" label="时间"/></el-table></el-card>
          </section>

          <section v-if="tab==='admin'" class="page"><h2>后台管理</h2><div class="stats-grid"><el-card><h3>用户</h3><p class="big">{{stats.users}}</p></el-card><el-card><h3>租户</h3><p class="big">{{stats.tenants}}</p></el-card><el-card><h3>国际生占比</h3><p class="big">{{stats.international_ratio}}</p></el-card></div><el-card class="mt"><h3>套餐管理</h3><el-table :data="plans"><el-table-column prop="name" label="套餐"/><el-table-column prop="price" label="价格"/><el-table-column prop="duration_days" label="时长"/><el-table-column prop="description" label="权益"/></el-table></el-card><el-card class="mt"><h3>充值卡密</h3><div class="filters"><el-select v-model="newCode.plan_code"><el-option label="月会员" value="vip_month"/><el-option label="年会员" value="vip_year"/><el-option label="三年会员" value="vip_three_year"/><el-option label="终身版" value="lifetime"/></el-select><el-input-number v-model="newCode.count" :min="1" :max="100"/><el-button @click="createCodes">生成卡密</el-button></div><el-table :data="codes"><el-table-column prop="code" label="卡密"/><el-table-column prop="plan_code" label="套餐"/><el-table-column prop="is_used" label="已使用"/></el-table></el-card><el-card class="mt"><h3>用户管理</h3><el-table :data="users"><el-table-column prop="email" label="账号"/><el-table-column prop="plan_code" label="套餐"/><el-table-column prop="role" label="角色"/><el-table-column prop="created_at" label="注册时间"/></el-table></el-card></section>
        </section>
      </main>
      <el-dialog v-model="unlockVisible" title="升级解锁国际生 Pro 权益" width="430px"><p>开通任意付费套餐即可解锁名校库、导出及智能AI助手等权益；各档位说明已在「会员中心」统一展示，避免重复。</p><el-button type="primary" @click="tab='member'; unlockVisible=false">前往会员中心</el-button></el-dialog>
      <el-dialog v-model="contactConsultVisible" :title="text.consultDialogTitle" width="560px" destroy-on-close>
        <el-alert type="info" :closable="false" :title="text.consultDialogIntro" class="consult-alert" />
        <el-descriptions :column="1" border class="mt">
          <el-descriptions-item :label="text.consultOrg">{{ consultBrand.orgName }}</el-descriptions-item>
          <el-descriptions-item :label="text.consultContactName">{{ consultBrand.contactName }}</el-descriptions-item>
          <el-descriptions-item :label="text.email">{{ consultBrand.email }}</el-descriptions-item>
          <el-descriptions-item :label="text.consultWechat">{{ consultBrand.wechat }}</el-descriptions-item>
          <el-descriptions-item :label="text.consultPhone">{{ consultBrand.phone }}</el-descriptions-item>
        </el-descriptions>
        <p class="muted mt">{{ consultBrand.extraNote }}</p>
        <el-divider />
        <p class="muted">{{ text.consultGuestHint }}</p>
        <el-form label-position="top" class="mt">
          <el-form-item :label="text.consultGuestName"><el-input v-model="guestLead.name" :placeholder="text.optional" /></el-form-item>
          <el-form-item :label="text.consultPhone"><el-input v-model="guestLead.phone" :placeholder="text.optional" /></el-form-item>
          <el-form-item :label="text.email"><el-input v-model="guestLead.email" :placeholder="text.optional" /></el-form-item>
          <el-form-item :label="text.consultWechat"><el-input v-model="guestLead.wechat" :placeholder="text.optional" /></el-form-item>
          <el-form-item :label="text.consultGuestNeed"><el-input v-model="guestLead.note" type="textarea" :rows="3" :placeholder="text.consultNeedPh" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="copyGuestLead">{{ text.consultCopy }}</el-button>
          <el-button type="primary" @click="contactConsultVisible=false">{{ text.consultClose }}</el-button>
        </template>
      </el-dialog>
      <el-dialog v-model="paymentDialog" title="购买会员套餐" width="520px">
        <template v-if="selectedPlan">
          <h3>{{ selectedPlan.name }} · ¥{{ selectedPlan.price }}</h3>
          <p class="muted">{{ selectedPlan.description }}</p>
          <el-radio-group v-model="paymentChannel" class="payment-methods"><el-radio-button label="wechat">微信支付</el-radio-button><el-radio-button label="alipay">支付宝</el-radio-button><el-radio-button label="mock">模拟支付</el-radio-button></el-radio-group>
          <div v-if="paymentOrder" class="payment-box"><p><b>订单号：</b>{{ paymentOrder.order_no }}</p><p><b>金额：</b>¥{{ paymentOrder.amount }}</p><p><b>状态：</b>{{ paymentOrder.status }}</p><div class="qr-box">{{ paymentOrder.qr_content }}</div><p class="muted">正式微信/支付宝支付需要配置商户号、证书和公网 HTTPS 回调。本地开发可点击模拟支付完成测试。</p></div>
          <div class="report-actions"><el-button type="primary" @click="createPaymentOrder">生成支付订单</el-button><el-button @click="checkPayment" :disabled="!paymentOrder">查询支付状态</el-button><el-button type="success" @click="mockPayOrder" :disabled="!paymentOrder || paymentOrder.channel!=='mock'">本地 mock 支付成功</el-button></div>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api, clearToken, setToken, syncTokenFromStorage } from './api'
import {
  accessibleStudents,
  activeStudentId,
  activeStudentLabel,
  clearActiveStudent,
  hasMultipleStudents,
  normalizeStudentId,
  setActiveStudentId,
  syncStudentsAndActive,
} from './activeStudent'
import StudentProfile from './StudentProfile.vue'

const user = ref(null), loading = ref(false), authTab = ref('login'), tab = ref('internationalDashboard'), unlockVisible = ref(false)
const darkMode = ref(localStorage.getItem('saas_theme') === 'dark')
function syncHtmlDark() { document.documentElement.classList.toggle('dark', darkMode.value) }
function persistSaasTheme() { localStorage.setItem('saas_theme', darkMode.value ? 'dark' : 'light'); syncHtmlDark() }
const lang = ref(localStorage.getItem('saas_lang') || 'zh')
const langOptions = [{ label: '中文', value: 'zh' }, { label: 'EN', value: 'en' }]
const login = ref({email:'demo@example.com', password:'demo123456'}), register = ref({tenant_name:'', email:'', password:'', tenant_type:'personal'})

const i18n = {
  zh: {
    systemName: '国际生资格智评系统 Pro', brandEyebrow: '国际生 SaaS', brandIntro: '基于原稳定版升级的独立 SaaS 收费系统，国际生判定为主，华侨生判定为辅，适配机构与个人用户。', tenantIsolation: '多租户隔离', memberPermission: '会员权限', universityLibrary: '名校库', assistant: '智能AI助手', login: '登录', register: '注册机构/个人', email: '邮箱', password: '密码', loginButton: '登录系统', tenantName: '租户名称', accountType: '类型', personal: '个人用户', agency: '机构用户', registerButton: '注册并进入', demoAccount: '演示账号：admin@example.com / admin123456；demo@example.com / demo123456', logout: '退出', internationalDashboard: '国际生工作台', huaqiaoDashboard: '华侨生工作台', dualJudge: '双模块判定', laws: '国籍法依据', schedules: '招生时间', history: '历史记录', memberCenter: '会员中心', admin: '后台管理', internationalCore: '国际生核心模块', internationalDashboardTitle: '国际生升学资格与会员化服务工作台', internationalDashboardDesc: '独立服务国际生资格判定、外国国籍与中国国籍状态核验、海外居住记录、国际生名校推荐和政策解读。', startInternational: '开始国际生判定', identityCheck: '身份合规核验', identityCheckDesc: '重点核验外国国籍、中国国籍状态、父母定居与海外出生情况。', elitePlanning: '名校升学规划', paidEliteOpen: '已解锁完整C9/985/211名校库、艺术体育专项和报告导出。', freeEliteLocked: '免费版仅开放基础院校，升级后解锁完整国际生名校规划。', internationalAssistant: '国际生政策解读', internationalAssistantDesc: '通过智能AI助手辅助解释复杂身份与材料准备。', entitlementList: '权益清单', huaqiaoAuxiliary: '华侨生辅助模块', huaqiaoDashboardTitle: '华侨生资格辅助判定工作台', huaqiaoDashboardDesc: '华侨生模块与国际生模块独立运行，主要用于中国国籍、海外定居、近两年海外居住和户籍状态的辅助判断。', startHuaqiao: '开始华侨生判定', huaqiaoIdentity: '中国国籍身份', huaqiaoIdentityDesc: '重点核验是否具有中国国籍且未取得外国国籍。', residenceEvidence: '海外定居与居住', residenceEvidenceDesc: '关注境外定居证明、出入境记录和近两年海外居住月份。', auxiliaryPosition: '辅助定位', auxiliaryPositionDesc: '华侨生为辅助模块，不与国际生判定混用。', huaqiaoScope: '华侨生模块适用范围', huaqiaoScopeDesc: '适用于以中国国籍身份咨询华侨生路径的用户；若用户以外国国籍身份申请，应回到国际生模块。', internationalJudge: '国际生判定', huaqiaoJudge: '华侨生判定', internationalJudgeDesc: '国际生判定独立处理外国国籍、中国国籍状态、海外居住与名校推荐。', huaqiaoJudgeDesc: '华侨生判定独立处理中国国籍、海外定居、居住记录与户籍状态。', yes: '是', no: '否', enabled: '已开通', disabled: '未开通', planCode: '当前套餐', paid: '付费状态', internationalFocus: '国际生核心定位', fullEliteUniversityLibrary: '完整C9/985/211名校库', artSportSpecialty: '艺术/体育专项专业', internationalPlanning: '国际生专属升学规划', assistantUnlimited: '智能AI助手无限问答', reportExport: '判定报告导出', unlimitedRecommendations: '无限制大学推荐', permanentHistory: '历史记录永久保存', freePlanText: '免费版，核心国际生权益待解锁', paidPlanText: '付费权益已开通', lawsDesc: '完整展示《中华人民共和国国籍法》全文，并提供条款解释、关键词搜索和判定依据对照。', searchLaws: '搜索条款关键词', fullLawText: '完整版全文', lawExplanation: '条款解释版', fullLawHint: '以下为系统内置国籍法全文条款，用于国际生/华侨生资格判定依据展示。', consultPlanning: '一对一规划咨询', consultDialogTitle: '一对一升学规划咨询', consultDialogIntro: '如需退籍与国籍状态材料、时间轴与院校目标的个性化方案，请通过以下方式联系我们（下方信息可在 App.vue 中修改 consultBrand）。', consultOrg: '机构名称', consultContactName: '联系人', consultWechat: '微信', consultPhone: '电话', consultGuestHint: '您可预留以下信息便于顾问回访（仅在本机填写，请点击「复制咨询信息」后发邮件或微信）。', consultGuestName: '您的姓名', consultGuestNeed: '规划需求简述', consultNeedPh: '例如：目标入学年份、目标院校、当前国籍与户籍情况等', consultCopy: '复制咨询信息', consultClose: '关闭', optional: '选填', themeLight: '浅色', themeDark: '深色', moePolicy: '教外函政策'
  },
  en: {
    systemName: 'International Student Eligibility Pro', brandEyebrow: 'International Student SaaS', brandIntro: 'A standalone SaaS edition upgraded from the stable system, with international student eligibility as the primary module and overseas Chinese eligibility as a separate auxiliary module.', tenantIsolation: 'Tenant Isolation', memberPermission: 'Membership', universityLibrary: 'University Library', assistant: 'Smart AI Assistant', login: 'Login', register: 'Register', email: 'Email', password: 'Password', loginButton: 'Login', tenantName: 'Tenant Name', accountType: 'Account Type', personal: 'Personal', agency: 'Agency', registerButton: 'Create Account', demoAccount: 'Demo accounts: admin@example.com / admin123456; demo@example.com / demo123456', logout: 'Logout', internationalDashboard: 'International Dashboard', huaqiaoDashboard: 'Overseas Chinese Dashboard', dualJudge: 'Eligibility Modules', laws: 'Nationality Law', schedules: 'Admission Timeline', history: 'History', memberCenter: 'Membership', admin: 'Admin', internationalCore: 'Primary International Module', internationalDashboardTitle: 'International Student Eligibility & SaaS Service Desk', internationalDashboardDesc: 'Dedicated workspace for foreign nationality, Chinese nationality status, overseas residence, elite university recommendation and policy interpretation.', startInternational: 'Start International Check', identityCheck: 'Identity Compliance', identityCheckDesc: 'Checks foreign nationality, Chinese nationality status, parents settlement and overseas birth context.', elitePlanning: 'Elite University Planning', paidEliteOpen: 'Full C9/985/211 library, art/sport specialties and report export are unlocked.', freeEliteLocked: 'Free plan only shows basic schools. Upgrade to unlock full international planning.', internationalAssistant: 'Policy Interpretation', internationalAssistantDesc: 'Use the Smart AI Assistant for complex identity and document preparation questions.', entitlementList: 'Entitlement List', huaqiaoAuxiliary: 'Auxiliary Overseas Chinese Module', huaqiaoDashboardTitle: 'Overseas Chinese Eligibility Auxiliary Desk', huaqiaoDashboardDesc: 'This module runs separately from the international student module and focuses on Chinese nationality, overseas settlement, two-year residence and household registration status.', startHuaqiao: 'Start Overseas Chinese Check', huaqiaoIdentity: 'Chinese Nationality', huaqiaoIdentityDesc: 'Checks whether the applicant has Chinese nationality and no foreign nationality.', residenceEvidence: 'Overseas Residence Evidence', residenceEvidenceDesc: 'Focuses on settlement proof, entry/exit records and two-year overseas residence months.', auxiliaryPosition: 'Auxiliary Position', auxiliaryPositionDesc: 'This is an auxiliary module and should not be mixed with international student checks.', huaqiaoScope: 'Module Scope', huaqiaoScopeDesc: 'For users applying through overseas Chinese paths with Chinese nationality. Foreign-nationality applicants should use the international module.', internationalJudge: 'International Check', huaqiaoJudge: 'Overseas Chinese Check', internationalJudgeDesc: 'Separately handles foreign nationality, Chinese nationality status, overseas residence and university recommendation.', huaqiaoJudgeDesc: 'Separately handles Chinese nationality, overseas settlement, residence records and household registration.', yes: 'Yes', no: 'No', enabled: 'Enabled', disabled: 'Disabled', planCode: 'Current Plan', paid: 'Paid Status', internationalFocus: 'International Focus', fullEliteUniversityLibrary: 'Full C9/985/211 Library', artSportSpecialty: 'Art/Sport Specialties', internationalPlanning: 'International Planning', assistantUnlimited: 'Unlimited Smart AI Assistant', reportExport: 'Report Export', unlimitedRecommendations: 'Unlimited Recommendations', permanentHistory: 'Permanent History', freePlanText: 'Free plan, premium international features locked', paidPlanText: 'Paid features enabled', lawsDesc: 'Full text of the Nationality Law with article explanations, search and eligibility basis mapping.', searchLaws: 'Search articles', fullLawText: 'Full Text', lawExplanation: 'Article Notes', fullLawHint: 'The following full text is used as the legal basis for international and overseas Chinese eligibility checks.', consultPlanning: 'Planning consultation', consultDialogTitle: 'One-on-one planning', consultDialogIntro: 'For personalized help on denationalization, nationality documents, timelines and university targets, contact us below (edit consultBrand in App.vue).', consultOrg: 'Organization', consultContactName: 'Contact', consultWechat: 'WeChat', consultPhone: 'Phone', consultGuestHint: 'Optionally fill in your details and use Copy to paste into email or WeChat.', consultGuestName: 'Your name', consultGuestNeed: 'Planning needs', consultNeedPh: 'e.g. target intake year, schools, nationality and household status', consultCopy: 'Copy message', consultClose: 'Close', optional: 'Optional', themeLight: 'Light', themeDark: 'Dark', moePolicy: 'MOE Policy Notice'
  }
}
const text = computed(() => i18n[lang.value])
const featureLabels = computed(() => ({ plan_code: text.value.planCode, paid: text.value.paid, international_focus: text.value.internationalFocus, full_elite_university_library: text.value.fullEliteUniversityLibrary, art_sport_specialty: text.value.artSportSpecialty, international_planning: text.value.internationalPlanning, assistant_unlimited: text.value.assistantUnlimited, report_export: text.value.reportExport, unlimited_recommendations: text.value.unlimitedRecommendations, permanent_history: text.value.permanentHistory }))
const featureRows = computed(() => Object.entries(user.value?.features || {}).map(([key, value]) => ({ key, label: featureLabels.value[key] || key, value: typeof value === 'boolean' ? (value ? text.value.enabled : text.value.disabled) : value })))
watch(lang, value => localStorage.setItem('saas_lang', value))

const fields = ['综合','理工','文史','医药','体育','音乐','美术','设计']
const provinces = ['北京','上海','天津','重庆','广东','江苏','浙江','湖北','湖南','陕西','四川','山东','福建','辽宁','吉林','黑龙江','安徽','河南','河北','山西','内蒙古','江西','广西','海南','贵州','云南','西藏','甘肃','青海','宁夏','新疆']
const tagFilters = ['C9','双一流','985','211']
const featureFilters = ['体育','音乐','艺术','师范']
function formatTags(school){ const raw = `${school.tags || ''},${school.fields || ''},${school.university_type || ''}`; return ['C9','双一流','985','211','体育','音乐','艺术','师范'].filter(t => t==='211' ? raw.includes('211') || raw.includes('纯211') : t==='艺术' ? ['艺术','美术','设计'].some(x=>raw.includes(x)) : raw.includes(t)).join(' / ') }
const judgeType = ref('international'), target = ref('international'), field = ref(''), month = ref(null), provinceFilter = ref(''), tagFilter = ref(''), featureFilter = ref(''), scheduleProvinceFilter = ref(''), scheduleTagFilter = ref(''), scheduleFeatureFilter = ref('')
const universities = ref([]), schedules = ref([]), laws = ref([]), allLaws = ref([]), policies = ref([]), lawKeyword = ref(''), lawView = ref('full'), records = ref([]), plans = ref([]), orders = ref([]), result = ref(null), redeemCode = ref('')
const paymentDialog = ref(false), selectedPlan = ref(null), paymentChannel = ref('mock'), paymentOrder = ref(null)
const users = ref([]), codes = ref([]), stats = ref({}), newCode = ref({plan_code:'vip_month', duration_days:30, count:1})
const assistant = ref({context:'', question:'', answer:''})
const studentProfileRef = ref(null)
/** Judge writeback uses shared activeStudentId (stable student_id). */
const profileStudentId = activeStudentId
const form = ref({name:'', birth_date:'', current_nationality:'', has_chinese_nationality:false, has_foreign_nationality:true, foreign_nationality_acquired_date:'', settled_abroad:true, permanent_residence_country:'', overseas_residence_months_last_2y:0, overseas_residence_months_last_4y:24, annual_months_overseas:9, has_mainland_household:false, has_denationalization_certificate:false, denationalization_certificate_info:'', parent_chinese_citizen:false, parent_settled_abroad_at_birth:false, born_abroad:false, intended_field:'综合', score:null, passport_info:'', household_info:'', complex_situation:''})
const planText = computed(() => user.value?.features?.paid ? text.value.paidPlanText : text.value.freePlanText)

async function refreshStudentSwitcher() {
  try {
    const r = await api.students()
    syncStudentsAndActive(r.students || [])
  } catch {
    /* not logged in / no students yet */
  }
}
function onHomeSwitchStudent(id) {
  const ok = setActiveStudentId(id)
  if (!ok) {
    ElMessage.warning('无法切换到该学生')
    return
  }
  if (tab.value === 'studentProfile' && studentProfileRef.value?.openStudent) {
    studentProfileRef.value.openStudent(id)
  }
}

const MEMBER_PLAN_ORDER = ['free', 'vip_month', 'vip_year', 'vip_three_year', 'lifetime']
function planSortKey(code) {
  const i = MEMBER_PLAN_ORDER.indexOf(code)
  return i === -1 ? 99 : i
}
const memberPlansList = computed(() => [...plans.value].filter((p) => MEMBER_PLAN_ORDER.includes(p.code)).sort((a, b) => planSortKey(a.code) - planSortKey(b.code)))
function formatPlanDuration(p) {
  const d = p?.duration_days
  if (!d) return ''
  if (d >= 36500) return '长期有效'
  if (d >= 365 && d % 365 === 0) return `${d / 365} 年`
  if (d >= 30 && d % 30 === 0) return `${d / 30} 个月`
  return `${d} 天`
}

async function boot(){
  if (!syncTokenFromStorage()) return
  try {
    user.value = await api.me()
    await refreshStudentSwitcher()
    await loadTab('internationalDashboard')
  } catch {
    clearToken()
    user.value = null
  }
}
async function doLogin() {
  if (loading.value) return
  loading.value = true
  try {
    const email = (login.value.email || '').trim()
    const password = login.value.password || ''
    if (!email || !password) {
      ElMessage.warning('请输入邮箱和密码')
      return
    }
    const r = await api.login({ email, password })
    if (!r?.token) throw new Error('登录响应缺少 token')
    setToken(r.token)
    user.value = r.user
    try {
      await refreshStudentSwitcher()
    } catch { /* students optional at login */ }
    await loadTab('internationalDashboard')
  } catch (e) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
async function doRegister() {
  if (loading.value) return
  loading.value = true
  try {
    const r = await api.register(register.value)
    if (!r?.token) throw new Error('注册响应缺少 token')
    setToken(r.token)
    user.value = r.user
    try { await refreshStudentSwitcher() } catch { /* optional */ }
    await loadTab('internationalDashboard')
  } catch (e) {
    ElMessage.error(e.message || '注册失败')
  } finally {
    loading.value = false
  }
}
function logout() {
  clearActiveStudent()
  clearToken()
  user.value = null
  location.reload()
}
function startJudge(type){ judgeType.value=type; tab.value='judge'; target.value=type; applyJudgeDefaults(type) }
function applyJudgeDefaults(type){
  if(type==='huaqiao') Object.assign(form.value, {has_chinese_nationality:true, has_foreign_nationality:false, settled_abroad:true, has_mainland_household:false, overseas_residence_months_last_2y:18, overseas_residence_months_last_4y:0, annual_months_overseas:0, has_denationalization_certificate:false})
  else Object.assign(form.value, {has_chinese_nationality:false, has_foreign_nationality:true, settled_abroad:true, has_mainland_household:false, overseas_residence_months_last_4y:24, annual_months_overseas:9})
}
watch(judgeType, applyJudgeDefaults)
async function refreshMe(){ user.value = await api.me() }
async function loadTab(name){ tab.value=name; if(name==='laws') await loadLaws(); if(name==='universities') await loadUniversities(); if(name==='schedules') await loadSchedules(); if(name==='history') await loadRecords(); if(name==='member'){ plans.value=await api.plans(); orders.value=await api.orders() } if(name==='admin'){ stats.value=await api.adminStats(); users.value=await api.adminUsers(); codes.value=await api.adminCodes(); plans.value=await api.adminPlans() } if(name==='studentProfile') await refreshStudentSwitcher() }
function onGotoJudgeFromProfile(payload){
  setActiveStudentId(payload.studentId, { allowUnknown: true })
  judgeType.value = payload.kind
  Object.assign(form.value, payload.prefills || {})
  tab.value = 'judge'
  target.value = payload.kind
}
async function confirmJudgeWriteback(){
  if(!profileStudentId.value || !result.value){ ElMessage.warning('请先从学生档案进入判定'); return }
  try{
    await api.studentWriteback(profileStudentId.value, { kind: judgeType.value, result: result.value.result, conclusion: result.value.conclusion || result.value.explanation, record_id: result.value.record_id, policy_version: 'R4.2', confirm: true })
    ElMessage.success('判定结果已确认写入学生档案')
    tab.value = 'studentProfile'
  }catch(e){ ElMessage.error(e.message) }
}
async function submitJudge(){ try{ result.value = judgeType.value==='international' ? await api.judgeInternational(form.value) : await api.judgeHuaqiao(form.value); await refreshMe(); if(profileStudentId.value && result.value){ try{ await api.studentWriteback(profileStudentId.value, { kind: judgeType.value, result: result.value.result, conclusion: result.value.conclusion || result.value.explanation, record_id: result.value.record_id, policy_version: 'R4.2', confirm: false }); ElMessage.success('判定完成，可确认写入学生档案') }catch{ ElMessage.success('判定完成') } } else { ElMessage.success('判定完成') } }catch(e){ ElMessage.error(e.message) } }
async function loadLaws(){ if(!allLaws.value.length) allLaws.value = await api.laws(''); policies.value = await api.policies(lawKeyword.value); laws.value = await api.laws(lawKeyword.value) }
async function loadUniversities(){ await refreshMe(); universities.value = await api.universities(target.value, field.value, {province: provinceFilter.value, tag: tagFilter.value, feature: featureFilter.value}) }
async function loadSchedules(){ schedules.value = await api.schedules(target.value, month.value || '', {province: scheduleProvinceFilter.value, tag: scheduleTagFilter.value, feature: scheduleFeatureFilter.value}) }
async function loadRecords(){ records.value = await api.records() }
async function openRecord(id){ result.value = await api.recordDetail(id); judgeType.value = result.value.type || judgeType.value; tab.value='judge' }
async function redeem(){ try{ const r=await api.redeem(redeemCode.value); user.value=r.user; ElMessage.success('开通成功'); await loadTab('member') }catch(e){ ElMessage.error(e.message) } }
function openPayment(plan){ selectedPlan.value=plan; paymentChannel.value='mock'; paymentOrder.value=null; paymentDialog.value=true }
async function createPaymentOrder(){ try{ paymentOrder.value=await api.createPayment({plan_code:selectedPlan.value.code, channel:paymentChannel.value}); ElMessage.success('支付订单已创建') }catch(e){ ElMessage.error(e.message) } }
async function checkPayment(){ if(!paymentOrder.value) return; try{ paymentOrder.value=await api.paymentStatus(paymentOrder.value.order_no); if(paymentOrder.value.status==='paid'){ await refreshMe(); await loadTab('member'); ElMessage.success('支付成功，权益已开通') } }catch(e){ ElMessage.error(e.message) } }
async function mockPayOrder(){ if(!paymentOrder.value) return; try{ const r=await api.mockPay(paymentOrder.value.order_no); user.value=r.user; paymentOrder.value={...paymentOrder.value, ...r.payment}; paymentDialog.value=false; await refreshMe(); ElMessage.success('模拟支付成功，会员已自动解锁，名校库已开放') }catch(e){ ElMessage.error(e.message) } }
async function ask(){ try{ assistant.value.answer=(await api.ask({question:assistant.value.question, context:assistant.value.context, mode:'qa'})).answer }catch(e){ ElMessage.error(e.message) } }
const contactConsultVisible = ref(false)
const consultBrand = {
  orgName: '（请修改为机构/公司名称）',
  contactName: '（顾问姓名）',
  email: 'your-service@example.com',
  wechat: '（请填写微信号）',
  phone: '（请填写联系电话）',
  extraNote: '可在此补充工作时间、办公地址等说明（同一文件内编辑 consultBrand）。',
}
const guestLead = ref({ name: '', phone: '', email: '', wechat: '', note: '' })
function openConsultDialog() { contactConsultVisible.value = true }
function copyGuestLead() {
  const b = consultBrand
  const g = guestLead.value
  const lines = [
    '【一对一规划咨询】',
    `机构：${b.orgName}`,
    `联系人：${b.contactName}`,
    `邮箱：${b.email}`,
    `微信：${b.wechat}`,
    `电话：${b.phone}`,
    `${b.extraNote}`,
    '',
    '—— 客户预留信息 ——',
    `姓名：${g.name || '（未填）'}`,
    `电话：${g.phone || '（未填）'}`,
    `邮箱：${g.email || '（未填）'}`,
    `微信：${g.wechat || '（未填）'}`,
    `需求：${g.note || '（未填）'}`,
  ]
  navigator.clipboard.writeText(lines.join('\n')).then(() => ElMessage.success(lang.value === 'zh' ? '已复制，可粘贴到邮件或微信' : 'Copied')).catch(() => ElMessage.warning(lang.value === 'zh' ? '复制失败，请手动选择文本' : 'Copy failed'))
}
const RECHARGE_PLAN_DURATION = { vip_month: 30, vip_year: 365, vip_three_year: 1095, lifetime: 36500 }
async function createCodes(){ try{ const d = RECHARGE_PLAN_DURATION[newCode.value.plan_code] ?? 30; await api.createCodes({ ...newCode.value, duration_days: d }); codes.value=await api.adminCodes(); ElMessage.success('已生成') }catch(e){ ElMessage.error(e.message) } }
function showUnlock(){ unlockVisible.value=true }
async function exportReport(recordId){ if(!user.value.features.report_export){ showUnlock(); return } try{ const text=await api.exportReport(recordId || result.value.record_id || result.value.id); const blob=new Blob([text],{type:'text/plain;charset=utf-8'}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`国际生判定报告-${recordId || result.value.record_id || result.value.id}.txt`; a.click(); URL.revokeObjectURL(url); ElMessage.success('报告已生成') }catch(e){ ElMessage.error(e.message) } }
onMounted(() => { syncHtmlDark(); boot() })

const ResultPanel = defineComponent({
  props:{result:Object, paid:Boolean, canWriteback:Boolean},
  emits:['export','unlock','openContact','writeback'],
  setup(props,{emit}){
    const planningBlock = () => {
      const p = props.result.planning
      if(!p) return null
      if(p.locked) return h('div',{class:'planning-lock'},[h('h3','升学规划与材料'), h('p', p.message || '如需个性化材料清单与时间轴，可通过「一对一规划咨询」联系顾问。'), h('button',{class:'plain-btn',onClick:()=>emit('openContact')},'联系顾问')])
      return h('div',{class:'planning-card'},[
        h('h3',p.title), h('p',{class:'muted'},p.notice),
        h('div',{class:'planning-grid'}, p.timeline.map(item=>h('article',{class:'mini-card'},[h('b',`${item.stage} · ${item.title}`), h('ul', item.items.map(x=>h('li',x)))]))),
        h('h3','需要准备的材料'), h('div',{class:'material-list'}, p.materials.map(x=>h('span',x)))
      ])
    }
    return()=>h('div',{class:'result-panel'},[
      h('div',{class:['result-hero', props.result.result==='PRELIMINARY_ELIGIBLE'?'pass':props.result.result==='MANUAL_REVIEW_REQUIRED'?'review':'fail']},[h('span', props.result.result==='PRELIMINARY_ELIGIBLE'?'初步符合':props.result.result==='MANUAL_REVIEW_REQUIRED'?'需人工复核':'初步不符合'), h('h2',props.result.conclusion)]),
      h('p',{class:'disclaimer'},'本结果为基于当前政策与用户提供信息生成的初步资格评估，不替代教育主管部门、联招办或高校的最终资格审核。'),
      h('h3','判定理由'), h('ul', props.result.reasons.map(r=>h('li',r))),
      props.result.manual_review_rules?.length ? h('div',{class:'review-box'},[h('h4','需人工复核项'),h('ul',props.result.manual_review_rules.map(r=>h('li',r)))]) : null,
      props.result.suggestions?.length ? h('p',{class:'muted'}, '建议：'+props.result.suggestions.join('；')) : null,
      planningBlock(),
      h('h3','国籍法依据'), h('div',{class:'law-mini'}, props.result.basis_articles.map(a=>h('article',[h('b',`第${a.number}条：${a.title}`), h('p',a.text), h('small',a.explanation)]))),
      h('h3','推荐大学'), h('div',{class:'school-grid'}, props.result.recommendations.map(u=>h('article',{class:'mini-card'},[h('b',`#${u.ranking} ${u.name}`), h('p',u.tags), h('p',u.fields), h('p',u.advantage_majors), h('small',u.match_reason)]))),
      h('div',{class:'report-actions'},[h('button',{class:'plain-btn',onClick:()=>emit('export',props.result.record_id||props.result.id)},'导出判定报告'), props.canWriteback?h('button',{class:'plain-btn',onClick:()=>emit('writeback')},'确认写入学生档案'):null, !props.paid?h('button',{class:'warn-btn',onClick:()=>emit('unlock')},'查看付费解锁权益'):null])
    ])
  }
})
</script>
