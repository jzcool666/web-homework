# REST API 接口契约

版本：设计基线 1.0，2026-09-28；2026-10-03 补充实验扩展。状态：E000—E070 已实现，实测结果见 `docs/testing/SPEC-*-执行报告.md` 与 [D7 集成验收报告](docs/testing/D7-集成验收报告.md)；E071—E082 为待实现设计。所有路径均以 `/api/v1` 为前缀；本文定义字段，模块 Spec 定义状态转换和验收。

## 1 通用协议

除文件上传外请求为 UTF-8 JSON，拒绝未知业务字段以防角色和成绩被批量覆盖。响应正常为 `{data,meta}`，meta 至少含 `server_time`；列表 data 为数组，meta 增加 page、page_size、total。时间 RFC3339 UTC，ID 正整数，比例为 0—1 或 null，界面自行转百分比。未特别注明时，字段均必填且非空；`?` 可省略；响应字段可空会标 null。

GET 成功 200、创建 201、PATCH/PUT/动作成功 200、DELETE 成功 200 且 data 为 `{deleted:true}`。GET 不改变除截止结算和会话有效性之外的业务状态；除截止最终化外，资源访问事件通过显式 POST 记录。

列表参数：`page?=1`、`page_size?=20`（1—100）、`q?`（0—100 字符）。统一稳定按 created_at、id 倒序；章节和条目按 sort_order/position。统计必填 class_id，可选 from/to；两者同时给出或都省略，采用 UTC `[from,to)`，默认最近 30 天，不超过 366 天。

错误响应：`{error:{code,message,details},meta:{server_time}}`。details 为字段错误或结构化约束列表，不含堆栈、SQL、口令或正确答案。

| HTTP | code | 含义 |
| --- | --- | --- |
| 400 | INVALID_REQUEST | JSON、分页或查询格式错误 |
| 401 | UNAUTHENTICATED / INVALID_CREDENTIALS | 未登录、过期或凭据无效 |
| 403 | FORBIDDEN / CSRF_FAILED | 无操作权限或 CSRF 错误 |
| 404 | NOT_FOUND | 不存在或属于无权访问的其他班级对象 |
| 409 | VERSION_CONFLICT / STATE_CONFLICT / DUPLICATE / DEADLINE_PASSED | 版本、状态、唯一性或时间冲突 |
| 413 | FILE_TOO_LARGE | 上传超限 |
| 415 | FILE_TYPE_UNSUPPORTED | 文件类型不支持 |
| 422 | VALIDATION_ERROR / INFEASIBLE_PAPER | 字段语义或组卷约束不满足 |
| 429 | RATE_LIMITED | 请求过于频繁，附 Retry-After |
| 503 | DB_BUSY / SOLVER_TIMEOUT / INDEX_UNAVAILABLE / RECOGNITION_TIMEOUT | 暂时不可用，可重试；INDEX_UNAVAILABLE 表示课程检索语料索引重建失败（E061），此时不用旧索引回答新语料；RECOGNITION_TIMEOUT 表示识别超出配置限时（E069），未保留任务 |

权限缩写：U=已登录用户；A=管理员；T=本人任教班级的教师；S=对应班级名单中的学生；O=内容所有者（teacher/admin）。T 不自动包含管理员，管理员需要教学账号才能操作课堂。无 class_id 的学生自练和学习记录仅本人可见。对跨班级资源返回 404，对已知角色不允许的集合操作返回 403。

写请求除初次 CSRF 创建外必须携带 `X-CSRF-Token`；会话由 Cookie 自动携带。可修改资源 PATCH 必须有 version；版本冲突示例见第 9 节。

## 2 字段模型

下列模型既是响应定义，也是表中请求字段的类型依据。DBD 内部字段不会自动全部暴露。

