# SPEC-001 执行报告

日期：2026-09-28。对象：SPEC-001 账号角色与班级权限。提交：`a58fd3d`（分支 `feature/spec-001`，基线 `develop` `d44bd99`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-001（E001—E010、迁移与管理初始化）。不包含尚未实现的后续模块，也不把设计意图记为运行通过。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用 SPEC-000 锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、waitress 3.0.2、python-dotenv 1.1.1、pytest 9.1.1）；本 Spec 未新增依赖 |
| 前端依赖 | 沿用 SPEC-000 锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等）；未新增依赖 |

口令散列使用 Werkzeug 自带的安全散列（默认 scrypt），未引入额外库；会话与 CSRF 令牌使用标准库 `secrets` + SHA-256。

## 2 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend -q` | 0 | `32 passed`（其中 SPEC-001 新增 21 条，SPEC-000 原有 11 条继续通过） |
| 2 | `flask --app app:create_app db upgrade`（工作目录 backend） | 0 | `Running upgrade 0001_baseline -> 0002_spec001` |
| 3 | `flask --app app:create_app init-admin --login-name admin_root --password <口令>` | 0 | `已创建管理员：id=1 login_name=admin_root` |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 4 | `npm run test:unit` | 0 | 4 个测试文件、`17 passed`（其中 SPEC-001 新增 2 个文件 11 条） |
| 5 | `npm run build` | 0 | `39 modules transformed`，产出 `dist/`（含各页面分块） |
| 6 | `git diff --check` | 0 | 无空白错误 |

## 3 浏览器实际流程

后端以 `wsgi.py`（开发配置，数据库 `backend/instance/app.sqlite`）监听 5000，前端用 Vite dev server 监听 5173 并代理 `/api`。用应用内浏览器按真实用户路径操作：

| 步骤 | 网络观测 | 界面结果 |
| --- | --- | --- |
| 打开 `/register` 并提交学生注册 | `GET /auth/csrf` 200 → `POST /auth/register` 201 → `POST /auth/login` 200 | 跳转个人资料页，显示 `student`、登录名、学号 |
| 点击「退出」 | `POST /auth/logout` 200 | 回到未登录态导航 |
| 以 `admin_root` 登录 | `POST /auth/login` 200；`GET /me` 返回 `role=admin` | 导航出现「账号管理」「班级管理」 |
| 在账号管理新建教师 `teacher_browser` | `POST /users` 201 | 列表出现 3 个账号，提示「已创建 teacher_browser」 |
| 在班级管理新建「浏览器班」并选任课教师 | `POST /classes` 201 | 列表出现 1 个班级，含「管理名单」入口 |
| 在名单页把学生加入班级 | `PUT /classes/1/enrollments` 200 | 名单出现「浏览器学生（20249999）」及加入时间 |

控制台：除未登录时 `GET /me` 的 401（路由守卫探测会话，属预期）外无报错，无未捕获异常。

说明（方法学限制）：验证过程中应用窗口被最小化，基于坐标的点击无法稳定命中，因此上述表单提交改用页面内的 `form.requestSubmit()` 触发——它与点击提交按钮走同一条提交事件与处理函数，但不等同于真实的鼠标点击。表单填写与页面跳转均为真实浏览器行为。

## 4 逐条验收

### T-001-01 注册携带 role=admin 被拒且不创建高权限账号；正常学生注册成功

覆盖用例：`test_T001_01_register_rejects_privileged_role`、`test_T001_01_register_creates_plain_student`、`test_T001_01_register_rejects_unknown_and_duplicate`。

| 观测 | 值 |
| --- | --- |
| POST /auth/register 带 `role=admin` | 422 `VALIDATION_ERROR`，details.unknown_fields 含 `role` |
| 注册后 `SELECT COUNT(*) FROM users WHERE role='admin'` | 0 |
| 正常学生注册 | 201，`role=student`、`active=true`，响应不含 `password_hash` |
| 重复登录名再注册 | 409 `DUPLICATE` |

### T-001-02 教师甲查询教师乙班级对象返回 404

覆盖用例：`test_T001_02_teacher_cannot_reach_other_teachers_class`、`test_T001_02_admin_sees_all_classes`。

| 观测 | 值 |
| --- | --- |
| 教师甲 `GET /classes/{乙的班}/enrollments` | 404 `NOT_FOUND` |
| 教师甲 `GET /classes` | 只返回本人任教班级 |
| 学生 `GET /classes/{班}/enrollments` | 403 `FORBIDDEN`（角色不允许的集合操作） |
| 管理员 `GET /classes` | 返回全部班级 |

「猜测学生答案 ID 同样拒绝」依赖 SPEC-009 的答案对象，本任务仅验证可复用的对象权限机制（按 `classes.teacher_id` 现算 + 跨班 404），该机制在 SPEC-009 实现时需接入其答案对象并补测，见第 5 节。

### T-001-03 退出、禁用或改密码后旧会话返回 401；缺 CSRF 写操作返回 403

