<template>
  <div :class="['mobile-app', darkMode ? 'dark' : 'light']">
    <van-nav-bar
      :title="navTitle"
      fixed
      placeholder
      safe-area-inset-top
      left-arrow
      @click-left="goBack"
    >
      <template #right>
        <van-switch v-model="darkMode" size="22px" @change="persistTheme" />
      </template>
    </van-nav-bar>

    <main class="screen" @touchstart="touchStart" @touchend="touchEnd">
      <section v-if="tab === 'home'" class="home-screen">
        <div class="hero-card">
          <h1 class="hero-title">
            <span class="hero-title-line hero-title-line--primary">国际生/华侨生</span>
            <span class="hero-title-line hero-title-line--secondary">资格判定系统</span>
          </h1>
          <p class="hero-lead">欢迎使用</p>
        </div>
        <van-cell-group v-if="studentSwitcherList.length" inset class="home-student-switch">
          <van-cell title="当前学生" :value="currentStudentLabel" />
          <van-field
            v-if="studentSwitcherList.length > 1"
            label="切换"
            is-link
            readonly
            :model-value="currentStudentLabel"
            placeholder="选择学生"
            @click="openHomeStudentPicker"
          />
        </van-cell-group>
        <van-popup v-model:show="showHomeStudentPicker" position="bottom" round>
          <van-picker
            v-if="showHomeStudentPicker"
            :key="`home-picker-${currentStudentId || 'none'}-${pickerEpoch}`"
            :columns="homeStudentColumns"
            :model-value="homePickerSelectedValues"
            @confirm="onHomePickStudent"
            @cancel="showHomeStudentPicker=false"
          />
        </van-popup>
        <van-grid :column-num="2" :gutter="10" class="home-grid">
          <van-grid-item icon="award-o" text="国际生判定" @click="openJudge('international')" />
          <van-grid-item icon="passed" text="华侨生判定" @click="openJudge('huaqiao')" />
          <van-grid-item icon="contact" text="学生档案" @click="openPage('profile')" />
          <van-grid-item icon="bookmark-o" text="国籍法条款" @click="openLawsNationality" />
          <van-grid-item icon="description" text="教外函政策" @click="openLawsPolicy" />
          <van-grid-item icon="wap-home-o" text="大学库" @click="openPage('universities')" />
          <van-grid-item icon="underway-o" text="招生时间" @click="openPage('schedule')" />
          <van-grid-item icon="records-o" text="历史记录" @click="openPage('history')" />
          <van-grid-item icon="vip-card-o" text="会员中心" @click="openPage('member')" />
          <van-grid-item icon="service-o" text="一对一规划咨询" @click="openConsultWithGate" />
        </van-grid>
      </section>

      <section v-if="tab === 'judge'" class="flow-screen">
        <van-steps :active="judgeStep" active-color="#2563eb">
          <van-step>身份</van-step>
          <van-step>居住</van-step>
          <van-step>专业</van-step>
          <van-step>提交</van-step>
        </van-steps>

        <van-form class="form-card" @submit="submitJudge">
          <!-- 步骤0：身份 -->
          <div v-show="judgeStep === 0" class="step-pane">
            <h2>{{ judgeType === 'huaqiao' ? '华侨生·身份与户籍' : '国际生·身份与国籍' }}</h2>
            <van-field v-model="form.name" label="姓名" placeholder="请输入姓名" required autocomplete="name" />
            <van-field v-model="form.birth_date" label="出生日期" placeholder="YYYY-MM-DD" type="text" inputmode="numeric" />
            <van-field v-model="form.current_nationality" :label="judgeType === 'huaqiao' ? '当前国籍' : '当前外国国籍'" placeholder="如：中国 / 美国" />
            <van-field v-if="judgeType === 'international'" v-model="form.foreign_nationality_acquired_date" label="外国国籍取得日" placeholder="YYYY-MM-DD，建议填写" />
            <template v-if="judgeType === 'huaqiao'">
              <van-cell title="具有中国国籍"><template #right-icon><van-switch v-model="form.has_chinese_nationality" size="22" /></template></van-cell>
              <van-cell title="具有外国国籍"><template #right-icon><van-switch v-model="form.has_foreign_nationality" size="22" /></template></van-cell>
              <van-cell title="已定居国外"><template #right-icon><van-switch v-model="form.settled_abroad" size="22" /></template></van-cell>
              <van-cell title="仍有内地户籍"><template #right-icon><van-switch v-model="form.has_mainland_household" size="22" /></template></van-cell>
            </template>
            <template v-else>
              <van-cell title="具有外国国籍"><template #right-icon><van-switch v-model="form.has_foreign_nationality" size="22" /></template></van-cell>
              <van-cell title="仍具有中国国籍"><template #right-icon><van-switch v-model="form.has_chinese_nationality" size="22" /></template></van-cell>
              <van-cell title="已定居国外"><template #right-icon><van-switch v-model="form.settled_abroad" size="22" /></template></van-cell>
              <van-cell title="出生在外国"><template #right-icon><van-switch v-model="form.born_abroad" size="22" /></template></van-cell>
              <van-cell title="父母一方为中国公民"><template #right-icon><van-switch v-model="form.parent_chinese_citizen" size="22" /></template></van-cell>
              <van-cell title="出生时父母一方已定居外国"><template #right-icon><van-switch v-model="form.parent_settled_abroad_at_birth" size="22" /></template></van-cell>
              <van-cell title="仍有内地户籍"><template #right-icon><van-switch v-model="form.has_mainland_household" size="22" /></template></van-cell>
            </template>
          </div>

          <!-- 步骤1：居住 -->
          <div v-show="judgeStep === 1" class="step-pane">
            <h2>{{ judgeType === 'huaqiao' ? '华侨生·居住' : '国际生·居住与月数' }}</h2>
            <van-field v-model="form.permanent_residence_country" label="永久/长期居留地" placeholder="国家或地区" />
            <van-field v-model.number="form.overseas_residence_months_last_2y" label="近2年海外月数" type="number" inputmode="numeric" />
            <template v-if="judgeType === 'international'">
              <van-field v-model.number="form.overseas_residence_months_last_4y" label="近4年海外月数" type="number" inputmode="numeric" />
              <van-field v-model.number="form.annual_months_overseas" label="单年最高海外月数" type="number" inputmode="numeric" />
            </template>
          </div>

          <!-- 步骤2：专业与其它 -->
          <div v-show="judgeStep === 2" class="step-pane">
            <h2>推荐与补充</h2>
            <van-field v-model="form.intended_field" is-link readonly label="意向专业领域" placeholder="选择领域" @click="showFieldPicker = true" />
            <van-field v-model.number="form.score" label="分数/成绩" type="number" inputmode="numeric" placeholder="可选，0-750" />
            <van-field
              v-if="judgeType === 'international'"
              v-model="denationalizationInfo"
              label="退籍/国籍状态说明"
              type="textarea"
              rows="3"
              autosize
              placeholder="选填：户籍注销、退出中国国籍证书、使领馆说明等（将合并进复杂情况提交）"
            />
            <van-field v-model="form.complex_situation" label="复杂情况说明" type="textarea" rows="4" autosize placeholder="护照、出入境、作品集或其它说明" />
          </div>

          <!-- 步骤3：确认 -->
          <div v-show="judgeStep === 3" class="step-pane confirm-pane">
            <h2>确认提交</h2>
            <p class="confirm-hint">确认后将保存判定结果并生成院校推荐。</p>
            <div class="summary-card">
              <p><b>判定类型：</b>{{ judgeTypeLabel }}</p>
              <p><b>专业领域：</b>{{ form.intended_field || '未选择' }}</p>
              <p><b>分数/成绩：</b>{{ form.score ?? '未填写' }}</p>
            </div>
          </div>

          <div class="flow-actions">
            <van-button block round native-type="button" @click="prevStep" v-if="judgeStep > 0">上一步</van-button>
            <van-button block round type="primary" native-type="button" @click="nextStep" v-if="judgeStep < 3">下一步</van-button>
            <van-button block round type="primary" native-type="submit" :loading="loading" v-if="judgeStep === 3">开始判定</van-button>
          </div>
        </van-form>
      </section>

      <section v-if="tab === 'result'" class="result-screen" ref="resultRef">
        <template v-if="result">
          <div :class="['result-hero', result.result === 'PRELIMINARY_ELIGIBLE' ? 'pass' : result.result === 'MANUAL_REVIEW_REQUIRED' ? 'review' : 'fail']">
            <span>{{ result.result === 'PRELIMINARY_ELIGIBLE' ? '初步符合条件' : result.result === 'MANUAL_REVIEW_REQUIRED' ? '需要人工复核' : '初步不符合条件' }}</span>
            <h2>{{ result.conclusion }}</h2>
            <p>{{ result.eligibility_type === 'huaqiao' ? '华侨生资格初判' : '国际生资格初判' }}</p>
          </div>
          <van-cell-group inset title="详细判定理由">
            <van-cell v-for="(reason, index) in result.reasons" :key="index" :title="reason" />
          </van-cell-group>
          <van-cell-group v-if="result.suggestions?.length" inset title="系统建议">
            <van-cell v-for="(s, i) in result.suggestions" :key="'s' + i" :title="s" />
          </van-cell-group>
          <van-cell-group inset title="国籍法依据">
            <van-collapse v-model="activeLawNames">
              <van-collapse-item v-for="article in result.basis_articles" :key="article.number" :name="article.number" :title="`第${article.number}条：${article.title}`">
                <p>{{ article.text }}</p>
                <van-tag type="primary">解释</van-tag>
                <p>{{ article.explanation }}</p>
              </van-collapse-item>
            </van-collapse>
          </van-cell-group>
          <van-cell-group inset title="推荐大学">
            <div v-if="result.recommendations?.length" class="recommend-list">
              <article v-for="school in result.recommendations" :key="school.id" class="school-card">
                <div class="school-title"><b>#{{ school.ranking }} {{ school.name }}</b><van-tag plain>{{ school.province }}</van-tag></div>
                <p>{{ formatTags(school) }}</p>
                <p><b>领域：</b>{{ school.fields }}</p>
                <p><b>优势专业：</b>{{ school.advantage_majors }}</p>
                <p><b>招生时间：</b>{{ school.admission_timeline }}</p>
                <p><b>招生办：</b>{{ school.admissions_office || '以学校官方发布为准' }}</p>
                <p><b>邮箱：</b>{{ school.admission_email || '以学校官方发布为准' }}</p>
                <p v-if="school.match_reason" class="match-reason">{{ school.match_reason }}</p>
                <van-button size="small" type="primary" plain :url="school.admission_url || school.official_url">报考链接</van-button>
              </article>
            </div>
            <van-empty v-else description="暂无推荐结果" />
          </van-cell-group>
          <div class="sticky-actions no-capture">
            <van-button round block type="default" icon="service-o" @click="showConsult = true">一对一规划咨询</van-button>
            <van-button round block icon="down" :loading="savingImage" @click="saveResultImage">保存结果图</van-button>
            <van-button round block type="primary" icon="replay" @click="openJudge(result.eligibility_type)">重新判定</van-button>
            <van-button v-if="profileStudentId && getSaasToken()" round block type="success" @click="confirmProfileWriteback">确认写入学生档案</van-button>
          </div>
        </template>
        <van-empty v-else description="暂无判定结果" />
      </section>

      <section v-if="tab === 'profile'" class="list-screen">
        <StudentProfile @goto-judge="onGotoJudgeFromProfile" @goto-member="openPage('member')" />
      </section>

      <section v-if="tab === 'laws'" class="list-screen laws-screen">
        <van-search v-model="lawKeyword" placeholder="搜索国籍法/教外函政策" @search="loadLaws" @clear="loadLaws" />
        <div id="law-nationality-anchor" class="laws-anchor" aria-hidden="true" />
        <van-cell-group inset title="《中华人民共和国国籍法》">
          <van-collapse v-model="activeLawNames">
            <van-collapse-item v-for="law in laws" :key="law.number" :name="law.number" :title="`第${law.number}条：${law.title}`">
              <p>{{ law.text }}</p>
              <van-tag type="primary">解释</van-tag>
              <p>{{ law.explanation }}</p>
            </van-collapse-item>
          </van-collapse>
        </van-cell-group>
        <div id="law-policy-anchor" class="laws-anchor" aria-hidden="true" />
        <van-cell-group inset title="教外函〔2020〕12号">
          <article v-for="doc in policies" :key="doc.id" class="policy-card">
            <h3>{{ doc.title }}</h3>
            <p>{{ doc.authority }} · {{ doc.code }}</p>
            <p v-if="doc.focus" class="policy-focus">{{ doc.focus }}</p>
            <p>{{ doc.summary }}</p>
            <section v-for="section in doc.sections" :key="section.heading">
              <b>{{ section.heading }}</b>
              <p>{{ section.text }}</p>
            </section>
          </article>
        </van-cell-group>
      </section>

      <section v-if="tab === 'universities'" class="list-screen">
        <van-dropdown-menu>
          <van-dropdown-item v-model="targetFilter" :options="targetOptions" @change="onTargetFilterChange" />
          <van-dropdown-item v-model="univFieldFilter" :options="univFieldOptions" @change="loadUniversities" />
          <van-dropdown-item v-model="provinceFilter" :options="provinceOptions" @change="loadUniversities" />
          <van-dropdown-item v-model="tagFilter" :options="tagOptions" @change="loadUniversities" />
          <van-dropdown-item v-model="featureFilter" :options="featureOptions" @change="loadUniversities" />
        </van-dropdown-menu>
        <p v-if="universities.length && universities[0]?.locked_notice" class="locked-notice">{{ universities[0].locked_notice }}</p>
        <div class="card-list">
          <van-empty v-if="!universities.length" description="暂无院校数据，可调整筛选或稍后重试" />
          <article v-for="school in universities" :key="school.id" class="school-card">
            <div class="school-title"><b>#{{ school.ranking }} {{ school.name }}</b><van-tag>{{ school.province }}</van-tag></div>
            <p>{{ formatTags(school) }}</p>
            <p><b>领域：</b>{{ school.fields }}</p>
            <p><b>优势专业：</b>{{ school.advantage_majors }}</p>
            <p>{{ school.description }}</p>
            <p><b>招生办：</b>{{ school.admissions_office || '以学校官方发布为准' }}</p>
            <p><b>邮箱：</b>{{ school.admission_email || '以学校官方发布为准' }}</p>
            <p><b>电话：</b>{{ school.admission_phone || '以学校官方发布为准' }}</p>
            <van-button size="small" type="primary" plain :url="school.admission_url || school.official_url">招生官网</van-button>
          </article>
        </div>
      </section>

      <section v-if="tab === 'schedule'" class="list-screen">
        <van-dropdown-menu>
          <van-dropdown-item v-model="targetFilter" :options="targetOptions" @change="onTargetFilterChangeSchedule" />
          <van-dropdown-item v-model="monthFilter" :options="monthOptions" @change="loadSchedules" />
          <van-dropdown-item v-model="scheduleProvinceFilter" :options="provinceOptions" @change="loadSchedules" />
          <van-dropdown-item v-model="scheduleTagFilter" :options="tagOptions" @change="loadSchedules" />
          <van-dropdown-item v-model="scheduleFeatureFilter" :options="featureOptions" @change="loadSchedules" />
        </van-dropdown-menu>
        <van-empty v-if="!schedules.length" description="暂无招生时间轴数据，可调整筛选或稍后重试" />
        <div v-else class="card-list">
          <article v-for="item in schedules" :key="item.id || `${item.university_name}-${item.year}-${item.month}`" class="school-card">
            <h3 class="school-title"><b>#{{ item.ranking }} {{ item.university_name }}</b><van-tag plain>{{ item.year }}年{{ item.month }}月</van-tag></h3>
            <p>{{ item.province }} · {{ formatTags(item) }} · {{ item.fields }}</p>
            <p><b>报名：</b>{{ item.registration_time }}</p>
            <p><b>材料截止：</b>{{ item.material_deadline }}</p>
            <p><b>考试/审核：</b>{{ item.exam_time }}</p>
            <p v-if="item.reminder">{{ item.reminder }}</p>
          </article>
        </div>
      </section>

      <section v-if="tab === 'history'" class="list-screen">
        <van-pull-refresh v-model="refreshing" @refresh="loadRecords">
          <van-cell-group inset>
            <van-cell v-for="record in records" :key="record.record_id" :title="record.conclusion" :label="`${record.eligibility_type} · ${new Date(record.created_at).toLocaleString()}`">
              <template #value><van-tag :type="record.result === 'PRELIMINARY_ELIGIBLE' ? 'success' : record.result === 'MANUAL_REVIEW_REQUIRED' ? 'warning' : 'danger'">{{ record.result === 'PRELIMINARY_ELIGIBLE' ? '初步符合' : record.result === 'MANUAL_REVIEW_REQUIRED' ? '需人工复核' : '初步不符合' }}</van-tag></template>
            </van-cell>
          </van-cell-group>
        </van-pull-refresh>
      </section>

      <section v-if="tab === 'member'" class="list-screen member-screen">
        <van-cell-group v-if="!saasUser" inset title="登录 SaaS 会员">
          <van-field v-model="loginEmail" label="邮箱" placeholder="注册邮箱" />
          <van-field v-model="loginPassword" type="password" label="密码" placeholder="密码" />
          <div class="consult-actions" style="padding:12px;">
            <van-button block round type="primary" :loading="saasBusy" @click="doSaasLogin">登录</van-button>
          </div>
        </van-cell-group>
        <van-cell-group v-else inset :title="'您好，' + (saasUser.name || saasUser.email)">
          <van-cell title="当前套餐" :value="saasUser.plan_code + (saasUser.paid ? '（在期）' : '')" />
          <van-cell title="全量院校库" :value="saasUser.features?.full_elite_university_library ? '已开通' : '未开通'" />
          <van-cell title="专家咨询" :value="saasUser.features?.one_on_one_expert ? '已开通' : '未开通'" />
          <van-cell title="智能时间轴" :value="saasUser.features?.full_timeline_reminders ? '已开通' : '年/三年会员'" />
          <div class="consult-actions" style="padding:12px;">
            <van-button block round type="danger" @click="doSaasLogout">退出登录</van-button>
          </div>
        </van-cell-group>

        <van-divider>订阅开通（mock 支付）</van-divider>
        <van-cell-group inset>
          <van-cell title="月会员" value="¥799/30天" is-link @click="buySaasPlan('vip_month')" />
          <van-cell title="年会员" value="¥999/年" is-link @click="buySaasPlan('vip_year')" />
          <van-cell title="三年会员" value="¥1999/三年" is-link @click="buySaasPlan('vip_three_year')" />
          <van-field v-model="redeemCode" label="卡密兑换" placeholder="PRO-…" />
          <van-button block round :loading="saasBusy" @click="doRedeem">兑换卡密</van-button>
        </van-cell-group>

        <van-divider>客户资料库</van-divider>
        <van-cell-group v-if="saasUser?.features?.customer_vault_cloud" inset>
          <van-field v-model="vaultJson.family_note" label="家庭信息" type="textarea" rows="2" autosize />
          <van-field v-model="vaultJson.child_identity" label="子女身份/国籍" type="textarea" rows="2" autosize />
          <van-field v-model="vaultJson.residence_note" label="居住记录" type="textarea" rows="2" autosize />
          <van-field v-model="vaultJson.goal_note" label="升学目标" type="textarea" rows="2" autosize />
          <van-field v-model="vaultJson.intended_major" label="意向专业" />
          <van-field v-model="vaultJson.target_schools" label="目标院校" type="textarea" rows="2" autosize />
          <van-button block round type="primary" :loading="vaultSaving" @click="saveVaultProfile">保存（云端加密+本地）</van-button>
        </van-cell-group>
        <van-empty v-else-if="saasUser" description="开通会员后可云端加密保存资料" />

        <van-divider>一对一专家咨询</van-divider>
        <van-cell-group v-if="saasUser?.features?.one_on_one_expert" inset>
          <van-field v-model="expertForm.title" label="主题" />
          <van-field v-model="expertForm.question" type="textarea" rows="3" autosize label="问题" />
          <van-field v-model="expertForm.personalization" type="textarea" rows="3" autosize label="个性化需求" />
          <van-field v-model="expertForm.contact_phone" label="电话" />
          <van-field v-model="expertForm.contact_email" label="邮箱" />
          <van-field v-model="expertForm.contact_wechat" label="微信" />
          <van-button block round type="primary" :loading="expertSubmitting" @click="submitExpertConsult">提交工单（智能AI助手撰写初稿）</van-button>
          <van-cell v-for="c in expertList" :key="c.id" :title="c.title || '咨询'" :label="expertStatusLabel(c.status)" is-link @click="openExpertDetail(c.id)" />
        </van-cell-group>
        <van-empty v-else-if="saasUser" description="开通会员后可提交专家工单" />

        <van-divider v-if="saasUser?.features?.full_timeline_reminders">升学节点提醒</van-divider>
        <van-cell-group v-if="saasUser?.features?.full_timeline_reminders" inset>
          <van-cell v-for="r in reminderList" :key="r.id" :title="r.title" :label="new Date(r.remind_at).toLocaleString() + ' · ' + r.category" />
        </van-cell-group>

        <van-popup v-model:show="expertDetailShow" round position="bottom" :style="{ height: '70%' }">
          <div class="consult-sheet" v-if="expertDetail">
            <h3>咨询进度</h3>
            <p>状态：{{ expertDetail.status }}</p>
            <p v-if="expertDetail.message">{{ expertDetail.message }}</p>
            <van-divider>正式报告（审核下发后可见）</van-divider>
            <p style="white-space:pre-wrap;">{{ expertDetail.final_report || '（尚无正式稿）' }}</p>
            <van-button block round @click="expertDetailShow = false">关闭</van-button>
          </div>
        </van-popup>
      </section>
    </main>

    <van-tabbar v-model="tab" fixed safe-area-inset-bottom @change="onTabChange">
      <van-tabbar-item name="home" icon="home-o">首页</van-tabbar-item>
      <van-tabbar-item name="universities" icon="wap-home-o">大学</van-tabbar-item>
      <van-tabbar-item name="schedule" icon="underway-o">时间</van-tabbar-item>
      <van-tabbar-item name="member" icon="vip-card-o">会员</van-tabbar-item>
      <van-tabbar-item name="history" icon="records-o">历史</van-tabbar-item>
    </van-tabbar>

    <van-popup v-model:show="showFieldPicker" round position="bottom">
      <van-picker :columns="fieldColumns" @cancel="showFieldPicker = false" @confirm="selectField" />
    </van-popup>

    <van-popup v-model:show="showConsult" round position="bottom" :style="{ height: '85%' }" class="consult-popup">
      <div class="consult-sheet">
        <h3 class="consult-sheet-title">一对一规划咨询</h3>
        <van-cell-group inset>
          <van-cell title="机构" :value="consultBrand.orgName" />
          <van-cell title="联系人" :value="consultBrand.contactName" />
          <van-cell title="邮箱" :value="consultBrand.email" />
          <van-cell title="微信" :value="consultBrand.wechat" />
          <van-cell title="电话" :value="consultBrand.phone" />
        </van-cell-group>
        <p class="consult-extra">{{ consultBrand.extraNote }}</p>
        <van-divider>您的预留信息（选填）</van-divider>
        <van-field v-model="guestLead.name" label="姓名" placeholder="选填" />
        <van-field v-model="guestLead.phone" label="电话" placeholder="选填" />
        <van-field v-model="guestLead.email" label="邮箱" placeholder="选填" />
        <van-field v-model="guestLead.wechat" label="微信" placeholder="选填" />
        <van-field v-model="guestLead.note" label="需求" type="textarea" rows="2" autosize placeholder="目标年份、院校、当前身份等" />
        <div class="consult-actions">
          <van-button block round type="primary" :loading="consultSubmitting" @click="submitConsultToServer">提交咨询请求</van-button>
          <van-button block round type="default" @click="copyConsult">复制咨询信息</van-button>
          <van-button block round @click="showConsult = false">关闭</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { showFailToast, showLoadingToast, showSuccessToast } from 'vant'
