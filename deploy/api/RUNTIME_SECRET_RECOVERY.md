# M1 Runtime Secret Recovery

只读找回 `:8010` 生产运行时曾使用的 `JWT_SECRET_KEY` / `VAULT_FERNET_KEY` / `ADMIN_TOKEN`，并在**每个 key 仅有唯一可信候选**时安全补回 `huaqiao-saas-pro/backend/.env`。

## 前提

- 生产库已在 revision `006_student_profile_slots`（本阶段**禁止**再跑 DB upgrade / alembic / seed / pg_restore）。
- `.env` 中已有且必须保留：`DATABASE_URL`、`GUOQIAO_SKIP_SEED`、`PUBLIC_BASE_URL`、`FRONTEND_BASE_URL`、`CORS_ORIGINS`。
- **禁止 invent / 自动生成**新 secret。找不到就停，不要启动生产 backend。

## Phase 1 — Discovery（只读）

```bash
cd /Users/agent001/deploy/huaqiao-international-eligibility-system
git pull origin cursor/mobile-cloud-preview
bash deploy/api/m1-runtime-secret-discover.sh
```

脚本扫描：shell history/profiles、LaunchAgents/Daemons、`~/.guoqiao`、`~/.config`、repo 忽略的 `.env*`、deploy 脚本、日志、Docker env、compose、**只读** git stash / history、backups 与 runtime state。

报告字段（**从不打印 secret 本文**）：

- `JWT_SECRET_KEY_FOUND` / `JWT_SECRET_SOURCE` / `JWT_SECRET_FINGERPRINT`
- `VAULT_FERNET_KEY_FOUND` / `VAULT_SECRET_SOURCE` / `VAULT_SECRET_FINGERPRINT`
- `ADMIN_TOKEN_FOUND` / `ADMIN_TOKEN_SOURCE` / `ADMIN_TOKEN_FINGERPRINT`
- `*_UNIQUE=YES|NO`、`READY_FOR_SECRET_RESTORE`

指纹为 sha256 前 12 位。多个不同指纹时**不自动挑选**，需人工确认。

计划文件（chmod 600，勿提交）：

- `~/.guoqiao/saas/secret-restore.plan` — 来源与指纹
- `~/.guoqiao/saas/secret-restore.values` — 仅 UNIQUE 时写入，供 restore 使用

## Phase 2 — Restore（仅 UNIQUE）

仅当 `READY_FOR_SECRET_RESTORE=YES`：

```bash
bash deploy/api/m1-runtime-secret-restore.sh
```

行为：

- 只补缺失的 `JWT_SECRET_KEY` / `VAULT_FERNET_KEY` / `ADMIN_TOKEN`
- 不覆盖受保护键；`chmod 600`；stdout 无 secret；不 commit `.env`
- 写 `.env.bak.<timestamp>` 备份

若 `*_UNIQUE=NO` 或计划缺失 → `RESTORE_RESULT=FAIL`，`USER_ACTION_REQUIRED=YES`。

## 找不到时

```
SECRET_RECOVERY_COMPLETE=NO
USER_ACTION_REQUIRED=YES
```

影响说明：

| Key | 影响 |
|-----|------|
| JWT | 旧 token/session 可能失效；换新 key 会强制重新登录 — discovery 阶段不自动生成 |
| VAULT | 若有历史加密 vault/profile，不能随意换 key；已知计数可为 0，discovery 阶段仍禁止 invent |
| ADMIN | 管理 token 可后续新建 — discovery 阶段不自动生成 |

当 discovery 已确认 `*_FOUND=NO` 且生产库无加密业务数据时，改走 bootstrap：

见 `deploy/api/RUNTIME_SECRET_BOOTSTRAP.md` / `m1-runtime-secret-bootstrap-and-go-live.sh`。

## 禁止

- alembic / migration / seed / pg_restore / DB rollback
- 再跑整套 `m1-production-db-upgrade-recover.sh`
- invent secret、commit `.env`、stdout 打印 secret 全文

## 本地静态测试

```bash
bash deploy/api/tests/test_runtime_secret_safety.sh
```
