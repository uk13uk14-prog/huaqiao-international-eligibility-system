@echo off
setlocal
cd /d "%~dp0"
if not exist .env copy .env.example .env
if not exist node_modules npm install
npm run build
npx cap add android
npx cap sync android
echo.
echo Android ?????????? npm run apk:open ?? Android Studio ?? APK?
endlocal
