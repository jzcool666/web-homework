# SPEC-002 执行报告

日期：2026-09-29。对象：SPEC-002 考勤与请假。提交：`d672a37`（分支 `feature/spec-002`，基线 `develop` `be65e1c`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-002（E028—E034、迁移 0003、考勤与请假页面）。不包含尚未实现的后续模块，也不把设计意图记为运行通过。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用 SPEC-000/001 锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、waitress 3.0.2、python-dotenv 1.1.1、pytest 9.1.1）；本 Spec 未新增依赖 |
| 前端依赖 | 沿用 SPEC-000/001 锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等）；未新增依赖 |

签到码散列使用标准库 `hashlib.sha256`，未引入额外库。

## 2 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend -q` | 0 | `70 passed`（SPEC-002 新增 35 条，SPEC-000/001 原有 35 条继续通过） |
| 2 | `python -m pytest tests/backend/test_spec002.py -q` | 0 | `35 passed` |
| 3 | `flask --app app:create_app db upgrade`（工作目录 backend） | 0 | `Running upgrade 0002_spec001 -> 0003_spec002` |
| 4 | `flask --app app:create_app db current` | 0 | `0003_spec002 (head)` |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 5 | `npm run test:unit` | 0 | 5 个测试文件、`25 passed`（其中 SPEC-002 新增 1 个文件 8 条） |
| 6 | `npm run build` | 0 | `44 modules transformed`，产出 `dist/`（含 `TeacherAttendanceView`、`StudentClassroomView` 分块） |
| 7 | `git diff --check` | 0 | 无空白错误 |

## 3 浏览器实际流程

后端以构建产物同源方式启动（`create_app().run(port=5051)`，工作目录 `backend`），页面访问 `http://localhost:5051`，使用 `frontend/dist` 的构建产物。按真实用户路径操作，网络观测如下：

| 步骤 | 网络观测 | 界面结果 |
| --- | --- | --- |
| 教师 `teacher_demo` 登录后打开「考勤与请假」 | `GET /classes` 200 → `GET /attendance-tasks?class_id=1` 200 → `GET /leave-requests?class_id=1` 200 | 班级自动选中「时序逻辑演示班」，表单按本地时间预填开始/迟到/结束 |
| 教师发布签到 | `POST /attendance-tasks` **201** | 提示「创建成功，六位签到码：336814（只显示这一次）」，任务列表出现「可签到 / 未结算」 |
| 学生 `stu_demo1` 打开「我的课堂」 | `GET /attendance-tasks?class_id=1` 200 → `GET /attendance-tasks/1/records` 200 | 显示班级、任务窗口、「可签到 / 待签到」，签到与请假表单出现 |
| 学生用正确码签到（迟到线之后） | `POST /attendance-tasks/1/sign-ins` **200** | 「签到成功：迟到（2026-09-29 09:18）」 |
| 学生 `stu_demo2` 提交请假 | `POST /leave-requests` **201** | 「请假申请已提交，等待教师审批」，页面显示「待审批（校外竞赛，无法到场）」 |
| 教师查看名单 | `GET /attendance-tasks/1/records` 200 | 名单行：甲「迟到 2026-09-29 09:18」、乙「待签到」、丙「待签到」 |
| 教师批准请假 | `PATCH /leave-requests/1` **200** | 「已批准请假」；乙变为「请假」，甲仍为「迟到」未被覆盖 |
| 教师发布窗口已过期的任务并结算 | `POST /attendance-tasks` 201 → `POST /attendance-tasks/2/settlements` 200 | 新任务显示「已结束 / 已结算」，名单三人全部「缺勤」 |
| 教师重置签到码 | `POST /attendance-tasks/1/code-resets` **200** | 「重置成功，六位签到码：472761（只显示这一次）」 |

重置后另行用 curl 复核旧码失效：旧码 `336814` 返回 `422 VALIDATION_ERROR`，新码 `472761` 返回 `200`（`status=late`）。同一人对同一任务连续 5 次错误码返回 422，第 6 次返回 **429** 且带 `Retry-After`。

库内核对（直接读 SQLite 文件）：

| 观测 | 值 |
| --- | --- |
| `attendance_tasks.code_hash` | SHA-256 摘要；曾出现过的三个明文码 `336814`、`472761`、`367682` 在整个 db 文件中均搜索不到 |
| 重置后 `version` | 1 → 2，`code_hash` 随之改变 |
| `attendance_records` | 任务 1：(生甲, late, 01:18:05Z)、(生乙, leave, null)、(生丙, late, 01:20:42Z)；任务 2：三人均 absent |
| `leave_requests` | 状态 approved、reviewer_id=2、reviewed_at 01:19:49Z、version 2 |
| 时间入库 | 表单本地 09:11 存为 `2026-09-29T01:11:00Z`，页面按本地时区显示回 09:11 |

### 方法学限制（必须与结论一起读）