| 模型 | 字段 |
| --- | --- |
| User | id、login_name:string、student_no:string/null、display_name:string、role:student/teacher/admin、active:boolean、version:int；永不返回 password_hash |
| Class | id、name:string(1—80)、teacher_id:id、active:boolean、version:int |
| Enrollment | class_id、student_id、active:boolean、joined_at:time、left_at:time/null |
| Chapter | id、title:string(1—100)、sort_order:int≥0、published:boolean、owner_id、version |
| Knowledge | id、chapter_id、title:string(1—100)、body_md:string≤20000、source_url:string/null、sort_order:int、published:boolean、owner_id、version |
| Resource | id、title:string(1—100)、category:slides/guide/reference/video、knowledge_id:id/null、published:boolean、owner_id、version、versions:ResourceVersion[] |
| ResourceVersion | id、version_no:int、kind:file/link、original_name:string/null、mime:string/null、size_bytes:int/null、external_url:string/null、note:string≤200、created_at:time；无 storage_key |
| Plan | id、title:string、planned_at:time/null、notes:string≤5000、items:PlanItem[]、owner_id、version |
| PlanItem | sort_order:int、target_type:knowledge/resource_version/question/experiment、target_id:id |
| Preview | id、class_id、plan_id、plan_title:string（发布时冻结的标题）、due_at:time/null、items:公开预习条目快照[]；题目仅含题干，不含答案 |
| AttendanceTask | id、class_id、title、opens_at、late_at、closes_at、settled_at:time/null、version；明文 code 仅创建响应和教师显式重置响应一次显示 |
| AttendanceRecord | id、task_id、student_id、student_display_name、student_no、status:pending/present/late/leave/absent、signed_at:time/null |
| Leave | id、task_id、student_id、student_display_name、student_no、reason:string(1—300)、status:pending/approved/rejected、review_note:string/null、reviewed_at:time/null、version |
| QuestionWrite | type:single/multiple/boolean、stem_md:string(1—10000)、options:[{key:string,label:string}]、answer:string[]、explanation_md:string(1—10000)、difficulty:1/2/3、knowledge_ids:id[1—3]、published:boolean |
| Question | id、QuestionWrite 全部字段、owner_id、version；仅题库管理接口返回完整答案 |
| StudentItem | id（测评条目 ID）、question_id、position、points:int、type、stem_md、options、knowledge_ids；不含 answer/explanation |
| Assessment | id、class_id:id/null、kind:practice/quiz/homework/exam、title、state:draft/published/closed、effective_state:upcoming/open/closed/draft、starts_at:time/null、ends_at:time/null、feedback_released:boolean、total_score:int、version、my_submission_id:id/null、items:StudentItem[]；my_submission_id仅返回当前学生自己的记录ID，教师为null。教师读取 E038 时，已发布条目另含发布快照中的 answer、explanation_md；学生投影始终不含这两个字段 |
| Submission | id、assessment_id、student_id、status:draft/submitted、answers:[{item_id,selected:string[]}]、version、saved_at:time、submitted_at:time/null、score:int/null |
| Result | submission_id、score:int、total_score:int、feedback_available:boolean、items:[{item_id,selected,correct,awarded_points,answer,explanation_md,knowledge_ids}]；反馈未开放时 score=null，items 只保留 item_id/selected |
| Experiment | id、title、knowledge_id、simulator_type:d/jk/counter/shift、config:SimulatorConfig、steps_md、input_sequence:SimEvent[]、published:boolean、version；无期望输出 |
| SimulatorConfig | initial_q:int 0—15、modulus?:int 2—16（counter 默认16）；d/jk 初态只允许0/1，shift固定4位；复位同步高有效、时钟初始0固定 |
| SimEvent | op:set/toggle_clock/reset_view；set 带 inputs:{d?:0/1,j?:0/1,k?:0/1,enable?:0/1,serial_in?:0/1,reset?:0/1}；仅允许对应模型字段 |
| Demo | id、class_id、experiment_id、active:boolean、version、state:{clock,inputs,q,step_no}、history:状态行[]、reveal_next:boolean、next_q:int/null、last_updated:time；next_q为按当前输入计算的下一个有效上升沿状态，预测隐藏时为null |
| AttemptResult | id、experiment_id:int、simulator_type:d/jk/counter/shift、passed:boolean、first_error_index:int/null、expected:int[]、actual:int[]、explanations:string[]、experiment_version:int |
| QAEntry | id、knowledge_id、question:string≤200、answer_md:string≤10000、source_url:string/null、published:boolean、version |

公开预习条目快照的元素形状（2026-09-29 随 SPEC-008 实现固定）：`{sort_order,target_type,target_id,content}`，`content` 按类型给发布时冻结的内容摘要——`knowledge:{title,excerpt,source_url}`、`resource_version:{resource_title,category,version_no,kind,original_name,mime,size_bytes,external_url,note}`、`question:{stem_md}`（**只有题干**，不含 answer/explanation，也不含选项）、`experiment:{title,simulator_type,steps_md}`。`excerpt` 是知识点正文的前 200 字摘要。备课单条目上限 50 条。

Question options：单选/多选 2—6 个唯一 key，答案必须在选项内；多选至少 2 个正确项，判断只有 true/false。创建模型的 owner_id 从会话取得，学生端不得提交 owner_id/role/score/correct。

## 3 账号和课程接口

| 编号 | 方法与路径 | 权限 | 入参 | 返回与特有错误 |
| --- | --- | --- | --- | --- |
| E000 | GET /health | 匿名 | 无 | {status:"ok",version:string}，数据库不可用503；无环境密钥 |
| E001 | GET /auth/csrf | 匿名/U | 无 | {csrf_token:string}，设短时匿名会话 |
| E002 | POST /auth/register | 匿名 | login_name:4—32字母数字下划线、student_no:6—20数字、display_name、password:10—128字符 | User；固定student、尚未入班，重复409 |
| E003 | POST /auth/login | 匿名 | login_name,password | {user:User,csrf_token:string}；轮换会话，失败401 |
| E004 | POST /auth/logout | U | {} | {logged_out:true}，清除会话Cookie |
| E005 | GET/PATCH /me | U | PATCH version,display_name?,current_password?,new_password? | User；改密码需旧密码，成功作废所有会话并要求重新登录 |
| E006 | GET/POST /users | A | GET role?/active?；POST 同注册+role | User列表/User，不返回密码 |
| E007 | PATCH /users/{id} | A | version、active?、role? | User；禁止禁用最后一名管理员，冲突409 |
| E008 | GET/POST /classes | A/T/S | GET按权限；POST仅A，name,teacher_id | Class列表/Class |
| E009 | PATCH /classes/{id} | A | version,name?,teacher_id?,active? | Class；任课教师切换即时改变教学数据权限 |
| E010 | GET/PUT /classes/{id}/enrollments | A/T | GET A/T；PUT仅A，student_id,active | Enrollment列表/Enrollment；已有其他有效班级409 |
| E011 | GET/POST /chapters | U/O | GET published?；POST O，title,sort_order,published | Chapter列表/Chapter |
| E012 | PATCH /chapters/{id} | O | version,title?,sort_order?,published? | Chapter |
| E013 | GET/POST /knowledge-points | U/O | GET chapter_id?,q?；POST O，Knowledge可写字段 | Knowledge列表/Knowledge |
| E014 | GET/PATCH /knowledge-points/{id} | U/O | PATCH O，version+可写字段 | Knowledge，学生只读已发布 |
| E015 | PUT/DELETE /me/favorites/{knowledge_id} | S | 无 | {knowledge_id,favorited:boolean}；重复设置幂等 |
| E016 | GET /me/favorites | S | 分页 | Knowledge列表 |
| E017 | GET/PUT /me/learning-progress | S | GET chapter_id?；PUT knowledge_id,completed:boolean | 列表/单项{knowledge_id,completed,completed_at} |
| E018 | GET/POST /resources | U/O | GET category?,knowledge_id?,q?；POST O，title,category,knowledge_id?,published | Resource列表/Resource |
| E019 | PATCH /resources/{id} | O | version,title?,category?,knowledge_id?,published? | Resource |
| E020 | POST /resources/{id}/versions | O | multipart file+note；或JSON external_url,note | ResourceVersion；413/415；文件与链接二选一 |
| E021 | GET /resource-versions/{id}/download | U | 无 | 文件流，附件响应；链接类返回422 |
| E022 | POST /resource-versions/{id}/events | S | event_kind:open/download | {recorded:boolean}，同人同版本同种类同UTC日去重 |
| E023 | GET/POST /lesson-plans | T | GET分页；POST title,planned_at?,notes?,items:PlanItem[] | Plan列表/Plan |
| E024 | GET/PATCH /lesson-plans/{id} | 所有者T | PATCH version,title?,planned_at?,notes?,items? | Plan；引用不可见草稿422 |
| E025 | POST /lesson-plans/{id}/copies | 所有者T | title | 新Plan，复制条目引用 |
| E026 | POST /preview-assignments | T | class_id,plan_id,due_at? | Preview；发布快照不含题目答案 |
| E027 | GET /preview-assignments | T/S | class_id | Preview列表，S必须本人班级 |

