# M1 Runtime Secret Bootstrap + Go-Live

当 secret discovery **找不到**旧 `JWT_SECRET_KEY` / `VAULT_FERNET_KEY` / `ADMIN_TOKEN` 时，允许在 **M1 本机**生成新的生产 secrets，并完成 `:8010` → Caddy `:8088` → 持久 Cloudflare Tunnel → H5 验收。

## 前提

- DB 已在 `006_student_profile_slots`，完整性已验（125 / 900 / users=2）
- discovery：`*_FOUND=NO`、`candidate_count=0`
- **禁止**再跑 migration / seed / pg_restore

## 接受的影响

| Key | 影响 |
|-----|------|
| JWT | 旧 session 全部失效，用户需重新登录 |
| VAULT | 当前 `customer_vaults=0` 且无 student master/timeline 业务加密数据，允许新 Fernet key |
| ADMIN | 新强随机 admin token |

## ONE_SHOT（仅 M1）

```bash
cd /Users/agent001/deploy/huaqiao-international-eligibility-system && \
git pull origin cursor/mobile-cloud-preview && \
bash deploy/api/m1-runtime-secret-bootstrap-and-go-live.sh
```

## 脚本行为摘要

1. **DB guard**：确认 alembic `006` + 125/900/users=2；不匹配则 ABORT；`MIGRATION_RUN=NO`
2. **生成 secrets**（仅补缺失）：`token_urlsafe(64)` / `Fernet.generate_key()` / `token_urlsafe(48)`
3. **原子写入** `huaqiao-saas-pro/backend/.env`（`chmod 600`）；保留 `DATABASE_URL` / `GUOQIAO_SKIP_SEED` / URL / CORS；写 `ENV=production`
4. **Settings 校验**：`.venv` + `get_settings()` + `validate_production_config()`；stdout **仅**指纹
5. **LaunchAgent** `com.guoqiao.saas-backend` → `:8010`（不用 nohup）
6. **Caddy** `:8088` → `:8010`
7. **持久 Tunnel**：仅使用已有 `~/.cloudflared` credentials；缺失则 `USER_ACTION_REQUIRED`（不造假配置）
8. **H5**：公网 health + catalog；登录需真实账号（可选 `GUOQIAO_TEST_EMAIL` / `GUOQIAO_TEST_PASSWORD`）

## 安全

- 禁止 stdout / commit / push / 聊天输出完整 secret
- 只报告 `*_GENERATED` + `*_FINGERPRINT`（sha256 前 12）
- `.env` 必须 gitignore

## 相关

- 先尝试找回旧值：`deploy/api/RUNTIME_SECRET_RECOVERY.md`
- 静态测试：`bash deploy/api/tests/test_runtime_secret_bootstrap_safety.sh`
