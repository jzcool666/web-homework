# SPEC-011 执行报告

日期：2026-10-02。对象：SPEC-011 约束智能组卷。提交：`a28fce4`（分支 `feature/spec-011`，基线 `origin/develop` `a28fce4`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-011（E062 组卷与服务、教师「智能组卷」页面）。题库、测评、提交与反馈由 SPEC-009/010 交付、本模块复用，未重写；不包含尚未实现的后续模块。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| 后端依赖 | 沿用既有锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、pytest 9.1.1）；本 Spec **未新增依赖** |
| Node / npm | v24.18.0 / 11.16.0 |
| 前端依赖 | 沿用既有锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等）；未新增依赖 |

**算法口径与设计基线的差异（已登记 CHG-RB）**：设计基线第 4 节写 NumPy 建模 + SciPy `milp` 求解。本工程不引入外部求解器依赖，实现改为**确定性分支定界**（深度优先 + 递减上界剪枝），约束集合（题量、每难度配额、每知识点覆盖下限、同题唯一）与目标函数（0.8·p_i + 0.2·seed 随机项，取最大值）与基线等价，**输入输出契约、路径与状态码均未改变**。另把「已公开历史首答」明确为目标班级**已提交**首答（同 SPEC-010 E057 的全历史最早口径），无历史题目按拉普拉斯平滑取 p_i=1/2。

## 2 迁移：本模块未新增

DBD 第 5 节末段明确「组卷输入、候选版本指纹、随机种子、求解状态及所选题号保存在 `assessments.generation_json`，不另设孤立组卷表」。逐项核对后确认不缺字段：

| 需求 | 现有承载 |
| --- | --- |
| 生成草稿本体 | SPEC-009 的 `assessments`（`origin='generated'`、`state='draft'`）+ `assessment_items`（含题目快照） |
| 求解输入/种子/算法版本/候选指纹/所选题号 | `assessments.generation_json` |
| 候选题目与知识点标签 | `questions`、`question_knowledge` |
| 历史首答（错误数/机会数） | `submissions` + `submission_answers` + `assessment_items.question_id` |
| 班级名单 | SPEC-001 的 `enrollments` |

因此**没有新增迁移**，Alembic head 仍为 `0008_spec008`。一次性库往返（worktree 根目录，venv）：

```
DB: sqlite:///.../worktrees/issue-17/backend/instance/app.sqlite
Running upgrade 0001_baseline -> 0002_spec001 ... -> 0008_spec008
upgrade done   （单一 head，链上无分叉）
```

## 3 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest -q` | 0 | `227 passed in 1225.54s`（全量回归，含 SPEC-011 新增 9 条，既有模块用例继续通过） |
| 2 | `python -m pytest tests/backend/test_spec011.py -q` | 0 | `9 passed in 63.57s`（加强 T-011-04 断言后的复跑；全量那一轮跑的是同一文件未加强版本，两者都通过） |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 3 | `npm run test:unit` | 0 | 19 个测试文件、`125 passed`（SPEC-011 新增导航入口 1 条；补齐 navigation 测试路由表） |
| 4 | `npm run build` | 0 | 构建成功，产出 `TeacherPaperGenerationView-*.js`（8.72 kB）等分块 |

文档与其他：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 5 | `python ../tools/check_docs.py <worktree 根>` | 0 | 相对链接 222 条、JSON 块 5 个，未发现问题 |
| 6 | `git diff --check` | 0 | 无空白错误 |

## 4 浏览器实际流程（后端 5058 端口，同源构建产物）

后端以构建产物同源方式启动（`create_app().run(port=5058)`），页面 `http://localhost:5058`。演练数据由 `开发工作区/tools/seed_spec011.py` 建立（教师 `teacher_demo`、1 个班 4 名学生、4 个知识点、28 道已发布题：12 基础 / 10 进阶 / 6 挑战）。