1. **应用窗口被其他窗口遮挡**：基于坐标的点击与截图不稳定（点击报「无法归因到框架」、截图超时）。表单提交改用页面内的 `requestSubmit()`／对真实按钮派发 `click()` 事件——与鼠标点击走同一条提交事件和处理函数，但不等同于真实鼠标点击。填表与路由跳转为真实浏览器行为。
2. **内嵌预览浏览器未能稳定保留应用的 HttpOnly 会话 Cookie**：整页刷新后，若干次已认证请求（`GET /classes`、`POST /sign-ins`）返回 401/403，而同一页面的其他请求正常。已排除应用缺陷：服务器下发的 `Set-Cookie` 属性正确（`curl -i` 核对：`HttpOnly; Path=/; SameSite=Lax; Max-Age=28800`），会话行在库内有效且未过期，用 curl Cookie jar 重复执行同一组流程全部成功，且该认证机制属 SPEC-001、本次未改动。因此每个交互步骤都在同一页面会话内、刚登录之后立即执行；上表网络观测均取自这些成功请求。
3. 未做局域网、HTTPS、生产 WSGI 形态下的复测；未做课堂并发或延迟负载测试（属 NFR-02/03，留待集成）。

## 4 逐条验收

### T-002-01 opens_at 时可签到，late_at 时为迟到，closes_at 时拒绝；时间使用服务器

覆盖用例：`test_T002_01_sign_in_at_opens_at_is_present`、`test_T002_01_sign_in_before_late_at_is_present`、`test_T002_01_sign_in_at_late_at_is_late`、`test_T002_01_sign_in_at_closes_at_is_rejected`、`test_T002_01_sign_in_before_opens_at_is_rejected`、`test_T002_01_client_cannot_submit_time`。

测试把服务器时钟冻结在固定时刻，精确命中三个边界：

| 时刻 | 结果 |
| --- | --- |
| `opens_at` 整点 | 200，`status=present`，`signed_at` 等于该时刻 |
| `opens_at` + 4:59 | 200，`status=present` |
| `late_at` 整点 | 200，`status=late` |
| `closes_at` 整点 | 409 `DEADLINE_PASSED`；直接查库确认无签到（`signed_at` 全为 NULL，状态仍 pending） |
| `opens_at` 之前 1 分钟 | 409 `DEADLINE_PASSED` |

服务器时间：签到请求体只接受 `code`，提交 `signed_at` 等时间字段返回 422 且 `details.unknown_fields` 列出该字段，客户端无法影响判定。浏览器实测在迟到线之后签到得到「迟到」，与库内 `signed_at=2026-09-29T01:18:05Z` 一致。

### T-002-02 同人并发两次签到仅一条记录；学生不在名单返回 404

覆盖用例：`test_T002_02_concurrent_sign_ins_keep_single_record`、`test_T002_02_repeat_sign_in_returns_original_record`、`test_T002_02_student_outside_roster_gets_404`、`test_T002_02_roster_copied_as_pending_on_publish`。

| 观测 | 值 |
| --- | --- |
| 两个线程经 `Barrier` 同时发起签到 | 两个响应均 200，返回同一条记录 id |
| 该学生该任务的记录数 | 1（`SELECT COUNT(*)` = 1），`status=present` |
| 窗口内重复签到 | 200，返回原记录，`signed_at` 不被刷新 |
| 乙班学生签到甲班任务 | 404 `NOT_FOUND` |
| 发布时名单 | 甲班两人的记录为 `pending`、`signed_at` 为 NULL；不含乙班学生 |

并发不产生第二行是因为记录不靠插入产生：发布时已按名单建好唯一行，签到只做
`UPDATE ... WHERE status='pending'`，命中 0 行时回读既有事实返回。两个线程实测都得到 200 与同一 id。

### T-002-03 任务结束结算两次结果一致；已签到和已请假记录不被覆盖

覆盖用例：`test_T002_03_settlement_is_idempotent`、`test_T002_03_read_settles_ended_task_and_keeps_signed_and_leave`、`test_T002_03_settlement_before_close_is_rejected`、`test_T002_03_unsettled_ended_task_still_shows_pending`、`test_T002_03_late_sign_in_counted_as_late`。

| 观测 | 值 |
| --- | --- |
| 结算返回 | `{present, late, leave, absent}` 计数；两次调用（间隔 9 分钟）返回的 `settled_at` 与计数完全相同 |
| `settled_at` | 只记首次结算时间，重复结算不刷新 |
| 已签到（present）与已请假（leave） | 结算前后状态不变，未被改成 absent |
| 结束前结算 | 409 `DEADLINE_PASSED`，且 `settled_at` 仍为 NULL |
| 未结算的已结束任务 | 直接查库仍为 pending，`settled_at` 为 NULL——不显示为已缺勤；读取接口（`GET /records`、`GET /attendance-tasks`）会触发结算 |

浏览器实测：窗口已过期的任务在教师查看列表时即显示「已结算」，名单三人全部「缺勤」。

### T-002-04 截止后审批原待处理请假可将 absent 改 leave；已签到者审批返回 409

