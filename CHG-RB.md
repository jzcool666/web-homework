# 变更记录与回滚手册

## 1 设计变更记录

| 日期 | 版本 | 变更 | 影响 |
| --- | --- | --- | --- |
| 2026-10-03 | UI 2.3 | 重构课堂主题选择、动态演示台和独立投屏布局；增加前进一拍快捷操作，显示已执行事件解释与移位回放 | 使用既有E052—E054；不改变API、迁移和仿真算法，预测仍由服务端决定。高电平前进分两次版本校验请求，失败停止并刷新。回滚仅回退前端及设计说明，数据库无需操作 |
| 2026-10-03 | UI 2.1 | 按六页参考图精修视觉与工作区；AttemptResult 增加只读 created_at，显示真实实验活动曲线 | E050/E051 返回已有 UTC 创建时间；无迁移、判分或请求字段变化，回滚无需数据库操作；旧客户端兼容新增响应字段 |
| 2026-10-03 | UI 2.0 | 修订 UI 信息顺序与统计口径，接通学生个人学习分析，重构首页、课程卡片、题号作答与服务端实验结果对照，统一导航与移动焦点 | 仅前端展示与现有接口组合；无 API/表结构/业务算法变化。方案与补验见 docs/design/UI实施方案.md、docs/testing/UI重构验收记录.md；回滚仅回退前端，不回滚数据库 |
| 2026-10-03 | 实验扩展设计1.0 | 教师补充实验箱连线过程与circ在线测评，新增FR-20/21、SPEC-018/019、E071—E082及lab三表设计；通用74系原厂引脚、Logisim-evolution5.0.0+Java21；真实探测失败退出0/纯headless失败，判分须解析完整输出 | 仅规划文档，无产品代码/迁移；#56共享基础→#57/#58并行→#59验收，旧D7仅原范围有效 |
| 2026-09-28 | 设计基线1.0 | 根据任务书、同类系统和发起人反馈形成六份设计文档、16份Spec及测试计划 | 仅文档，无数据库或运行版本 |
| 2026-09-28 | 设计基线1.0 | 确定课堂使用优先，突出计数器、寄存器和状态转换 | PRD、页面设计、SPEC-008/010/012/013 |
| 2026-09-28 | 设计基线1.0 | 明确约束组卷采用NumPy建模与SciPy求解，预警有规则分数和可选聚类 | ADR、SPEC-004/011 |
| 2026-09-28 | 设计基线1.0 | 修正SPEC-012对不存在“附录”的章节引用，改为第4节 | 仅文档引用修正，无业务规则变化 |
| 2026-09-28 | 设计基线1.0 | 答案保护延长至反馈公开：自练与推荐排除已发布但未公开反馈的班级测评题，含已结束未公开 | SPEC-009/010/015及测试计划 |
| 2026-09-28 | 设计基线1.0 | 明确管理员初始化归SPEC-001、完整业务种子随各模块，SPEC-000验收限于工程、迁移与基础测试数据 | SPEC-000/001及测试计划 |
| 2026-09-28 | 设计基线1.0 | 澄清E000路径为/api/v1/health且遵循APIC第1节公共封装（data为{status,version}） | SPEC-000第2节；原表述与APIC通用协议不一致 |
| 2026-09-28 | 工程阶段 | README运行步骤由“待实现契约”更新为实测命令并记录环境版本；目录树标注已建立/待创建 | README；依据为SPEC-000执行报告 |
| 2026-09-28 | SPEC-000评审修正 | testing配置不继承环境中的DATABASE_URL，避免测试误连已有数据库；同步工程阶段状态描述 | 配置、隔离测试、README、ADR、Spec索引；无迁移或数据变更 |
| 2026-09-28 | 设计基线1.0（范围校正） | 按任务书补齐时序逻辑知识图谱与识别辅助：新增SPEC-016/017、接口E066—E070、结果模型与recognition_tasks表 | PRD第4节、APIC、DBD、ADR-007、README、Spec索引、组员分工表、测试计划、实施计划、页面流程 |
| 2026-09-28 | 设计基线1.0（范围校正） | 撤销“暂缓预警、智能组卷、推荐”的精简建议；任务书六类智能模块均保留真实轻量算法 | PRD第4节；#15/#17/#18继续保留 |
| 2026-09-28 | 设计基线1.0（范围校正） | 精简自定素材数量：18知识点/60题/30问答调整为12知识点/36题/16问答，实验仍为4个 | PRD第5节、实施计划第3节；只减自定数量，不减模块 |
| 2026-09-28 | 设计基线1.0（范围校正） | 明确课程内容仅限时序逻辑，排除组成原理、运算器、存储器与指令执行 | PRD第4节；演示、实验、题库与智能数据同步限定 |
| 2026-09-28 | SPEC-001实现 | 实现账号角色与班级权限：新增迁移 `0002_spec001`（users/sessions/classes/enrollments）、接口 E001—E010、`init-admin` 命令及注册/登录/资料/班级管理页面 | 字段与路径按 APIC/DBD 已定义内容实现，无契约变更；测试计划第 5 节状态更新 |
| 2026-09-28 | SPEC-001实现 | 错误封装支持响应头字段 `ApiError.headers`，用于 429 的 `Retry-After` | app/errors.py；APIC 第 1 节已要求 429 附 Retry-After，无状态码或错误码变化 |
| 2026-09-28 | SPEC-001实现 | 会话读取失败时按 503 DB_BUSY 返回；健康检查跳过会话读取，保持 SPEC-000 的 503 语义 | app/auth.py；避免数据库不可用时被误判为 500 |
| 2026-09-29 | SPEC-001评审修正 | 角色变更须先转交任课班级或移出有效班级；学生角色必须有学号；停用班级或学生不能新增有效入班关系 | SPEC-001、DBD、迁移 0002、服务层与回归测试；现有数据尚未部署，无线上迁移 |
| 2026-09-28 | SPEC-016/017评审修正 | 图谱关系明确为种子维护与只读投影；识别格式v1、任务班级归属及同步完成状态固定 | SPEC-016/017、APIC、DBD、测试计划与页面流程；无代码或迁移变更 |
| 2026-09-29 | SPEC-002实现 | 实现考勤与请假：新增迁移 `0004_spec002`（attendance_tasks/attendance_records/leave_requests）、接口 E028—E034、教师「考勤与请假」与学生「我的课堂」页面 | 字段与路径按 APIC/DBD 已定义内容实现，无路径或状态码变更；新增后端 35 条、前端 8 条用例；执行结果见 SPEC-002 执行报告 |
| 2026-09-29 | SPEC-002实现 | AttendanceRecord 与 Leave 响应增加只读联表字段 `student_display_name`、`student_no` | APIC 第 2、4 节；教师查看签到名单与请假申请需识别学生，而 GET /users 仅管理员可用。增量字段，未增表列 |
| 2026-09-29 | SPEC-002实现 | 迁移链前移后，`tests/backend/test_migrations.py` 显式回退到 `0001_baseline` 再升级 | 测试随单一迁移链前移的必要更新，未放宽验收条件。SPEC-002 接在 SPEC-005 的 `0003_spec005` 后 |
| 2026-09-29 | SPEC-002评审修正 | 停用班级禁止新的考勤动作；已离班学生不能凭旧名单快照提交新签到或请假 | SPEC-002、api_attendance.py 与回归测试；历史读取及结算仍可用 |
| 2026-09-29 | SPEC-005实现 | 实现课程知识与教学资源：新增迁移 `0003_spec005`（chapters、knowledge_points、knowledge_edges、resources、resource_versions、favorites、learning_progress、resource_events）、接口 E011—E022、`seed-content` 命令（六单元 12 知识点、15 条先修关系、一份外链资料）及教师内容管理、学生学习与收藏页面 | 字段、路径、状态码按 APIC/DBD 已定义内容实现，无契约变更；先修关系写入前做无环校验，图谱读取接口仍属 SPEC-016 |
| 2026-09-29 | SPEC-005实现 | Markdown 渲染由前端 `src/utils/markdown.js` 自行实现：整段先转义、只生成白名单标签，链接仅放行 http/https；未引入新的前端或后端依赖 | 新增前端模块与单测；ADR-008 已要求禁用原始 HTML 并净化输出 |
| 2026-09-29 | SPEC-014实现 | 实现实验学习统计：E058 的 JSON 与 CSV、教师「实验统计」页面；只读 `experiment_attempts`/`experiments`/`enrollments`，无需新字段，因此未新增迁移 | APIC 路径、字段与状态码按已定义内容实现；新增后端 12 条、前端 13 条用例；执行结果见 SPEC-014 执行报告 |
| 2026-09-29 | SPEC-014实现 | SPEC-014 第 4 节补充作用域口径：`published_count` 与 `experiments[]` 同为「已发布实验」作用域且条数一致；学生未入班或已退班不计入任何班级统计 | docs/specs/SPEC-014.md 业务规则第 5、6 条；不改 APIC 字段名或类型 |
| 2026-09-29 | SPEC-014评审修正 | 明确作用域为「当前已发布实验」；取消发布后历史尝试仍在个人记录，但不再计入当前班级统计 | SPEC-014 第 4 节及回归用例，避免把已撤回实验的历史尝试误读为当前班级统计 |
| 2026-09-29 | SPEC-014实现 | 导航新增教师「实验统计」入口；导航单测补上该路由与高亮断言 | frontend/src/navigation、frontend/src/router 及其测试；SPEC-013 教师端计划入口保持原样 |
| 2026-09-29 | SPEC-005实现 | `testing` 配置的上传目录改到系统临时目录；测试不再写入仓库内 `instance/uploads` | app/config.py；与 SPEC-000「测试不触碰仓库内 instance/」的隔离原则一致 |
| 2026-09-29 | SPEC-005实现 | 迁移测试由按步数回退（`-1`）改为显式回退到 `0001_baseline` | tests/backend/test_migrations.py；迁移链随各模块前移后，按步数回退不再表达原意 |
| 2026-09-29 | SPEC-005评审修正 | 未入班学生不能借个人写接口记录课程数据；外链要求有效主机名；上传备注先校验再落盘 | SPEC-005、api_content.py 与回归测试；不改变 E011—E022 路径字段 |
| 2026-09-29 | SPEC-009实现 | 实现题库练习与错题：新增迁移 `0006_spec009`（questions/question_knowledge/assessments/assessment_items/assessment_roster/submissions/submission_answers）、接口 E035—E047、教师「题库」与学生「习题训练/作答/结果/错题本」页面 | 字段与路径按 APIC/DBD 已定义内容实现，无路径或状态码变更；发布时在单个事务里冻结题目快照、名单与总分，判分只读快照；执行结果见 SPEC-009 执行报告 |
| 2026-09-29 | SPEC-009实现 | 明确反馈投影：`feedback_released=false` 时学生的 `Submission.score` 同样返回 null，不只是 Result.score | APIC 第 5 节。分数本身也是对错信息，未到公开时机提前返回等于绕过 E041；任课教师读本班提交不受该时机限制。属投影口径明确，未增删字段 |
| 2026-09-29 | SPEC-009实现 | 回填 Issue #6 的跨模块补测：#4 T-001-02「教师猜测其他班学生答案 ID 同样拒绝」已用本模块的 `submissions` 对象实测，跨班读结果返回 404 | SPEC-001 执行报告第 4 节与 SPEC-009 执行报告；无代码变更 |
| 2026-09-29 | SPEC-009评审修正 | 未入班学生不能创建自练；离班或停用班级不能产生新的测评作答；重复答案条目返回422，不按列表顺序静默覆盖 | SPEC-009、APIC 第5节、api_assessment.py 与回归测试；保留历史读取，不改迁移或接口路径 |
| 2026-09-29 | SPEC-012实现 | 实现课堂演示与时序仿真：新增迁移 `0005_spec012`（experiments、demo_sessions）、接口 E048/E049/E052—E054、`seed-experiments` 命令（D、JK、模 6 计数器、4 位移位寄存器四个预置实验）及教师课堂/控制台/投屏与学生只读页面 | 字段与路径按 APIC/DBD 已定义内容实现；实验预测提交 E050/E051 属 SPEC-013，本模块未实现 |
| 2026-09-29 | SPEC-012实现 | Demo 响应增加只读字段 `experiment`：创建演示时固定的实验快照（id/title/simulator_type/config/steps_md） | APIC 第 2 节 Demo 未含模型类型，学生端无法据此渲染；该字段同时避免依赖可能被撤回为草稿的实验定义 |
| 2026-09-29 | SPEC-012实现 | 固定 `history` 状态行口径：`seq/op/clock/inputs/q_before/q/rising/step_no` | APIC 第 2 节只写「状态行[]」；SPEC-012 第 4 节第 5 条要求记录时钟、输入、旧 Q、新 Q 与是否有效沿 |
| 2026-09-29 | SPEC-012实现 | 演示初始 `reveal_next=false`：预测先隐藏，教师显式揭示后才返回 next_q | SPEC-012 第 4 节第 5 条与页面设计「下一状态 [待揭示]」 |
| 2026-09-29 | SPEC-010实现 | 实现随堂测与测评统计：教师测评页面（建草稿/发布/进度/提前结束/公开反馈/讲评/投屏）与学生作答页的短延迟自动保存、保存确认后提交、刷新恢复与断线提示；新增接口 E057 `GET /analytics/assessment`（含 CSV 导出） | **未新增迁移**，复用 SPEC-009 的 questions/assessments/assessment_items/assessment_roster/submissions/submission_answers，head 仍为 `0006_spec009`；E037—E046 沿用 SPEC-009 实现，未改路径或状态码 |
| 2026-09-29 | SPEC-010实现 | AssessmentStats 增加 `blank_count`（白卷）与 `unanswered_count`（漏答）两个只读字段，并固定 `option_counts` 形状、`score_buckets.range` 取值与 E057 的 CSV 列顺序 | APIC 第 7 节。SPEC-010 第 4.5 条要求白卷与漏答单列核算、选项分布可对账，原模型的两个字段无法表达 |
| 2026-09-29 | SPEC-010实现 | 截止最终化的 `submitted_at` 取测评有效截止时间：自然截止取 `ends_at`，教师提前结束时把 `ends_at` 收缩到实际结束时间 | APIC 第 8 节与 SPEC-010 第 4.7 条。避免把访问触发的延迟处理时间算作提交时间，也不需要新增关闭时间列；`ends_at` 始终等于有效截止时间 |
| 2026-09-29 | SPEC-010评审修正 | E057 的提交与首答统一按右开窗口筛选，默认窗口覆盖服务器当前秒；指定 assessment_id 时只统计该测评内的全历史首答；知识点首答使用 Pandas 分组并锁定 Pandas/NumPy 版本；教师 E038 讲评读取发布快照答案；学生自动保存串行并显示未保存改动；投屏隐藏讲评内容 | APIC、SPEC-010、api_assessment.py、models_assessment.py、stats_assessment.py 与前后端回归测试；学生条目继续不含答案，不新增迁移 |
| 2026-09-29 | SPEC-012实现 | `app/auth.py` 新增 `require_course_access()`，实验与演示沿用与 SPEC-005 相同的课程读取门槛 | 两处以外的模块将重复实现同一选课校验；该函数为纯新增，未改变既有接口行为 |
| 2026-09-29 | SPEC-012实现 | experiments 不存期望输出；预置实验只提供配置与输入序列（每个模型不少于 4 个有效上升沿） | APIC 第 2 节 Experiment「无期望输出」；期望状态由 SPEC-013 按同一套仿真规则计算 |
| 2026-09-29 | SPEC-012评审修正 | 演示动作按 `expected_version` 原子条件更新，防止并发旧版本动作互相覆盖；切换实验类型时重验配置和序列；停用班级禁止新演示与控制动作 | SPEC-012、api_experiment.py 与三条回归测试；旧演示可关闭和读取，不改接口路径或迁移 |
| 2026-09-29 | SPEC-009集成 | SPEC-009 迁移改为 `0006_spec009`，接续已合入的 `0005_spec012`，保持单一 Alembic head | 两个并行模块原先都从 `0004_spec002` 分叉；后合入方顺序调整，不修改已部署的早期迁移 |
| 2026-09-29 | SPEC-013实现 | 实现实验辅助与结果验证（学生端）：新增迁移 `0007_spec013`（experiment_attempts）、接口 E050/E051、`experiment_service.py` 复用 `simulator.py` 重放固定输入序列得到检查点与标准状态，以及学生实验列表、逐拍预测、提交结果与本人记录页面 | 字段与路径按 APIC/DBD 已定义内容实现；教师端实验管理页仍未提供 |
| 2026-09-29 | SPEC-013实现 | Experiment 响应新增只读字段 `checkpoints`：`[{index, step_no, inputs}]`，只含拍号与该拍输入，**不含**标准状态 | 预测界面需要知道要答几拍以及每拍的输入；把这一层交给前端会等于在前端重算有效沿规则。标准状态仍在提交后由 E050 返回 |
| 2026-09-29 | SPEC-013实现 | AttemptResult 增加只读字段 `experiment_id` | APIC 的 AttemptResult 未含所属实验，E051 的跨实验历史无法标明每条记录属于哪个实验 |
| 2026-09-29 | SPEC-013评审修正 | AttemptResult 增加只读字段 `simulator_type`，来自提交时的实验快照 | 实验日后切换模型时，旧记录仍按原模型位宽显示，不受当前实验配置影响 |
| 2026-09-29 | SPEC-013评审修正 | E051 增加 `GET /me/experiment-attempts/{id}`，仅能读取本人记录，其他学生的 ID 返回 404 | 落实 T-013-04 的按记录 ID 越权查询验收，列表接口无法验证单条 404 |
| 2026-09-29 | SPEC-013实现 | 同一 `request_key` 同内容重试返回原记录（HTTP 200）并复用 `first_error_index`；不同内容返回 409 `DUPLICATE` | SPEC-013 第 4 节第 4 条；唯一约束 `UNIQUE(student_id, request_key)`，并发冲突回滚后按同内容再判一次 |
| 2026-09-29 | SPEC-008实现 | 实现备课与预习发布：新增迁移 `0008_spec008`（lesson_plans、lesson_plan_items、preview_assignments）、接口 E023—E027、教师「备课与预习」页面与学生首页预习待办 | 字段与路径按 APIC/DBD 已定义内容实现，无路径或状态码变更；题目快照只含题干；执行结果见 SPEC-008 执行报告 |
| 2026-09-29 | SPEC-008实现 | 固定公开预习条目快照的形状：`{sort_order,target_type,target_id,content}`，并写清各 target_type 的 content 摘要字段与知识点摘要长度 | APIC 第 2 节只写「公开预习条目快照[]」，未固定元素形状；DBD 要求「固定备课条目及内容摘要、资源版本」。属口径明确，未增删接口字段 |
| 2026-09-29 | SPEC-008实现 | 备课单条目上限固定为 50 条；发布预习时对条目引用再做一次可见性校验 | SPEC-008 第 4 节第 2 条「只引用可见内容」：备课单可能引用了之后被他人撤回为草稿的内容，发布时必须拒绝而不是把不可见内容冻结进快照 |
| 2026-09-29 | SPEC-008独立评审 | Preview 增只读 `plan_title`，取发布时已冻结的备课单标题；停用班级拒绝新预习发布，历史预习仍可读取 | 学生首页展示明确的预习标题；遵守 DBD 停用班级不得发起新活动的规则 |
| 2026-09-29 | SPEC-006实现 | 实现学习进度与资源统计：新增接口 E056 `GET /analytics/learning`（含 CSV 导出）、`stats_learning.py`（Pandas 分组与去重）与教师「学情分析」页面 | **未新增迁移**，复用 SPEC-005 的 learning_progress／resource_events／knowledge_points 与 SPEC-001 的 enrollments，head 仍为 `0008_spec008`；学生端「学习分析」保持待开放，因为 E056 仅教师可访问 |
| 2026-09-29 | SPEC-006实现 | 固定 E056 的统计口径：默认窗口截止到当前 UTC 日的下一日 00:00；分母只算当前已发布知识点、为 0 时完成率为 null；`completed_at` 为空或晚于 `to` 不计分子；`chapter_id` 同时收窄进度与资源两侧；`resources` 只列窗口内有去重事件的资料；退班学生不计当前进度名单但保留历史访问 | APIC 第 7 节。SPEC-006 第 4 节要求「当前快照近似」「from 只过滤资源事件」「UTC 整日边界」，原文字未覆盖这些边界 |
| 2026-09-29 | SPEC-006实现 | CSV 与 JSON 在同一处算出同一份 payload、共用同一套权限校验后才分流；CSV 生成复用 `stats_assessment` 的 `to_csv`／`csv_safe` | SPEC-006 第 4 节第 4 条「CSV与同筛选JSON一致」；避免出现第二份公式注入防护实现 |
| 2026-09-29 | SPEC-006独立评审 | 历史资源事件按入班日至退班日的 UTC 日范围归属，避免转班后的访问继续计入旧班；CSV 固定包含 summary 行 | 现有事件只有日期、入班表只有一组起止时间，同日转班或反复入班不能精确归属；空班级导出仍须保留分母和窗口元数据 |
| 2026-10-02 | SPEC-003实现 | 实现出勤与风险因素统计：接口 E055 `GET /analytics/attendance`（JSON 与 CSV）、`stats_attendance.py`（Pandas 分组与 Pearson）与教师端「出勤统计」页面 | **未新增迁移**，复用 SPEC-002 的 attendance_tasks／attendance_records／enrollments 与 SPEC-009/010 的 assessments／submissions，head 仍为 `0008_spec008`；新增后端 11 条、前端 17 条用例；执行结果见 SPEC-003 执行报告 |
| 2026-10-02 | SPEC-003实现 | `AttendanceStats.students[]` 增加只读联表字段 `student_no`／`display_name` | APIC 第 7 节。教师需要认出学生，而 GET /users 仅管理员可用（与 SPEC-002 增加 `student_display_name` 同一理由）。增量读取字段，不改变表结构 |
| 2026-10-02 | SPEC-003实现 | APIC 第 7 节补充 E055 口径：窗口按 `opens_at` 且只含已结算任务、`students` 为窗口内的历史名单、成绩只取非 practice 且 `submitted_at` 在窗口内的提交、CSV 列顺序与 `summary`/`student`/`correlation` 三个 section | APIC、SPEC-003 第 4 节新增第 5、6 条；原文只说「同班历史名单」与「同窗口」，未固定这些边界 |
| 2026-10-02 | SPEC-003实现 | 统计接口复用 SPEC-002 的 `_settle_task` 做幂等结算，不另写一套结算语义 | `api_attendance_stats.py` 跨模块引用既有结算函数；未修改 `api_attendance.py`，避免与并行模块冲突 |
| 2026-10-02 | SPEC-003实现 | 导航新增教师「出勤统计」入口；导航单测补该路由与高亮断言 | frontend/src/navigation、frontend/src/router 及其测试 |
| 2026-10-02 | SPEC-011实现 | 实现约束智能组卷：接口 E062 `POST /paper-generations`、`generation_service.py`（确定性分支定界）与教师「智能组卷」页面 | **未新增迁移**，复用 SPEC-009 的 questions／question_knowledge／assessments／assessment_items／submissions／submission_answers 与 SPEC-001 的 enrollments，head 仍为 `0008_spec008`；结果与候选指纹写入 `assessments.generation_json`，不另设组卷表（DBD 第 5 节末段） |
| 2026-10-02 | SPEC-011实现 | 组卷求解由设计基线的 SciPy `milp` 改为确定性分支定界（DFS + 递减上界剪枝、固定遍历顺序）；并把「已公开历史首答」明确为目标班级**已提交**首答（拉普拉斯平滑错误率，无历史取 1/2） | ADR-007 第 2 条、SPEC-011 第 2/4 节与执行报告；E062 输入输出字段、路径、状态码均未变，未新增依赖，同种子可复现 |
| 2026-10-02 | SPEC-007实现 | 实现课程检索问答：新增迁移 `0009_spec007`（qa_entries）、接口 E059/E060/E061、`retrieval.py` 语料索引（字符 2—4 gram TF-IDF 余弦）、`seed-qa` 语料种子（16 条）与教师语料管理、学生提问页面 | 字段与路径按 APIC/DBD 已定义内容实现；检索在库内语料上进行，未接入任何外部大模型服务 |
| 2026-10-02 | SPEC-007实现 | 索引语料构成固定为：每个已发布知识点一条标题语料 + 一条正文档，每条已发布问答条目一条文档；命中按知识点归并取最高分，摘要始终取有内容的语料 | 标题与长正文合并后再归一化会稀释短查询的余弦，实测使「时钟上升沿的作用是什么」等改述查询排不进 Top3。标题语料只参与打分，不改变返回字段 |
| 2026-10-02 | SPEC-007实现 | APIC 错误表 503 增加 `INDEX_UNAVAILABLE`：语料索引重建失败时保留旧索引并让请求显式失败 | SPEC-007 第 4 节第 3 条「失败保留旧索引并显式报错，不返回混合版本」；沿用 `DB_BUSY` 会掩盖真实原因 |
| 2026-10-02 | SPEC-007实现 | 导航条目由「AI 辅导」（学生）与「智能工具」（教师）改为「课程问答」，两端分别指向 `/student/qa`、`/teacher/qa` | 本模块是文本检索而不是生成式辅导，原名称会让人以为存在未实现的能力；UI 基线第 10 节要求「入口名称不增加业务范围」，改名是收窄口径 |
| 2026-10-02 | SPEC-007实现 | 依赖新增 `scikit-learn==1.9.1`（连带 scipy、joblib、threadpoolctl） | ADR-007 第 1 条指定 scikit-learn 的 TF-IDF 与余弦检索；沿用 requirements.txt「算法库随对应模块追加」的既有做法（SPEC-010 已追加 numpy/pandas） |
| 2026-10-02 | SPEC-004实现 | 实现学习预警与分组：新增迁移 `0010_spec004`（warning_snapshots）、接口 E063/E064、`warning_service.py`（规则评分 + KMeans 分组）与教师端「学习预警」页面 | 路径与字段按 APIC/DBD 已定义内容实现；新增后端 18 条、前端 12 条用例；执行结果见 SPEC-004 执行报告 |
| 2026-10-02 | SPEC-004实现 | APIC 第 7 节补 E063/E064 口径：factors 的权重与「只对可用因素归一化」、三因素的可用门槛、level 是项目规则档位而非校准概率、批次完整性与 E064 的返回形状；并把 Warning 的 `available_factors` 定为名称数组、`sample_counts` 定为逐因素样本量 | APIC、SPEC-004 第 4 节新增第 6、7 条；原文这两处未给类型，实现必须选一种并写明 |
| 2026-10-02 | SPEC-004实现 | 沿用 SPEC-007 已引入的 `scikit-learn==1.9.1` 做 KMeans 班级分组（ADR-007 第 3 条）；本模块未再新增依赖 | backend/requirements.txt 仅补记 SPEC-004 的用途注释，版本行未变 |
| 2026-10-02 | SPEC-004实现 | 三个因素沿用既有统计口径：出勤复用 SPEC-003 的按学生出勤率与 `_settle_task` 幂等结算；进度复用 SPEC-006 的完成率快照；首答正确率沿用 SPEC-010「全历史最早已提交作答、再按 submitted_at 落窗」的规则并按学生分组 | `api_warning.py`；未修改 `api_attendance.py`／`api_learning.py`／`api_assessment.py` |
| 2026-10-02 | SPEC-004实现 | 导航新增教师「学习预警」入口；导航单测补该路由与高亮断言 | frontend/src/navigation、frontend/src/router 及其测试 |
| 2026-10-02 | SPEC-004实现 | 合入前同步最新 develop：本模块迁移原先接在 `0008_spec008` 之后（revision `0009_spec004`），与并行合入的 SPEC-007 `0009_spec007` 会是同一个父节点的两个 head；已改接为 `0010_spec004`（父 `0009_spec007`） | backend/migrations/versions/0010_spec004_warnings.py；APIC、CHG-RB、README、导航测试的并行改动已一并合并 |
| 2026-10-02 | SPEC-016实现 | 实现时序逻辑知识图谱：E066/E067/E068 三个只读接口、`graph_service.py`（BFS 最短路、分层 Kahn 拓扑排序、Tarjan 环检测）与「知识图谱」页面（学生端与教师端共用） | **未新增迁移**，DBD 第 5 节末段明确图谱是 `knowledge_edges` 的只读投影、实时计算；复用 SPEC-005 的 chapters/knowledge_points/knowledge_edges 与 SPEC-001 的 enrollments，全量回归时 head 为 `0010_spec004` |
| 2026-10-02 | SPEC-016实现 | 前端依赖新增 `echarts@6.1.0`（`frontend/package.json` 精确锁定） | ADR-007 第 5 条要求用 ECharts 关系图渲染；README「技术和目录约定」已把 ECharts 列为前端技术栈，这是本模块唯一预期内的新依赖 |
| 2026-10-02 | SPEC-016实现 | 明确 `GraphNode.depth/dimension` 与 `KnowledgeGraph.truncated`、`has_cycle/cycle_edges` 的语义：未指定 `root_id` 时 depth=0、dimension 标记入度为 0 的根节点集合，裁剪按 `(chapter_id, sort_order, id)`；环只描述本次响应范围内的子图 | APIC 第 2 节只固定字段名与类型，未定义这些语义；T-016-04 要求「节点超限按规则返回 truncated」，需要把规则写死才能测 |
| 2026-10-02 | SPEC-016实现 | 查询参数错误分类：`depth` 非整数 400、整数越界 422；`chapter_id/root_id/from/to` 指向不存在的对象 404 | SPEC-016 第 4 节新增第 8 条；沿用 APIC 第 1 节「格式错误 400 / 字段错误 422 / 对象不存在 404」，原 Spec 未区分 |
| 2026-10-02 | SPEC-016实现 | 合入前同步最新 develop（SPEC-004 已合入）：本模块无迁移，链上无分叉；`app/__init__.py`、router、navigation 及其测试、CHG-RB、README 的并行追加改动已合并保留两端 | 导航测试同时保留「学习预警」与「知识图谱」两条入口用例 |