import html2canvas from 'html2canvas'
import {
  accessibleStudents,
  activeStudentId,
  activeStudentLabel,
  clearActiveStudent,
  normalizeStudentId,
  setActiveStudentId,
  switchActiveStudent,
  syncStudentsAndActive,
} from './activeStudent'
import { api } from './api'
import { getSaasToken, saasApi, setSaasToken } from './saasApi'
import StudentProfile from './StudentProfile.vue'

const VAULT_LOCAL_KEY = 'hq_customer_vault_v1'

const tab = ref('home')
const historyStack = ref(['home'])
const darkMode = ref(localStorage.getItem('mobile-theme') === 'dark')
const eligibilityContext = ref('international')
const judgeType = ref('international')
const judgeStep = ref(0)
const loading = ref(false)
const savingImage = ref(false)
const result = ref(null)
const resultRef = ref(null)
const activeLawNames = ref([])
const laws = ref([])
const policies = ref([])
const lawKeyword = ref('')
const universities = ref([])
const schedules = ref([])
const records = ref([])
const refreshing = ref(false)
const showFieldPicker = ref(false)
const showConsult = ref(false)
const denationalizationInfo = ref('')
const targetFilter = ref('international')
const univFieldFilter = ref('')
const provinceFilter = ref('')
const tagFilter = ref('')
const featureFilter = ref('')
const scheduleProvinceFilter = ref('')
const scheduleTagFilter = ref('')
const scheduleFeatureFilter = ref('')
const monthFilter = ref('')
const touchX = ref(0)

