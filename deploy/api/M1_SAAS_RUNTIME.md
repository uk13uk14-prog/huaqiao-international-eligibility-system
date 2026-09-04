# M1 SaaS Runtime（:8010）

## 根因（已证实）

误用 Homebrew 系统解释器：

```text
/opt/homebrew/bin/python3.12 -c "import app.main"
→ ModuleNotFoundError: No module named 'fastapi'
```

旧进程曾是：

```text
Python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

停掉后用错误 Python 重启 → `PORT_8010_DOWN`。  
**不是** Caddy / Cloudflare / student 路由 / 数据库 schema 问题。

## 仓库约定

| 项 | 路径 |
|----|------|
| 后端 | `huaqiao-saas-pro/backend` |
| 依赖（本地/M1） | `requirements.txt`（README 启动方式） |
| 依赖（Docker/CI 锁） | `requirements-locked.txt` |
| 环境变量 | `backend/.env`（gitignore；模板 `.env.example`） |
| 默认 DB | `sqlite:///./saas_pro.db`（无 `DATABASE_URL` 时） |
| Docker Compose | `backend-saas` → 容器内 `:8000` 映射主机 `8002`（**不是** M1 现网 `:8010`） |
| Coze adapter | `deploy_adapter/start.sh` → `:9091`（非现网） |

本仓 **无** 既有 LaunchAgent/plist；现网 `:8010` 此前多为手工/venv `uvicorn`。

## ONE_SHOT（M1）

```bash
cd /path/to/huaqiao-international-eligibility-system
git pull origin cursor/mobile-cloud-preview
bash deploy/api/m1-saas-runtime-recover.sh
```

脚本会：

1. **发现** 可 `import fastapi,uvicorn,sqlalchemy` 的 Python（项目 `.venv`、历史、LaunchAgent、有限范围 find、pyenv/conda）。
2. 若无 → 在 `huaqiao-saas-pro/backend/.venv` **新建隔离 venv**，按 `requirements.txt`（+ locked）安装；**不**污染系统 Python。
3. **不覆盖** 已有 `backend/.env`；不凭空写生产 `DATABASE_URL`。
4. 安装 `~/Library/LaunchAgents/com.guoqiao.saas-backend.plist`（`KeepAlive` + `RunAtLoad`）。
5. 验收：`/api/health`→200，`/api/students`→401，`/api/students/meta`→200。
6. 再执行 `deploy/api/m1-go-live.sh`（Caddy + Tunnel）。

状态文件：`~/.guoqiao/saas/runtime.env`、日志 `~/.guoqiao/saas/logs/`。

仅恢复 runtime、跳过 Tunnel：

```bash
SKIP_GO_LIVE=1 bash deploy/api/m1-saas-runtime-recover.sh
```

## 安全

- 不改 eligibility / 大学库 / 时间线数据 / schema / CNber / main  
- 不动用户 stash  
- 不 `sudo pip` / 不向 Homebrew 全局装项目依赖  
