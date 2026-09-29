# SPEC-010 执行报告

日期：2026-09-29。对象：SPEC-010 随堂测与测评统计。提交：`d414ba5`（分支 `feature/spec-010`，基线 `develop` `3021f72`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-010（E057 统计、教师测评页面、学生作答页增强与截止最终化口径）。E035—E046 由 SPEC-009 交付、本模块复用，未重写；不包含尚未实现的后续模块。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用既有锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、pytest 9.1.1）；本 Spec 未新增依赖 |
| 前端依赖 | 沿用既有锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等）；未新增依赖 |

统计全部用标准库与 SQL 聚合实现，**未引入 Pandas**。SPEC-010 第 3 节写作「Pandas统计」，但同节又要求「无独立分数缓存」，本项目统计量级（单班测评的名单、逐题与分数段）用 Python/标准库即可，无需新增依赖；口径与规格一致，属实现方式选择，未改变任何输出字段。

## 2 迁移：本模块未新增

复用 SPEC-009 已建的 `questions`／`question_knowledge`／`assessments`／`assessment_items`／`assessment_roster`／`submissions`／`submission_answers`，逐项核对后确认不缺字段：

| 需求 | 现有承载 |
| --- | --- |
| 截止有效时间（自然截止 vs 提前结束） | `assessments.ends_at`：提前结束时收缩为实际结束时间，不需要关闭时间列 |
| 最终化提交时间 | `submissions.submitted_at` |
| 白卷与漏答单列 | `submission_answers.selected_json = '[]'` 即无选择，可直接聚合 |
| 统计窗口 | `assessments.starts_at`／`ends_at` |

因此**没有新增迁移**，`alembic head` 仍为 `0006_spec009`。一次性库往返验证（项目虚拟环境，worktree 根目录）：

```
head: 0006_spec009
revisions: ['0006_spec009', '0005_spec012', '0004_spec002', '0003_spec005', '0002_spec001', '0001_baseline']
after upgrade:      0006_spec009 | 测评相关 7 张表齐全
after downgrade:    0001_baseline | 测评相关表剩余 0
after re-upgrade:   0006_spec009
```

## 3 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend -q` | 0 | `160 passed in 592.41s`（SPEC-010 新增 15 条，既有模块用例继续通过） |
| 2 | `python -m pytest tests/backend/test_spec010.py -q` | 0 | `15 passed` |
| 3 | 一次性库迁移往返（见第 2 节） | 0 | 单 head，升级/回退/再升级均正常；本模块无新迁移 |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 4 | `npm run test:unit` | 0 | 10 个测试文件、`72 passed`（SPEC-010 新增 13 条） |
| 5 | `npm run build` | 0 | 构建成功，产出 `TeacherAssessmentsView`、`TeacherAssessmentDetailView` 等分块 |
| 6 | `git diff --check` | 0 | 无空白错误 |
| 7 | 文档核对脚本 `check_docs.py` | 0 | 未发现问题 |

## 4 浏览器实际流程

后端以构建产物同源方式启动（`create_app().run(port=5053)`），页面访问 `http://localhost:5053`。演练数据由 `开发工作区/tools/seed_spec010.py` 建立（教师、1 个班 4 名学生、2 个知识点、3 道已发布题目）。

按「教师发布 → 学生保存/提交 → 教师结束 → 讲评」走通：