const consultBrand = {
  orgName: '（请修改为机构名称）',
  contactName: '（顾问姓名）',
  email: 'your-service@example.com',
  wechat: '（微信号）',
  phone: '（电话）',
  extraNote: '可补充工作时间、办公地址等。发布前务必改成真实联系方式。',
}
const guestLead = ref({ name: '', phone: '', email: '', wechat: '', note: '' })
const consultSubmitting = ref(false)
const APP_VERSION = '1.0.0'

const saasUser = ref(null)
const loginEmail = ref('')
const loginPassword = ref('')
const saasBusy = ref(false)
const redeemCode = ref('')
function vaultDefaults() {
  return { family_note: '', child_identity: '', residence_note: '', goal_note: '', intended_major: '', target_schools: '' }
}
const vaultJson = ref(vaultDefaults())
const vaultSaving = ref(false)
const expertForm = ref({ title: '', question: '', personalization: '', contact_phone: '', contact_email: '', contact_wechat: '' })
const expertList = ref([])
const expertSubmitting = ref(false)
const expertDetailShow = ref(false)
const expertDetail = ref(null)
const expertDetailLoading = ref(false)
const reminderList = ref([])
const profileStudentId = activeStudentId
const showHomeStudentPicker = ref(false)
const pickerEpoch = ref(0)
const studentSwitcherList = computed(() => accessibleStudents.value.slice())
const currentStudentId = computed(() => normalizeStudentId(activeStudentId.value))
const currentStudentLabel = computed(() => activeStudentLabel.value)
const homeStudentColumns = computed(() => studentSwitcherList.value.map(s => ({
  text: s.display_name || `学生 #${s.id}`,
  value: normalizeStudentId(s.id),
})))
const homePickerSelectedValues = computed(() => {
  const id = currentStudentId.value
  return id != null ? [id] : []
})

