# SPEC-006 执行报告

日期：2026-09-29。对象：SPEC-006 学习进度与资源统计。提交：`f8dd600`（分支 `feature/spec-006`，基线 `develop` `6411fac`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-006（E056 `GET /analytics/learning`、教师「学情分析」页面）。不包含尚未实现的后续模块（如 SPEC-003 出勤统计、SPEC-004 预警、SPEC-007 问答、SPEC-011 组卷、SPEC-015 推荐）。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用既有锁定版本；本 Spec 未新增依赖。requirements.txt 已锁定 `pandas==3.0.6`，本模块按 SPEC-006 第 4 节第 4 条用它完成分组与去重 |
| 前端依赖 | 沿用既有锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等）；未新增依赖 |

## 2 迁移：本模块未新增

复用 SPEC-005 的 `learning_progress`、`resource_events`、`knowledge_points`、`resources`、`resource_versions` 与 SPEC-001 的 `enrollments`／`users`，逐项核对后确认不缺字段：

| 需求 | 现有承载 |
| --- | --- |
| 完成状态与完成时间 | `learning_progress.completed`／`completed_at` |
| 按 UTC 日去重的访问事件 | `resource_events.event_day`（主键含 学生+版本+类型+日） |
| 分母（当前已发布知识点） | `knowledge_points.published` |
| 进度名单与退班判定 | `enrollments.active` |
| 资源归属与章节 | `resource_versions.resource_id` → `resources.knowledge_id` → `knowledge_points.chapter_id` |

因此**没有新增迁移**，本分支的 `alembic head` 仍为 `0008_spec008`。一次性库往返验证（项目虚拟环境，worktree 根目录）：

```
head: 0008_spec008
chain: ['0008_spec008', '0007_spec013', '0006_spec009', '0005_spec012', '0004_spec002', '0003_spec005', '0002_spec001', '0001_baseline']
after upgrade:   0008_spec008 → knowledge_points / learning_progress / resource_events 齐全
after base:      无版本      → 三张表全部移除
after re-upgrade:0008_spec008 → 三张表恢复
```

## 3 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend -q` | 0 | `216 passed in 845.83s`（SPEC-006 新增 14 条，既有模块用例继续通过） |
| 2 | `python -m pytest tests/backend/test_spec006.py -q` | 0 | `14 passed` |
| 3 | 一次性库迁移往返（见第 2 节） | 0 | 单 head，本模块无新迁移 |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 4 | `npm run test:unit` | 0 | 19 个测试文件、`124 passed`（SPEC-006 新增 1 个文件 7 条，并扩充导航用例 1 条） |
| 5 | `npm run build` | 0 | 构建成功，产出 `TeacherLearningAnalyticsView` 等分块 |
| 6 | `git diff --check` | 0 | 无空白错误 |
| 7 | 文档核对脚本 `check_docs.py` | 0 | 未发现问题 |

## 4 浏览器实际流程

后端以构建产物同源方式启动（`create_app().run(port=5055)`），页面访问 `http://localhost:5055`。演练数据由 `开发工作区/tools/seed_spec006.py` 建立（教师、1 个班 3 名学生、2 个章节、4 个已发布知识点 + 1 个草稿知识点、1 份含 2 个版本的资料，以及完成记录与资源访问事件）。

