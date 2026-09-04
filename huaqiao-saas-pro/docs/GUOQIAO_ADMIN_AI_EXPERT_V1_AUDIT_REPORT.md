# GUOQIAO_ADMIN_AI_EXPERT_V1_AUDIT_REPORT

> Phase 1 — 只读审计 + 架构 + Admin V1 scaffold proposal  
> 审计日期：2026-09-04  
> 生产基线分支：`cursor/mobile-cloud-preview`  
> 本轮：**PRODUCTION_CHANGED=NO / DATABASE_CHANGED=NO / CNBER_CHANGED=NO / MAIN_CHANGED=NO**

---

## 1. 审计结论（一句话）

当前**没有**可上线的国侨升学运营/顾问后台；仅有 SaaS 内嵌「管理员 Tab」+ Free 栈 `ADMIN_TOKEN` 咨询页。学生主档、专家咨询版本流、OpenAI-compatible AI 配置均已存在，可复用；缺 Student 360 / 角色分层 / `student_id` 绑定咨询 / 持久化审计 / 独立 `huaqiao-admin`。

---

## 2. 存在性检查清单

| 能力 | 状态 | 位置 / 说明 |
|------|------|-------------|
| admin frontend（真正运营后台） | **NO** | 无 `huaqiao-admin/`；无 `admin.guoqiaoplan.com` 部署/DNS 配置 |
| 嵌入式 admin UI | **PARTIAL** | `huaqiao-saas-pro/frontend`：`user.role==='admin'` 时「后台管理」Tab — 用户/套餐/卡密/粗统计，无 Student 360 |
| legacy Free admin | **YES（隔离栈）** | `backend/static/admin.html` + `ADMIN_TOKEN` — 咨询线索，非 SaaS 学生运营 |
| admin routes（SaaS） | **YES（窄）** | `/api/admin/users|stats|plans|recharge-codes|expert-consultations|customer-vaults|timeline-reminders|students/{id}/restore` |
| admin auth | **YES（单角色）** | JWT + `require_admin`（`role == "admin"`） |
| admin role | **YES** | `users.role = "admin"`；另有 `permissions` JSON（如 `sensitive_data_access`） |
| consultant role | **NO** | 无 `consultant` |
| support role | **NO** | 无 `support` |
| student management UI（运营侧） | **NO** | 学生 CRUD 仅在学生端 `huaqiao-app` + `/api/students/*`（owner 隔离） |
| customer service UI | **NO** | 无客服工作台；仅有 vault 管理员解密读 |
| AI planning backend | **PARTIAL** | `expert_report.py` / `expert_tasks.py`：一对一咨询 AI 初稿，非 Student 360 规划工作台 |
| AI provider integration | **YES（单一 OpenAI-compatible）** | `ai_api_key` / `ai_base_url` / `ai_model` → `POST {base}/chat/completions`；无 key 则本地模板 fallback |

---

## 3. 数据库表审计（schema 已存在）

| 表 | 存在 | 运营后台可直接复用程度 |
|----|------|------------------------|
| `users` | YES | 高 — 用户管理 / Trial(`plan_code`+`membership_until`) |
| `tenants` | YES | 高 — 租户维度 |
| `student_master_profiles` | YES | 高 — 学生列表 + 360 主对象（按 `id`） |
| `student_timeline_items` | YES | 高 — 已按 `student_id` 隔离 |
| `eligibility_records` | YES | 中 — 当前绑定 `user_id`/`tenant_id`，**无 `student_id`** |
| `customer_vaults` | YES | 中 — 按 `user_id` 一户一库（会员级），非 per-student |
| `membership_plans` / `orders` | YES | 高 — Dashboard / 付费态 |
| `expert_consultations` | YES | 中 — 有 draft/publish/review；**缺 `student_id`、assignee、provider 字段** |
| `consultation_report_versions` | YES | 高 — 版本化已通 |
| `member_timeline_reminders` | YES | 中 — 用户级提醒，非 student 级 |

DB revision 基线：`006_student_profile_slots`（与生产一致）。

---

## 4. 可直接复用的现有能力

### 4.1 后端 API（REUSABLE）

- `GET/PATCH /api/admin/users*`、`/stats`、`/plans`、`/recharge-codes`
- `GET/PATCH /api/admin/expert-consultations*`（列表/详情/编辑终稿/发布）
- `GET /api/admin/customer-vaults/{uid}`（管理员解密读 — **需收紧权限与脱敏**）
- `POST /api/admin/students/{student_id}/restore`
- timeline reminders admin CRUD
- 学生端 `/api/students/*` 的 **owner + tenant 隔离模式**（Admin 侧应镜像为 `student_id` 强制过滤，禁止跨档）
- Trial 判定逻辑：`membership_trial` / `trial_info` / `is_paid`（Dashboard Trial 指标）

### 4.2 专家咨询流（EXISTING_EXPERT_CONSULTATION）

流程已在代码层存在：

`member create` → `pending_ai` → AI 生成 `ai_draft` → admin PATCH `final_report`（写 version）→ `status=published`

