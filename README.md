# 华侨生国际生资格智能判定系统

一个前后端分离的全栈项目，用于华侨生与国际生报考资格初判、国籍法依据展示、大学信息查询、招生时间管理和 智能AI助手咨询。

## 技术栈

- 前端：Vue 3、Vite、Element Plus、响应式布局、深色/浅色模式
- 后端：Python FastAPI、SQLAlchemy、Pydantic
- 数据库：SQLite，首次启动自动建表并写入示例院校与时间表
- 智能AI助手：通用 Chat Completions 兼容接口

## 项目结构

```text
backend/
  app/
    main.py                 # FastAPI 入口与接口
    models.py               # SQLite 表结构
    schemas.py              # API 入参与响应模型
    seed.py                 # 初始大学与招生时间数据
    services/
      nationality_law.py    # 国籍法全文条款与解释
      rules.py              # 华侨生/国际生独立判定逻辑
      ai.py                 # 智能AI助手接入与本地兜底
  rules_config.json         # 判定阈值配置
  scripts/init_db.py        # 数据库初始化脚本
frontend/
  src/App.vue               # 主界面
  src/api.js                # API 封装
  src/styles.css            # 响应式与主题样式
start.bat / start.ps1       # 一键启动脚本
```

## 快速启动

Windows 双击：

```powershell
start.bat
```

或在 PowerShell 中运行：

```powershell
.\start.ps1
```

启动后访问：

- 前端：http://127.0.0.1:5173
- API 文档：http://127.0.0.1:8000/docs

## 手动启动

后端：

```powershell
cd backend
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python scripts\init_db.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

## 智能AI助手配置

编辑 `backend/.env`：

```env
AI_API_KEY=你的智能AI助手服务 API Key
AI_BASE_URL=https://api.example.com/v1
AI_MODEL=default-chat-model
```

未配置 API Key 时，系统会自动使用本地规则助手，前端智能AI助手仍可使用。

## 判定逻辑配置

编辑 `backend/rules_config.json` 可调整阈值：

- `huaqiao.min_overseas_months_last_2y`：华侨生近两年海外居住月份阈值
- `international.min_overseas_months_last_4y`：国际生近四年海外居住月份阈值
- `international.min_annual_overseas_months`：单年海外居住月份辅助阈值

系统判定为报考资格初判，不替代学校、联招办、公安机关或使领馆的最终审核。

## 本次升级说明

### 大学数据库

系统已内置中国大学排名前 50 名，并额外补充体育、音乐、美术、设计等顶尖特色高校。每所学校包含：

- 排名
- C9 / 985 / 211 / 双一流 / 特色标签
- 专业领域：综合、理工、文史、医药、体育、音乐、美术、设计
- 招生对象：华侨生、国际生
- 招生时间轴
- 优势专业
- 报考链接

启动或执行 `python scripts\init_db.py` 时会自动补全 SQLite 表字段并更新数据，无需手动删库。

### 大学推荐功能

华侨生/国际生判定表单新增：

- 意向专业领域
- 分数/成绩（可选）

判定完成后，结果页会自动展示匹配大学推荐，包含学校名称、标签、领域、优势专业、招生时间和报考链接。后端也提供独立接口：

```text
GET /api/recommendations?target=huaqiao&intended_field=设计&score=630
GET /api/recommendations?target=international&intended_field=音乐&score=600
```