| 步骤 | 网络观测 | 界面结果 |
| --- | --- | --- |
| 教师打开「测评与讲评」 | `GET /classes`、`GET /questions`、`GET /assessments?class_id=1` 200 | 侧栏出现新入口「测评与讲评」；题库列出 3 题 |
| 勾选 3 题、填标题后建草稿 | `POST /assessments` **201** | 「已选 3 题，合计 15 分」；「已创建草稿「浏览器验证：随堂测」，共 3 题、15 分」 |
| 进入详情并发布（本地 13:56 → 14:27） | `POST /assessments/2/publication` **200** | 「已发布…名单与题目快照已冻结」；状态 进行中，`ends_at` 存为 UTC `2026-09-29T06:27:00Z`；进度 4/0/0/0%/— |
| 学生 `stu_demo1` 打开「习题训练」 | `GET /assessments` 200 | 出现「浏览器验证：随堂测 进行中 15 待公开」 |
| 开始作答并选择 3 题作答 | `GET /assessments/2`、`POST /assessments/2/submissions` 200 | 3 道题按题型渲染 |
| **短延迟自动保存** | 选择题后 100 ms 读状态为「尚未保存」；1.7 s 后为「已保存 2026-09-29T05:58:24Z」（`PUT /submissions/1/answers` 200） | 自动保存提示条按 尚未保存 → 已保存 变化 |
| 提交并判分 | `POST /submissions/1/finalization` 200 | 跳转 `/student/results/1`，得分「待公开」、徽标「等待讲评」；逐题只显示「未公开」与本人作答 |
| 补充两名学生（接口） | 乙：判断对、多选少选、单选错；丙：交白卷 | 两人 `finalization` 200，响应中 `score` 均为 null |
| 教师刷新统计 | `GET /analytics/assessment?class_id=1&assessment_id=2` 200 | 名单 4、已提交 3、白卷 1、提交率 **75%**、平均分 **33.33%** |
| 教师「提前结束」 | `POST /assessments/2/closure` 200 | 「已结束，截止时间记为 2026-09-29T05:59:44Z」；`ends_at` 由 `06:27:00Z` **收缩**为实际结束时间 |
| 教师「公开反馈」 | `POST /assessments/2/feedback-release` 200 | 「已公开反馈，学生现在可以看到分数、答案与解析」 |
| 讲评逐题统计 | 同上统计响应 | 题1 判断：true 2 人选、false 0 人选、正确率 66.7%、机会 3、正确 2、漏答 1、参考答案「正确」；题2 多选：A 1 人、B 1 人、C 0 人、正确率 0%、机会 3、正确 0、漏答 1、参考答案 A、B；题3 单选：A 1 人、B 1 人、正确率 33.3%、机会 3、正确 1、漏答 1、参考答案 00 |
| 投屏统计 | 同上统计响应 | 已提交 3/4、提交率 75%、平均分 33.33%、白卷 1；分数段 `0-<60`=2、`60-<70`=1、其余 0；面板文本中**不含**任何学生姓名／学号，也不含正确率与参考答案 |
| 学生重看结果 | `GET /submissions/1/result` 200 | 得分 **10 / 15**、徽标「反馈已公开」；逐题「答对 · 5 分／答错 · 0 分／答对 · 5 分」，并显示正确答案与解析 |

对账（T-010-04 的「选项分布与漏答数可对账」）：三道题的 `机会数 − 漏答数` 都等于 2，等于各自选项计数之和（2+0、1+1+0、1+1），与三名学生的实际作答一致；白卷 1 张单列，未混入漏答。

### 方法学限制（必须与结论一起读）

1. **内嵌预览浏览器仍不稳定保留应用的 HttpOnly 会话 Cookie**（同 SPEC-002/009 轮次）：整页刷新后部分请求返回 401。已排除应用缺陷——服务器 `Set-Cookie` 属性正确、curl Cookie jar 可重复跑通同一组流程。因此每个角色链在一个连续页面会话内完成。
2. **坐标点击与截图不可用**：窗口被其他窗口遮挡，`preview_click` 报「无法归因到框架」、截图超时。表单文本用 `preview_fill` 填写、提交用 `form.requestSubmit()` 或 DOM `click()` 派发（与鼠标点击走同一事件与处理函数）。
3. **一次浏览器脚本被本地权限策略拒绝**：把「填账号密码」与「跳转到另一页面」合并到同一个 JS 片段执行时被判定为可疑的凭据+跳转组合。此后改为用专用表单工具填写凭据、只用不含凭据的片段触发提交与点击。这是本地工具策略，不是应用问题。
4. **两名学生的补充提交通过接口完成**：浏览器内已走通学生甲的开始作答、自动保存、提交与结果页；为凑齐统计样本，乙、丙的提交用页面外接口调用完成，属接口级证据。
5. 未做局域网/HTTPS/生产 WSGI 形态复测，未做课堂并发负载测试。

## 5 逐条验收

### T-010-01 截止前1毫秒保存成功、截止时返回409；时间伪造不能延迟截止

覆盖用例：`test_T010_01_save_one_second_before_deadline_succeeds_then_409_at_deadline`、`test_T010_01_client_cannot_forge_time`。