适合作为 **AI GENERATE → consultant review → edit → approve → send** 的骨架。

### 4.3 报告版本（EXISTING_REPORT_VERSIONING）

`consultation_report_versions`：`version_no` / `content` / `source`(`ai`|`admin_edit`) / `editor_user_id` / `created_at` — **优先复用，勿另造版本表**。

### 4.4 AI Provider（EXISTING_AI_PROVIDER）

- Env：`AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL`（Settings：`ai_*`）
- 实现：OpenAI-compatible `chat/completions`
- Secret 已在 backend env — **前端不得持有**
- V1 建议：抽象一层 `AIProvider`（OpenAI-compatible / DeepSeek / DashScope / Doubao / custom），**只接线一个 OpenAI-compatible 实现**

### 4.5 隐私（可复用思路）

- Vault Fernet 加密（`customer_vaults` / `student_master_profiles.cipher_blob`）
- 成员侧脱敏 + `sensitive_data_access` permission
- 日志 redact（`log_redaction` / `redact_log_message`）

### 4.6 审计（可复用思路，实现不足）

- `AuditLogger` + `AuditAction`（含 `ADMIN_ACCESS_PROFILE` 等）
- 中间件对 `/api/admin/*` 轻量记录
- **缺口**：多为进程内内存 / 日志，非持久化审计表；AI 生成/发布未完整入审计

---

## 5. 缺口（MISSING_ADMIN_APIS — 提案，本轮不实现）

1. **Dashboard V1**：总用户 / Trial / 付费 / Trial 即将到期 / 学生档案数 / 待人工审核 / 最近咨询  
2. **用户详情**：学生数量、Trial 态、套餐与到期聚合  
3. **学生管理**：全站/按租户列出 `student_master_profiles` + 搜索（`display_name` / owner email）  
4. **Student 360**：按 `student_id` 聚合 profile 解密视图（脱敏）、timeline、eligibility（若可关联）、consultations、顾问备注  
5. **AI Expert Workspace**：按 `student_id` 触发多模板生成（画像/资格风险/选校/冲稳保/材料缺口/路线/时间线/本周行动/家长报告/一对一报告）→ 一律标记 **DRAFT**  
6. **角色**：`super_admin` / `consultant` / `support` + 学生分配（assignee）  
7. **持久化 audit_events**（或等价表）

---

## 6. Schema Migration Proposal（本轮不执行）

**SCHEMA_MIGRATION_REQUIRED=YES**

### MIGRATION_REASON

`expert_consultations` 仅绑定 `user_id`，无法保证 Student 360「禁止串档」；缺顾问分配与 provider 元数据；`eligibility_records` 未挂 `student_id` 时 360 资格块无法严格按学生聚合。

### 建议增量（proposal only）

```text
expert_consultations:
  + student_id INTEGER NULL FK → student_master_profiles.id  (index)
  + assigned_consultant_id INTEGER NULL FK → users.id
  + ai_provider VARCHAR(40) NULL   -- openai_compatible | deepseek | ...
  + report_kind VARCHAR(60) NULL  -- portrait | eligibility_risk | ...
  -- 现有：ai_draft, ai_model, final_report, status, reviewed_by_user_id, published_at 保留

consultation_report_versions: 不变（可扩展 source 枚举值，非必须迁移）

可选：
  student_consultant_assignments(student_id, consultant_id, ...)
  audit_events(actor_id, action, resource_type, resource_id, student_id, created_at, details_json)
  eligibility_records.student_id NULL FK  -- 新写入挂学生；旧数据可空
```

**禁止本轮**：production migration / production DB write。

---

## 7. 产品与架构建议

### RECOMMENDED_ADMIN_PATH

新建独立应用：`huaqiao-admin/`（禁止改学生端 `huaqiao-app` 业务路径）

### RECOMMENDED_STACK

Vue 3 + Vite + Element Plus；桌面优先；对接现有 SaaS API `:8010` / `https://api.guoqiaoplan.com`

### ADMIN_DOMAIN

`https://admin.guoqiaoplan.com`（已预留；本轮不改 Cloudflare / Tunnel / Caddy）

### AI_EXPERT_ARCHITECTURE

```text
Student 360 (student_id)
  └─ AI Expert Workspace (右侧)
       ├─ Provider abstraction (backend only; secrets in env)
       ├─ Prompt templates per report_kind
       ├─ Context loader: ONLY authorized fields for this student_id
       ├─ Output → ExpertConsultation.ai_draft (status=draft / pending_review)
       └─ Versions → consultation_report_versions
```

### AI_DRAFT_REVIEW_PUBLISH_FLOW

```text
AI GENERATE (DRAFT)
  → consultant review
  → edit (new version, source=admin_edit|consultant_edit)
  → approve
  → send/publish to student (status=published, published_at, reviewed_by_user_id)
```

AI 输出**不得**直接成为正式学生规划。

### PRIVACY_MODEL