async function refreshStudentSwitcher() {
  if (!getSaasToken()) return
  try {
    const r = await saasApi.students()
    syncStudentsAndActive(r.students || [])
  } catch { /* ignore */ }
}
function openHomeStudentPicker() {
  pickerEpoch.value += 1
  showHomeStudentPicker.value = true
}
function extractPickerStudentId(payload) {
  if (payload == null) return null
  // Vant 4 object payload
  const fromOpt = payload?.selectedOptions?.[0]
  if (fromOpt && typeof fromOpt === 'object') {
    const id = normalizeStudentId(fromOpt.value ?? fromOpt.id)
    if (id != null) return id
  }
  const fromValues = payload?.selectedValues?.[0]
  const fromValuesId = normalizeStudentId(fromValues)
  if (fromValuesId != null) return fromValuesId
  // Legacy: confirm may pass array of values / options directly
  if (Array.isArray(payload)) {
    const first = payload[0]
    if (first && typeof first === 'object') {
      return normalizeStudentId(first.value ?? first.id)
    }
    return normalizeStudentId(first)
  }
  return normalizeStudentId(payload)
}
function onHomePickStudent(payload) {
  showHomeStudentPicker.value = false
  const id = extractPickerStudentId(payload)
  if (id == null) {
    showFailToast('请选择有效学生档案')
    return
  }
  if (id === currentStudentId.value) return
  const beforeCount = accessibleStudents.value.length
  if (!switchActiveStudent(id)) {
    showFailToast('无法切换到该学生')
    return
  }
  if (accessibleStudents.value.length !== beforeCount) {
    refreshStudentSwitcher()
  }
}

