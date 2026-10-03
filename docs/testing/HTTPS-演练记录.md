# HTTPS 部署演练记录

对应 [Issue #55](https://github.com/jzcool666/web-homework/issues/55)。2026-10-04（北京时间），代码基线 `develop@6466876`。本次验证本机 HTTPS 入口、production 配置和会话链路，不代表已部署公网 HTTPS 或已由真实班级使用。

## 1 环境与范围

Windows 11、Python 3.14.7、Node 24.18.0、npm 11.16.0；新建独立 Python 虚拟环境和 SQLite 库，按锁定依赖安装。前端以 `npm ci` 和 `npm run build` 构建，由 Waitress 同源提供。未修改前后端业务代码、配置读取或数据库迁移。

本机没有可用的 openssl 命令，也没有 Git 目录下的 openssl.exe。本次使用本机已有工具环境的 cryptography 50.0.1 生成等价自签证书，没有为后端增加依赖。证书 SAN 含 DNS `localhost` 和 IP `127.0.0.1`，RSA 2048 / SHA-256，有效期七天。证书和私钥均在仓库外；没有修改系统证书信任库。

入口 `https://localhost:5443` / `https://127.0.0.1:5443`，TLS 脚本和上游均只绑定 `127.0.0.1`，上游 Waitress 端口为 5330。production 默认 `COOKIE_SECURE=true`，演练没有设置 `COOKIE_SECURE=false`。

## 2 执行步骤

在独立目录全新安装，以下实际步骤均退出 0；完整迁移和初始化输出见 [bootstrap-output.txt](HTTPS-证据/bootstrap-output.txt)。日志不含私钥、SECRET_KEY 或账号口令。

| 步骤 | 结果 |
| --- | --- |
| 创建独立 venv，`pip install -r backend/requirements.txt` | 全部安装成功 |
| 前端 `npm ci` | 147 个包，审计 0 漏洞 |
| 前端 `npm run build` | 786 modules transformed，构建成功 |
| `flask --app app:create_app db upgrade` | 空库升级至单一 head `0012_spec018` |
| `init-admin` | 创建演练管理员，不使用真实个人账号 |
| 管理员调用 E006 创建演练教师 | 201 |
| `seed-content --owner-login https_teacher` | 六章节、12 知识点、15 条先修边、1 资料 |
| `seed-experiments --owner-login https_teacher` | 四个预置实验 |
| `seed-qa --owner-login https_teacher` | 16 条问答 |
| `seed-labs` | 四个接线/电路任务 |
| 启动 Waitress 与本地 TLS 反代 | 两个进程分别绑定 127.0.0.1:5330 / 5443 |

可复现的命令如下。`$appPython` 指向新建后端 venv；`$certPython` 指向另一个已安装 cryptography 的工具环境。若没有该工具依赖，可在独立工具 venv 安装 `cryptography==50.0.1`。`$drill` 为仓库外的演练目录。设置生产密钥时自行生成，不把真实值写进文档或版本库。

```powershell
# 仓库根目录；证书工具不安装到后端依赖中
& $certPython scripts/generate_local_certificate.py --out-dir "$drill/certificates"

# 环境变量在迁移、初始化和 Waitress 进程中保持一致
$env:APP_ENV = 'production'
$env:DATABASE_URL = "sqlite:///$($drill.Replace('\','/'))/app.sqlite"
$env:UPLOAD_DIR = "$drill/uploads"
# SECRET_KEY 使用自己生成的随机值；不覆盖 COOKIE_SECURE 的生产默认值
Remove-Item Env:COOKIE_SECURE -ErrorAction SilentlyContinue
Set-Location backend
& $appPython -m flask --app app:create_app db upgrade
& $appPython -m flask --app app:create_app init-admin --login-name https_admin --password $demoPassword
# 登录管理员，在账号管理中创建 https_teacher，再执行种子
& $appPython -m flask --app app:create_app seed-content --owner-login https_teacher
& $appPython -m flask --app app:create_app seed-experiments --owner-login https_teacher
& $appPython -m flask --app app:create_app seed-qa --owner-login https_teacher
& $appPython -m flask --app app:create_app seed-labs
& $appPython -m waitress --listen=127.0.0.1:5330 wsgi:app

# 另一个终端，仓库根目录
& $appPython scripts/local_tls_proxy.py --cert "$drill/certificates/localhost.pem" --key "$drill/certificates/localhost.key" --port 5443 --upstream-port 5330
```

初始化阶段的账号创建由隔离库的应用接口完成；后续验收调用真实运行的 HTTPS 服务。辅助验收脚本留在仓库外，结果 JSON 与界面实拍已归档在本文证据目录。

## 3 实测结果

真实 Chromium 页面登录、填写表单并点击按钮；证书信任与 HTTP 对照另由 Python 标准库验证。浏览器仅在本次独立测试上下文中忽略自签信任错误，另外使用证书文件作为 CA 验证两个 SAN 名称，不能把浏览器忽略错误当作证书验证通过。

| 检查 | 实际结果 |
| --- | --- |
| localhost 的证书链与 SAN | 显式信任演练证书后健康接口 200 |
| 127.0.0.1 的证书链与 SAN | 显式信任演练证书后健康接口 200 |
| 系统默认信任 | 拒绝该自签证书，符合预期 |
| HTTPS 表单登录 | POST /auth/login 200，跳转个人资料 |
| Secure Cookie | 响应和浏览器存储都确认 Secure / HttpOnly / SameSite=Lax |
| 个人资料表单保存 | PATCH /me 200，界面显示“资料已更新” |
| 缺少 CSRF 的相同写操作 | 403 `CSRF_FAILED`，不保存修改 |
| 携带有效 CSRF 创建班级 | POST /classes 201，班级管理页显示新班级 |
| 刷新 | 仍已登录且班级可见 |
| IP 地址登录与鉴权读取 | 200，读取 12 个课程知识点 |
| 页面资源和运行异常 | HTTP 混合资源 0，pageerror 0 |
| 1366×768 / 390px | 同一登录会话正常加载；390px 整页无横向溢出 |
| 反代 HEAD / 非本机 Host | HEAD 200 无正文；未知 Host 400 |
| HTTP 上游健康接口 | 本机直连 200；没有伪造为不可达或重定向 |
| Python 标准 Cookie 策略下 HTTP /me | 不发送 Secure Cookie，401 |

浏览器检查 12/12 通过，详见 [results.json](HTTPS-证据/results.json)；证书与 HTTP 对照见 [tls-results.json](HTTPS-证据/tls-results.json)。SID 原文已脱敏，实际响应属性保留，例如：

```text
sid=<redacted>; Max-Age=28800; Secure; HttpOnly; Path=/; SameSite=Lax
```

完整脱敏 Set-Cookie（含服务端 Expires）保存在 results.json。两次页面运行均通过；手机截图在尺寸切换的侧栏动画结束后采集，避免把过渡帧作为布局结论。

桌面：[管理员班级管理实拍](HTTPS-证据/https-admin-1366.png)。手机：[390px 实拍](HTTPS-证据/https-admin-390.png)。

## 4 范围与局限

1. 自签证书仍会触发未受信任提示；本次没有安装受信任证书或修改系统信任库。真实部署需使用相应域名与受信任证书。
2. 反代脚本是本机演练工具，固定转发到 127.0.0.1，不承担生产代理、流式传输或负载验证。它保留多条 Set-Cookie，只允许 localhost / 127.0.0.1 Host，限制请求体，拒绝 chunked 请求。
3. 本机上游 HTTP 仍可访问，没有另设 HTTP 跳转入口。正式 HTTPS 部署应由生产代理提供 TLS，并限制上游只能被代理访问；本记录不宣称已完成该部署。
4. Secure Cookie 的普通 HTTP 限制用 Python CookieJar 实测。不同浏览器可能对 loopback 有特殊处理，不能据此把本机 HTTP 可访问解释为公网安全配置。
5. 本轮没有重跑课堂负载或真实师生使用，也没有启动电路测评 worker；这些不属于 HTTPS 链路演练。既有功能验收见相应报告。

## 5 代码与清洁检查

新增两个 scripts 工具和本记录/脱敏证据，不修改业务、配置、前端源码或迁移。两个脚本 `py_compile` 通过，`git diff --check` 干净。证书生成器拒绝在仓库内输出并拒绝覆盖已有证书；私钥和证书不入库。
