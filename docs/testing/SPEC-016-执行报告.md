# SPEC-016 执行报告

日期：2026-10-02。对象：SPEC-016 时序逻辑知识图谱与可视化。提交：`feaa76e`（实现）、`d0340f0`（画布尺寸与路径边界修正）、`6dc49a6`（文档）；分支 `feature/spec-016`，基线 `origin/develop` `221afce`（rebase 后）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-016（E066/E067/E068 与「知识图谱」页面）。章节、知识点与先修关系由 SPEC-005 交付、本模块只读复用，未重写；不包含尚未实现的后续模块。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| 后端依赖 | 沿用既有锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、pytest 9.1.1）；本 Spec **未新增后端依赖** |
| Node / npm | v24.18.0 / 11.16.0 |
| 前端依赖 | 新增 `echarts@6.1.0`；其余沿用既有锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等） |

**图算法的实现口径**：ADR-007 第 5 条与 README 的写法是「使用标准库与 NumPy」。本模块的图遍历（BFS 最短路、分层 Kahn 拓扑排序、Tarjan 强连通分量做环检测、按深度子图裁剪）**只用标准库**，没有用到 NumPy —— 这些是纯图算法，NumPy 在这里只是多一个依赖。这是实现方式，不改输入输出契约，已登记 CHG-RB。

## 2 迁移：本模块未新增

DBD 第 5 节末段明确「知识图谱不另建表，是 `knowledge_edges`（先修关系）的只读投影，结果实时计算」。逐项核对确认现有表够用：

| 需求 | 现有承载 |
| --- | --- |
| 节点与章节归属 | `knowledge_points`（id/title/chapter_id/sort_order/published） |
| 先修关系 | `knowledge_edges`（prerequisite_id → target_id，复合主键） |
| 课程访问门槛 | SPEC-001 的 `enrollments`（`require_course_access`） |
| 图查询结果 | 实时计算，不落库、不缓存 |

因此**没有新增迁移**。分支建立时 Alembic head 为 `0009_spec007`；合入前 SPEC-004（PR #42）先一步合入 develop 并追加了 `0010_spec004_warnings`，本模块无迁移所以只需 rebase，链上无分叉，重跑全量测试时 head 为 `0010_spec004`。worktree 内一次性升级结果：

```
DB: sqlite:///.../worktrees/issue-23/backend/instance/app.sqlite
Running upgrade 0007_spec013 -> 0008_spec008 ... -> 0009_spec007
（rebase 后 head 变为 0010_spec004；本模块未追加任何 revision）
```

**合入前 rebase**：`origin/develop` 在分支建立后前进了 3 个提交（`29b1ed2`/`57e4072`/`221afce`，SPEC-004 合入）。已 `git rebase origin/develop` 解决共享文件冲突：`frontend/src/navigation/__tests__/navigation.spec.js` 保留「学习预警」与「知识图谱」两条入口用例；`CHG-RB.md`、`README.md` 两端行全部保留。`app/__init__.py`、`router/index.js`、`navigation/index.js` 自动合并，两个模块的路由与蓝图都在。

## 3 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest -q` | 0 | `280 passed in 1125.84s`（**rebase 到含 SPEC-004 的最新 develop 后**的全量回归：262 条为 rebase 前本分支的值，另 18 条来自 SPEC-004；含 SPEC-016 7 条） |
| 2 | `python -m pytest tests/backend/test_spec016.py -q` | 0 | `7 passed in 28.40s`（rebase 后复跑） |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 3 | `npm run test:unit` | 0 | 26 个测试文件、`174 passed`（SPEC-016 新增 1 个文件 13 条：4 条纯函数 + 9 条页面/降级；navigation 同步补齐路由与 1 条入口用例。26/174 为 rebase 合入 SPEC-004 后的复跑值） |
| 4 | `npm run build` | 0 | 构建成功，产出 `KnowledgeGraphView-*.js`（491.19 kB，gzip 165.67 kB）——ECharts 随该路由懒加载，不进首屏 |

文档与其他：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 5 | `python ../tools/check_docs.py <worktree 根>` | 0 | 相对链接 232 条、JSON 块 5 个，未发现问题 |
| 6 | `git diff --check` | 0 | 无空白错误 |

## 4 本地人工核验（后端 5061 端口）

后端以构建产物同源方式启动（`create_app().run(port=5061)`），演练数据由 `开发工作区/tools/seed_spec016.py` 建立（教师 `teacher_demo`、1 个班 4 名学生，并复用 SPEC-005 的课程种子写入六单元 12 知识点、15 条先修关系、1 份外链资料）。

**说明**：本次会话的 Browser 窗格无法加载页面——`preview_start` 报告服务已起、`curl http://127.0.0.1:5061/` 返回 200，但窗格导航后停在 `chrome-error://chromewebdata/`（重开服务后仍然如此），因此**没有截图或无障碍树证据**。改为对同一进程发真实 HTTP 请求核验（Python `urllib` + CookieJar），并如实记录：