课程公开内容的 U 还须满足教师/管理员身份或有效学生选课；新注册未入班学生只能查看 /me 与入班提示。

## 4 考勤接口

| 编号 | 方法与路径 | 权限 | 入参 | 返回与规则 |
| --- | --- | --- | --- | --- |
| E028 | GET/POST /attendance-tasks | T/S | GET class_id；POST T class_id,title,opens_at,late_at,closes_at | 列表/AttendanceTask+code:6位数字，发布时生成名单 |
| E029 | POST /attendance-tasks/{id}/sign-ins | S | code:6位数字 | AttendanceRecord；重复成功返回原记录，错误码422，时间冲突409 |
| E030 | POST /attendance-tasks/{id}/settlements | T | {} | {settled_at,counts:{present,late,leave,absent}}；结束前409，重复幂等 |
| E031 | GET /attendance-tasks/{id}/records | T/S | 分页 | AttendanceRecord列表；学生仅本人 |
| E032 | POST /attendance-tasks/{id}/code-resets | T | version | {code,version}，原码失效；结束后409 |
| E033 | GET/POST /leave-requests | T/S | GET class_id?,task_id?,status?；POST S task_id,reason | Leave列表/Leave；重复申请409 |
| E034 | PATCH /leave-requests/{id} | T | version,status:approved/rejected,review_note? | Leave；已审批或已签到冲突409 |

登录限流：账号+来源 15 分钟内 10 次失败后返回429；签到码错误同人同任务一分钟5次后限流。具体远端IP通过可信代理配置读取，不能信任任意转发头。

AttendanceRecord 与 Leave 的 `student_display_name`、`student_no` 为只读联表字段（2026-09-29 随 SPEC-002 增加）：教师查看签到名单与请假申请时需要认出学生，而 GET /users 仅管理员可用。二者不来自可写字段，客户端提交会被未知字段规则拒绝。

## 5 测评接口

| 编号 | 方法与路径 | 权限 | 入参 | 返回与规则 |
| --- | --- | --- | --- | --- |
| E035 | GET/POST /questions | T | GET knowledge_id?,difficulty?,type?,q?；POST QuestionWrite | Question列表/Question；教师可读已发布共享题及自己草稿 |
| E036 | GET/PATCH /questions/{id} | T/所有者 | PATCH version+QuestionWrite可改字段 | Question，编辑仅所有者 |
| E037 | GET/POST /assessments | T/S | GET class_id?,kind?；POST T class_id,kind:quiz/homework/exam,title,items:[{question_id,points}] | Assessment列表/草稿；新建1—30题 |
| E038 | GET/PATCH /assessments/{id} | T/S | PATCH仅T草稿，version,title?,items? | Assessment；教师读取已发布条目的答案与解析取发布快照，不取后续可编辑题库；未到开始时间学生只获活动概要，items为空 |
| E039 | POST /assessments/{id}/publication | T | version,starts_at,ends_at | Assessment；固定题目/名单/总分；结束须晚于开始 |
| E040 | POST /assessments/{id}/closure | T | version | Assessment；结束并最终化已开始草稿 |
| E041 | POST /assessments/{id}/feedback-release | T | version | Assessment；有效结束前409，公开后幂等 |
| E042 | POST /practice-sessions | S | knowledge_ids?:id[]、difficulty?:1/2/3、count?:1—20（默认5）、mistake_question_ids?:id[] | 已发布且开放反馈的Assessment；过滤和错题重练二选一，不足时422并说明可用题数 |
| E043 | POST /assessments/{id}/submissions | S | {} | Submission；创建或返回本人原草稿，自练24小时内有效 |
| E044 | PUT /submissions/{id}/answers | 本人S | version,answers:[{item_id,selected:string[]}] | Submission；局部覆盖所列题，[]表示清空；保存不判分 |
| E045 | POST /submissions/{id}/finalization | 本人S | version | Submission；以服务器已保存答案判分，同已提交版本重试返回原结果 |
| E046 | GET /submissions/{id}/result | 本人S/所属班T | 无 | Result，按反馈策略裁剪 |
| E047 | GET /me/mistakes | S | knowledge_id?,resolved?:boolean,分页 | [{question_id,last_wrong_at,latest_correct,knowledge_ids,review_available}]；受未公开测评题保护，不泄露题干答案 |

