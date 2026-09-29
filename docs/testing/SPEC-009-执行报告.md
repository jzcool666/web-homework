# SPEC-009 执行报告

日期：2026-09-29。对象：SPEC-009 题库练习与错题。提交：`73327dc`（分支 `feature/spec-009`，基线 `develop` `74e47ae`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-009（E035—E047、迁移 0005、题库与练习页面）。不包含尚未实现的 SPEC-010 随堂测，也不把设计意图记为运行通过。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用 SPEC-000/001/002/005 锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、waitress 3.0.2、pytest 9.1.1）；本 Spec 未新增依赖 |
| 前端依赖 | 沿用现有锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等）；未新增依赖 |

判分与结构校验只用标准库（`hashlib`、`json`），未引入 NumPy/Pandas 等算法依赖。

## 2 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend -q` | 0 | `122 passed in 448.75s`（SPEC-009 新增 32 条，既有模块用例继续通过） |
| 2 | `python -m pytest tests/backend/test_spec009.py -q` | 0 | `32 passed` |
| 3 | 一次性库迁移往返（脚本见下） | 0 | `upgrade → 0005_spec009`，7 张新表齐全；`downgrade 0001_baseline` 后新表为 0；再 `upgrade` 恢复齐全 |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 4 | `npm run test:unit` | 0 | 8 个测试文件、`48 passed`（其中 SPEC-009 新增 1 个文件 10 条，并扩充导航用例 1 条） |
| 5 | `npm run build` | 0 | 构建成功，产出含 `TeacherQuestionsView`、`StudentPracticeView`、`StudentAssessmentView`、`StudentResultView`、`StudentMistakesView` 分块 |
| 6 | `git diff --check` | 0 | 无空白错误 |
| 7 | 文档核对脚本 `check_docs.py` | 0 | 未发现问题（链接、JSON、编号唯一性、覆盖矩阵） |

一次性库迁移往返命令（在 worktree 根目录执行，使用项目虚拟环境）：

```
python -c "import sys; sys.path[:0]=['backend','tests/backend']; ... upgrade(app); downgrade(app,'0001_baseline'); upgrade(app)"
```

输出：`head before: 0005_spec009` → `after upgrade: 0005_spec009 | spec009 tables: [7 张]` → `after downgrade to 0001: 0001_baseline | spec009 tables left: []` → `after re-upgrade: 0005_spec009 | spec009 tables: [7 张]`。

## 3 浏览器实际流程

后端以构建产物同源方式启动（`create_app().run(port=5052)`，工作目录 `backend`），页面访问 `http://localhost:5052`，使用 `frontend/dist`。演练数据由 `开发工作区/tools/seed_spec009.py` 建立（管理员、教师、一个班三名学生、章节与两个知识点）；**题目刻意不预置**，全部由教师页面创建，使浏览器验证走真实产品路径。

| 步骤 | 网络观测 | 界面结果 |
| --- | --- | --- |
| 教师 `teacher_demo` 登录，侧栏出现「题库」 | `POST /auth/login` 200；导航项 `题库` | 进入 `/teacher/questions`，知识点下拉已加载「同步复位／异步复位」 |
| 新建单选题（2 选项，选 A，基础，同步复位，直接发布） | `POST /questions` **201** | 「已创建题目 #1」，列表出现「单选题 … A 基础 同步复位 已发布」 |
| 新建多选题（3 选项，选 A、B，进阶，异步复位） | `POST /questions` **201** | 「已创建题目 #2」；表单提示「当前正确答案：A、B」 |
| 新建判断题（true/false 只读选项，选 true） | `POST /questions` **201** | 「已创建题目 #3」，列表显示答案 `true` |
| 编辑题目 #2，把难度改为挑战并改解析 | `PATCH /questions/2` **200** | 表单回填题干与答案，保存后列表难度变「挑战」 |
| 学生 `stu_demo1` 登录，进入「习题训练」 | `GET /knowledge-points` 200、`GET /assessments` 200 | 知识点默认选中第一项（接口不允许无条件出题） |
| 选「同步复位」+3 题生成自练 | `POST /practice-sessions` **422** `INFEASIBLE_PAPER` | 「题库可用题目不足」——该知识点只有 1 题，服务端说明可用题数 |
| 改选「异步复位」+2 题生成自练 | `POST /practice-sessions` **201** | 「已生成自练…共 2 题」，跳转 `/student/assessments/1` |
| 作答：多选题只选 A（少选），判断题选 true，保存草稿 | `POST /assessments/1/submissions` 200/201、`PUT /submissions/1/answers` **200** | 「已保存（2026-09-29T03:35:38Z）」，未作答题数从 2 变 0 |
| 提交并判分 | `POST /submissions/1/finalization` **200** | 跳转 `/student/results/1?assessment=1`，**得分 1 / 2**；多选题「答错 · 0 分」并给出正确答案与解析，判断题「答对 · 1 分」 |
| 进入错题本 | `GET /me/mistakes` 200 | 一行：`#2 异步复位 未纠正 2026-09-29T03:37:15Z 可重练` |
| 勾选后「重练选中错题」 | `POST /practice-sessions` **201** | 跳转 `/student/assessments/2`，只有该多选错题 |
| 这次选 A、B 并提交 | `POST /submissions/2/finalization` **200** | `/student/results/2`：**1 / 1** |
| 回到错题本 | `GET /me/mistakes` 200 | `#2 异步复位 **已纠正** 2026-09-29T03:37:15Z 可重练`——最近状态已纠正，而**最近答错时间仍是第一次** |
| 反馈时机（班级测评，通过接口驱动；教师侧发布/结束页属 SPEC-010，本轮无对应页面） | 见下 | 见下 |

