# SPEC-008 执行报告

日期：2026-09-29。对象：SPEC-008 备课与预习发布。提交：`dd6749b`（分支 `feature/spec-008`，基线 `develop` `f179b4c`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-008（E023—E027、迁移 0008、教师备课页面与学生首页预习待办）。不包含尚未实现的后续模块（如 SPEC-003/006/007/011 的统计与智能模块）。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用既有锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、pytest 9.1.1）；本 Spec 未新增依赖 |
| 前端依赖 | 沿用既有锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等）；未新增依赖 |

## 2 迁移

新增 `0008_spec008`，`down_revision = 0007_spec013`（本任务开始时的 develop head，已核对远端确为 `f179b4c` 且 head 为 `0007_spec013`）：

- `lesson_plans`：title、owner_id、planned_at?、notes、version、created_at、updated_at；INDEX(owner_id)。
- `lesson_plan_items`：plan_id、sort_order、四个可空外键（knowledge_id／resource_version_id／question_id／experiment_id）；CHECK 四条恰好一个非空；UNIQUE(plan_id, sort_order)。
- `preview_assignments`：plan_id、class_id、due_at?、snapshot_json；INDEX(class_id, created_at)。

一次性库往返验证（项目虚拟环境，worktree 根目录）：

```
head: 0008_spec008
chain: ['0008_spec008', '0007_spec013', '0006_spec009', '0005_spec012', '0004_spec002', '0003_spec005', '0002_spec001', '0001_baseline']
after upgrade:        0008_spec008 → lesson_plans / lesson_plan_items / preview_assignments 齐全
after downgrade -1:   0007_spec013 → 三张表全部移除
after re-upgrade:     0008_spec008 → 三张表恢复
after downgrade base: 无版本      → 三张表仍不存在
after full re-upgrade:0008_spec008 → 三张表恢复
```

## 3 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend -q` | 0 | `188 passed in 828.71s`（SPEC-008 新增 10 条，既有模块用例继续通过） |
| 2 | `python -m pytest tests/backend/test_spec008.py -q` | 0 | `10 passed` |
| 3 | 一次性库迁移往返（见第 2 节） | 0 | 链为单一 head，升级／回退／再升级与回退到 base 均正常 |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 4 | `npm run test:unit` | 0 | 15 个测试文件、`101 passed`（SPEC-008 新增 1 个文件 8 条，并扩充导航用例 1 条） |
| 5 | `npm run build` | 0 | 构建成功，产出 `TeacherLessonPlansView` 等分块 |
| 6 | `git diff --check` | 0 | 无空白错误 |
| 7 | 文档核对脚本 `check_docs.py` | 0 | 未发现问题 |

## 4 浏览器实际流程

后端以构建产物同源方式启动（`create_app().run(port=5054)`），页面访问 `http://localhost:5054`。演练数据由 `开发工作区/tools/seed_spec008.py` 建立（教师、甲班 2 名学生、乙班 1 名学生、2 个知识点、含 2 个版本的资料、1 道已发布题目、1 个已发布实验）；**备课单与预习刻意不预置**，由教师页面创建。

| 步骤 | 网络观测 | 界面结果 |
| --- | --- | --- |
| 教师登录并打开「备课」 | `GET /classes`、`GET /knowledge-points`、`GET /resources`、`GET /questions`、`GET /experiments`、`GET /lesson-plans` 200 | 侧栏「备课」由待开放变为可点击；知识点下拉 2 项 |
| 依次添加四种条目并创建 | `POST /lesson-plans` **201** | 条目按顺序显示：1 知识点「同步复位」、2 资源版本「第 3 周课件 v1」、3 题目「预热：同步复位在时钟沿的哪一侧生效？」、4 实验「D 触发器逐拍演示」；列表出现「第 3 周备课 v1 · 知识点 1 · 资源版本 1 · 题目 1 · 实验 1」 |
| 选择甲班、填截止时间后「保存并发布」 | `PATCH /lesson-plans/1` 200 → `POST /preview-assignments` **201** | 「已发布预习（4 项），快照已冻结」；已发布列表显示 `预习 #1 · 2026-10-02T10:00:00Z`，条目文案与上面一致；**题目条目只显示题干** |
| 甲班学生打开首页 | `GET /classes`、`GET /preview-assignments?class_id=1` 200 | 「预习待办」卡片出现：`第 1 次预习 · 4 项`、徽标「截止 2026-10-02T10:00:00Z」，逐条列出四类条目；卡片文本中检索不到「正确答案」「解析」 |
| 乙班学生打开首页 | `GET /preview-assignments?class_id=2` 200 | 「暂无预习任务」——甲班的预习对乙班不可见 |