教师列表不返回其他教师的班级测评。自练 owner 是学生，只有其本人可访问。保存答案和最终提交分两步：客户端提交前等待所有保存回执；失败则停止最终提交并提示。过期保存返回409，不把离线暂存当服务器成功。

反馈投影（2026-09-29 随 SPEC-009 实现明确）：学生读取测评时服务器投影掉 answer、explanation_md 与 difficulty，不靠前端隐藏。`feedback_released=false` 时，学生的 Result 中 score=null、items 只保留 item_id/selected，Submission 中的 score 同样返回 null——分数本身也是对错信息，未到公开时机不能提前给出；任课教师读取自己班级的提交不受该时机限制。发布时冻结的题目快照是判分的唯一依据，题库改题不回写已发布测评与已有成绩。首答取该学生该题目最早已提交的一次机会，漏答计错；错题视图的 latest_correct 只看最近一次已公开反馈的已提交答案。

作答权限（2026-09-29 SPEC-009 评审明确）：创建自练、开始班级测评、保存答案和最终提交均按当前有效入班关系及班级启用状态校验；发布时的名单快照不授权离班学生发起新作答。历史提交及结果仍可读取。一次保存请求中重复的 item_id 返回 422。

## 6 仿真与实验接口

| 编号 | 方法与路径 | 权限 | 入参 | 返回与规则 |
| --- | --- | --- | --- | --- |
| E048 | GET/POST /experiments | U/O | GET knowledge_id?,q?；POST O，Experiment可写字段 | Experiment列表/Experiment |
| E049 | GET/PATCH /experiments/{id} | U/O | PATCH O，version+可写字段 | Experiment；发布记录更新需保留旧快照 |
| E050 | POST /experiments/{id}/attempts | S | experiment_version、predictions:int[]、request_key:UUID | AttemptResult；相同key同payload返回原结果，不同payload409 |
| E051 | GET /me/experiment-attempts；GET /me/experiment-attempts/{id} | S | 列表：experiment_id?,分页；单条：id | 本人AttemptResult列表或单条；其他学生的记录与不存在的 id 均返回404 |
| E052 | GET/POST /demo-sessions | T/S | GET class_id,active?；POST仅T class_id,experiment_id | Demo列表/Demo，配置从实验快照初始化；班级已有active则409 |
| E053 | GET /demo-sessions/{id} | T/S | 无 | Demo；reveal_next=false时不含未执行下一状态与未来轨迹 |
| E054 | POST /demo-sessions/{id}/actions | T | expected_version、event:SimEvent 或 {op:"set_reveal",value:boolean} 或 {op:"close"} | Demo；后端重算，不允许请求直接指定q；版本冲突409 |

演示中历史只包含已执行事件。预测模式不返回未来答案，学生本地练习仍可自行探索。教师连续点击须串行等待动作回执。关闭后动作返回409，学生轮询显示已结束。

## 7 统计和智能接口

| 编号 | 方法与路径 | 权限 | 入参 | 返回与规则 |
| --- | --- | --- | --- | --- |
| E055 | GET /analytics/attendance | T | class_id,from?,to?,format?:json/csv | AttendanceStats |
| E056 | GET /analytics/learning | T | class_id,from?,to?,chapter_id?,format? | LearningStats |
| E057 | GET /analytics/assessment | T | class_id,from?,to?,assessment_id?,format? | AssessmentStats；讲评前可给教师统计，学生无权访问 |
| E058 | GET /analytics/experiment | T | class_id,from?,to?,experiment_id?,format? | ExperimentStats |
| E059 | GET/POST /qa-entries | T | GET分页；POST QAEntry可写字段 | 列表/QAEntry |
| E060 | PATCH /qa-entries/{id} | 所有者T | version+可写字段 | QAEntry |
| E061 | POST /qa/queries | U且有课程访问权 | query:string(2—200) | {matched:boolean,corpus_version:string,matches:[{knowledge_id,title,excerpt,source_url,similarity}]}；最多3条 |
| E062 | POST /paper-generations | T | class_id,title,kind:quiz/homework/exam,count:1—30,difficulty_counts:{easy,medium,hard},knowledge_minimums:[{knowledge_id,min_count}],seed:int | {assessment_id,selected_ids,solver_status,coverage,difficulty_counts,seed}，生成草稿不自动发布 |
| E063 | POST /warnings/generations | T | class_id,from?,to? | {generated_at,algorithm_version,students:Warning[]}；最长366天，默认30天 |
| E064 | GET /warnings | T | class_id,from?,to? | 最近同窗口完整批次列表；无批次返回[]，不自动假造 |
| E065 | GET /me/recommendations | S | limit?:1—10（默认5） | {algorithm_version,items:[{kind:knowledge/question,resource_id,knowledge_id,title,score,reasons:string[]}]} |
| E066 | GET /knowledge-graph | U且有课程访问权 | chapter_id?,root_id?,depth?=1—3 | KnowledgeGraph；只含已发布知识点 |
| E067 | GET /knowledge-graph/path | U且有课程访问权 | from,to | {matched:boolean,nodes:[GraphNode],edges:[GraphEdge]}；无路径matched=false |
| E068 | GET /knowledge-graph/topological | U且有课程访问权 | chapter_id? | {order:int[],has_cycle:boolean,cycle_edges:[GraphEdge]}；有环不返回order |
| E069 | POST /recognition-tasks | S/T | multipart image、class_id、kind:state_table | RecognitionTask；S仅本人有效班级、T仅本人任教班级；413/415；同步处理并限时 |
| E070 | GET /recognition-tasks/{id} | 创建者/所属班T | 无 | RecognitionTask；以任务保存的class_id核对任课关系，跨班404，失败含格式原因 |