| 角色 | 能力 |
|------|------|
| `super_admin` | 全权限；敏感证件需二次授权/显式「揭开」 |
| `consultant` | 仅被分配学生；AI 规划；默认掩码护照/身份证 |
| `support` | 账号/套餐/客服联系信息；不可看完整证件；不可发布规划 |

默认：护照号/身份证/敏感证件 **掩码**；解密走现有 vault；日志禁止明文敏感字段。

### AUDIT_MODEL

所有：查看学生 360、揭开敏感字段、AI 生成、编辑报告、发布 — 记 `谁 / 何时 / student_id / 动作 / 报告类型`；优先把现有 `AuditLogger` **落库**，而非仅内存。

---

## 8. Admin V1 页面映射（scaffold proposal）

| 页面 | 数据源 | 备注 |
|------|--------|------|
| Dashboard | users + plans + expert status counts | 不做复杂 BI |
| 用户管理 → 详情 | users + student count | Trial 用 plan_code/membership_until |
| 学生管理 | student_master_profiles | 搜索；展示 owner |
| Student 360 | profile + timeline + eligibility + reports | **强制 student_id** |
| AI Expert Workspace | expert_consultations + versions | 右侧栏；DRAFT 强制 |

---

## 9. 正式字段输出

```text
GUOQIAO_ADMIN_AI_EXPERT_V1_AUDIT_REPORT
EXISTING_ADMIN=PARTIAL
EXISTING_ADMIN_PATH=huaqiao-saas-pro/frontend (embedded admin tab); backend/static/admin.html (legacy Free, separate stack); NO huaqiao-admin
EXISTING_ADMIN_AUTH=SaaS JWT + require_admin(role==admin); Free ADMIN_TOKEN (legacy only)
EXISTING_ROLES=admin|member (+ permissions JSON e.g. sensitive_data_access); NO consultant/support/super_admin
STUDENT_DATA_SOURCE=student_master_profiles (+ student_timeline_items; customer_vaults by user_id; eligibility_records by user_id)
STUDENT_ID_ISOLATION=YES for student_timeline_items & /api/students owner scope; NO for expert_consultations (user_id only); eligibility_records lacks student_id
EXISTING_EXPERT_CONSULTATION=YES (expert_consultations + admin list/detail/patch publish)
EXISTING_REPORT_VERSIONING=YES (consultation_report_versions)
EXISTING_AI_PROVIDER=YES OpenAI-compatible via ai_api_key/ai_base_url/ai_model; local template fallback; no multi-provider abstraction
REUSABLE_BACKEND_APIS=/api/admin/users|/stats|/plans|/recharge-codes|/expert-consultations*|/customer-vaults/{uid}|/timeline-reminders*|/students/{id}/restore; student owner APIs pattern; expert AI draft generator
MISSING_ADMIN_APIS=dashboard_v1; user_detail_with_students; admin_student_list_search; student_360; ai_expert_workspace_by_student; role_rbac_assignee; durable_audit_query
SCHEMA_MIGRATION_REQUIRED=YES
MIGRATION_REASON=expert_consultations missing student_id/assignee/provider/report_kind; eligibility not student-scoped; audit not durable — proposal only, do not run on production this phase
RECOMMENDED_ADMIN_PATH=huaqiao-admin/ (new Vue3 app; do not embed in huaqiao-app)
RECOMMENDED_STACK=Vue 3 + Vite + Element Plus (desktop-first)
ADMIN_DOMAIN=https://admin.guoqiaoplan.com
AI_EXPERT_ARCHITECTURE=Student360→AI Workspace→Provider abstraction(OpenAI-compatible V1)→ExpertConsultation DRAFT→versions; secrets backend-only
AI_DRAFT_REVIEW_PUBLISH_FLOW=AI GENERATE(DRAFT)→consultant review→edit→approve→publish/send to student
PRIVACY_MODEL=mask passport/ID by default; vault decrypt; RBAC super_admin|consultant|support
AUDIT_MODEL=extend AuditLogger to durable events for view/generate/edit/publish per student_id
PRODUCTION_CHANGED=NO
DATABASE_CHANGED=NO
CNBER_CHANGED=NO
MAIN_CHANGED=NO
RECOMMENDED_PHASE_1=本报告：审计+架构+scaffold proposal（已完成）；可选：仓库内文档合入 feature branch
RECOMMENDED_PHASE_2=新建 huaqiao-admin scaffold + 非生产环境 admin APIs stub；迁移脚本仅写 alembic draft，不执行 production；接线单一 AI provider；Student 360 只读原型
NEXT_ACTION=人工确认 Phase 2 范围后，在 feature branch 实现 huaqiao-admin scaffold + admin student_id APIs（staging），禁止触碰生产 DB/Tunnel/Caddy/secret/main
```

---

## 10. 明确不触碰清单（本轮已遵守）

- production deploy  
- DB migration / production DB write  
- student data edit  
- Cloudflare / Tunnel / Caddy / secret 变更  
- main merge / CNber  
- 学生端功能回归风险变更  
