# 国侨升学正式 API — Cloudflare Tunnel + 本机反代

目标：

```
https://app.guoqiaoplan.com  (H5 Worker)
        ↓ HTTPS
https://api.guoqiaoplan.com  (Cloudflare Tunnel)
        ↓
M1 本机 Caddy 127.0.0.1:8088
        ↓
SaaS Pro 127.0.0.1:8010
        ↓
现有 PostgreSQL / SQLite（不迁移、不公网暴露）
```

生产 H5（`VITE_API_BASE` / `VITE_SAAS_API`）统一打到 `api.guoqiaoplan.com`，
Caddy **全部**反代到 SaaS `:8010`。旧 Free `:8000` **不是**生产必需。

## 硬约束

- 不暴露 PostgreSQL 公网端口
- 不暴露 SSH
- 不把 Tailscale / 局域网 IP 写进 H5
- 不修改 eligibility 业务规则 / 大学数据 / 时间线内容 / DB schema / CNber
- 不破坏 M1 现有服务

## 架构选择：A — Cloudflare Tunnel（推荐）

Cloud Agent **无法**直接登录 M1 / Tailscale。本目录只准备配置；上线需在 M1 做一次最小动作（见文末）。

### 1. 本机反代（合并双后端到同一 HTTPS 域名）

H5 生产环境变量：

```
VITE_API_BASE=https://api.guoqiaoplan.com
VITE_SAAS_API=https://api.guoqiaoplan.com
```

两端均请求 `/api/...`（不要 `/saas-api` 前缀，避免 `/saas-api/saas-api`）。

- **匿名判定 / 法规 / 历史 / telemetry** → Free `backend` `:8000`
- **登录 / 学生档案 / 会员 / 大学库 / 时间线（会员感知）** → SaaS `:8010`

使用仓库内 `Caddyfile`（仅监听本机，由 cloudflared 接入）。

### 2. Cloudflare Tunnel

使用 `cloudflared-config.example.yml`：

1. 在 Cloudflare Zero Trust 创建 Tunnel，名称建议 `guoqiao-api`
2. 将生成的 tunnel id / credentials 填入本机配置（**勿提交 credentials JSON**）
3. Public hostname：`api.guoqiaoplan.com` → `http://127.0.0.1:8088`（Caddy）
4. DNS：Cloudflare 自动创建 CNAME（当前 zone NS 已是 Cloudflare）

### 3. CORS（精确来源，禁止 `*`）

SaaS / Free 后端生产环境变量示例见 `env.production.example`：

```
CORS_ORIGINS=https://app.guoqiaoplan.com,https://huaqiao-international-eligibility-system.rambolluk.workers.dev
```

`allow_credentials=True`，必须精确列出来源。

### 4. H5 部署

- 分支：`cursor/mobile-cloud-preview`
- Worker：`huaqiao-international-eligibility-system`（Static Assets）
- `huaqiao-app/.env.production` 已指向 `https://api.guoqiaoplan.com`
- 勿污染 H5 Worker：API Tunnel / Caddy 独立于 H5 `wrangler.toml`

## 数据完整性（仓库内审计，非生产库覆盖）

权威目录基线（`data_baseline.py`）：

| 指标 | 期望 |
|------|------|
| UNIVERSITY_COUNT（seeded） | 125（catalog 122 + free 3） |
| TIMELINE（AdmissionSchedule after seed） | 900 |
| ELIGIBILITY_ENGINE | 两端均存在 `eligibility_engine.py` |

仓库内本地副本 `huaqiao-saas-pro/backend/saas_manual.db` 抽样：

- universities = 125
- admission_schedules = 900
- student_master_profiles = 2

**不自动覆盖任何生产数据库。** 若 M1 生产库数量偏离基线，先人工核对再决定。

## 用户最小动作（M1）

**已确认本仓 Cloud Agent 环境内 SaaS 监听端口为 `8010`（勿猜）。**  
Cloud Agent **无法** SSH M1 / 无 self-hosted worker；Tunnel 必须在 M1 执行一次。

若 API 尚未解析 / 未接通，在 M1 仓库根目录执行：

```bash
# 0) SaaS CORS（重启 backend 生效；禁止 *）
# CORS_ORIGINS=https://app.guoqiaoplan.com,https://huaqiao-international-eligibility-system.rambolluk.workers.dev

# 1) 确认 SaaS 本机后端（:8000 Free 非必需）；须为当前 HEAD 进程（含 student_api）
curl -sS http://127.0.0.1:8010/api/health
curl -sS http://127.0.0.1:8010/api/students
# 期望：401 {"detail":"请先登录"} —— 若 404，请重启 uvicorn 加载当前分支的 student_api

# 2) 一次性拉起 Caddy(:8088→:8010) + Cloudflare Tunnel
brew install caddy cloudflare/cloudflare/cloudflared   # 若未安装
cloudflared login                                      # 仅首次
bash deploy/api/m1-go-live.sh
```

路径对齐见 `deploy/api/ENDPOINT_MATRIX.md`。

验证：

```bash
curl -sS https://api.guoqiaoplan.com/api/health
```

完成后无需再改 H5 代码；已指向正式 API 域名。

## H5 部署 secrets（GitHub Actions）

若 Actions 报 `SECRET_REQUIRED=YES`，在 GitHub repo → Settings → Secrets 添加（**不要把 token 发给 Agent**）：

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

或依赖 Cloudflare Dashboard → Workers Builds 从 `cursor/mobile-cloud-preview` 自动 `npx wrangler versions upload`。