| 步骤 | 网络观测 | 界面结果 |
| --- | --- | --- |
| 教师登录，侧栏「学情分析」由待开放变为可点击 | `GET /classes`、`GET /chapters`、`GET /analytics/learning?class_id=1&from=…&to=…` 200 | 打开 `/teacher/analytics/learning`；窗口默认 `2026-08-31T00:00:00Z → 2026-09-30T00:00:00Z`（最近 30 个 UTC 自然日，截止到当前 UTC 日的下一日 00:00），并注明「统计时区：UTC（自然日边界为 UTC 00:00）」 |
| 学习进度快照面板 | 同上 | 「已发布知识点（分母）：**4**」+ 口径徽标 `current_completed_before_to`；三名学生分别 `#3 3 75%`、`#4 1 25%`、`#5 0 0%`；面板上方写明「进度为当前快照近似…**不代表历史精确掌握率或学习时长**」，下方注明进度名单只含当前在册学生 |
| 资源访问时间窗面板 | 同上 | 资料 `#1`：去重人数 **2**、去重事件 **3**；面板写明「同人、同版本、同类型、同一天只算一个去重事件…同一人访问多个版本会各计一个事件，但人数只计一次」「时间窗只过滤资源事件，不改变进度快照的口径」 |
| 导出 CSV | `GET /analytics/learning?class_id=1&from=…&to=…&format=csv` 200 | 响应头 `Content-Type: text/csv; charset=utf-8`、`Content-Disposition: attachment; filename=learning-stats.csv`；正文带 UTF-8 BOM，列为 `section,student_id,completed_count,completion_rate,published_knowledge_count,resource_id,unique_students,dedup_events,window_from,window_to,progress_basis` |
| CSV 与 JSON 对账 | 同上 | CSV 的 progress 行为 `3→0.75`、`4→0.25`、`5→0.0`（分母 4），resource 行为 `1→2 人、3 事件`，与屏幕上的 JSON **逐字段一致** |
| 切换章节筛选到「寄存器与计数器」 | `GET /analytics/learning?class_id=1&…&chapter_id=2` 200 | 分母从 4 变为 **1**（只算该章节的已发布知识点），三名学生均为 0%；资源面板切换为「该时间窗内没有资源访问记录」空状态（那份资料属于另一章节） |
| 学生 `stu_demo1` 登录后的导航 | — | 学生导航**没有**「学情分析」，「学习分析」仍显示「待开放」 |
| 学生直接访问教师统计接口 | `GET /analytics/learning?class_id=1` → **403**；`…&format=csv` → **403** | 页面无法进入；接口与导出同时被拒 |

补充：为了在浏览器里看到章节筛选的真实差异，第二个章节与其知识点是通过页面外接口调用创建的（教师身份、`POST /chapters` + `POST /knowledge-points`）；**筛选与观察本身是界面操作**。

### 方法学限制（必须与结论一起读）

1. **内嵌预览浏览器仍不稳定保留应用的 HttpOnly 会话 Cookie**（同前几个模块轮次）：整页刷新后部分请求返回 401。已排除应用缺陷——服务器 `Set-Cookie` 属性正确、curl Cookie jar 可重复跑通同一组流程。每个角色链在一个连续页面会话内完成。
2. **坐标点击与截图不可用**：窗口被其他窗口遮挡，`preview_click` 报「无法归因到框架」、截图超时。凭据用专用表单工具填写，选择与提交用设置 `value` + 派发 `input`/`change`、`requestSubmit()` 或 DOM `click()` 派发（与鼠标点击走同一事件与处理函数）。
3. **CSV 的 BOM 在浏览器里读不到**：`fetch().text()` 会按编码规范消费掉开头的 BOM，因此页内 `charCodeAt(0)` 不是 `0xFEFF`；BOM 本身由后端测试与 `curl` 落盘核对确认（第 4 节与第 5 节的 CSV 用例）。
4. 未做局域网/HTTPS/生产 WSGI 形态复测，未做课堂规模的统计负载测试。

## 5 逐条验收

### T-006-01 4个已发布知识点完成3个得到0.75，草稿知识点不计分母

覆盖用例：`test_T006_01_three_of_four_published_points_is_075`、`test_T006_01_other_student_counts_are_independent`。

| 观测 | 值 |
| --- | --- |
| 4 个已发布 + 1 个草稿知识点，完成 3 个 | `published_knowledge_count=4`（草稿不计），`completed_count=3`，`completion_rate=0.75` |
| 响应口径字段 | `progress_basis="current_completed_before_to"` |
| 草稿知识点 | 学生用 E017 标记草稿知识点被 **404** 拒绝，因此不可能进入分子 |
| 三名学生各自独立 | 4/4 → `1.0`、1/4 → `0.25`、0/4 → `0.0` |

### T-006-02 0知识点返回null，0个完成且已有分母返回0

覆盖用例：`test_T006_02_zero_denominator_is_null_and_zero_completion_is_zero`、`test_T006_02_completed_after_to_is_excluded`。

