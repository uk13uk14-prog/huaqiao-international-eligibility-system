# 华侨生国际生资格判定 APP

这是基于当前稳定后端生成的独立手机端版本，目录为 `huaqiao-app`。它不修改原 PC 前端，直接复用现有 FastAPI 后端、SQLite 数据库、国籍法条款、判定逻辑、大学库、推荐逻辑和智能AI助手接口。

## 技术栈

- Vue 3
- Vite
- Vant 移动端 UI
- html2canvas 结果截图保存
- Capacitor Android APK 壳

## 启动前提

先启动原后端：

```powershell
cd C:\Users\eulan\huaqiao-international-eligibility-system\backend
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

或直接使用项目根目录原有 `start.ps1` 同时启动 PC 与后端。

## 手机端开发启动

```powershell
cd C:\Users\eulan\huaqiao-international-eligibility-system\huaqiao-app
.\start-mobile.ps1
```

访问：

```text
http://127.0.0.1:5174
```

同一局域网手机访问时，请把 `huaqiao-app/.env` 中的 `VITE_API_BASE` 设置为电脑局域网 IP，例如：

```env
VITE_API_BASE=http://192.168.1.10:8000
```

然后重新运行 `npm run dev`。

## 功能清单

- 华侨生 / 国际生双独立判定
- 国籍法条款依据展示
- 完整大学库：前 50、C9、985、211、双一流和特色高校
- 体育 / 音乐 / 美术 / 设计等专业领域筛选
- 判定结果自动推荐大学
- 招生时间轴展示
- 智能AI助手
- 判定历史记录
- 深色 / 浅色模式
- 一步一屏手机表单
- 手势返回
- 加载动画与状态提示
- 表单键盘适配
- 结果一键保存为图片，手机浏览器可保存到相册

## H5 打包

```powershell
npm run h5:zip
```

生成：

```text
huaqiao-app-h5.zip
```

可部署到 Nginx、对象存储、静态网站托管或封装为 H5 APP。

## APK 打包

详见 `docs/APK_BUILD.md`。

## 小程序说明

本项目是标准 Vue3 + Vite + Vant H5 应用。若要发布微信/支付宝小程序，建议使用 uni-app 或 Taro 迁移页面层，API 层可直接复用 `src/api.js` 的接口路径和字段。


