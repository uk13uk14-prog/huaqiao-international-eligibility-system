# Cloudflare Pages：huaqiao-app H5 云预览

目标：Cloud Cursor 改代码 → push 本分支 → Cloudflare 自动构建 → iPhone Safari 打开 `https://*.pages.dev` 验收。

**不依赖** M1 SSH、Tailscale、本机 Docker `:4190`。

## 仓库侧已就绪

| 项 | 值 |
|----|-----|
| Root directory | `huaqiao-app` |
| Build command | `npm run build` |
| Output directory | `dist` |
| Preview env 模板 | `.env.preview.example` |
| SPA 回退 | `public/_redirects` |
| 静态头 | `public/_headers` |

构建变量（Preview）：

- `VITE_API_BASE` — 免费版 API 根（HTTPS，无尾斜杠）；留空则请求相对路径 `/api`
- `VITE_SAAS_API` — SaaS API 根（HTTPS）；留空则相对路径 `/saas-api`

当前业务 API 若仅在私网/Tailscale 可达，**不要**把 `100.97.*` / `192.168.*` / `localhost` 填进 Preview。静态 H5 仍可打开；完整数据需后续 Staging API（`STAGING_API_REQUIRED=YES`）。

## Cloudflare Dashboard 最少步骤

1. **Workers & Pages** → **Create** → **Pages** → **Connect to Git** → 选择本仓库。
2. 生产分支可先选 `main`（或暂用 `cursor/mobile-cloud-preview`）；**Root directory** 填 `huaqiao-app`。
3. **Build command** = `npm run build`；**Build output directory** = `dist`。
4. **Save and Deploy**。部署成功后得到 `https://<project>.pages.dev`。
5. （推荐）**Settings → Builds & deployments → Branch deployments**：确保 `cursor/mobile-cloud-preview` 可生成 Preview URL。
6. （可选，有 Staging API 后再做）**Settings → Environment variables → Preview** 按 `.env.preview.example` 配置 `VITE_API_BASE` / `VITE_SAAS_API`（必须 HTTPS 公网地址），然后 **Retry deployment**。

## iPhone 验收

Safari 打开 Preview URL → 应看到首页网格（国际生/华侨生判定等），**不应白屏**。无 Staging API 时列表可能为空，属预期。

## 禁止事项

- 不要把 Tailscale IP / LAN IP 写进 Cloudflare 环境变量
- 不要为云预览开放 M1 SSH / PostgreSQL 公网
- 不要修改 CNber；本链路只服务 `huaqiao-app` H5
