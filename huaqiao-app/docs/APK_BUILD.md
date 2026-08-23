# APK 打包说明

## 1. 环境准备

需要安装：

- Node.js
- Android Studio
- Android SDK
- JDK 17 或 Android Studio 自带 JDK

确保 Android Studio 能正常创建和构建 Android 项目。

## 2. 配置后端地址

APK 在真机上不能访问电脑自己的 `127.0.0.1`。请编辑 `huaqiao-app/.env`：

```env
VITE_API_BASE=http://你的后端服务器IP:8000
```

示例：

```env
VITE_API_BASE=http://192.168.1.10:8000
```

后端启动时建议绑定局域网地址：

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 3. 生成 Android 工程

```powershell
cd C:\Users\eulan\huaqiao-international-eligibility-system\huaqiao-app
.\build-apk.bat
```

或手动执行：

```powershell
npm install
npm run build
npx cap add android
npx cap sync android
```

## 4. 使用 Android Studio 打包

```powershell
npm run apk:open
```

打开 Android Studio 后：

1. 等待 Gradle 同步完成。
2. 选择 Build > Build Bundle(s) / APK(s) > Build APK(s)。
3. Debug APK 通常输出在 `android/app/build/outputs/apk/debug/app-debug.apk`。

## 5. 命令行打包

```powershell
npm run apk:build
```

如果首次 Gradle 下载较慢，请在 Android Studio 中完成一次同步后再执行。

## 6. 真机测试注意事项

- 手机和后端服务器需在同一网络，或后端已公网部署。
- Windows 防火墙需允许 8000 端口访问。
- 如果使用 HTTP，部分 Android 版本可能需要在原生工程中允许明文流量；开发测试建议使用同网段 HTTP，生产发布建议使用 HTTPS。
- 保存结果到相册在 H5/Capacitor 中会先生成 PNG 下载文件，用户可在系统下载或分享菜单中保存到相册。