| 观测 | 值 |
| --- | --- |
| 分母为 0（筛选到只有草稿知识点的章节） | `published_knowledge_count=0`，每名学生 `completion_rate` 均为 **null**、`completed_count=0` |
| 已有分母但 0 个完成 | `completion_rate = 0.0`（**不是 null**），名学生仍在名单里 |
| 边界：`completed_at` 晚于窗口结束 | 该完成记录不计入分子，`completed_count` 从 1 变 0、完成率从 1.0 变 0.0 |

### T-006-03 同人访问两版本为2事件1人，另一个人访问后人数为2

覆盖用例：`test_T006_03_two_versions_one_student_then_second_student`、`test_T006_03_download_and_open_count_as_separate_events`。

| 观测 | 值 |
| --- | --- |
| 同一学生访问同一资料的两个版本 | `dedup_events=2`、`unique_students=1` |
| 该学生再次访问同一版本（同类型同日） | E022 返回 `recorded=false`，事件数仍为 2 |
| 第二名学生访问其中一个版本 | `dedup_events=3`、`unique_students=2` |
| 同人同版本 open + download | 记为 2 个去重事件、1 个人 |
| 浏览器实测 | 资料 `#1` 显示「去重人数 2、去重事件 3」，与上面完全一致 |

### T-006-04 时间窗和chapter筛选正确；跨班请求拒绝；进度界面不标为历史精确掌握率

覆盖用例：`test_T006_04_utc_day_window_filters_events`、`test_T006_04_window_must_be_utc_whole_day`、`test_T006_04_default_window_ends_at_next_utc_day_midnight`、`test_T006_04_chapter_filter_applies_to_progress_and_resources`、`test_T006_04_left_student_leaves_progress_but_keeps_history`、`test_T006_04_permissions_are_class_scoped`。

| 观测 | 值 |
| --- | --- |
| 时间窗过滤 | 窗口内那一天的事件计入，10 天前的事件被排除（`dedup_events` 2 → 1）；窗口右开，`[from,to)` 不含 `to` 当天 |
| UTC 整日边界 | `from=…T05:00:00Z` → **422 `VALIDATION_ERROR`**，`details.fields.from` 说明必须是整日边界；只给一个 → 400；`to<=from` → 400；>366 天 → 400 |
| 默认窗口 | 冻结服务器时间为 `2026-09-29T06:30Z` 时，`window.from=2026-08-31T00:00:00Z`、`window.to=**2026-09-30T00:00:00Z**`（当前 UTC 日的下一日 00:00） |
| 章节筛选 | 进度与资源两侧同时收窄：切到另一章节后分母 4 → 1、该章节的完成与资源分别计入；未关联知识点的资料在带章节筛选时不出现 |
| 退班学生 | 把学生置为退班后：他不再出现在 `students`（不计当前进度名单），但他的资源访问仍计入 `resources`（`unique_students=1`、`dedup_events=1`） |
| 权限 | 跨班教师读 → **404**；学生读 → **403**；管理员 → 403；匿名 → 401；缺 `class_id` → 400；跨班导出 → 404，学生导出 → 403 |
| 界面不标为历史精确掌握率 | `PROGRESS_BASIS_NOTE` 单测断言：文案含「当前快照近似」，且「掌握率」「学习时长」的每一次出现都落在「不代表…」的否定里；浏览器页面显示同一文案 |

### JSON 与 CSV 对账

覆盖用例：`test_T006_json_and_csv_share_the_same_numbers`、`test_T006_csv_escapes_formula_like_text`。

| 观测 | 值 |
| --- | --- |
| 同一筛选下 | CSV 的 progress 行数与 `students` 一致、resource 行数与 `resources` 一致，且 `completed_count`／`completion_rate`／`published_knowledge_count`／`progress_basis`／`window_from`／`unique_students`／`dedup_events` 逐字段与 JSON 相同 |
| CSV 头 | `section,student_id,completed_count,completion_rate,published_knowledge_count,resource_id,unique_students,dedup_events,window_from,window_to,progress_basis`；带 UTF-8 BOM |
| 权限 | CSV 与 JSON 走同一套校验（跨班 404、学生 403） |
| 公式注入 | CSV 生成复用 `stats_assessment.to_csv`／`csv_safe`（以 `=`、`+`、`-`、`@` 开头的文本加前缀），单测覆盖；E056 的 CSV 只含固定标签与数字 ID，不含用户输入文本 |

