# 桌面应用构建指南

本文档说明如何将华侨生资格评估系统打包为独立的 Windows/macOS/Linux 桌面应用。

## 架构概述

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron 应用                             │
│  ┌─────────────────┐      ┌─────────────────────────────┐  │
│  │   Vue 前端      │─────▶│  Python FastAPI 后端        │  │
│  │   (dist/)       │      │  (huaqiao-backend.exe)      │  │
│  │                 │      │  - SQLite 数据库            │  │
│  │  http://127.0.0.│      │  - 127.0.0.1:9090          │  │
│  │  1:9090/api     │      │  - 数据目录: %APPDATA%      │  │
│  └─────────────────┘      └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**核心特性**：
- ✅ 一键安装，无需 Python/Node.js 环境
- ✅ 后端自动启动，无需命令行
- ✅ 数据存储在用户目录（%APPDATA%）
- ✅ 仅监听 127.0.0.1，不暴露外网

## 构建环境要求

### Windows 构建（推荐）

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.10+ | 用于打包后端 |
| Node.js | 18+ | 用于构建前端 |
| npm | 8+ | 随 Node.js 安装 |

### macOS 构建

| 依赖 | 版本要求 |
|------|----------|
| Python | 3.10+ |
| Node.js | 18+ |
| Xcode Command Line Tools | 最新版 |

### Linux 构建

| 依赖 | 版本要求 |
|------|----------|
| Python | 3.10+ |
| Node.js | 18+ |
| gcc/make | 用于编译原生模块 |

## 快速构建

### Windows 一键构建

```batch
# 在项目根目录执行
build-windows.bat
```

构建完成后，安装包位于：
```
frontend/release/华侨生资格判定系统 Setup 1.0.0.exe
```

### macOS 构建

```bash
# 在项目根目录执行
chmod +x build-macos.sh
./build-macos.sh
```

构建完成后，安装包位于：
```
frontend/release/华侨生资格判定系统-1.0.0.dmg
```

### Linux 构建

```bash
# 在项目根目录执行
chmod +x build-linux.sh
./build-linux.sh
```

构建完成后，安装包位于：
```
frontend/release/华侨生资格判定系统-1.0.0.AppImage
```

## 手动构建步骤

如需更细粒度的控制，可按以下步骤手动构建：

### 1. 构建后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt pyinstaller

# 使用 PyInstaller 打包
pyinstaller huaqiao-backend.spec --clean --noconfirm
```

产物位于：`backend/dist/huaqiao-backend/`

### 2. 构建前端

```bash
cd frontend

# 安装依赖
npm install

# 构建 Vue 应用
npm run build
```

产物位于：`frontend/dist/`

### 3. 打包 Electron

```bash
cd frontend

# 构建 Windows 安装包
npx electron-builder --win --x64

# 构建 macOS 安装包
npx electron-builder --mac

# 构建 Linux AppImage
npx electron-builder --linux
```

## 数据目录

应用数据存储在用户目录：

| 操作系统 | 路径 |
|----------|------|
| Windows | `%APPDATA%\HuaqiaoEligibility\` |
| macOS | `~/Library/Application Support/HuaqiaoEligibility/` |
| Linux | `~/.local/share/huaqiao-eligibility/` |

目录结构：
```
HuaqiaoEligibility/
├── data/
│   └── eligibility.db    # SQLite 数据库
├── logs/                 # 日志文件
└── config/               # 配置文件（预留）
```

## 分发说明

### Windows 安装包

- 格式：NSIS 安装程序
- 大小：约 200-250 MB
- 支持：Windows 10/11 (x64)
- 特性：
  - 可选安装目录
  - 创建桌面快捷方式
  - 创建开始菜单快捷方式
  - 支持卸载

### macOS 安装包

- 格式：DMG
- 大小：约 180-220 MB
- 支持：macOS 10.15+
- 注意：首次运行需要右键打开（绕过 Gatekeeper）

### Linux AppImage

- 格式：AppImage
- 大小：约 180-200 MB
- 支持：Ubuntu 20.04+, Fedora 32+, Debian 10+
- 运行：`chmod +x *.AppImage && ./*.AppImage`

## 故障排除

### 后端启动失败

**现象**：应用启动时显示"后端服务启动失败"

**排查**：
1. 检查 `%APPDATA%\HuaqiaoEligibility\logs\` 下的日志
2. 确认端口 9090 未被占用
3. 检查杀毒软件是否拦截

### 数据库错误

**现象**：评估功能无法保存数据

**排查**：
1. 检查数据目录权限
2. 确认磁盘空间充足
3. 备份并删除 `eligibility.db` 重建

### 端口冲突

**现象**：后端无法启动，提示端口被占用

**解决**：
```bash
# Windows
netstat -ano | findstr :9090
taskkill /PID <进程ID> /F

# macOS/Linux
lsof -i :9090
kill -9 <进程ID>
```

## 开发模式

开发时可分别启动前后端：

```bash
# 终端 1：启动后端
cd backend
python launcher.py

# 终端 2：启动前端开发服务器
cd frontend
npm run dev

# 终端 3：启动 Electron（开发模式）
cd frontend
npm run electron:dev
```

## 安全说明

- 后端仅监听 `127.0.0.1`，不暴露外网
- 数据库使用 SQLite，数据本地存储
- 敏感数据（R4.3 隐私保护）使用 Fernet 加密
- 无远程访问功能，纯本地应用

## 版本信息

- 应用版本：1.0.0
- Electron：43.x
- Python：3.10+
- 构建日期：2024

---

**技术支持**：如有问题，请联系开发团队。
