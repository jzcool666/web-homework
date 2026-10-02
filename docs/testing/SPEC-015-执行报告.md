# SPEC-015 执行报告

日期：2026-10-02。对象：SPEC-015 个性化复习推荐。提交：`9ca4bb6`（实现）与随后一条文档提交；分支 `feature/spec-015`，基线 `origin/develop` `b128f1a`。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-015（E065 与「复习推荐」页面）。错题、进度与实验数据由 SPEC-006/009/013/014 交付、本模块只读复用，未重写；不包含尚未实现的后续模块。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| 后端依赖 | 沿用既有锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、pytest 9.1.1）；本 Spec **未新增后端依赖** |
| Node / npm | v24.18.0 / 11.16.0 |
| 前端依赖 | 沿用既有锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2、echarts 6.1.0 等）；**未新增前端依赖** |

**算法口径与设计基线的差异**：SPEC-015 第 4 节第 1 条写「NumPy 按 0.5/0.3/0.2 对可用项归一化」。三个信号的加权和用纯 Python 就能算清楚（每个学生至多 12 个知识点），引入 NumPy 只是多一个依赖，因此**本模块未使用 NumPy**。权重、归一化方式与缺失项处理与规格一致，输入输出契约未变，已登记 CHG-RB 与覆盖矩阵。

## 2 迁移：本模块未新增

DBD 第 5 节末段明确「推荐首版实时计算，不持久保存学生隐式画像；只返回当前候选和理由」。逐项核对确认不缺字段：

| 需求 | 现有承载 |
| --- | --- |
| 错题信号 e | SPEC-009 的 `submissions`／`submission_answers`／`assessment_items.snapshot_json`（知识点标签） |
| 进度信号 p | SPEC-006 的 `learning_progress` |
| 实验信号 x | SPEC-013/014 的 `experiment_attempts` + SPEC-012 的 `experiments.knowledge_id` |
| 先修关系 | SPEC-005 的 `knowledge_edges` |
| 候选练习 | SPEC-009 的 `questions`／`question_knowledge`；屏蔽题复用 `api_assessment._blocked_question_ids` |
| 推荐结果 | 每次请求实时计算，不落库、不缓存 |

因此**没有新增迁移**，Alembic head 仍为 `0011_spec017`。worktree 内一次性升级结果：

```
DB: sqlite:///.../worktrees/issue-18/backend/instance/app.sqlite
Running upgrade 0009_spec007 -> 0010_spec004 -> 0011_spec017
（单一 head，链上无分叉；本模块未追加任何 revision）
```

## 3 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend/test_spec015.py -q` | 0 | `7 passed in 20.49s` |
| 2 | `python -m pytest -q` | 0 | `307 passed in 1236.97s`（全量回归，含 SPEC-015 新增 7 条，既有模块用例继续通过） |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 3 | `npm run test:unit` | 0 | 29 个测试文件、`193 passed`（SPEC-015 新增 1 个文件 8 条：4 条换算 + 4 条页面；navigation 同步补齐路由与 1 条入口用例） |
| 4 | `npm run build` | 0 | 构建成功，产出 `StudentRecommendationsView-*.js` 分块 |

文档与其他：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 5 | `python ../tools/check_docs.py <worktree 根>` | 0 | 相对链接与 JSON 块检查通过，未发现问题 |
| 6 | `git diff --check` | 0 | 无空白错误 |

## 4 本地人工核验（后端 5060 端口）

后端以构建产物同源方式启动（`create_app().run(port=5060)`），演练数据由 `开发工作区/tools/seed_spec015.py` 建立（教师 `teacher_demo`、1 个班 4 名学生、SPEC-005 的六单元 12 知识点与 15 条先修关系，外加 4 道已发布题目）。

**说明**：本次会话的 Browser 窗格依旧无法加载页面——`preview_start` 报告服务已起、`curl http://127.0.0.1:5060/` 返回 200，但窗格导航后停在 `chrome-error://chromewebdata/`（与 SPEC-016 那轮相同的现象），因此**没有截图或无障碍树证据**。界面结论改由组件级测试给出，接口结论改由对同一进程发真实 HTTP 请求核验（Python `urllib` + CookieJar）：