const fieldValues = ['综合', '理工', '文史', '医药', '体育', '音乐', '美术', '设计']
const fieldColumns = fieldValues.map(text => ({ text, value: text }))
const univFieldOptions = [{ text: '全部领域', value: '' }, ...fieldValues.map(text => ({ text, value: text }))]
const targetOptions = [{ text: '国际生', value: 'international' }, { text: '华侨生', value: 'huaqiao' }]
const provinceOptions = ['全部地区','北京','上海','天津','重庆','广东','江苏','浙江','湖北','湖南','陕西','四川','山东','福建','辽宁','吉林','黑龙江','安徽','河南','河北','山西','内蒙古','江西','广西','海南','贵州','云南','西藏','甘肃','青海','宁夏','新疆'].map(text => ({ text, value: text === '全部地区' ? '' : text }))
const tagOptions = ['全部层级','C9','双一流','985','211'].map(text => ({ text, value: text === '全部层级' ? '' : text }))
const featureOptions = ['全部特色','体育','音乐','艺术','师范'].map(text => ({ text, value: text === '全部特色' ? '' : text }))
const monthOptions = [{ text: '全部月份', value: '' }, ...Array.from({ length: 12 }, (_, i) => ({ text: `${i + 1}月`, value: i + 1 }))]
const pendingLawScroll = ref(null)