| 步骤 | 网络观测 | 界面结果 |
| --- | --- | --- |
| 教师登录后打开「智能组卷」 | `GET /classes`、`GET /knowledge-points?published=true` 200 | 侧栏出现新入口「智能组卷」，页面标题「约束智能组卷」，班级默认「时序逻辑演示班」 |
| 填题量 10、难度 4/4/2、种子 20261002，添加两个知识点下限量 3/2，点「生成草稿」 | `POST /paper-generations` **201** | 「已生成草稿 #7，共 10 题」；求解状态「已证明最优」；难度 基础4/进阶4/挑战2；覆盖表 `同步复位 3/3 是`、`异步复位 3/2 是`；所选题号 `28、3、6、12、24、15、11、13、20、16` |
| 同 seed 再提交一次（接口层） | `POST /paper-generations` **201** | 返回 `selected_ids` 与上一次逐项相同（可重放） |
| 难度改为挑战 10（题库仅 6 道）再提交 | `POST /paper-generations` **422** | 页面显示「题库无法满足当前条件（已证明无解），请调整难度配额或知识点下限量」，并列出「难度 hard：需要 10 题，题库仅 6 题」 |
| 难度配额之和 ≠ 题量（5 vs 2+2） | 前端拦截并提示；接口直接请求为 **422 VALIDATION_ERROR** `fields.difficulty_counts` | — |
| 打开「测评与讲评」 | `GET /assessments?class_id=1` 200，`GET /assessments/7` 200 | 生成的草稿出现在列表中（`state=draft`，总分 100）；详情页 10 个条目，可继续改题或发布 |

补充说明：本次会话中 Browser 窗格的 `preview_click`/`preview_screenshot` 无法使用（点击不能落到帧上、截图 5 秒超时），因此上述界面结论取自 `preview_snapshot`（无障碍树）与页面内 `preview_eval` 的 DOM 读取，网络结论取自同一会话里的 `fetch` 响应；未使用截图作为证据。

## 5 验收清单对照

| 编号 | 结论 | 证据 |
| --- | --- | --- |
| T-011-01 | 通过 | `test_T011_01_selection_satisfies_count_difficulty_and_knowledge`：16 道候选（6/6/4）选 10 题 4/4/2，逐题难度计数精确、无重复，覆盖 `≥3`/`≥2` 且 `satisfied=true`；落库 `origin=generated`、`state=draft`、10 条 `assessment_items`，`generation_json` 与响应一致 |
| T-011-02 | 通过 | `test_T011_02_multitag_coverage_sum_exceeding_count_is_not_rejected`：`min_count` 之和 4 > 题量 2，两道双标签题同时满足，返回 201 而非误拒 |
| T-011-03 | 通过 | `test_T011_03a_difficulty_shortfall_returns_422_with_explanation`：hard 需 3 实有 1 → **422 INFEASIBLE_PAPER**，`details.constraints` 含 `{kind:difficulty, difficulty:hard, required:3, available:1}`。`test_T011_03b_timeout_without_solution_returns_503_not_422`：把 `PAPER_SOLVER_TIME_LIMIT_SECONDS` 设为 0 → **503 SOLVER_TIMEOUT**；恢复 2 秒后同一输入 → **422 INFEASIBLE_PAPER**，证明两条路径不混用 |
| T-011-04 | 通过 | `test_T011_04_same_seed_replays_and_history_changes_selection`：同 seed 两次 `selected_ids` 相同；四名学生全部答错最后一题后，该题因错误率最高必入选，且 `generation_json.priorities` 与作答前不同 |

公共错误约定另有 5 条用例覆盖：匿名 401、学生 403、跨班 `class_id` 404、停用班级 409、字段类 422（未知字段 / 配额和不等 / 知识点重复 / 知识点不存在 / 超过 18 个 / 题量越界）。

**超时用例的说明**：T-011-03 要求「模拟求解超时无可行解返回 503」。实现里限时来自配置项 `PAPER_SOLVER_TIME_LIMIT_SECONDS`（默认 2 秒），测试把它设为 0 秒，使搜索在未证明无解前即中止，从而稳定复现 503 而不必真的等待 2 秒；这不是放宽验收，而是把「限时」这一变量显式暴露出来。

## 6 局限与未执行项

- 分支定界在候选接近 500、题量接近 30 且约束很紧时，可能在 2 秒内无法**证明最优**；此时返回 `solver_status=feasible`（限时可行解）而非 `optimal`。若在限时内连可行解都没找到，返回 503 而不是 422——即超时情形不宣称「无解」。
- 可复现性限定在「同一机器、同一候选题库版本、同一历史分布、同一 seed」；`solver_status=feasible` 的结果在跨机器/跨版本时不保证逐位一致（SPEC-011 第 4 节第 5 条的原话即「不保证跨版本绝对相同」）。
- 知识点下限量按题目标签计数，多标签题可同时计入多个知识点；本模块不校验知识点是否属于目标班级的授课范围（知识点是全局内容，不属于班级）。
- 未做：组卷结果的自动发布（E062 只生成草稿，发布仍走 SPEC-010 的 E039）、跨班题库隔离（题库为已发布共享题，与 SPEC-009 一致）、组卷历史列表页（所选题号可通过生成的草稿详情查看）。
