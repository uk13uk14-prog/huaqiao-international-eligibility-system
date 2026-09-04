# M1 Persistent Tunnel + Production Freeze

目标：把 `api.guoqiaoplan.com` 固定到 **named Cloudflare Tunnel** `guoqiao-api`，并让 M1 重启后自动恢复：

| 组件 | 持久化方式 |
|------|------------|
| Postgres `huaqiao-postgres` | Docker `restart` policy（已有） |
| SaaS `:8010` | LaunchAgent `com.guoqiao.saas-backend`（已有） |
| Caddy `:8088` → `:8010` | LaunchAgent `com.guoqiao.caddy` |
| cloudflared | LaunchAgent `com.guoqiao.cloudflared` |

## 禁止

- migration / alembic / seed / DB write / restore
- secret 再生成 / `.env` 覆盖
- CNber / beta / main merge / 业务规则 / 大学与时间线数据改动
- 伪造 tunnel credentials / commit credential JSON

## ONE_SHOT（仅 M1）

```bash
cd /Users/agent001/deploy/huaqiao-international-eligibility-system && \
git pull origin cursor/mobile-cloud-preview && \
bash deploy/api/m1-persistent-tunnel-and-freeze.sh
```

若缺少 Cloudflare cert：

```
USER_ACTION_REQUIRED=YES
USER_ACTION=cloudflared tunnel login
```

浏览器登录完成后**再跑同一脚本**（唯一人工动作）。

## 行为摘要

1. 只读审计 `cloudflared` / `~/.cloudflared` 文件名 / tunnel list（不打印 credential 内容）
2. 复用已有 `guoqiao-api`；不存在才 `tunnel create`
3. `tunnel route dns guoqiao-api api.guoqiaoplan.com`（已存在则不破坏）
4. 写入 `~/.cloudflared/config.yml`（`chmod 600`，不 commit）
5. 安装 LaunchAgent：`com.guoqiao.cloudflared` + `com.guoqiao.caddy`
6. 公网验收 health / universities / schedules + H5
7. `RELOGIN_REQUIRED=YES`（旧 JWT 已失效；不 invent 测试密码）
8. 全 PASS 时写 `~/.guoqiao/saas/PRODUCTION_FREEZE.txt`（冻结说明；**不 merge main**）

## 模板

- `deploy/api/launchd/com.guoqiao.cloudflared.plist.example`
- `deploy/api/launchd/com.guoqiao.caddy.plist.example`
- `deploy/api/cloudflared-config.example.yml`

## 静态测试

```bash
bash deploy/api/tests/test_persistent_tunnel_safety.sh
```