覆盖用例：`test_T001_03_missing_csrf_is_rejected`、`test_T001_03_logout_invalidates_session`、`test_T001_03_deactivation_invalidates_session`、`test_T001_03_password_change_invalidates_sessions`、`test_T001_03_change_password_requires_current_password`、`test_T001_03_role_change_invalidates_session`。

| 场景 | 观测 |
| --- | --- |
| 写请求缺 `X-CSRF-Token` 或令牌错误 | 403 `CSRF_FAILED` |
| 退出后用旧 Cookie 重放 `GET /me` | 401（服务端已删除会话行） |
| 管理员停用该账号后旧 Cookie 重放 | 401 |
| 改密码后旧 Cookie 重放 | 401；原密码登录 401，新密码登录 200 |
| 角色变更后旧 Cookie 重放 | 401 |
| 改密码未提供当前密码 | 422 |

### T-001-04 学生已在班甲再加入班乙返回 409；班级换教师后旧教师失去访问权

覆盖用例：`test_T001_04_student_can_have_only_one_active_class`、`test_T001_04_teacher_change_takes_effect_immediately`。

| 观测 | 值 |
| --- | --- |
| 学生有效在班甲时再加入班乙 | 409 `DUPLICATE` |
| 先退出班甲再加入班乙 | 200，且学生 `GET /classes` 只看到班乙 |
| 管理员把班甲改派给教师乙 | 200 |
| 改派后教师甲访问班甲名单 | 404 |
| 改派后教师乙访问班甲名单 | 200 |

### 其他边界

- 最后一名有效管理员：`test_last_admin_cannot_be_disabled_or_demoted`（停用/降级均 409；存在第二名管理员后降级成功）。
- 越权：`test_admin_endpoints_reject_non_admin`（学生 `GET /users` 403、`POST /classes` 403）。
- 凭据：`test_password_hashed_and_secrets_never_exposed`（库存散列非明文；响应无 `password_hash`；会话 Cookie `HttpOnly`；库内 `token_hash` 为 64 位摘要）。
- 会话轮换：`test_login_session_is_rotated`（登录后会话标识与匿名阶段不同）。
- 登录限流：`test_login_rate_limited_after_repeated_failures`（15 分钟内 10 次失败后 429，附 `Retry-After`）。
- 管理员初始化：`test_init_admin_refuses_duplicate_login_name`、`test_init_admin_rejects_short_password`。

## 5 未执行／待后续模块集成验证

- **学生答案等跨班对象**：SPEC-009 起才有答案对象，`test_T001_02` 只覆盖班级对象；后续模块必须把同级 `teacher_id`/班级校验接到自己的对象上并补测，本报告不记为已通过。
- **`seed-demo`（两教师两班样例）**：涉及课程内容，随各业务模块交付，未实现。
- **Element Plus / ECharts 与算法库**：仍按 SPEC-000 的记录未安装；本 Spec 页面用原生 HTML/CSS 实现，与 SPEC-000 的 HomeView 一致。README 列出的目标前端栈未因此变更契约。
- **迁移 downgrade**：初次实现时只执行了 upgrade；评审阶段在一次性数据库补测，见第 7 节。
- **部署形态**：未在局域网、HTTPS、生产 WSGI + 前端构建同源下重跑 SPEC-001 流程；本轮只验证开发形态与测试。
- **负载**：未做课堂并发或延迟测试（属 NFR-02/03，留待集成）。
- 未提交/未开始 #5 及之后的模块；未合并 PR、未关闭 Issue。

## 6 契约与共享代码变更

- 未改变 APIC 的路径、字段或状态码；E001—E010 按已合并文档实现。
- `app/errors.py` 的 `ApiError` 增加可选 `headers`，用于 APIC 第 1 节已要求的 429 `Retry-After`。
- 会话读取失败按 503 `DB_BUSY` 返回，健康检查跳过会话读取以保持 SPEC-000 的 503 语义。
- `tests/backend/test_migrations.py` 原先硬编码期望 `alembic_version = '0001_baseline'`；新增迁移后改为按 Alembic head 动态断言，属测试随迁移链前移的必要更新，未放宽任何验收条件。
- 以上均记录在 [CHG-RB](../../CHG-RB.md) 第 1 节。

## 7 独立评审补充（2026-09-29）

评审发现角色变更可留下指向非教师的班级、非学生的有效入班关系，或无学号学生；停用班级及停用学生仍能新增有效入班关系。现已在服务层拒绝这些操作，并在 `users` 表增加学生必须有学号的约束。未修改 E001—E010 的路径或字段。补充了两条针对关系完整性的回归测试，并在一次性数据库验证 `0002` 可升级、回退、再升级。

在 `feature/spec-001` 工作树使用项目虚拟环境执行 `python -m pytest tests/backend -q`：`35 passed`。前端单测 `17 passed`，`npm run build` 成功；文档检查脚本未发现问题，`git diff --check` 无空白错误。原第 2 节的 `32 passed` 是初次实现时的记录，以本节的复核结果为准。