覆盖用例：`test_T002_04_approve_after_deadline_turns_absent_into_leave`、`test_T002_04_approve_signed_in_student_is_409`、`test_T002_04_approved_leave_blocks_sign_in`、`test_T002_04_leave_request_after_close_is_rejected`、`test_T002_04_duplicate_leave_request_is_409`、`test_T002_04_review_twice_and_reject_keeps_record`、`test_T002_04_stale_version_is_409`。

| 观测 | 值 |
| --- | --- |
| 截止后先结算（该生 absent）再批准 | 200，记录由 `absent` 改为 `leave`；再结算计数为 leave 1 / absent 1 |
| 已签到学生再审批请假 | 409 `STATE_CONFLICT`，记录仍为 `present` |
| 已批准请假后签到 | 409 `STATE_CONFLICT` |
| 结束前未申请、结束后申请 | 409 `DEADLINE_PASSED` |
| 同一任务重复申请 | 409 `DUPLICATE` |
| 已审批后再次审批 | 409 `STATE_CONFLICT` |
| 携带过期 version | 409 `VERSION_CONFLICT` |
| 驳回 | 200，记录保持 pending，不改为 leave |

### 其他规则（第 4 节第 1、5 条）

| 观测 | 值 |
| --- | --- |
| 六位码只在创建/重置响应出现 | 列表响应无 `code` 也无 `code_hash`；库内只有 sha256 |
| 重置旧码立即失效 | 旧码 422，新码 200 |
| 重置的状态与并发保护 | 结束后重置 409 `DEADLINE_PASSED`；version 不符 409 `VERSION_CONFLICT` |
| 错误尝试限流 | 同人同任务 1 分钟内第 6 次 429 并带 `Retry-After`；不影响同班其他学生；成功签到后计数清零 |
| 权限 | 教师访问他班任务 404；管理员访问考勤接口 403；学生只读本人记录；匿名 401；缺 CSRF 403 |
| 字段校验 | 窗口不满足 `opens_at ≤ late_at < closes_at` 返回 422 并指向 `late_at`；未知字段 422 |

## 5 未执行与局限

- **未执行**：局域网/HTTPS/生产 WSGI 形态复测；60 人课堂负载与并发延迟；E2E 自动化（Playwright 尚未引入，本轮浏览器流程为手工驱动）。
- **未执行**：`E055 /analytics/attendance` 统计接口（属 SPEC-003），本模块只保证记录与结算结果正确。
- **已知限制（代码内注明）**：教师名单页按 APIC 上限取 `page_size=100` 的第一页；班级人数超过 100 时需要翻页，属首版限制。
- **已知限制（沿用 SPEC-001 部署说明）**：签到码错误限流为进程内计数，单实例重启会清空。
- **浏览器证据的强度**：受第 3 节限制 1、2 影响，点击与整页刷新后的会话维持不稳定；已完成的观测为真实请求与真实渲染，但不能等同于完整的人工鼠标走查。
- 未合并 PR、未关闭 Issue #11，未开始其他模块。

## 6 契约与共享代码变更

- **增量读取字段**：`AttendanceRecord` 与 `Leave` 响应新增只读联表字段 `student_display_name`、`student_no`。教师查看签到名单与请假申请时需要识别学生，而 `GET /users` 仅管理员可用，按 APIC 第 2 节模型前端无法解析学号。字段为增量，未增加表或列，已同步 APIC 第 4 节与 CHG-RB 第 1 节。
- **迁移链**：新增 `0003_spec002`（`down_revision = 0002_spec001`）。`tests/backend/test_migrations.py` 原先用 `downgrade(app, "-1")` 断言「回退一步即清空 SPEC-001 的表」，迁移链变长后该断言不再成立，改为回退到 `base` 再升级；只改断言方式，未放宽任何验收条件。与并行的 #5 合并时需按提交先后把两条新迁移接成单一链。
- 未改变 E028—E034 的路径、入参、状态码或公共错误码。
- 上列变更均登记在 [CHG-RB](../../CHG-RB.md) 第 1 节。

## 7 独立评审补充（2026-09-29）

评审发现停用班级仍可发布签到任务并接受签到、请假、重置码；已退出班级的学生也可凭发布时的名单快照继续提交。现已在这些新活动入口复核班级有效状态与当前入班关系，历史读取和结算不变。新增两条针对性回归用例。初次实现阶段的后端 `70 passed` 保留为原始记录；本分支修正后完整后端测试 `72 passed`。与 SPEC-005 合并后的结果另行复核。

## 8 与 SPEC-005 集成复核（2026-09-29）

PR #29 先合入 `develop` 后，考勤迁移改为 `0004_spec002`，父迁移为 `0003_spec005`；Alembic 只报告 `0004_spec002 (head)`。应用同时注册课程内容与考勤接口，前端同时保留课程学习、教师内容管理和考勤页面路由及入口。

在合并代码上实测：后端 `90 passed`（包含迁移回退和再升级），前端 `34 passed`，Vite 构建成功（51 modules），文档检查未发现问题。第 2 节记录的是本模块首次提交时的原始结果；本节是合并后最终复核结果。