反馈时机与答案保护，在同一页面上下文内按「教师→学生→教师→学生」顺序实测：

| 阶段 | 观测 |
| --- | --- |
| 教师建并发布班级测评（`POST /assessments` 201 → `POST /assessments/4/publication` 200，state=published） | 快照、名单、总分在一个事务内冻结 |
| 学生读测评详情 `GET /assessments/4` | 条目字段集合为 `[id, knowledge_ids, options, points, position, question_id, stem_md, type]`——**无 answer、无 explanation_md、无 difficulty**；整个响应中检索不到 `"answer"` 或 `explanation_md` |
| 学生保存并最终化 | 最终化 200，响应中 **`score` 为 null** |
| 学生读结果 `GET /submissions/{id}/result` | `feedback_available=false`、`score=null`、条目字段只有 `[item_id, selected]`，`total_score=10` |
| 教师 `POST /assessments/4/closure` 200 → `POST /assessments/4/feedback-release` 200 | `feedback_released=true` |
| 学生再读结果 | `feedback_available=true`、`score=0`、条目字段含 `answer, awarded_points, correct, explanation_md, knowledge_ids`，`correct=false`、`answer=["A"]` |

库内核对（直接读 SQLite 文件）：

| 观测 | 值 |
| --- | --- |
| `questions` | 三题答案分别为 `["A"]`、`["A","B"]`、`["true"]`；题目 #2 编辑后 `version=2` |
| `question_knowledge` | 每题 1 个知识点，关联正确 |
| `submission_answers` | 首次作答：多选条目 `selected=["A"]`、`correct=0`、`awarded_points=0`；判断条目 `correct=1`、`awarded_points=1` |
| 首答语义 | 按 `s.submitted_at` 升序取第一条，该 (学生, 题目) 的 `correct` 仍为 0——重练答对不改变首答 |

### 方法学限制（必须与结论一起读）

1. **内嵌预览浏览器仍不稳定保留应用的 HttpOnly 会话 Cookie**：与 SPEC-002 轮次相同，整页刷新后部分已认证请求返回 401/403。已排除应用缺陷：服务器 `Set-Cookie` 属性正确，用 curl Cookie jar 重复执行同一组流程全部成功（含 `GET /me/mistakes` 返回 200 且内容正确），会话行在库内有效。因此每个交互片段都在同一页面会话内、刚登录之后连续执行；跨片段的长链路（登录→作答→提交）改为一次连续执行完成。
2. **坐标点击与截图不可用**：窗口被其他窗口遮挡，`preview_click` 报「无法归因到框架」、截图超时。表单填写用 `preview_fill`／设置 `value` 并派发 `input` 事件，提交用 `form.requestSubmit()` 或对真实按钮派发 `click()`——与鼠标点击走同一条事件与处理函数，但不等同于真实鼠标点击。
3. **教师侧「发布/结束/公开反馈」没有页面**：APIC 将 E037—E041 的课堂状态归 SPEC-010，本轮未做其页面（用户明确要求不实现 SPEC-010）。这些步骤用页面内 `fetch` 调用接口完成，属接口级证据而非界面证据。
4. 未做局域网/HTTPS/生产 WSGI 形态复测，未做并发负载测试。