const form = ref(defaultForm('international'))
const navTitle = computed(() => ({ home: '国际生/华侨生资格判定', judge: judgeType.value === 'huaqiao' ? '华侨生判定' : '国际生判定', result: '判定结果', laws: '政策与法规', universities: '大学库', schedule: '招生时间轴', member: '会员中心', history: '历史记录', profile: '学生档案' }[tab.value]))
const judgeTypeLabel = computed(() => judgeType.value === 'huaqiao' ? '华侨生' : '国际生')

watch(targetFilter, (v) => { eligibilityContext.value = v })

function defaultForm(type) {
  const base = {
    name: '',
    birth_date: '',
    current_nationality: '',
    foreign_nationality_acquired_date: '',
    settled_abroad: true,
    permanent_residence_country: '',
    overseas_residence_months_last_2y: type === 'huaqiao' ? 18 : 0,
    overseas_residence_months_last_4y: type === 'international' ? 24 : 0,
    annual_months_overseas: type === 'international' ? 9 : 0,
    has_mainland_household: false,
    parent_chinese_citizen: false,
    parent_settled_abroad_at_birth: false,
    born_abroad: false,
    passport_info: '',
    household_info: '',
    complex_situation: '',
    intended_field: '综合',
    score: null,
  }
  if (type === 'huaqiao') {
    return { ...base, has_chinese_nationality: true, has_foreign_nationality: false }
  }
  return { ...base, has_chinese_nationality: false, has_foreign_nationality: true }
}

function formatTags(school) {
  const raw = `${school.tags || ''},${school.fields || ''},${school.university_type || ''}`
  return ['C9', '双一流', '985', '211', '体育', '音乐', '艺术', '师范'].filter(t => t === '211' ? raw.includes('211') || raw.includes('纯211') : t === '艺术' ? ['艺术', '美术', '设计'].some(x => raw.includes(x)) : raw.includes(t)).join(' / ')
}

function syncHtmlDark() {
  document.documentElement.classList.toggle('dark', darkMode.value)
}

function persistTheme() {
  localStorage.setItem('mobile-theme', darkMode.value ? 'dark' : 'light')
  syncHtmlDark()
}

function copyConsult() {
  const b = consultBrand
  const g = guestLead.value
  const lines = [
    '【一对一规划咨询】',
    `机构：${b.orgName}`,
    `联系人：${b.contactName}`,
    `邮箱：${b.email}`,
    `微信：${b.wechat}`,
    `电话：${b.phone}`,
    b.extraNote,
    '',
    '—— 客户预留 ——',
    `姓名：${g.name || '（未填）'}`,
    `电话：${g.phone || '（未填）'}`,
    `邮箱：${g.email || '（未填）'}`,
    `微信：${g.wechat || '（未填）'}`,
    `需求：${g.note || '（未填）'}`,
  ]
  navigator.clipboard.writeText(lines.join('\n')).then(() => showSuccessToast('已复制')).catch(() => showFailToast('复制失败，请长按选择'))
}

function getClientId() {
  let id = localStorage.getItem('mobile-client-id')
  if (!id) {
    id = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `c-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`
    localStorage.setItem('mobile-client-id', id)
  }
  return id
}

function detectPlatform() {
  const ua = navigator.userAgent || ''
  if (/Android/i.test(ua)) return 'android'
  if (/iPhone|iPad|iPod/i.test(ua)) return 'ios'
  return 'h5'
}

async function submitConsultToServer() {
  const g = guestLead.value
  if (!g.name?.trim() && !g.phone?.trim() && !g.email?.trim() && !g.wechat?.trim() && !g.note?.trim()) {
    showFailToast('请至少填写一项联系方式或需求')
    return
  }
  consultSubmitting.value = true
  try {
    await api.submitConsultation({
      client_id: getClientId(),
      name: g.name,
      phone: g.phone,
      email: g.email,
      wechat: g.wechat,
      note: g.note,
    })
    showSuccessToast('已提交，顾问将尽快与您联系')
    guestLead.value = { name: '', phone: '', email: '', wechat: '', note: '' }
  } catch (error) {
    showFailToast(error.message || '提交失败')
  } finally {
    consultSubmitting.value = false
  }
}

function pushTab(name) { if (tab.value !== name) historyStack.value.push(name); tab.value = name }

function openPage(name) {
  if (name === 'universities' || name === 'schedule') {
    targetFilter.value = eligibilityContext.value
  }
  if (name === 'profile' || name === 'home') {
    refreshStudentSwitcher()
  }
  pushTab(name)
  onTabChange(name)
}

function expertStatusLabel(s) {
  const m = { pending_ai: '初稿生成中', draft_ready: '待审核', in_review: '审核中', published: '已发布', archived: '已归档', ai_failed: '处理异常' }
  return m[s] || s
}

async function refreshSaasUser() {
  if (!getSaasToken()) {
    saasUser.value = null
    return
  }
  try {
    saasUser.value = await saasApi.me()
  } catch {
    setSaasToken('')
    saasUser.value = null
  }
}