| 2026-10-02 | SPEC-017实现 | 实现时序逻辑识别辅助：新增迁移 `0011_spec017`（recognition_tasks）、接口 E069/E070、`recognition_service.py`（OpenCV/Pillow 灰度化、Otsu 二值化、网格切分、0/1 模板比对）与学生端「状态表识别」页面 | 按 APIC/DBD/ADR-007 第 6 条实现；新增后端 20 条、前端 11 条用例；格式 v1 样例图片与人工核对表见执行报告 |
| 2026-10-02 | SPEC-017实现 | APIC 第 7 节补 E069/E070 细节：multipart 字段名（`image`/`class_id`/`kind`）、413/415、配置项 `RECOGNITION_TIMEOUT_SECONDS` 与 503、失败任务的五个错误码、states/transitions/confidence 形状、读取权限按任务保存的 class_id 核对 | APIC 第 1、7 节与 SPEC-017 第 4 节新增第 8、9 条 |
| 2026-10-02 | SPEC-017实现 | E069 **显式忽略**多出来的 multipart 字段（如客户端塞 `passed`/`score`）：T-017-03 要求这类字段被忽略而不是报错 | 对 APIC 第 1 节「拒绝未知业务字段」的一处显式例外；本模块没有客户端可写的判分字段，忽略不会造成字段被覆盖 |
| 2026-10-02 | SPEC-017实现 | 新增依赖 `opencv-python-headless==5.0.0.93` 与 `Pillow==12.3.0` | ADR-007 第 6 条要求 OpenCV/Pillow；服务端无需 GUI 组件，故用体积更小的 headless 版；未引入其他依赖 |
| 2026-10-02 | SPEC-017实现 | 新增配置项 `RECOGNITION_TIMEOUT_SECONDS`（默认 5 秒）与错误码 `RECOGNITION_TIMEOUT`：识别超时返回 503，并删除刚写入的图片、不保留任务 | app/config.py、app/errors.py、api_recognition.py；SPEC-017 第 4 节第 7 条 |
| 2026-10-02 | SPEC-017实现 | 导航新增学生「状态表识别」入口；导航单测补该路由与高亮断言 | frontend/src/navigation、frontend/src/router 及其测试 |
| 2026-10-02 | SPEC-017实现 | 提交格式 v1 样例图片 `docs/testing/样例-状态表格式v1-模6计数器.png`（27KB，与测试同参数生成）与人工核对表 | SPEC-017 第 4 节第 2 条要求实现时制作样例图片与核对表；覆盖矩阵第 6 节的对应待办已勾销 |
| 2026-10-02 | SPEC-017实现 | 合入前同步最新 develop（SPEC-016 已合入）：本模块迁移接在 `0010_spec004` 之后，链上无分叉；`app/__init__.py`、router、navigation 及其测试、CHG-RB、README 的并行追加改动已合并保留两端 | 导航测试同时保留「知识图谱」与「状态表识别」两条入口用例；SPEC-016 新增的 `echarts@6.1.0` 与本模块的 OpenCV/Pillow 互不影响 |
| 2026-10-02 | SPEC-015实现 | 实现个性化复习推荐：接口 E065 `GET /me/recommendations`、`recommendation_service.py`（信号归一化与排序）与学生端「复习推荐」页面 | **未新增迁移**，DBD 第 5 节末段明确推荐首版实时计算、不另存汇总表、不持久保存学生隐式画像；复用 SPEC-006 的 learning_progress、SPEC-009 的 submissions/submission_answers/questions、SPEC-014/013 的 experiment_attempts 与 SPEC-005 的 knowledge_points/knowledge_edges，head 仍为 `0011_spec017` |
| 2026-10-02 | SPEC-015实现 | APIC 第 2 节新增 `Recommendation` 字段模型与 E065 口径补充：`resource_id`/`knowledge_id` 各自含义、`score=null` 表示基础路径条目（不是 0 分）、排序与组装顺序、`limit` 的错误分工 | APIC 原文只给字段名，没有类型语义与排序规则；T-015-02 要求「新用户 score=null」、T-015-03 要求「已掌握被排除」，不写死就无法测 |
| 2026-10-02 | SPEC-015实现 | 「未完成先修」只认**明确记录**（`completed=0`），无记录的先修不算未完成；「已公开首答」沿用 SPEC-009/010 的 `feedback_released=1` 口径 | SPEC-015 第 4 节新增第 6、7、8 条。第 1 条已写明 p 只取「明确未完成记录」，先修按同一口径才自洽；否则任何薄弱点都会被一串从未打开过的先修挤到后面 |
| 2026-10-02 | SPEC-015实现 | 屏蔽题复用 SPEC-009 的 `api_assessment._blocked_question_ids`（跨模块导入既有私有函数），未复制第三份实现 | 第 4 节第 4 条的「未公开反馈测评题排除」与 SPEC-009/010 同规则；把「首答聚合」抽成公共函数是评审记录的 D7 清理项，本模块不顺手重构他人模块 |