## 6 未执行与局限

- **未新增迁移**：确认现有表不缺字段，`head` 仍为 `0008_spec008`。
- **学生端统计未开放**：E056 权限为 T（仅教师），因此「学习分析」在学生导航里保持「待开放」。APIC 没有给学生侧的班级统计接口；若要给学生看个人进度，需要新增学生侧的 `/me` 统计接口并登记 APIC。
- **退班判定用 `enrollments.active`**：SPEC-006 第 4 节只写「当前已退班学生不计当前进度名单」。历史活动保留的做法是「曾在本班有 enrollment 记录的学生都计入资源统计」；如果评审希望资源统计也只算当前在册学生，需要修改口径并同步 APIC。
- **`resources` 只列窗口内有去重事件的资料**：没有访问的资料不出现在列表里（否则每个班都会列出全部资料）。APIC 未明确这一点，已在第 7 节补充说明。
- **页面用学生 ID 而不是姓名**：`LearningStats.students` 只有 `student_id`（APIC 如此），教师端页面显示 `#id`；如需姓名需要给该模型加只读字段。
- **未实现**：`/analytics/attendance`(E055)、`/analytics/experiment`(E058，属 SPEC-014，已由该模块交付)、`/analytics/assessment`(E057，属 SPEC-010，已交付)，以及 SPEC-003/007/011/015 等模块；未做把点击次数估算成学习时长或掌握度的任何推导（SPEC-006 第 1 节明确列为非目标）。
- 未做局域网/HTTPS/生产 WSGI 复测与课堂规模负载测试。

## 7 实现中修正的问题

1. **章节筛选比较错了对象**（单元测试抓到）：资源侧原先把「资料关联的 `knowledge_id`」直接与 `chapter_id` 比较，等于拿知识点 ID 比章节 ID，导致带章节筛选时资源列表恒为空。已改为按 `knowledge_points.chapter_id` 关联判断。
2. **CSV 的 `Content-Type` 出现两次 `charset`**（浏览器实测抓到）：`mimetype` 里写了 `text/csv; charset=utf-8`，Flask 又会追加一次 `charset=utf-8`，实际响应头成为 `text/csv; charset=utf-8; charset=utf-8`。已改为只给 `mimetype="text/csv"`，由 Flask 补 `charset`，实测响应头现在是单一 `text/csv; charset=utf-8`。同类写法在 SPEC-010 的 E057 与 SPEC-014 的 E058 里也存在（响应值不受影响，只是头部重复），未在本分支改动，留待评审决定是否一并整理。

## 8 契约与共享代码变更

- **固定 E056 的统计口径**并写入 APIC 第 7 节：默认窗口截止到当前 UTC 日的下一日 00:00；分母只算当前已发布知识点、为 0 时完成率为 null；`completed_at` 为空或晚于 `to` 不计分子；`chapter_id` 同时收窄进度与资源两侧（资源按「关联知识点所属章节」判断）；`resources` 只列窗口内有去重事件的资料；退班学生不计当前进度名单但保留历史访问。属口径明确，**未增删接口字段**，已登记 CHG-RB。
- 未改变 E056 的路径、入参或状态码。
- **代码复用**：CSV 落盘与比例口径复用 `stats_assessment` 的 `to_csv`／`csv_safe`／`ratio`，避免出现第二份公式注入防护；统计实现放在新文件 `stats_learning.py`（Pandas 分组与去重），接口放在新文件 `api_learning.py`。
- 共享文件只做必要增量：`backend/app/__init__.py` 注册一个蓝图；`frontend/src/router/index.js` 增加 1 条路由；`frontend/src/navigation/index.js` 把教师「学情分析」由 `planned` 改为已实现路由（学生「学习分析」保持待开放）；`README.md`／`CHG-RB.md`／测试计划仅增本模块条目。未改 `api_content.py`／`api_assessment.py`／`api_experiment_stats.py`／`api_lesson.py` 等其他模块的业务文件。
- 本分支未新增迁移，因此不会与并行分支产生迁移链分叉。