时间换算核对：页面填的本地 `2026-10-02T18:00` 存为 UTC `2026-10-02T10:00:00Z`，与页面显示一致。

### 方法学限制（必须与结论一起读）

1. **内嵌预览浏览器仍不稳定保留应用的 HttpOnly 会话 Cookie**（同前几个模块轮次）：整页刷新后部分请求返回 401。已排除应用缺陷——服务器 `Set-Cookie` 属性正确、curl Cookie jar 可重复跑通同一组流程。每个角色链在一个连续页面会话内完成。
2. **坐标点击与截图不可用**：窗口被其他窗口遮挡，`preview_click` 报「无法归因到框架」、截图超时。表单文本用 `preview_fill` 填写，选择与提交用设置 `value` + 派发 `input`/`change` 事件、`requestSubmit()` 或 DOM `click()` 派发（与鼠标点击走同一事件与处理函数）。
3. **一次把「填账号密码」与「跳转」合并的脚本会被本地权限策略拒绝**（同 SPEC-010 轮次），因此凭据一律用专用表单工具填写，触发提交的片段不含凭据。
4. 未做局域网/HTTPS/生产 WSGI 形态复测，未做并发或多教师同时备课的负载测试。

## 5 逐条验收

### T-008-01 创建备课单含四种条目，按sort_order返回

覆盖用例：`test_T008_01_plan_with_four_target_kinds_is_returned_in_sort_order`、`test_T008_01_item_structure_is_validated`、`test_T008_01_only_visible_content_can_be_referenced`。

| 观测 | 值 |
| --- | --- |
| 乱序提交四类条目（4、1、3、2） | 返回与 GET 均按 sort_order 排列为 1—4，类型依次 knowledge／resource_version／question／experiment |
| 对外字段 | 每条只有 `sort_order`、`target_type`、`target_id` |
| 库内约束 | 四条记录都满足「四个外键恰好一个非空」 |
| 结构校验 | 重复 sort_order、非法 target_type、缺 target_id、多出未知字段、sort_order < 1、目标不存在 → 均 422，`details.fields` 指向 `items` |
| 引用可见性 | 引用他人未发布草稿 → 422；引用本人草稿或共享已发布内容 → 201 |

### T-008-02 复制后修改新单不改变原单；资源版本引用不因新版本上传改变

覆盖用例：`test_T008_02_copy_is_independent_and_edit_does_not_touch_source`、`test_T008_02_new_resource_version_does_not_change_reference_or_snapshot`。

| 观测 | 值 |
| --- | --- |
| 复制 | 201，新 id、新标题，条目引用逐条相同，`version=1` |
| 改副本（改标题并整表替换条目） | 原单标题、备注、条目与 version **完全不变** |
| 给被引用的资料追加新版本 | 计划条目的 `target_id` 仍指向旧版本 |
| 已发布快照 | 快照中的 `version_no` 仍是旧版本号 |

### T-008-03 发布到班甲后班乙学生查不到；题目快照不含答案

覆盖用例：`test_T008_03_preview_is_class_scoped_and_question_snapshot_hides_answers`、`test_T008_03_publishing_revalidates_references`。

| 观测 | 值 |
| --- | --- |
| 甲班学生读本班预习 | 200，看到 4 项 |
| 题目条目内容 | 恰好等于 `{"stem_md": "预习题干"}`；序列化后不含 `answer`、`explanation`、解析文本 |
| 库内 `snapshot_json` | 同样检索不到 `answer`／`explanation`／解析文本 |
| 乙班学生读甲班预习 | **404**（跨班对象） |
| 乙班学生读本班 | 200 且为空列表 |
| 乙班教师读甲班 | 404；甲班教师读本班 200 |
| 发布时重新校验引用 | 甲班教师引用乙班教师的共享题目并成功发布后，乙班教师把该题撤回为草稿；甲班教师再次发布 → **422**，不把已不可见的内容冻结进快照 |