| 2026-10-03 | D7集成验收 | 系统集成验收：E2E-01/02/03、SEC-01、十类基础功能逐类运行时抽查、知识图谱与识别辅助的失败/无数据分支，共 81 条断言全部通过；全新空目录按 README 完成安装—迁移（0001→0011 单链）—初始化—种子—构建—waitress 启动；60 模拟客户端 10 分钟负载；备份恢复演练 | [D7 集成验收报告](docs/testing/D7-集成验收报告.md)；未完成项在其第 12 节逐条列出 |
| 2026-10-03 | D7集成验收 | 缺陷修复：`RECOGNITION_TIMEOUT_SECONDS` 此前只作为类默认值存在，`BaseConfig.from_env()` 不读同名环境变量、`.env.example` 也未登记，与 README「配置项」和 SPEC-017 第 4 节不符 | app/config.py、backend/.env.example；留空视为沿用默认 5 秒，非数字报错。生产 WSGI 实测限时 1e-06 秒 → 503 `RECOGNITION_TIMEOUT` 且不保留任务 |
| 2026-10-03 | D7集成验收 | 清理项：跨模块复用的 `_settle_task`、`_blocked_question_ids` 提升为公开名 `settle_task`、`blocked_question_ids`（SPEC-003 执行报告曾提请） | api_attendance/api_attendance_stats/api_warning/api_assessment/api_recommendation；纯重命名，无行为变化 |
| 2026-10-03 | D7集成验收 | 清理项评估：首答聚合**不**抽公共函数。SPEC-010 按知识点+窗口、SPEC-004 按学生+全历史最早再落窗、SPEC-015 按本人+`feedback_released=1`+无窗口，三者口径不同，统一需带多个开关的查询构造器 | [D7 集成验收报告](docs/testing/D7-集成验收报告.md) 第 14 节 |
| 2026-10-03 | D7集成验收 | 新增检查材料 `tests/e2e/d7_acceptance.py`、`tests/perf/load_test.py` 与 `scripts/backup.py`、`scripts/restore.py`（备份/恢复按第 3 节要求用 SQLite backup API）；`.gitignore` 增加 `backups/` | README 目录树中 `tests/e2e/`、`scripts/` 由「待创建」更新为已建立；PERF 产物标记 SIMULATED_DATA |