统计模型：

- AttendanceStats：`window, settled_tasks, counts:{present,late,leave,absent}, attendance_rate:number/null, students:[{student_id,student_no,display_name,counts,attendance_rate}], correlation:{coefficient:number/null,n:int,reason:string/null}`。相关仅用同窗口出勤和百分制平均测评分数均存在的学生，n≥5且两列非恒定才计算 Pearson，说明不代表因果。`students` 的 `student_no`/`display_name` 是只读联表字段：教师需要认出学生，而 GET /users 仅管理员可用（与 SPEC-002 同一理由）。

E055 的统计口径补充（2026-10-02 随 SPEC-003 实现固定）：窗口按任务 `opens_at` 落入 `[from,to)` 选择，且只纳入已结算任务——进入统计前先对窗口所在班级已结束但未结算的任务做一次幂等结算，进行中的任务不进入分母。出勤率 =（present + late）/（present + late + absent），请假从分母排除；分子分母都为 0 时 `attendance_rate` 为 null（不是 0%）。`students` 是窗口内出现过的考勤记录所属学生（即该窗口的历史名单），不是当前在册名单。成绩列只取本班非 practice 测评中 `submitted_at` 落入窗口的已提交记录，按学生取百分制均值；`correlation.n` 是两列都有值的学生数，不足 5 名或任一列取值恒定时 `coefficient` 为 null 并在 `reason` 给出原因。CSV 的列顺序固定为 `section,student_id,student_no,display_name,settled_tasks,present,late,leave,absent,attendance_rate,coefficient,n,reason,window_from,window_to`，三个 section（`summary`／`student`／`correlation`）的数字与 JSON 同名段一一对应。
- LearningStats：`window:{from,to}, published_knowledge_count, students:[{student_id,completed_count,completion_rate}], resources:[{resource_id,unique_students,dedup_events}]`。进度是 to 时点前已完成且当前仍完成的记录快照近似，不声称精确历史重建；from只过滤资源事件，响应给出 `progress_basis:"current_completed_before_to"`。资源事件按UTC整日计，from/to须为UTC日边界，非法非整日范围422；页面将日期选择转换为对应UTC日并标注口径。

E056 的统计口径补充（2026-09-29 随 SPEC-006 实现固定）：`window` 的 from/to 是 UTC 整日边界，省略时默认最近 30 个 UTC 自然日、截止到当前 UTC 日的下一日 00:00（按日记录的事件不能用当前时刻做右界）。分母只算**当前已发布的**知识点，分母为 0 时 `completion_rate` 为 null（不是 0）；分子只算 `completed_at` 非空且早于 `to` 的记录，因此撤销过完成、或没有完成时间的记录都不计入。「已退班」由 `enrollments.active` 判定：`students` 只含当前有效在册学生；`resources` 保留曾在本班学生入班日至退班日（均为 UTC 日）的历史访问，退班日之后的访问不归入旧班。事件仅保存日期且入班表仅保留一组起止时间，同日转班及反复入班不能精确还原归属。`chapter_id` 同时收窄进度与资源两侧——资源按「它关联的知识点所属章节」判断，未关联知识点的资料在带章节筛选时不出现。`resources` 只列出窗口内至少有 1 个去重事件的资料。CSV 始终包含一行 summary，空班级时仍保留分母、窗口和口径元数据。
- AssessmentStats：`window:{from,to}, assessments:[{id,roster_count,submitted_count,blank_count,submission_rate,mean_percent}], items:[{item_id,answered_count,unanswered_count,correct_count,correct_rate,option_counts}], knowledge:[{knowledge_id,first_attempt_count,first_correct_count,first_accuracy}], score_buckets:[{range,count}]`。空答案算题目机会（计入 answered_count 分母）但各选项不增计；漏答数单列在 unanswered_count，白卷单列在 blank_count，便于与选项分布对账。`option_counts` 是 `{选项key: 被选次数}`，一次选中只计一次。`score_buckets.range` 取 `0-<60`、`60-<70`、`70-<80`、`80-<90`、`90-100`。计入窗口的班级测评是起止区间与 `[from,to)` 有交集的测评；提交率分母是发布时固定的名单，平均分与分数段只含已提交（白卷按 0 分计入）。返回值只有聚合值，不含学生身份。
- ExperimentStats：`window,published_count,participants,passed_students,pass_rate,attempt_count,experiments:[{experiment_id,participants,passed_students,attempt_count,pass_rate}]`。总通过人数指至少通过一个实验；单实验口径分别给出，不能误写全部实验均通过。
- Warning：`student_id,score:number/null,level:insufficient/low/medium/high,factors:{attendance?,progress?,accuracy?},available_factors:string[],sample_counts:{attendance:int,progress:int,accuracy:int},cluster_label:int/null,reasons:string[],generated_at`。factors 是风险方向的值（1−对应表现率），不可用的因素为 null，不按 0 计入。

