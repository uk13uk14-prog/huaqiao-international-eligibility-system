# 国际生资格智评系统 SaaS Pro

独立收费版项目，完全隔离免费版，目录：`huaqiao-saas-pro`。本版本基于原已稳定的单机版能力升级，保留原系统核心功能，并新增 SaaS 多租户、会员收费、权限锁和后台管理。

## 核心定位

SaaS Pro 以国际生资格判定、国际生名校库、国际生专属升学规划和机构批量服务为核心，华侨生判定作为辅助模块。

## 功能

- 多租户：机构/个人注册，租户数据隔离。
- 账号登录：Bearer Token 鉴权。
- 套餐：免费版、月度会员、年度会员、终身版。
- 权限：免费版仅基础判定和少量非核心院校；付费版解锁完整名校库、艺术体育专项、智能AI助手、报告导出权益、无限推荐和永久历史。
- 后台：用户管理、套餐、充值卡密、开通时长、数据统计，重点统计国际生使用数据。
- 支付：内置微信支付、支付宝支付、模拟支付三通道；本地开发可用模拟支付自动解锁会员，正式上线需配置商户号、证书、HTTPS 域名与回调验签。
- 核心业务：国际生判定为主、华侨生判定为辅，国籍法依据、智能AI助手、招生时间、院校库、推荐规则。
- 完整继承原版数据：18 条《中华人民共和国国籍法》条款、前50名校库、C9/985/211/双一流标签、体育/音乐/美术/设计特色高校、招生时间轴。
- 前端页面：国际生工作台、双模块判定、国籍法依据、名校库、招生时间、智能AI助手、历史记录、会员中心、后台管理。
- 部署：支持私有化部署和公有云 SaaS。

## 启动

后端：

```powershell
cd backend
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python scripts\init_db.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

访问：`http://127.0.0.1:5180`

## 默认账号

- 管理员：`admin@example.com` / `admin123456`
- 示范用户：`demo@example.com` / `demo123456`

## 智能AI助手配置

编辑 `backend/.env`：

```env
AI_API_KEY=你的智能AI助手服务 API Key
AI_BASE_URL=https://api.example.com/v1
AI_MODEL=default-chat-model
```

未配置时系统使用本地规则助手。

## 支付配置说明

当前系统已提供完整支付闭环接口：

- `POST /api/payments/create`：创建微信/支付宝/模拟支付订单
- `GET /api/payments/{order_no}`：查询支付状态
- `POST /api/payments/mock/{order_no}/pay`：本地模拟支付成功
- `POST /api/payments/notify/wechat`：微信支付回调入口
- `POST /api/payments/notify/alipay`：支付宝回调入口

本地测试建议选择“模拟支付”，点击“本地 mock 支付成功”后系统会自动开通会员权益。

正式上线微信/支付宝支付前，需要准备企业商户资质、HTTPS 公网域名、商户号、应用私钥/证书、平台公钥/证书，并在回调接口中补充生产级验签逻辑。