## 4 逐条验收

### T-009-01 单选正确得分，多选少选/多选/非法 key 分别 0 分或 422，漏答 0 分

覆盖用例：`test_T009_01_single_correct_scores_full_points`、`test_T009_01_single_wrong_and_empty_score_zero`、`test_T009_01_multiple_subset_extra_and_exact`、`test_T009_01_multiple_exact_match_scores_full`、`test_T009_01_boolean_correct`、`test_T009_01_invalid_option_key_is_422_on_save`、`test_T009_01_missing_answer_scores_zero_and_leaves_trace`、`test_T009_01_question_write_rules`。

| 观测 | 值 |
| --- | --- |
| 单选答对 | 满分（10 / 10），`correct=true`、`awarded_points=10` |
| 单选答错 / 提交空数组 | 0 分 |
| 多选少选（只选 A，正确为 A、B） | 0 分 |
| 多选多选（A、B、C 全选） | 0 分 |
| 多选恰好相同（顺序不同） | 满分 |
| 判断题答对 | 满分 |
| 非法选项 key | 保存时 **422 `VALIDATION_ERROR`**，`details.fields` 指向 `selected` |
| 漏答（未提交该题） | 0 分，且 `submission_answers` 留痕 `selected_json='[]'`、`correct=0` |
| 题库写入规则 | 单选两个答案、多选一个答案、判断题非 true/false 选项、选项 key 重复、答案不在选项内分别 422，字段名指向 `answer` 或 `options` |

评分口径：`selected` 集合与快照答案集合完全相同才得分，空答案 0 分。数量不设上限（多选少选/单选多选按集合不等判 0），只有**选项 key 不存在**才拒绝保存——这样学生仍能看到自己的原始作答。

### T-009-02 题库改答案后，已发布测评题和已有成绩不改变

覆盖用例：`test_T009_02_editing_question_does_not_change_published_items_or_scores`、`test_T009_02_draft_items_can_be_edited_before_publication`。

| 观测 | 值 |
| --- | --- |
| 发布后再改题目（answer A→B、改题干） | `PATCH /questions/{id}` 200，题目 `version` 递增 |
| 已发布测评的 `assessment_items.snapshot_json` | 修改前后**逐字节相同** |
| 已有成绩结果页 | 仍按发布时的答案解释：`items[0].answer == ["A"]`，`score` 不变 |
| 改题后新发布的测评 | 使用新答案（原本选 B 得满分） |
| 草稿阶段 | 条目与总分可改（5 → 12） |

### T-009-03 同测评同学生并发开始只一份 submission；重试最终化返回原结果

覆盖用例：`test_T009_03_concurrent_start_keeps_single_submission`、`test_T009_03_repeated_finalization_returns_original_result`、`test_T009_03_submitted_submission_rejects_further_edits`、`test_T009_03_stale_version_on_save_is_409`、`test_start_submission_returns_existing_after_deadline`。

| 观测 | 值 |
| --- | --- |
| 两线程经 `Barrier` 同时 `POST /assessments/{id}/submissions` | 状态码为 {200, 201}，返回同一 `id`；`COUNT(*)` = 1 |
| 重复最终化 | 逐字段返回原结果（两次响应体完全相等），不重新判分 |
| 已提交后再改答案 | 409 `STATE_CONFLICT` |
| 保存答案 version 过期 | 409 `VERSION_CONFLICT` |
| 截止后取回已有提交 | 200（仍能取回自己的记录）；无提交者新建被 409 `DEADLINE_PASSED` 拦住 |

并发只有一份提交来自 `UNIQUE(assessment_id, student_id)`：插入冲突后回滚并回读既有行。

### T-009-04 首答错误重练正确：首答正确率不增加，错题最新状态变已纠正，仍能看到原错误；未公开反馈的班级测评题不进入自练与错题重练候选

覆盖用例：`test_T009_04_first_attempt_stays_wrong_after_correct_retry`、`test_T009_04_unreleased_class_questions_are_excluded_from_practice_and_mistakes`、`test_mistakes_filters_and_isolation`。