E063/E064 的口径补充（2026-10-02 随 SPEC-004 实现固定）：factors 的权重为 attendance 0.3、progress 0.2、accuracy 0.5，只对可用因素按权重归一化，score = 100×加权和。可用门槛为：出勤要有已结算任务的有效分母；进度要有明确完成/未完成记录且当前已发布知识点数大于 0；答题至少 3 次首答。可用项少于 2 个时 score 为 null、level 为 insufficient。`available_factors` 是可用因素的名称数组，`sample_counts` 是各因素的实际样本量（出勤分母、进度记录条数、首答次数）。level 是项目规则档位（score<30 为 low、<60 为 medium、否则 high），**不是**经训练校准的学业风险概率。E063 一次生成写入一个批次，批次号与生成时的名单规模记在 `evidence_json`（同时保存 factors/sample_counts/reasons）；响应为 `{generated_at,algorithm_version,window,cluster_reason,disclaimer,students:Warning[]}`。E064 返回该窗口最近一个**完整批次**（该批次行数与生成时名单规模一致）的 Warning 数组，无批次时 `data` 为 `[]`，支持 page/page_size、默认按 student_id 升序。只有三因素齐全的学生参与 KMeans 分组（n≥10 且不同向量≥3，k=3、random_state=42、n_init=10），按各簇中心平均风险升序编号 0/1/2，不覆盖规则等级；`cluster_reason` 在未分组时给出原因。
- Recommendation：`kind:knowledge/question,resource_id,knowledge_id,title,score:number/null,reasons:string[]`；`kind=knowledge` 时 `resource_id` 与 `knowledge_id` 同为知识点 ID，`kind=question` 时 `resource_id` 是题目 ID、`knowledge_id` 是所属知识点；条目不含选项、答案与解析。

E065 的补充（2026-10-02 随 SPEC-015 实现固定）：`score` 是 0—100 的个性化优先度（已公开首答错误率 e、明确未完成 p、实验失败比例 x 按 0.5/0.3/0.2 只对可用项归一化），**没有任何可用信号时为 `null`**，表示基础路径条目，不得读作 0 分；`reasons` 至少一条且只来自实际可用信号。排序为薄弱知识点降序（同分按章节顺序、章内 sort_order、ID），每个薄弱点先给「明确未完成」的先修、再给它自己、再给它尚未答对的练习，最后按章节顺序补基础路径；已掌握（完成 + 首答正确率 ≥ .8 + 无未通过实验）的知识点被排除。`limit` 默认 5，非整数 400、越界 422。端点固定按本人会话计算，不接收学生 ID 参数；教师与管理员不可访问（403）。
- GraphNode：`knowledge_id,title,chapter_id,depth:int,dimension:0/1`；dimension 表示是否根节点集合的成员，供前端同层对齐。
- GraphEdge：`prerequisite_id,target_id`；方向为先修指向后继。
- KnowledgeGraph：`nodes:[GraphNode],edges:[GraphEdge],has_cycle:boolean,truncated:boolean`；truncated 为节点超上限被裁剪时为 true。
- RecognitionTask：`id,class_id,kind:state_table,status:done/failed,created_at,result:{rows:int,cols:int,states:[{row:int,value:int}],transitions:[{from:int,to:int}],confidence:number,requires_review:true}或null,error:{code,message,details}或null`；同步处理完成后才返回任务，status=failed 时 result 为 null 且 error 给出格式原因。

E069/E070 的补充（2026-10-02 随 SPEC-017 实现固定）：E069 是 multipart，字段名为 `image`（PNG/JPEG，单文件 ≤20MiB）、`class_id`、`kind=state_table`；扩展名白名单之外返回 415、超限返回 413。**本接口刻意忽略多出来的 multipart 字段**（例如客户端塞 `passed`/`score`）：T-017-03 要求这类字段被忽略而不是报错，且本模块没有任何客户端可写的判分字段，忽略不会造成字段被覆盖（这是对第 1 节「拒绝未知业务字段」的一处显式例外，已登记 CHG-RB）。学生只能选择本人当前有效班级、教师只能选择本人任教班级，否则 404。处理同步完成并受配置项 `RECOGNITION_TIMEOUT_SECONDS`（默认 5 秒）限制，超时返回 503 `RECOGNITION_TIMEOUT` 且**不保留任务**、可重试，不引入后台队列。E070 允许任务创建者与该任务保存的 `class_id` 的任课教师读取，其余人一律 404（不区分不存在与无权）。`result.states` 按行给出十进制状态值（位序 Q3Q2Q1Q0，最左列为高位），`transitions` 是相邻行推导出的次态对，`confidence` 是各格最高匹配度的最小值；失败任务的 `error.code` 取 `IMAGE_DECODE_FAILED`／`GRID_NOT_DETECTED`／`SHAPE_MISMATCH`／`CELL_NOT_BINARY`／`CELL_UNCERTAIN`，分别对应图片无法解码、未检测到网格、行列数不符、格内非 0/1、字符不确定。识别结果始终是辅助信息（`requires_review:true`），实验判分仍由 SPEC-013 从配置与输入序列重算，不采信识别结论或客户端字段。

E057 的提交、平均分、逐题统计与分数段只计 `submitted_at ∈ [from,to)` 的记录；首答先从全历史确定最早作答，再检查其是否属于本次选中的测评和时间窗口。省略 `from/to` 时，默认窗口的 `to` 取服务器当前秒的下一秒，以覆盖当前秒刚提交的记录；显式传入的 `to` 始终右开。

CSV 返回 UTF-8 BOM 文件，包含相同过滤条件的可展开明细，不包含密码、会话或答案；对以 =、+、-、@ 开头的用户输入文本加安全前缀。JSON 字段名和 CSV 列说明在实现测试中固定。E057 的 CSV 把四个块展开为同一张表，用 `section` 区分（`assessment`／`item`／`knowledge`／`score_bucket`），列顺序固定为 `section,assessment_id,item_id,knowledge_id,range,roster_count,submitted_count,blank_count,submission_rate,mean_percent,answered_count,unanswered_count,correct_count,correct_rate,option_counts,first_attempt_count,first_correct_count,first_accuracy,count`；`option_counts` 在 CSV 中写成 `key=次数;key=次数`。

