# SPEC-003 执行报告

日期：2026-10-02。对象：SPEC-003 出勤与风险因素统计。提交：`1ceebcb`（分支 `feature/spec-003`，基线 `develop` `a28fce4`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-003（E055 与教师端出勤统计页）。未实现或未执行的项在第 5 节逐条列出。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用既有锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、pandas、numpy 等已在 SPEC-006/010 引入）；本 Spec 未新增依赖 |
| 前端依赖 | 沿用既有锁定版本；本 Spec 未新增依赖 |

## 2 命令与结果

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend/test_spec003.py -q` | 0 | `11 passed` |
| 2 | `python -m pytest tests/backend -q` | 0 | `229 passed`（全量回归，整轮 1218.88 秒 ≈ 20 分 19 秒） |
| 3 | `npm run test:unit`（frontend） | 0 | 21 个测试文件、`137 passed`（SPEC-003 新增 17 条） |
| 4 | `npm run build`（frontend） | 0 | 构建成功，产物含 `TeacherAttendanceAnalyticsView` 分块 |
| 5 | `git diff --check` | 0 | 无空白错误 |
| 6 | 文档一致性检查（项目外 `开发工作区/tools/check_docs.py`） | 0 | 未发现问题：接口 71 条、模块用例 72 条、相对链接 223 条有效 |

**迁移**：本 Spec 只读既有表，未新增字段，因此**没有新迁移**；`flask db upgrade` 仍停在既有 head `0008_spec008`。

**关于整轮耗时**：229 条用例共 20 分 19 秒（约 5.3 秒/条），成本主要是两项既有设计，不是本轮实现引入的：Werkzeug 的 scrypt 口令散列实测约 0.34 秒/次（每个用例都要建管理员、教师、学生并登录校验），以及每个用例建独立库都要跑完整 8 步 Alembic 链（实测约 0.38 秒）。本轮只增加了 11 条用例，未改变这两项成本；若后续需要更快反馈，可在测试夹具中复用已迁移的库或降低测试环境的口令散列强度，但那属于独立变更。

## 3 浏览器实际流程

以同源方式启动（`create_app()` 在 5056 端口同时提供 API 与已构建前端），用应用内浏览器驱动**真实 DOM 事件**：在 `/login` 用真实 `input`/`change` 事件填入教师账号后 `requestSubmit()`，再以 `history.pushState` + `popstate` 做 SPA 导航到 `/teacher/analytics/attendance`，最后断言 DOM 与接口。

固定种子：1 个班、5 条已结算考勤任务、5 名出勤率 0.2—1.0 递增且测评均分 40—80 递增的学生，另有 1 名全请假学生。

| 观测 | 结果 |
| --- | --- |
| 登录（teacher_aaa） | `GET /api/v1/me` 200 |
| 导航高亮 | `a.nav-item--active` 文本为「出勤统计」 |
| 出勤分布 | 已结算任务 5、出勤 15、迟到 0、请假 5、缺勤 10、出勤率 60% |
| 学生明细 | 6 行：出勤率 20%／40%／60%／80%／100%，全请假学生显示 **—（无分母）** |
| 相关分析 | 相关系数 1、共同样本 5 |
| CSV 导出 | 200，`text/csv`，带 UTF-8 BOM；summary 行 `5,15,0,5,10,0.6,1.0,5`；6 条 student 行与 JSON 逐项一致，全请假学生的 `attendance_rate` 为空列 |
| JSON 接口 | 与页面、CSV 三处数字一致 |
| 错误提示 | 无（`.error` 不存在） |

方法学限制：应用内浏览器面板常为 0×0 或最小化，基于坐标的点击与截图不可靠。上述流程改用页面自身的处理函数（真实输入事件 + `requestSubmit` + 路由事件）驱动，与用户点击走同一条代码路径与同一组 HTTP 请求；**本轮没有可提供的截图**，不作已截图的记录。

## 4 逐条验收

### T-003-01 present=2、late=1、leave=1、absent=1 得到出勤率 0.75

用例 `test_T003_01_attendance_rate_excludes_leave`：一条已结算任务，5 名学生分别 present/present/late/leave/absent。

观测：`settled_tasks=1`、`counts={present:2,late:1,leave:1,absent:1}`、`attendance_rate=0.75`（请假从分母排除）；只有请假的学生的个人出勤率为 null，缺勤学生为 0.0，出勤学生为 1.0；响应同时给出 `student_no`/`display_name`。

### T-003-02 全部请假或无结束任务返回 null

| 场景 | 用例 | 观测 |
| --- | --- | --- |
| 全员请假 | `test_T003_02_all_leave_returns_null` | `counts={present:0,late:0,leave:5,absent:0}`、`attendance_rate=null`，逐学生同样为 null |
| 窗口内只有进行中的任务 | `test_T003_02_no_settled_task_in_window_returns_null` | `settled_tasks=0`、`attendance_rate=null`、`students=[]` |
| 窗口外的已结算任务 | 同上 | 不计入 |
| 已结束但未结算 | `test_ended_pending_records_are_settled_before_counting` | 统计前先结算：`settled_at` 落库、pending 全部转 absent、出勤率 0.0 |

### T-003-03 相关系数

| 场景 | 用例 | 观测 |
| --- | --- | --- |
| 5 个完全同向非恒定样本 | `test_T003_03_five_aligned_samples_give_one` | 出勤率 0.2—1.0 与均分 40—80 同向，`coefficient=1.0`、`n=5`、`reason=null` |
| 只有 4 个共同样本 | `test_T003_03_fewer_than_five_samples_returns_null_with_reason` | `coefficient=null`、`n=4`，`reason` 说明样本不足 |
| 至少一列恒定 | `test_T003_03_constant_column_returns_null_with_reason` | 全员每次出勤 → 出勤率恒为 1，`coefficient=null`、`n=5`，`reason` 说明取值恒定 |
| practice 不得混入成绩列 | `test_practice_assessments_are_excluded_from_scores` | 同向样本下额外插入一条 class_id 为空的自练提交；若被计入则相关系数不再是 1.0，实测仍为 `1.0` |

### T-003-04 权限、CSV 对账与转义

用例 `test_T003_04_cross_class_access_is_rejected`：教师乙读班甲的 JSON 与 CSV 均 404（班级确实存在，是权限而非不存在）；教师甲读班乙 404；学生 403、管理员 403、匿名 401。

用例 `test_T003_04_csv_matches_json_and_escapes_formulas`：CSV summary 行的四种状态计数分别等于 JSON 顶层 `counts`、也等于逐学生行之和；`settled_tasks`、`attendance_rate`、窗口字段一致；每条 student 行与 JSON 的 `students[]` 逐项相等；以 `=SUM(A1:A9)` 为姓名的学生在 CSV 中写成 `'=SUM(A1:A9)`，导出文本里不再出现未转义的公式。