| 步骤 | 观测 |
| --- | --- |
| 匿名 `GET /me/recommendations` | **401 UNAUTHENTICATED** |
| 教师会话 `GET /me/recommendations` | **403 FORBIDDEN**（E065 角色是 S） |
| 冷启动学生（无任何作答/进度/实验记录） | 200，前两条均为 `kind=knowledge`、`score=null`、`reasons=["按章节顺序的基础路径"]`，首条是第一章的「组合逻辑与时序逻辑的区别」 |
| 该学生自练「模 6 计数器与 5→0 回卷」1 题并答错后 | 200，首条变为该知识点，`score=100.0`，理由 `1/1 道相关题目首答错误（错误率 100%）` |
| 同一响应的第二条 | `kind=question`，`resource_id` 为该题 ID、`knowledge_id` 为该知识点，理由 `“模 6 计数器与 5→0 回卷”的相关练习，尚未答对`；题干不含选项与答案 |
| `?limit=10` | 200，10 条 |
| `?limit=0` / `?limit=11` | **422 VALIDATION_ERROR**（`details.fields.limit`） |
| `?limit=abc` | **400 INVALID_REQUEST** |
| 另一名无记录学生 | 三条全部 `score=null`，与前者不同（数据隔离） |

## 5 验收清单对照

| 编号 | 结论 | 证据 |
| --- | --- | --- |
| T-015-01 | 通过 | `test_T015_01_weak_points_drive_different_recommendations`：甲错 2 道计数器题、乙错 1 道寄存器题；甲首条是该计数器知识点（理由「2/2 道相关题目首答错误」），乙首条是该寄存器知识点（理由「1/1 …」），两条推荐的知识点、标题与理由都不同；甲的两道未答对练习都进入推荐 |
| T-015-02 | 通过 | `test_T015_02_new_student_gets_plain_base_path_without_fake_reasons`：新学生返回 5 条、全部 `kind=knowledge`、`score` 全为 `null`、理由只有「按章节顺序的基础路径」，且不含「答错/未通过/未完成」等虚构原因；首条是第一章第一个知识点 |
| T-015-03 | 通过 | `test_T015_03_mastered_candidate_is_excluded_and_short_list_is_not_padded`：首答全对 + 标记完成的知识点被判为已掌握并从推荐中排除；把其余知识点撤下发布后，`?limit=10` 只返回实际候选数（<10）且条目互不重复 |
| T-015-04 | 通过 | `test_T015_04_recommendations_are_own_only_and_hide_unreleased_questions`：把题放进班级测评并发布但不公开反馈后，该题不出现在推荐里，同知识点的另一道可见题正常出现；伪造 `?student_id=1` 不改变本人的结果，两名学生的推荐不同 |
| 公共约定 | 通过 | `test_access_control_and_limit_validation`：匿名 401、教师 403；`limit=0/11` → 422、`limit=abc` → 400；`limit=1/10` 与默认 5 的条数分别正确 |

纯函数另有 2 条用例：权重与缺失项（单信号按自身归一化、三信号齐全 0.55）、已掌握判定边界（正确率 .75 不算、.9 且无未通过实验才算）以及「未完成先修」只认明确记录。

## 6 局限与未执行项

- 首答信号只取 `feedback_released=1` 的测评（自练恒为已公开）。正在测评、尚未公开反馈的班级测评里的错题在反馈公开前**不会**影响推荐——这是刻意的：学生自己都看不到对错，系统也不该据此排序。
- 知识点粒度的信号是「该知识点下所有题的混合」，不区分题型与难度；同分只按章节顺序、章内 sort_order、题目/知识点 ID 决定，没有更细的权重。
- 「已掌握」的判定需要同时满足完成标记、首答正确率 ≥ .8 与无未通过实验；教师未公开反馈的测评不产生首答，因此这类知识点不会被判为已掌握（会以基础路径条目出现）。
- 基础路径条目是「按章节顺序」而非个性化排序，`score` 恒为 `null`；页面对此有专门文案，避免被读成 0 分。
- 前端「练习」条目跳转到自练页而不是「已按该知识点筛选」的深链接：自练页目前不读 URL 参数，本模块不便改动他人页面。
- 未做：教师端查看推荐（E065 角色是 S，且 SPEC-015 第 1 节把「给教师推送个人画像」列为非目标）、推荐结果的反馈闭环（点击/采纳埋点）、跨设备画像缓存（DBD 明确不持久保存隐式画像）。
- 组件级测试在 jsdom 下断言的是渲染结果与请求参数，不是真实浏览器观感；本轮 Browser 窗格不可用，未取得截图证据。