## 8 幂等、时间和状态

- 自练在创建时固定 starts_at=当前时间、ends_at=24小时后；仅创建者列入名单。所有作答范围是 `[starts_at,ends_at)`。
- 活动关闭、结果读取、统计查询和截止后的提交进入同一个幂等 finalize 服务；已开始草稿按最后保存答案评分，未开始者仍记未提交。最终化的 `submitted_at` 取测评的有效截止时间：自然截止取 `ends_at`，教师提前结束时先把 `ends_at` 收缩到实际结束时间，因此统计窗口不会把访问触发的延迟处理时间算成提交时间，也不需要额外的关闭时间列。
- 最终化已提交试卷不再改分；重复 finalization 返回原结果，无需重新计算。旧草稿保存必须返回409。
- POST 创建普通资源不保证重复点击幂等，前端须避免重复发送；实验使用 request_key，其他有自然唯一键的动作依约返回原对象或409。
- 文件上传失败不得保留有效版本记录；落库失败清理本次临时文件。算法执行过程中引用版本变化返回409，不能写入与请求不符的快照。

## 9 成功与失败样例

创建测评草稿 E037：

```json
{"class_id":1,"kind":"quiz","title":"模6计数器下一状态","items":[{"question_id":12,"points":10}]}
```

201 响应示意，示例 ID 不代表数据库已有记录：

```json
{"data":{"id":8,"class_id":1,"kind":"quiz","title":"模6计数器下一状态","state":"draft","effective_state":"draft","starts_at":null,"ends_at":null,"feedback_released":false,"total_score":10,"version":1,"my_submission_id":null,"items":[{"id":41,"question_id":12,"position":1,"points":10,"type":"single","stem_md":"Q=0101时，下一个有效时钟沿后的状态是什么？","options":[{"key":"A","label":"0000"},{"key":"B","label":"0110"}],"knowledge_ids":[15]}]},"meta":{"server_time":"2026-09-28T05:00:00Z"}}
```

演示版本冲突 E054：

```json
{"error":{"code":"VERSION_CONFLICT","message":"演示已更新，请刷新后再操作","details":{"expected_version":3,"current_version":4}},"meta":{"server_time":"2026-09-28T05:00:01Z"}}
```

组卷不可满足 E062：

```json
{"error":{"code":"INFEASIBLE_PAPER","message":"题库无法满足当前条件","details":{"constraints":[{"kind":"difficulty","difficulty":"hard","required":3,"available":1}]}},"meta":{"server_time":"2026-09-28T05:00:02Z"}}
```

查询无可靠匹配 E061：

```json
{"data":{"matched":false,"corpus_version":"v1","matches":[]},"meta":{"server_time":"2026-09-28T05:00:03Z"}}
```

所有其他接口依本节统一封装和字段模型返回，模块中特有的边界样例及测试编号见对应 Spec。

## 10 实验箱与电路文件测评（待实现）

关联 FR-20/21、SPEC-018/019，行为及限制见[实验扩展方案](docs/design/实验箱接线与电路测评方案.md)。不改 E048—E058 的旧实验模型或统计分母。下列权限 S 指本人当前有效班级学生，T 指对象保存的 class_id 当前任课教师；历史只读允许已退班的记录创建者，禁用账号无访问。A 不获得教学记录权限。

| 模型 | 字段 |
| --- | --- |
| LabTask | id、code:LAB-D/LAB-C6/LAB-S4/LAB-FSM、title、knowledge_id、version、catalog_version、instructions_md、ports:[{label,direction:input/output,width:int}]、board:{chips:[{id,model}],terminals:[{id,label,kind:rail/switch/clock/probe,port:string/null,bit:int/null}]}、catalog:{version,models:[{model,pin_count:int,pins:[{number:int,name,direction:input/output/power/ground,unit:string/null}],units:[{id,kind,input_pins:int[],output_pins:int[]}]}]}；不含私有向量/标准接线 |
| LabSession | id、task_id、task_version、class_id、owner_id、kind:practice/demo、version、saved_at、board:{wires:[{id,from,to}],switches:终端值映射,power:boolean,clock:0/1}、events:[{seq,action_key,op,payload,received_at}]、state:{status:off/ready/blocked,pins:端点逻辑值映射,outputs:端口位串映射,diagnostics:[{code,message,endpoints:string[]}],trace:公开操作状态行[]}；逻辑值0/1/X/Z，位串高位在前 |
| LabAttempt | id、task_id、task_code、task_version、class_id、student_id、student_display_name、student_no、mode:wiring/circ、session_id:id/null、created_at、finished_at:time/null、status:queued/running/done/error、score:number/null、passed:boolean/null、passed_checkpoints:int/null、total_checkpoints:int/null、first_failure:{checkpoint:int,inputs:公开端口映射,expected:输出位串映射,actual:输出位串映射,reason:string}/null、error:{code,message}/null、suite_version、engine_version、file:{original_name,size_bytes,sha256}/null；queued/running/error 的成绩和通过字段为null；详情另给只读session_snapshot或null，不给文件路径/命令/私有全向量 |
| LabSummary | class_id、tasks:[{task_id,mode,participant_count,attempt_count,passed_student_count,pass_rate:number/null,queued_count,running_count,error_count}]；当前有效在册名单，participant_count按至少一条done去重、attempt_count为done条数、通过人数按任一次passed去重，pass_rate=通过人数/参与人数，无参与null |

