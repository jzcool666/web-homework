# SPEC-014 执行报告

日期：2026-09-29。对象：SPEC-014 实验学习统计。提交：`9f37110`（分支 `feature/spec-014`，基线 `develop` `f179b4c`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-014（E058 与教师实验统计页）。未实现或未执行的项在第 5 节逐条列出。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用既有锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、pandas 等已在 SPEC-010 引入）；本 Spec 未新增依赖 |
| 前端依赖 | 沿用既有锁定版本；本 Spec 未新增依赖 |

## 2 命令与结果

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend -q` | 0 | `190 passed`（SPEC-014 新增 12 条；既有 SPEC-000—013 用例继续通过）。整轮耗时约 14 分钟 |
| 2 | `npm run test:unit`（frontend） | 0 | 16 个测试文件、`104 passed`（SPEC-014 新增 13 条） |
| 3 | `npm run build`（frontend） | 0 | 构建成功，产物含 `TeacherExperimentStatsView` 分块 |
| 4 | `git diff --check` | 0 | 无空白错误 |
| 5 | 文档一致性检查（项目外 `开发工作区/tools/check_docs.py`） | 0 | 未发现问题：接口 71 条、模块用例 72 条（18 份 Spec × 4 且与测试计划描述逐字一致）、相对链接 213 条有效 |

**迁移**：本 Spec 只读既有表，未新增字段，因此**没有新迁移**；`flask db upgrade` 仍停在既有 head `0007_spec013`。

## 3 浏览器实际流程

以同源方式启动（后端 `create_app()` 在 5002 端口同时提供 API 与已构建的前端），用应用内浏览器驱动**真实 DOM 事件**：在 `/login` 用真实 `input`/`change` 事件填入教师账号后 `requestSubmit()`，再以 `history.pushState` + `popstate` 做 SPA 导航到 `/teacher/experiment-stats`，最后断言 DOM 与接口。

| 观测 | 结果 |
| --- | --- |
| 登录（teacher_aaa） | `GET /api/v1/me` 200 |
| 导航高亮 | `a.nav-item--active` 文本为「实验统计」 |
| 汇总卡片 | 已发布实验 2、参与人数 2、通过人数 1、总通过率 50.0%、尝试次数 4 |
| 逐实验明细 | 实验一（2 参与 / 1 通过 / 4 尝试 / 50.0%）；实验二（0 / 0 / 0 / **—**） |
| 窗口说明 | `统计窗口：2026-08-30T07:29:35Z → 2026-09-29T07:29:35Z（UTC，右开区间）` |
| CSV 导出 | 200，`text/csv`，带 UTF-8 BOM；summary 行 `2,2,1,0.5,4`；实验二 `pass_rate` 为空列 |
| JSON 接口 | 与页面、CSV 三处数字一致 |
| 错误提示 | 无（`.error` 不存在） |

无参与时页面显示「—」而不是 0%，与 SPEC-014「无参与返回 null」一致。

方法学限制：应用内浏览器面板常为 0×0 或最小化，基于坐标的点击与截图不可靠。上述流程改用页面自身的处理函数（真实输入事件 + `requestSubmit` + 路由事件）驱动，与用户点击走同一条代码路径与同一组 HTTP 请求；**本轮没有可提供的截图**，不作已截图的记录。

## 4 逐条验收

### T-014-01 一学生失败两次后通过：参与 1，通过 1，尝试 3，通过率 1

用例 `test_T014_01_repeated_attempts_count_once_as_participant`：同一学生用三个不同 `request_key` 提交（通过 E050 真实提交，判分由服务端重算），前两次失败、第三次通过。

观测：`participants=1`、`passed_students=1`、`attempt_count=3`、`pass_rate=1.0`；逐实验行同为 1/1/3/1.0。

### T-014-02 第二学生只失败一次：参与 2，通过 1，尝试 4，通过率 .5

用例 `test_T014_02_second_student_changes_pass_rate`：在 T-014-01 基础上增加一名只失败一次的学生。

观测：`participants=2`、`passed_students=1`、`attempt_count=4`、`pass_rate=0.5`；逐实验行 2/1/4/0.5。同结果在浏览器实测中复现（第 3 节）。

### T-014-03 无参与显示 null；窗口外尝试不计入；按实验过滤正确

| 场景 | 用例 | 观测 |
| --- | --- | --- |
| 窗口内无任何尝试 | `test_T014_03_no_participation_returns_null` | `participants=0`、`pass_rate=null`、逐实验 `pass_rate=null`；`published_count` 仍为 2 |
| 一条尝试被改到 2020 年 | `test_T014_03_attempts_outside_window_are_excluded` | 参与与尝试都只计窗口内那一条（1/1） |
| `experiment_id` 过滤 | `test_T014_03_experiment_filter_narrows_scope` | 只返回该实验，`published_count=1`，各口径随之收窄 |
| 参数边界 | `test_T014_03_window_parameters_are_validated` | 只给 from、from≥to、窗口 >366 天、缺 class_id、`format=xlsx` 均 400 |

### T-014-04 CSV 和 JSON 人数一致；教师乙不能导出班甲数据

用例 `test_T014_04_csv_matches_json`：逐段核对 CSV 与 JSON——summary 的 `published_count/participants/passed_students/attempt_count/pass_rate` 与顶层字段相等；每条实验行的 `participants/passed_students/attempt_count/experiment_title/pass_rate` 与该实验块相等；`pass_rate` 为 null 时 CSV 单元格为空。列顺序固定为 `section,experiment_id,experiment_title,window_from,window_to,published_count,participants,passed_students,pass_rate,attempt_count`。

用例 `test_T014_04_other_teacher_cannot_read_or_export`：教师乙请求班甲的 JSON 与 CSV 均 404，且班级确实存在（说明是权限而非不存在）；教师乙读自己班级 200。用例 `test_T014_04_non_teacher_roles_are_rejected`：学生 403、管理员 403、匿名 401。

### 其他口径边界

- `test_only_current_roster_is_counted`：班乙学生的尝试不计入班甲；同一实验在班乙单独统计；学生退班后其历史尝试不再计入（退班历史仍留在个人记录里）。
- `test_total_passed_counts_students_passing_any_experiment`：顶层通过人数是「至少通过一个实验」的学生数，与逐实验口径分开给出。
- `test_summarize_experiment_stats_handles_empty_input`：纯函数在零输入下 `pass_rate` 为 null。

## 5 未执行／未完成项

- **没有新迁移**，因此没有 downgrade 变更需要验证。
- **未在生产 WSGI + 前端构建同源之外的环境**（局域网、HTTPS）重跑；未做课堂并发或延迟测试（属 NFR-02/03，留待集成）。
- **未实现「易错实验排行」的独立失败率排序**：SPEC-014 只要求参与/通过/尝试/通过率，明细按参与人数降序给出，未排名失败率。
- **未做历史班级归属分析**：SPEC-014 第 4 节第 4 条明确要求另立变更，不从当前名单倒推。
- **未改动 #10（备课）相关业务文件**；若 #10 先合入 develop，本分支需 rebase 后重跑受影响测试。
- 未合并 PR、未关闭 #13、未开始下一个模块。

## 6 契约与共享文件变更

- **APIC 未改**：E058 的路径、参数、字段名与状态码按已合并文档实现。
- **SPEC-014 第 4 节补第 5、6 条**：明确 `published_count` 与 `experiments[]` 同为「已发布实验」作用域且条数一致、顶层数字为作用域合计、未入班/已退班不计入任何班级统计，以及本模块无迁移。
- **前端共享文件**：`router/index.js` 与 `navigation/index.js` 各新增一条教师「实验统计」入口；`navigation/__tests__/navigation.spec.js` 的测试用路由表补上该路由并新增一条高亮断言（该文件用自建路由表挂载 AppShell，不补会因解析不到路由而失败）。SPEC-013 的教师端计划入口保持原样。
- **窗口与 class_id 解析**采用本模块内的私有实现（与 SPEC-010 的统计接口口径一致），未改动 `api_assessment.py` 的同类逻辑，以免与并行模块产生文件冲突；后续可抽为公共模块。
- 以上均记录在 [CHG-RB](../../CHG-RB.md) 第 1 节。