| 步骤 | 观测 |
| --- | --- |
| 匿名 `GET /knowledge-graph`、`/path`、`/topological`（全新会话，不带 Cookie） | 三个都 **401 UNAUTHENTICATED** |
| 在班学生登录后 `GET /knowledge-graph`、`/topological` | **200**（`require_course_access` 通过） |
| `GET /knowledge-graph`（整图） | 200，**12 节点 / 15 条边**，与 SPEC-005 种子一致 |
| `GET /knowledge-graph?root_id=<模6计数器>&depth=1` | 200，节点 `[(10, depth0, dim1), (9, depth1, dim0), (6, depth1, dim0)]`，边 `6→10`、`9→10`；`has_cycle=false`、`truncated=false` |
| `GET /knowledge-graph?chapter_id=<第五单元>` | 200，**2 节点 / 1 条边**（跨章边被排除） |
| `GET /knowledge-graph/path?from=<D触发器>&to=<模6计数器>` | 200，`matched=true`，节点链 `[3, 9, 10]` |
| `GET /knowledge-graph/path?from=<模6计数器>&to=<D触发器>` | 200，`matched=false`，`nodes=[]`、`edges=[]` |
| `GET /knowledge-graph/topological` | 200，`has_cycle=false`，`order` 长 12 |
| 直接写入 `模6→二进制` 造成环后 `GET /topological` | 200，`has_cycle=true`，`cycle_edges=[9→10, 10→9]`，**响应中没有 `order` 字段**；`GET /knowledge-graph` 的 `has_cycle` 同样为 true |
| 删除该边后 `GET /topological` | 200，`has_cycle=false`，`order` 恢复为 12 项 |
| `GET /knowledge-graph?depth=99` | **422 VALIDATION_ERROR**，`details.fields.depth = 必须是 1—3 的整数` |

未入班学生 403、节点超 200 时的 `truncated` 与悬空边、草稿知识点排除由第 3 节的自动化用例覆盖（人工核验未重复构造，因为需要批量写入 260 个知识点）。

## 5 验收清单对照

| 编号 | 结论 | 证据 |
| --- | --- | --- |
| T-016-01 | 通过 | `test_T016_01_root_subgraph_depth_one_excludes_draft`：以模 6 计数器为 root、depth=1 返回该节点、其两个直接先修（二进制计数器、次态推导）与两条边，depth/dimension 正确；depth=2 在前一层基础上继续扩展。插入草稿知识点与它连出的边后，草稿节点与边都不出现在 depth=2 子图和整图里 |
| T-016-02 | 通过 | `test_T016_02_cycle_is_reported_and_fixed_graph_gives_unique_order`：加 `模6→二进制` 造环后 `has_cycle=true`、`cycle_edges` 恰为环上两条边、**响应不含 `order`**；删除该边后恢复 12 项唯一拓扑序，且与环前一致，先修排在后续之前 |
| T-016-03 | 通过 | `test_T016_03_shortest_path_and_no_path_is_not_fabricated`：触发器→模 6 计数器返回 `[3, 9, 10]` 与两条边；反方向 `matched=false` 且 `nodes=[]`；直接邻居只返回一条边；起点与终点相同时返回单节点、零条边而不是「无路径」 |
| T-016-04 | 通过 | `test_T016_04_access_control_and_argument_errors`（匿名三接口 401、未入班学生 403、在班学生与教师 200、depth=99 → 422、depth=0 → 422、depth=abc → 400、root_id/chapter_id/from/to 不存在 → 404）、`test_T016_04_node_limit_truncates_without_silent_drop`（260+ 节点 → `truncated=true`、恰好 200 节点、无悬空边；未超限章节 `truncated=false`）、`test_T016_04_chapter_filter_keeps_edges_inside_the_chapter`、`test_T016_04_no_write_endpoints`（三个路由只有 GET，POST 返回 405） |

## 6 局限与未执行项

- 拓扑序的「同层」按 **Kahn 分层 + (sort_order, id)** 落序：它是确定且唯一的，但不等于「所有最长路径上的层号相等」这一更强的分层定义；有环时按规格不返回任何顺序。
- `has_cycle` / `cycle_edges` 只描述**本次响应范围内**的子图。按 `root_id + depth` 或 `chapter_id` 收窄后，被切掉的那段关系不算环。
- 未指定 `root_id` 时不做深度分层（`depth` 恒为 0），裁剪按 `(chapter_id, sort_order, id)` 稳定排序取前 200；此时 `dimension` 表示该节点在作用域内没有先修。
- 节点上限 200 是服务端常量；种子规模（12 个知识点）远未触及，超限路径由构造数据在测试里覆盖，未做真实大图性能测试。
- 未做：先修关系的网页编辑（SPEC-016 第 4 节第 6 条明确本期不提供写入口）、跨章节的自动摘要、图的持久化缓存。
- 前端 ECharts 在本仓库的 jsdom 环境里没有 2D 上下文，因此组件级测试断言的是**数据装配与文字清单**以及画布不可用时的降级提示，不是像素级渲染结果；真实浏览器下的画布外观未在本轮取得截图证据（Browser 窗格不可用）。