LabTask 的 board 只暴露固定器件/终端和目录事实，不提前提供正确导线。knowledge_id 必须对应已发布知识点；任务列表只列已发布任务。任务首版经幂等种子维护，没有开放任务编辑/任意向量上传接口。已停用任务或班级仍可读历史，禁新建/动作/提交；更新种子不得覆盖使用中的版本或改历史。

端点ID规则：芯片为`chip:{固定chip_id}:{pin_number}`，箱端子为`terminal:{固定terminal_id}`；chip_id/terminal_id仅ASCII字母数字下划线。4位端口拆分bit=0—3，input使用switch、output使用probe，板上实际信号权重按对应ports与方案位序；1位也标bit=0。power/ground脚不作为主动输出，rails为唯一+5V/GND源，箱开电时为1/0、关电Z。catalog模型不携带运行代码，前端不得eval。每个活动时序单元CLK必须直接连接箱CLK节点，本版不支持门控/派生时钟，错误连接给CIRCUIT_UNSUPPORTED，不静默采用错误有效沿。

| 编号 | 方法与路径 | 权限 | 入参 | 返回与特有错误 |
| --- | --- | --- | --- | --- |
| E071 | GET /lab-tasks | S/T | 常规分页 | LabTask列表，稳定按code；未入班学生404，管理员403 |
| E072 | GET /lab-tasks/{id} | S/T | 无 | LabTask；已发布且可用任务，无私有测试或答案接线 |
| E073 | POST /lab-sessions | S/T | task_id、task_version、class_id、request_key:string 8—64 | 201 LabSession；学生practice、教师demo，空箱；同owner同key同载荷200原对象、异载荷409 |
| E074 | GET /lab-sessions/{id} | 创建者/T | 无 | LabSession；教师读取学生会话只读，本人/本班判定，跨班404 |
| E075 | POST /lab-sessions/{id}/actions | 创建者S/T | version、action_key:string 8—64、op、payload | LabSession；原子版本动作，同key同载荷200原动作时快照、异载荷409，陈旧新动作409；未知动作/客户端state字段422；结构问题保存后state.status=blocked |
| E076 | POST /lab-attempts/wiring | S | session_id、session_version、task_version、request_key:string 8—64 | 201 LabAttempt(done)；取服务器会话/任务快照；无效结构422、不生成成绩；引擎超时503；同key同载荷200原对象 |
| E077 | POST /lab-attempts/circ | S | multipart file、task_id、task_version、class_id、request_key:string 8—64 | 202 LabAttempt(queued)，显式状态例外；非circ415、超2MiB413、版本/端口/XML/外部依赖422、限流429、引擎/worker不可用503；同key同文件哈希/任务载荷200原对象，异载荷409 |
| E078 | GET /lab-attempts | S/T | T必填class_id；task_id?、mode?、status?、student_id?仅T；常规分页 | LabAttempt列表；学生本人、教师本班；S携带student_id/class_id过滤422 |
| E079 | GET /lab-attempts/{id} | 本人/T | 无 | LabAttempt详情；可轮询队列，不在GET触发运行，跨班/他人404 |
| E080 | GET /lab-attempts/{id}/file | 本人/T | 无 | circ附件；wiring无文件404；下载鉴权、防原名注入、不输出storage_key |
| E081 | GET /lab-tasks/{id}/template | S/T | 无 | 5.0.0 circ模板附件，仅main与指定Pin，无答案；任务不可用404 |
| E082 | GET /analytics/labs | T | class_id、task_id? | LabSummary；无时间窗、当前在册汇总；S/A403，跨班404，不改变旧E058 |

E075 payload：connect 为 `{from:string,to:string}`，端点必须在任务目录；disconnect 为 `{wire_id:string}`；set_switch 为 `{terminal_id:string,value:0/1}`；set_clock 为 `{value:0/1}`；power 为 `{on:boolean}`；reset 为 `{}`。所有端点为单引脚/单开关，4位端口在板上拆成四个终端。未知字段422。connect/disconnect仅关电可用，否则409；连接相同无序端点已存在409，端点相同422。set_clock仅开电可用；reset恢复空箱但保留过程。事件序号从1起，服务器received_at，超512返回422保留已有记录。每个成功新动作version+1；幂等键的载荷指纹含原version，返回该事件时可重放得到的快照，前端不得用旧回执覆盖更高版本状态。

E076/E077 的幂等键按student全局唯一并包含mode。新提交必须处于本人当前有效班级；历史读取依保存的class_id与创建者。旧task_version409要求刷新；旧会话不能自动迁移芯片或线，重新创建练习。E076只准practice会话，demo不进入成绩；取得快照后在事务外计算，写成绩前复核session_version/task_version，变化409。E077 XML/库/属性校验在入队前完成，入队事务失败删除本次文件，不留成功记录。

错误补充：422 `CIRCUIT_INVALID`/`CIRCUIT_UNSUPPORTED`/`LAB_LIMIT_EXCEEDED`；503 `LAB_ENGINE_UNAVAILABLE`/`LAB_SIMULATION_TIMEOUT`；429附Retry-After。worker运行失败写attempt.error（例如GRADING_TIMEOUT/GRADING_OUTPUT_INVALID/GRADING_PROCESS_FAILED/WORKER_INTERRUPTED），GET仍返回200对象及null成绩，不能靠HTTP200认定通过。API从不接受q、passed、score、expected、suite或任意文件路径字段；E077未知multipart业务字段同样422，不沿用E069的显式例外。