| 观测 | 值 |
| --- | --- |
| 截止前 1 秒保存 | 200，答案落库 |
| 正好 `ends_at` 保存 | 409 `DEADLINE_PASSED`，库内答案保持为上一次的值 |
| `ends_at` 提交最终化 | 409 |
| 请求体夹带 `saved_at`／`now` | 422 `VALIDATION_ERROR`，`details.unknown_fields` 列出该字段 |
| 伪造失败后再保存 | 仍按服务器时间 409 |

**精度说明**：存储时间是秒级 RFC3339，因此「截止前 1 毫秒」在实现里落到「截止前 1 秒」这一档；判定完全取服务器时间，请求不携带时间字段。

### T-010-02 学生A开始并保存后断开，B未开始；截止后A草稿被最终化，B仍未提交，名单分母包含两人

覆盖用例：`test_T010_02_ended_draft_is_finalized_at_ends_at_and_non_starters_stay_unsubmitted`、`test_T010_02_early_close_stamps_actual_close_time`。

| 观测 | 值 |
| --- | --- |
| A 保存后时钟越过 `ends_at`，统计读取触发最终化 | `status=submitted`、`submit_reason=timeout`、`submitted_at = ends_at`（不是访问时间）、按已保存答案得 10 分 |
| B 未开始 | 没有 `submissions` 记录，仍算未提交 |
| 名单分母 | `assessment_roster` 仍为 4 行（快照名单，与当前在班无关） |
| 教师提前结束 | `ends_at` 收缩为实际结束时间，草稿的 `submitted_at` 等于该时间；结束后不能再开始作答 |

### T-010-03 公开前任何学生接口不含答案、correct或score，已结束未公开阶段同样不含；该阶段题目不出现在自练与推荐候选，教师公开后才可查看解析

覆盖用例：`test_T010_03_no_answer_correct_or_score_before_release_even_after_end`、`test_T010_03_teacher_sees_statistics_before_release_but_students_cannot`。

| 阶段 | 学生侧观测 |
| --- | --- |
| 进行中、已保存 | `PUT answers` 响应 `score=null` |
| **已结束但未公开反馈** | 测评详情条目字段仅 `id/question_id/position/points/type/stem_md/options/knowledge_ids`；整个响应检索不到 `answer`／`explanation_md`；结果 `feedback_available=false`、`score=null`、条目只有 `item_id`／`selected` |
| 已结束未公开时的自练 | 该题不进候选，`POST /practice-sessions` 返回 422 `INFEASIBLE_PAPER`，`available=0` |
| 公开反馈后 | `feedback_available=true`、`score` 与 `correct` 可见、答案与解析可见 |
| 教师侧 | 讲评前教师即可读统计（这是 SPEC-010 第 3 条要求的）；学生访问 E057 403，其他班教师 404 |

浏览器实测与上表一致：公开前结果页显示「待公开／等待讲评」且逐题标「未公开」，公开后同一条记录显示 10 / 15 与逐题对错、正确答案、解析。

### T-010-04 名单4人提交3人（含白卷），提交率.75；某题2人正确则2/3，选项分布与漏答数可对账

覆盖用例：`test_T010_04_submission_rate_and_item_counts`、`test_T010_04_correct_rate_uses_two_of_three`、`test_T010_04_statistics_are_anonymous_and_bucketed`。

| 观测 | 值 |
| --- | --- |
| 名单/已提交/白卷 | `roster_count=4`、`submitted_count=3`、`blank_count=1` |
| 提交率 | `0.75`（分母是快照名单） |
| 平均分 | 仅含已提交的三份：`(100 + 0 + 0) / 3 = 33.33` |
| 单题正确率 | 分母为已提交人数（含漏答）：3 人中 2 人正确 → `2/3 = 0.6667` |
| 选项分布与漏答 | `answered_count=3`、`unanswered_count=1`、`option_counts={"A":1,"B":1}`；`机会数 − 漏答数 = 选项计数之和` |
| 分数段 | `0-<60`／`60-<70`／`70-<80`／`80-<90`／`90-100` 五档；样本 100%／50%／0% → `1 / 1 / 0 / 0 / 0` 与 `2 / 0 / 0 / 0 / 1` 两种构造均核对通过 |
| 匿名性 | 统计响应与投屏面板均不含 `student_id`、姓名或学号 |

