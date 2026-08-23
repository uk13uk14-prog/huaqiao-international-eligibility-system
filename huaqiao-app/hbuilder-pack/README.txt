华侨生国际生资格判定 · HBuilderX 离线打包说明
================================================

本目录下的 www 由命令自动生成，勿手工改构建资源（每次 build:hbuilder 会覆盖）。

一、生成 www
   在项目 huaqiao-app 根目录执行：
     npm install
     npm run build:hbuilder
   需已配置生产环境 API（见根目录 .env.production 中 VITE_API_BASE）。

二、在 HBuilderX 中使用
   1. 菜单：文件 -> 新建 -> 项目 -> 「5+App」或「Wap2App」类 HTML5+ 模板（任选官方空壳）。
   2. 用本目录 www 内的全部文件，替换新项目中的 www 目录内容（删除旧文件后粘贴）。
   3. 打开 manifest.json：
      - 「应用首页」设为 index.html
      - App 模块 -> 「应用访问域名白名单」或 Android/iOS 网络权限中，加入你的 API 域名（与 VITE_API_BASE 一致），否则真机无法请求接口。
   4. 真机调试：运行 -> 运行到手机模拟器/真机。
   5. 发行 -> 原生 App-云打包（按 DCloud 账号流程上传签名与包名）。

三、与 Capacitor 关系
   仍可使用 npm run apk:prepare / Android Studio 打包；HBuilderX 与 Capacitor 二选一即可，共用同一份 npm run build（需 base 为相对路径 ./）。

四、接口地址
   开发时可用 Vite 代理；正式发布必须在 .env.production 写入公网 HTTPS 的 VITE_API_BASE（无尾斜杠），例如：
   VITE_API_BASE=https://your-api.example.com