| 观测 | 值 |
| --- | --- |
| 首答错误（班级测评）→ 公开反馈 | 错题本：`latest_correct=false`，`last_wrong_at` = 首次提交时间 |
| 用 `mistake_question_ids` 重练并答对 | 自练提交后 `score=1`（反馈立即公开） |
| 重练后错题本 | `latest_correct=**true**`，`last_wrong_at` **与第一次相同**（未被重练刷新） |
| 首答统计 | 按 `submitted_at` 升序取第一条已提交作答，`correct` 仍为 0——重练答对不增加首答正确率 |
| 历史错误 | 首次提交的结果仍可查：`score=0`、`correct=false`、`selected=["B"]` |
| `resolved=false` 过滤 | 已纠正的题目不再出现 |
| 未公开反馈的班级测评题 | 该题**不进入**自练候选（`POST /practice-sessions` 返回 422 `INFEASIBLE_PAPER`，`available=0`），也**不出现**在错题视图；公开反馈后两者同时恢复 |
| 未公开反馈时的结果 | `feedback_available=false`、`score=null`，条目只有 `item_id`／`selected` |

“结束不等于公开”：排除条件是 `state IN (published, closed) AND feedback_released = 0`，因此已结束但未公开反馈的测评题同样被排除。

## 5 跨模块补测（Issue #6 要求）

Issue #6「跨模块待补测」要求实现本模块时补测 #4 的 T-001-02「教师猜测其他班学生答案 ID 同样拒绝」。用例 `test_other_teacher_cannot_read_result`：

| 观测 | 值 |
| --- | --- |
| 教师乙读教师甲班学生的 `GET /submissions/{id}/result` | **404 `NOT_FOUND`** |
| 同班另一名学生读他人提交 | 404 `NOT_FOUND` |
| 任课教师本人读该提交 | 200 |

证据已回填 [SPEC-001 执行报告](SPEC-001-执行报告.md) 第 4 节 T-001-02。

## 6 未执行与局限

- **未实现（按用户范围）**：SPEC-010 随堂测的教师页面（发布、进度、讲评）与 E057 统计、E060—E070 等其他模块。E037—E041 在接口层完整实现并通过测试，但没有对应页面。
- **未执行**：`E057 /analytics/assessment` 等统计接口（属 SPEC-010）；局域网/HTTPS/生产 WSGI 复测；课堂并发负载；Playwright E2E（尚未引入，本轮为手工驱动）。
- **组卷**：E042 按题目 ID 升序取前 `count` 条，不声称随机抽题（随机与约束组卷属 SPEC-011）。错题重练由前端传 `count = 选中题数`，因为接口的 `count` 默认 5，错题不足 5 题时不传会被判为题目不足。
- **已知限制**：题目的模板/批量导入未做；题库列表按 `page_size` 上限取页；Result 模型不含题干与选项，结果页依赖调用方传入 `?assessment=<id>` 取题目投影回显，缺少该参数时按条目展示（不伪造题干）。
- **浏览器证据的强度**：受第 3 节限制 1、2 影响，点击与整页刷新后的会话维持不稳定；已完成的观测为真实请求与真实渲染，但不能等同于完整的人工鼠标走查。教师侧发布/结束/公开反馈为接口级证据。
- 未合并 PR、未关闭 Issue #6，未开始下一模块。

## 7 契约与共享代码变更

- **反馈投影口径明确**：`feedback_released=false` 时学生的 `Submission.score` 也返回 null（原 APIC 只规定 `Result.score=null`）。分数本身是对错信息，提前返回等于绕过 E041；任课教师读本班提交不受该时机限制。属投影口径明确，未增删字段，已同步 APIC 第 5 节与 CHG-RB 第 1 节。
- **迁移链**：新增 `0005_spec009`（`down_revision = 0004_spec002`，即本任务开始时的 develop head）。与并行的 #7（SPEC-012）都可能新增迁移，先按当前 head 编写，后合并方接续并复核单一 head。
- 未改变 E035—E047 的路径、入参、状态码或公共错误码。
- 共享文件只做必要增量：`backend/app/__init__.py` 注册一个蓝图、`frontend/src/router/index.js` 增加 5 条路由、`frontend/src/navigation/index.js` 把「题库」「习题训练」两个 planned 入口改为已实现路由（并在导航用例中补一条断言）。前端复用既有 `AppShell`、`PageHeader`、`SectionCard`、`StatePanel`、`StatusBadge` 与 `tokens.css`，未新建 Shell。