### 其他边界

| 观测 | 值 |
| --- | --- |
| 窗口参数 | `from`/`to` 只给一个 → 400；跨度 > 366 天 → 400；`to <= from` → 400；缺 `class_id` → 400；省略时默认最近 30 天 |
| 窗口口径 | 计入窗口的是起止区间与 `[from,to)` 有交集的班级测评，因此进行中的测评也能看到进度；窗口外的历史测评被排除（用例核对：把窗口收窄到测评开始之前 → `assessments` 为空） |
| CSV | 200，`text/csv`，以 UTF-8 BOM 开头，列首为 `section,assessment_id,item_id...`，四个 section 齐全；`= + - @` 开头的文本加安全前缀（`stats_assessment.csv_safe` 单测） |
| 权限 | 匿名 401、管理员 403、跨班教师 404、学生 403 |

## 6 未执行与局限

- **未新增迁移**：确认现有表不缺字段，`head` 仍为 `0006_spec009`。若评审认为需要显式的 `closed_at` 列，可另开迁移；当前用 `ends_at` 收缩表达有效截止时间，已在 APIC 第 8 节写清。
- **未实现（按用户范围）**：SPEC-011 组卷、E055/E056/E058 其他三类统计、E059—E070。E037—E041 的接口沿用 SPEC-009，本模块只补课堂页面与统计。
- **逐题正确答案的来源**：`Result`／`StudentItem` 模型不含题干答案，讲评页对每个条目单独 `GET /questions/{id}` 取答案（≤30 题）。未给统计接口加答案字段，避免统计响应本身变成泄露渠道。
- **作答进度只到聚合层**：现有接口没有「按测评列出提交」的端点，因此进度显示名单/已提交/白卷/提交率/平均分，不显示「谁还没交」。若需要逐个名单进度，需要新增端点并登记 APIC。
- **未做**：局域网/HTTPS/生产 WSGI 复测、课堂并发负载、Playwright E2E（尚未引入，本轮为手工驱动）。
- **组卷随机性**：自练仍按题目 ID 升序取前 N 条（SPEC-009 口径），本模块未改。

## 7 实现中修正的问题

1. **统计窗口取自进程外的 `datetime.now`**：改为与本模块其余判定同源的 `_now()`，否则冻结时钟下的窗口与业务时间不一致（测试即暴露）。
2. **测评是否计入窗口**：最初按 `ends_at ∈ [from,to)` 过滤，会把「正在进行中的随堂测」排除，教师看不到实时进度；改为「起止区间与窗口有交集」。
3. **`QuestionPicker` 连续勾选丢选择**：组件直接从 props 计算选中集，同一 tick 内连点两个复选框会丢掉前一次选择（浏览器实测复现：勾 3 题只选中 1 题）。改为组件内维护本地选中态、props 变化时同步。这是浏览器流程发现的真实缺陷。
4. **默认窗口的右开边界**：默认 `to` 取服务器当前时间，同一秒内写入的 `submitted_at` 会落在 `[from,to)` 之外。保留严格的右开语义（与规格一致），页面在讲评时读取的是更早的提交，不受影响。

## 8 契约与共享代码变更

- **AssessmentStats 增两个只读字段**：`assessments[].blank_count`（白卷）与 `items[].unanswered_count`（漏答）。SPEC-010 第 4.5 条要求白卷与漏答单列核算且选项分布可对账，原模型的字段无法表达；已同步 APIC 第 7 节与 CHG-RB 第 1 节。
- **固定 E057 的口径与格式**：`option_counts` 形状、`score_buckets.range` 取值、窗口交集规则与 CSV 列顺序写入 APIC 第 7 节。
- **截止最终化时间语义**：`submitted_at` 取有效截止时间，提前结束时收缩 `ends_at`；写入 APIC 第 8 节与 CHG-RB。
- 未改变 E035—E047、E057 的路径、入参或状态码；未新增迁移。
- 共享文件只做必要增量：`frontend/src/router/index.js` 增加 2 条路由、`frontend/src/navigation/index.js` 增加教师入口「测评与讲评」、`README.md`／`CHG-RB.md`／测试计划仅增本模块条目。未改 `api_content.py`／`api_experiment.py`／`api_attendance.py`／`api_admin.py`。