async function doSaasLogin() {
  saasBusy.value = true
  try {
    const r = await saasApi.login(loginEmail.value, loginPassword.value)
    setSaasToken(r.token)
    saasUser.value = r.user
    showSuccessToast('登录成功')
    await refreshStudentSwitcher()
    await loadVaultFromSources()
    await loadExpertList()
    await loadReminders()
    await loadUniversities()
    await loadSchedules()
  } catch (error) {
    showFailToast(error.message || '登录失败')
  } finally {
    saasBusy.value = false
  }
}

function doSaasLogout() {
  setSaasToken('')
  saasUser.value = null
  clearActiveStudent()
  expertList.value = []
  reminderList.value = []
}

async function buySaasPlan(plan_code) {
  if (!getSaasToken()) {
    showFailToast('请先登录')
    return
  }
  saasBusy.value = true
  try {
    const o = await saasApi.createPayment(plan_code, 'mock')
    await saasApi.mockPay(o.order_no)
    await refreshSaasUser()
    showSuccessToast('已开通（模拟支付）')
    await loadVaultFromSources()
    await loadExpertList()
    await loadReminders()
    await loadUniversities()
    await loadSchedules()
  } catch (error) {
    showFailToast(error.message || '支付失败')
  } finally {
    saasBusy.value = false
  }
}

async function doRedeem() {
  if (!getSaasToken()) {
    showFailToast('请先登录')
    return
  }
  if (!redeemCode.value?.trim()) {
    showFailToast('请输入卡密')
    return
  }
  saasBusy.value = true
  try {
    const r = await saasApi.redeem(redeemCode.value.trim())
    if (r.user) saasUser.value = r.user
    else await refreshSaasUser()
    showSuccessToast(r.message || '兑换成功')
    redeemCode.value = ''
    await loadVaultFromSources()
    await loadExpertList()
    await loadReminders()
    await loadUniversities()
    await loadSchedules()
  } catch (error) {
    showFailToast(error.message || '兑换失败')
  } finally {
    saasBusy.value = false
  }
}

async function loadVaultFromSources() {
  const merged = { ...vaultDefaults(), ...JSON.parse(localStorage.getItem(VAULT_LOCAL_KEY) || '{}') }
  vaultJson.value = merged
  if (!getSaasToken() || !saasUser.value?.features?.customer_vault_cloud) return
  try {
    const r = await saasApi.vaultGet()
    if (r.profile && typeof r.profile === 'object' && Object.keys(r.profile).length) {
      vaultJson.value = { ...vaultJson.value, ...r.profile }
    }
  } catch {
    /* 未开通或 402 */
  }
}

async function saveVaultProfile() {
  const payload = { ...vaultJson.value }
  localStorage.setItem(VAULT_LOCAL_KEY, JSON.stringify(payload))
  if (!getSaasToken()) {
    showSuccessToast('已保存至本机')
    return
  }
  if (!saasUser.value?.features?.customer_vault_cloud) {
    showSuccessToast('已保存至本机（开通会员后可同步加密云端）')
    return
  }
  vaultSaving.value = true
  try {
    await saasApi.vaultPut({ profile: payload })
    showSuccessToast('已保存本机并同步加密云端')
  } catch (error) {
    showFailToast(error.message || '云端保存失败')
  } finally {
    vaultSaving.value = false
  }
}

async function loadExpertList() {
  if (!getSaasToken() || !saasUser.value?.features?.one_on_one_expert) {
    expertList.value = []
    return
  }
  try {
    expertList.value = await saasApi.expertList()
  } catch {
    expertList.value = []
  }
}

async function loadReminders() {
  if (!getSaasToken() || !saasUser.value?.features?.full_timeline_reminders) {
    reminderList.value = []
    return
  }
  try {
    reminderList.value = await saasApi.reminders()
  } catch {
    reminderList.value = []
  }
}

async function submitExpertConsult() {
  expertSubmitting.value = true
  try {
    await saasApi.expertCreate({ ...expertForm.value })
    showSuccessToast('已提交')
    expertForm.value = { title: '', question: '', personalization: '', contact_phone: '', contact_email: '', contact_wechat: '' }
    await loadExpertList()
  } catch (error) {
    showFailToast(error.message || '提交失败')
  } finally {
    expertSubmitting.value = false
  }
}

async function openExpertDetail(id) {
  expertDetailLoading.value = true
  try {
    expertDetail.value = await saasApi.expertDetail(id)
    expertDetailShow.value = true
  } catch (error) {
    showFailToast(error.message || '加载失败')
  } finally {
    expertDetailLoading.value = false
  }
}

async function openConsultWithGate() {
  if (!getSaasToken()) {
    showFailToast('请先在会员中心登录')
    openPage('member')
    return
  }
  await refreshSaasUser()
  if (!saasUser.value?.features?.one_on_one_expert) {
    showFailToast('一对一专家咨询仅对付费会员开放')
    openPage('member')
    return
  }
  openPage('member')
}

function openLawsNationality() {
  pendingLawScroll.value = 'nationality'
  openPage('laws')
}

function openLawsPolicy() {
  pendingLawScroll.value = 'policy'
  openPage('laws')
}

function openJudge(type, prefills) {
  eligibilityContext.value = type
  judgeType.value = type
  judgeStep.value = 0
  denationalizationInfo.value = ''
  form.value = { ...defaultForm(type), ...(prefills || {}) }
  pushTab('judge')
}

function onGotoJudgeFromProfile(payload) {
  setActiveStudentId(payload.studentId, { allowUnknown: true })
  openJudge(payload.kind, payload.prefills)
}

function onTargetFilterChange() {
  eligibilityContext.value = targetFilter.value
  loadUniversities()
}

function onTargetFilterChangeSchedule() {
  eligibilityContext.value = targetFilter.value
  loadSchedules()
}

function goBack() {
  if (tab.value === 'judge' && judgeStep.value > 0) {
    judgeStep.value -= 1
    return
  }
  if (historyStack.value.length > 1) {
    historyStack.value.pop()
    tab.value = historyStack.value.at(-1) || 'home'
    return
  }
  tab.value = 'home'
}