### T-008-04 预习发布后编辑原计划，已发布快照保持原内容

覆盖用例：`test_T008_04_published_snapshot_survives_plan_edits`。

| 观测 | 值 |
| --- | --- |
| 发布后改计划标题、备注、整表替换条目，并改题干预习题干 | `snapshot_json` 与发布时**逐字段相同** |
| 快照内容 | `plan_title` 仍是「发布前标题」，题目条目 `content.stem_md` 仍是「原始预习题干」 |
| 学生侧 | 读到的仍是旧内容与原来的 2 条条目 |

### 其他边界

| 观测 | 值 |
| --- | --- |
| 备课单归属 | 他人读／改／复制我的备课单 → 404；我的列表不含他人计划 |
| 角色 | 管理员与学生访问 `/lesson-plans` → 403；匿名 401；缺 CSRF 写操作 403 |
| 版本冲突 | PATCH 携带过期 version → 409 `VERSION_CONFLICT` |
| 字段 | 标题为空、notes 超过 5000、`planned_at` 非 UTC-Z 格式 → 422 |
| 预习发布 | 发布到他人任教班级 → 404；班级不存在 → 404；缺 `class_id` 查询 → 400；学生调用发布 → 403 |

## 6 未执行与局限

- **预习待办没有独立的学生页面**：按 SPEC-008 第 4 节第 4 条「首版为学生首页待办列表」，待办渲染在首页卡片里，没有单独的预习详情页（条目内容已在卡片上展示摘要）。若需要打开完整预习内容，需新增学生侧预习详情接口与页面。
- **Preview 模型不含备课单标题**：APIC 的 Preview 只有 `id/class_id/plan_id/due_at/items`，因此待办文案由快照里各条目的内容摘要拼出（如「知识点「同步复位」」），未给接口加标题字段。若评审认为需要显示「第 3 周备课」这类计划标题，需要给 Preview 增加只读字段并登记 APIC。
- **未实现**：学校课表排课、外部消息推送（短信／邮件／站内通知）——按 SPEC-008 第 1 节的非目标明确排除；SPEC-003/006/007/011 等其他模块。
- **备课单不可删除**：DBD 要求「业务历史一律保留，软停用和归档代替删除已使用数据」，本模块未提供删除或归档接口（接口契约里也没有）。
- **并发**：未做多教师同时编辑同一备课单的并发测试；PATCH 走 version 乐观并发，冲突返回 409。
- 未做局域网/HTTPS/生产 WSGI 复测与课堂负载测试。

## 7 实现中修正的问题

浏览器流程发现一处真实缺陷：`save()` 在成功后调用 `edit(saved)` 回填表单，而 `edit()` 会清空提示，导致「已创建备课单」的提示刚设置就被清掉，用户看不到保存结果。已改为先回填、后设置提示，并保留「点击编辑时清空旧提示」的行为。

## 8 契约与共享代码变更

- **固定公开预习条目快照的形状**：`{sort_order,target_type,target_id,content}`，并写清各 `target_type` 的 content 摘要字段；`question` 的 content **只有 `stem_md`**（不含 answer／explanation，也不含选项），知识点摘要 `excerpt` 取正文前 200 字。APIC 第 2 节原先只写「公开预习条目快照[]」，未固定元素形状；属口径明确，未增删接口字段。已登记 APIC 与 CHG-RB。
- **备课单条目上限 50 条**，并明确发布预习时对条目引用再做一次可见性校验（SPEC-008 第 4 节第 2 条）。已登记 CHG-RB。
- 未改变 E023—E027 的路径、入参或状态码。
- 共享文件只做必要增量：`backend/app/__init__.py` 注册一个蓝图；`frontend/src/router/index.js` 增加 1 条路由；`frontend/src/navigation/index.js` 把「备课」由 `planned` 改为已实现路由；`frontend/src/views/HomeView.vue` 增加一行 `StudentPreviewTodo`（其余实现放在新组件里）；`README.md`／`CHG-RB.md`／测试计划仅增本模块条目。未改 `api_content.py`／`api_assessment.py`／`api_experiment.py`／`api_attendance.py`／`api_admin.py`。
- 迁移接在实际 head `0007_spec013` 之后，为单一版本链；与并行 #13 若同时新增迁移，后合并方按既有约定重编号并复核单一 head。