用例 `test_invalid_parameters_are_rejected`：缺 class_id、只给 from、from≥to、窗口 >366 天、非 RFC3339 时间（422）、`format=xlsx` 均按预期拒绝。

## 5 未执行／未完成项

- **没有新迁移**，因此没有 downgrade 变更需要验证。
- **未在生产 WSGI 同源之外的环境**（局域网、HTTPS）重跑；未做课堂并发或延迟测试（属 NFR-02/03，留待集成）。
- **未实现「易错实验排行」或风险分组**：SPEC-003 第 1 节明确非目标为因果结论与纪律处罚，本模块只给出相关分析与原因说明。
- **同日转班/反复入班的归属**：`students` 取窗口内的考勤记录名单，而每份考勤记录的名单是发布时的快照，因此统计口径本身不受转班影响；但没有按入班日/退班日再切分。
- **未跑迁移回滚**：本模块无新迁移。
- 未合并 PR、未关闭 Issue、未开始下一个模块。

## 6 契约与共享文件变更

- **APIC 第 7 节**：`AttendanceStats.students[]` 增加只读 `student_no`/`display_name`（教师需要认出学生，而 GET /users 仅管理员可用，与 SPEC-002 同一理由）；新增一段 E055 口径补充，固定窗口按 `opens_at`、只含已结算任务、`students` 为窗口历史名单、成绩列只取非 practice 且 `submitted_at` 在窗口内的提交，以及 CSV 列顺序与三个 section 的对应关系。
- **SPEC-003 第 4 节**新增第 5、6 条，写明同样的口径。
- **结算复用**：`api_attendance_stats.py` 引用 SPEC-002 的 `_settle_task`，不另写一套结算语义；未修改 `api_attendance.py`，避免与并行模块冲突。该函数当前是模块私有名，若后续还有模块要复用，建议提升为公开函数。
- **前端共享文件**：`router/index.js` 与 `navigation/index.js` 各新增一条教师「出勤统计」入口；`navigation/__tests__/navigation.spec.js` 的测试用路由表补上该路由并新增一条高亮断言（该文件用自建路由表挂载 AppShell，不补会因解析不到路由而失败）。
- **未新增依赖**：pandas/numpy 已在 `backend/requirements.txt` 中。
- 以上均记录在 [CHG-RB](../../CHG-RB.md) 第 1 节。