当前没有发布版本或实际回滚记录，但有部署与恢复演练：D7 在仓库外的全新目录完成部署，并在部署副本上完成一次备份→写入额外记录→恢复→核对的演练。以下为后续实现必须提供的流程。

## 2 变更控制

涉及功能范围先更新 PRD；涉及路径/字段/权限先更新 APIC；涉及表和约束先更新 DBD；业务规则与用例更新对应 Spec。每次变更记录原因、涉及版本、迁移方案、向后兼容性和回滚限制。通过评审后再实施。

分支 main 保存稳定版本，develop 汇总已验收模块，feature/spec-* 对应功能，hotfix/* 对应紧急修复。提交如 `feat(spec-012): 实现时钟单步演示`。合并前保存相关测试结果，未通过不以“功能基本可用”替代。

## 3 备份集合

每个可部署版本保存：应用提交号、依赖锁文件、前端构建版本、数据库迁移号、数据库一致性备份、上传文件目录及哈希清单、脱敏配置说明。实际密钥单独保存，不进入源码包。

不允许写入期间只复制SQLite主文件。优先用backup API，或停止应用后完整备份数据目录。备份目录命名 `backup-日期时间-版本`，必须在恢复前验证可读及剩余空间。

## 4 发布前检查

1. 在独立副本运行迁移及测试，验证原有记录数量、外键和关键成绩未变化。
2. 明确维护窗口，停止新的课堂测评和演示，再停止写服务。
3. 生成一致性备份，记录数据截止时间。
4. 更新应用和迁移，启动后核对登录、当前班级、历史测评、资源下载和一个仿真测试。
5. 通过后开放使用；失败则按以下场景恢复。

## 5 回滚场景

| 场景 | 处理 | 限制 |
| --- | --- | --- |
| 仅前端展示回归 | 回退至对应已验证构建，清理过期缓存后核对API兼容性 | 不回滚数据库 |
| 后端代码回归且schema兼容 | 停服，切回已验证代码和锁文件，重启测试 | 不混用新schema与旧模型 |
| 数据库迁移失败 | 保持停服；用迁移前数据库和配套文件备份恢复，核对迁移号 | 不盲目执行有数据丢失风险的downgrade |
| 发布后已产生新业务数据 | 先备份当前故障状态，评估修复前进或导出新数据再恢复 | 不能直接覆盖并丢掉新提交，记录涉及时间窗 |
| 错误导入模拟数据 | 停止继续导入，根据导入批次和备份恢复 | 不使用“清空所有表”快捷修复 |

## 6 恢复验收

恢复后检查账号与班级数量、测评题目快照和成绩、考勤状态、上传文件哈希、权限隔离以及核心仿真向量。记录操作者、时间、版本、备份路径、执行命令、数据差异及未恢复部分。演练在测试副本完成，首次实际课堂使用前至少成功执行一次。**D7 已执行一次**：备份点 `backup-20261002-163645-d7`，恢复后迁移号、19 张关键表行数与上传文件哈希全部一致，额外写入的探针用户与文件被正确丢弃；核对明细见 [D7-OPS-02恢复核对.json](docs/testing/D7-证据/D7-OPS-02恢复核对.json)。核心仿真向量与权限隔离的核对见同报告第 4、6 节。

## 7 交付平台迁移

开发阶段的Git历史推送至Gitea后核对分支与提交号，文档/源代码/测试应一致。PR、Issue和平台附件不会随Git数据自动迁移，需要的评审及检查证据保存到docs后再核对。迁移不改写现有提交作者与日期。Gitea地址和实际迁移结果在执行后记录。

## 8 实验扩展实现补充（2026-10-03）

- E074/E079增加可选at_seq，LabSession及详情LabAttempt增加只读task快照；回放由服务器完成，不增加可写成绩字段。
- 迁移0012_spec018接续0011_spec017，三表及外键按DBD建立；新任务通过seed-labs加入，已有任务不覆盖。
- 文件测评增加LAB_JAVA/LAB_JAR部署配置，Windows普通CLI已验证；Java/JAR不入库，未配置时接线和旧课堂可用。
- 运行锁/心跳排除于业务备份，恢复核对增加三张实验表，避免Windows活锁复制失败或恢复旧健康声明；真实恢复见[实验扩展验收报告](docs/testing/实验扩展验收报告.md)。
- 共享文件仅增加模块注册、路由/导航、配置和上述备份能力；不改旧课堂引擎、旧实验统计分母和PR #53的视觉方案。

## 9 预警缺省窗口修正（2026-10-04）

Issue #67：原E063/E064缺省窗口取当前秒+1，生成后再读会因窗口不同返回空，且教师首页缺省查询与预警页整日查询不一致。先将APIC/SPEC-004缺省口径明确为最近30个UTC自然日，再修改默认时间计算。显式窗口、已有快照、权限、评分与聚类规则不变，无迁移；旧缺省秒级批次仍可用其原from/to精确读取。回滚该提交恢复旧缺省计算，不删除快照数据。