function touchStart(event) { touchX.value = event.changedTouches[0].clientX }
function touchEnd(event) {
  const dx = event.changedTouches[0].clientX - touchX.value
  if (touchX.value < 30 && dx > 80) goBack()
}

function nextStep() {
  if (judgeStep.value === 0 && !form.value.name) {
    showFailToast('请先填写姓名')
    return
  }
  judgeStep.value += 1
}

function prevStep() { judgeStep.value = Math.max(0, judgeStep.value - 1) }

function selectField({ selectedOptions }) {
  form.value.intended_field = selectedOptions[0]?.value || '综合'
  showFieldPicker.value = false
}

async function submitJudge() {
  loading.value = true
  eligibilityContext.value = judgeType.value
  const toast = showLoadingToast({ message: '正在判定...', forbidClick: true, duration: 0 })
  try {
    let complex = form.value.complex_situation || ''
    if (judgeType.value === 'international' && denationalizationInfo.value.trim()) {
      complex = [complex, `【退籍/国籍状态说明】${denationalizationInfo.value.trim()}`].filter(Boolean).join('\n')
    }
    const payload = { ...form.value, complex_situation: complex }
    result.value = judgeType.value === 'huaqiao' ? await api.judgeHuaqiao(payload) : await api.judgeInternational(payload)
    if (profileStudentId.value && getSaasToken()) {
      try {
        await saasApi.studentWriteback(profileStudentId.value, {
          kind: judgeType.value,
          result: result.value.result,
          conclusion: result.value.conclusion || result.value.explanation,
          record_id: result.value.record_id,
          policy_version: 'R4.2',
          confirm: false,
        })
      } catch { /* 档案写回失败不影响判定展示 */ }
    }
    pushTab('result')
    await loadRecords()
    showSuccessToast('判定完成')
  } catch (error) {
    showFailToast(error.message)
  } finally {
    toast.close()
    loading.value = false
  }
}

async function confirmProfileWriteback() {
  if (!profileStudentId.value || !result.value) {
    showFailToast('没有可写入的档案')
    return
  }
  try {
    await saasApi.studentWriteback(profileStudentId.value, {
      kind: result.value.eligibility_type || judgeType.value,
      result: result.value.result,
      conclusion: result.value.conclusion || result.value.explanation,
      record_id: result.value.record_id,
      policy_version: 'R4.2',
      confirm: true,
    })
    showSuccessToast('已确认写入学生档案')
    pushTab('profile')
  } catch (error) {
    showFailToast(error.message || '写入失败')
  }
}

async function loadLaws() {
  laws.value = await api.laws(lawKeyword.value)
  policies.value = await api.policies(lawKeyword.value)
}

async function loadUniversities() {
  const filters = { province: provinceFilter.value, tag: tagFilter.value, feature: featureFilter.value }
  try {
    universities.value = await saasApi.universities(targetFilter.value, univFieldFilter.value, filters)
  } catch (error) {
    try {
      const all = await api.universities(targetFilter.value, univFieldFilter.value, filters)
      universities.value = all.slice(0, 8).map((u) => ({ ...u, locked_notice: u.locked_notice || 'SaaS 不可用时仅展示部分院校' }))
    } catch {
      showFailToast(error.message || '院校加载失败')
      universities.value = []
    }
  }
}

async function loadSchedules() {
  const filters = { province: scheduleProvinceFilter.value, tag: scheduleTagFilter.value, feature: scheduleFeatureFilter.value }
  try {
    schedules.value = await saasApi.schedules(targetFilter.value, monthFilter.value, filters)
  } catch (error) {
    try {
      schedules.value = await api.schedules(targetFilter.value, monthFilter.value, filters)
    } catch {
      showFailToast(error.message || '招生时间加载失败')
      schedules.value = []
    }
  }
}

async function loadRecords() {
  records.value = await api.records()
  refreshing.value = false
}

async function onTabChange(name = tab.value) {
  if (!historyStack.value.includes(name)) historyStack.value.push(name)
  if (name === 'universities' || name === 'schedule') {
    targetFilter.value = eligibilityContext.value
  }
  if (name === 'member') {
    await refreshSaasUser()
    await loadVaultFromSources()
    await loadExpertList()
    await loadReminders()
  }
  if (name === 'laws') {
    await loadLaws()
    const which = pendingLawScroll.value
    pendingLawScroll.value = null
    if (which) {
      await nextTick()
      const id = which === 'policy' ? 'law-policy-anchor' : 'law-nationality-anchor'
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }
  if (name === 'universities') await loadUniversities()
  if (name === 'schedule') await loadSchedules()
  if (name === 'history') await loadRecords()
}

async function saveResultImage() {
  if (!resultRef.value) return
  savingImage.value = true
  await nextTick()
  try {
    const hidden = resultRef.value.querySelectorAll('.no-capture')
    hidden.forEach(item => { item.style.display = 'none' })
    const bg = darkMode.value ? '#0b1120' : '#e4eaf4'
    const canvas = await html2canvas(resultRef.value, { backgroundColor: bg, scale: Math.min(window.devicePixelRatio || 2, 3), useCORS: true })
    hidden.forEach(item => { item.style.display = '' })
    const url = canvas.toDataURL('image/png')
    const link = document.createElement('a')
    link.download = `资格判定结果-${Date.now()}.png`
    link.href = url
    link.click()
    showSuccessToast('已生成图片，请在系统下载/相册中查看')
  } catch (error) {
    showFailToast('保存失败，请重试')
  } finally {
    savingImage.value = false
  }
}

onMounted(async () => {
  syncHtmlDark()
  api.telemetrySession({
    client_id: getClientId(),
    app_version: APP_VERSION,
    platform: detectPlatform(),
  })
  await refreshSaasUser()
  await refreshStudentSwitcher()
  await Promise.all([loadLaws(), loadUniversities(), loadSchedules(), loadRecords()])
})
</script>
