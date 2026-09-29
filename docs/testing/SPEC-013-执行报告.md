# SPEC-013 执行报告

日期：2026-09-29。对象：SPEC-013 实验辅助与结果验证（学生端）。提交：`db08fd8`（分支 `feature/spec-013`，基线 `develop` `3021f72`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-013 的 E050/E051、迁移 0007 与三张学生页面。教师端实验管理页面不在本次范围，T-012-* 属 SPEC-012。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用 SPEC-000 锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、waitress 3.0.2、python-dotenv 1.1.1、pytest 9.1.1）；本 Spec 未新增依赖 |
| 前端依赖 | 沿用 SPEC-000 锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等）；本 Spec 未新增依赖 |

标准状态由 `experiment_service.py` 调用 SPEC-012 的 `simulator.py` 重放固定输入序列得到，**没有**第二套仿真实现。本次浏览器验证让后端同源提供已构建的前端（`create_app().run(port=5055)` 提供 `frontend/dist`），未使用 Vite 代理。

## 2 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend -q` | 0 | `158 passed`（SPEC-013 新增 13 条；原有 145 条继续通过） |
| 2 | `flask --app app:create_app db upgrade`（工作目录 backend） | 0 | `Running upgrade 0006_spec009 -> 0007_spec013` |
| 3 | `flask --app app:create_app seed-content --owner-login teacher_aaa` | 0 | `课程种子：章节 +6，知识点 +12，先修关系 +15，资源 +1` |
| 4 | `flask --app app:create_app seed-experiments --owner-login teacher_aaa` | 0 | `预置实验：新增 4 个` |
| 5 | 一次性库迁移往返 | 0 | head `0007_spec013`（单一 head）；回退到 `0006_spec009` 后 `experiment_attempts` 移除、`experiments` 保留；再升级恢复 |
| 6 | 四个预置实验的检查点重放 | 0 | D 4 拍 `[1,1,0,0]`、JK 8 拍 `[1,0,1,1,0,0,0,0]`、模 6 计数器 8 拍 `[1,2,3,4,5,0,1,1]`、移位寄存器 5 拍 `[13,14,7,3,3]`（每个 ≥4 拍） |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 7 | `npm run test:unit` | 0 | 12 个测试文件、`78 passed`（本 Spec 新增 2 个文件 12 条 + 1 条导航用例） |
| 8 | `npm run build` | 0 | `93 modules transformed`，产出 `dist/`（含三个新页面分块） |
| 9 | `python 开发工作区/tools/check_docs.py <worktree>` | 0 | `未发现问题` |
| 10 | `git diff --check` | 0 | 无空白错误 |

## 3 浏览器实际流程

后端同源提供构建产物，浏览器访问 `http://localhost:5055`。数值列由同一会话直接读取接口核对。

### 3.1 实验中心

学生登录后导航出现可点击的「实验中心」（此前是「待开放」）。`/student/experiments` 列出四个已发布实验：

| 实验 | 模型 | 需要预测 |
| --- | --- | --- |
| 4 位移位寄存器：串行输入右移 | 4 位移位寄存器 | 5 拍 |
| 模 6 计数器：0—5 循环 | 4 位计数器 | 8 拍 |
| JK 触发器：保持 / 清零 / 置位 / 翻转 | JK 触发器 | 8 拍 |
| D 触发器：有效上升沿把 D 送入 Q | D 触发器 | 4 拍 |

每行另有「上次：…」与状态徽标；初次进入显示「还没有记录」。

### 3.2 逐拍预测（模 6 计数器）

`/student/experiments/3` 显示实验条件（初态 `0000`、模数 `6`、检查点 `8 拍`、实验版本 `1`）、固定输入序列表，以及 8 个输入框。输入框逐拍标注该拍输入：

```
第 1—7 拍  EN=1 RESET=0
第 8 拍     EN=0 RESET=0
```

第 8 拍正是输入序列里 `enable=0` 的那一拍，说明检查点上下文如实来自服务器对固定序列的重放。

### 3.3 T-013-01 / T-013-02：提交、出错定位与通过

| 提交 | 结果 |
| --- | --- |
| `[1,2,3,4,5,9,1,1]` | 未通过 · **第 6 拍出错** · 共 8 拍；结果表恰有 1 行标「错误」 |
| `[1,2,3,4,5,0,1,1]` | **通过 · 全部预测正确** |

第 6 拍的出错行（界面原文）：

| 拍 | 该拍输入 | 你填的 | 正确答案 | 说明 |
| --- | --- | --- | --- | --- |
| 第 6 拍 | EN=1 RESET=0 | 1001 | 0000 | 第 6 拍：EN=1 RESET=0，Q 由 0101（5） 变为 0000（0）；正确答案 0000（0），你填了 1001（9）。计数器每个有效上升沿加 1，到达模数后回到 0；enable=0 时保持。 |

即验收用例要求的「指出该拍应回到 0」。

### 3.4 本人实验记录

`/student/attempts`：标题「我的实验记录」，汇总「共 2 次提交，通过 1 次」（当时的状态），表格行 `通过/模 6 计数器：0—5 循环/4 位计数器/8/0001/1` 与 `第 6 拍出错/…/8/0001/1`，并附最近一次的逐拍对照。实验页底部「本实验记录」随后显示 3 次（含版本冲突前的一次错误提交）。

### 3.5 旧实验版本冲突

教师把实验标题改为「模 6 计数器：0—5 循环（课堂修订）」并把版本由 1 升到 2；学生页面仍持有版本 1，此时点击「提交预测」：

- 界面提示「实验已被更新，请刷新后再提交」；
- 页面自动重新拉取实验，标题与「实验版本」更新为 2；
- 已填的 8 个答案被清空（实验口径已变，旧答案不再适用）；
- 没有新增记录。

### 3.6 权限

以下以自动化测试为准，浏览器侧只做了常规路径：教师与管理员提交预测返回 403；未入班学生 403；匿名读 401（写请求缺 CSRF 令牌按 SPEC-001 公共规则返回 403）；草稿实验 404；另一名学生的历史里不出现本人记录。

方法学限制（浏览器自动化）：与前几轮相同——Browser 面板为 0×0 且隐藏，无法坐标级点击、无法截图；面板仍会在两次工具调用之间间歇性丢失会话 Cookie。**本轮已让后端同源提供构建产物（不经 Vite 代理），Cookie 仍会在调用之间丢失**，可见这是预览面板的限制而不是代理造成的。因此交互改为在页面内对应用自身处理器派发真实 DOM 事件，需要会话的流程在同一页面会话内连续执行；并已在报告外多次复跑。同一请求在会话有效时均返回预期状态码。

## 4 逐条验收

### T-013-01 计数器M6初态4连续4拍预期[5,0,1,2]，完全匹配通过

覆盖用例：`test_replay_checkpoints_uses_simulator_rules`、`test_T013_01_correct_predictions_pass`，以及第 3.3 节的浏览器流程。

| 观测 | 值 |
| --- | --- |
| 初态 4、模 6 的四拍检查点 `q_before` | `[4, 5, 0, 1]` |
| 服务端标准状态 | `[5, 0, 1, 2]` |
| 提交 `[5,0,1,2]` | 201；`passed=true`、`first_error_index=null`、`expected=[5,0,1,2]`、`actual=[5,0,1,2]`、`experiment_version` 与实验一致 |
| 每拍说明 | 4 条，均含「预测正确」 |
| 落库 | `experiment_attempts` 1 行，`passed=1` |

浏览器侧另证：预置模 6 计数器（初态 0）8 拍的标准序列 `[1,2,3,4,5,0,1,1]`，全部答对后显示「通过 · 全部预测正确」。

### T-013-02 预测[5,6,1,2]时首错index1并指出第二拍应回0

覆盖用例：`test_T013_02_first_error_index_is_zero_based`，以及第 3.3 节的浏览器流程。

| 观测 | 值 |
| --- | --- |
| 提交 `[5,6,1,2]` | 201；`passed=false`、`first_error_index=1`（从 0 开始） |
| `expected` / `actual` | `[5,0,1,2]` / `[5,6,1,2]` |
| `explanations[1]` | 含「第 2 拍」、正确答案 `0000`、学生所填 `0110` |
| `explanations[0]` | 含「预测正确」 |
| 界面 | 结果页显示「第 2 拍出错」；浏览器实测的等价场景显示「第 6 拍出错」并写出正确答案 |

### T-013-03 伪造passed=true或自带input_sequence被拒绝，不影响后端判分

覆盖用例：`test_T013_03_forged_fields_are_rejected_and_grading_stays_server_side`、`test_checkpoints_do_not_leak_expected_states`。

| 请求携带的多余字段 | 结果 |
| --- | --- |
| `passed` / `expected` / `actual` / `first_error_index` / `student_id` / `experiment_id` | 422，`details.unknown_fields` 列出该字段 |
| `input_sequence` | 422 |

伪造请求前后 `experiment_attempts` 行数不变；随后提交 `[9,9,9,9]` 仍由服务器判为未通过（`passed=false`）。另外 Experiment 响应的 `checkpoints` 只有 `index/step_no/inputs` 三个键，未提交前响应里不出现标准状态。

### T-013-04 同key重试不新增尝试；不同预测复用key409；其他学生查记录404

覆盖用例：`test_T013_04_request_key_idempotency`、`test_T013_04_history_is_own_records_only`，前端 `student-experiment-view.spec.js` 的网络重试用例。

| 观测 | 值 |
| --- | --- |
| 同 key 同内容再提交 | 200，返回**同一条**记录（id 相同、内容逐字段相同），行数不变 |
| 同 key 不同预测 | 409 `DUPLICATE`，行数不变 |
| 换 key、不同内容 | 201，新增 1 行 |
| 同一 key 拿去另一个实验 | 409（内容不同） |
| 学生 B 查 `?experiment_id=` | 返回空列表、`total=0`，看不到学生 A 的记录 |
| 教师查 `GET /me/experiment-attempts` | 403 |

说明：APIC 未提供按尝试 ID 读取单个记录的接口，E051 只返回本人记录，因此「其他学生查记录 404」在本模块落实为**他人记录不存在可见路径**（列表里查不到），而不是某个接口返回 404。

### 其他边界

- **长度**：`predictions` 长度不等于检查点数时 422，`details.fields.predictions` 给出应有的拍数。
- **取值范围**：计数器允许 0—15，16 或 −1 为 422；D/JK 只允许 0/1，填 2 为 422；布尔与字符串同样 422。
- **request_key**：非 UUID 字符串 422；大小写不同的同一 UUID 规范化为同一个 key。
- **旧版本**：`experiment_version` 与当前不符返回 409 `VERSION_CONFLICT`，`details` 给出 `current_version`；浏览器侧表现为提示 + 重新拉取 + 清空答案。
- **快照隔离**：某次提交之后把实验改成模 10 并调整序列，旧记录的 `expected`、`passed`、`experiment_version` 与 `explanations` 全部不变；新提交按新配置判分。
- **无有效沿的实验**：检查点为空时提交返回 422 并说明「没有有效上升沿」，避免空预测被误判为通过。
- **输入序列被写坏**：重放时抛出可读错误（`CheckpointError`），而不是静默算出错误答案。

## 5 未执行／待后续模块集成验证

- **教师端实验管理页面**：`/teacher/experiments`（E048/E049 的界面）未提供，教师导航中该项仍标为计划入口「SPEC-013 教师端」。实验目前经 `seed-experiments` 或接口建立。
- **SPEC-014 实验统计（E058、T-014-*）**：属 Issue #13，未实现。
- **NFR-04 尺寸验收**：1366×768 与 390px 视口未验证——本轮无法截图。
- **真正断网重试**：`request_key` 的幂等重试在单元测试里用「模拟网络失败后复用同一 key」验证，浏览器侧未真正断网。
- **性能**：未做课堂并发或延迟测试。
- **部署形态**：本轮以开发配置运行（Flask 开发服务器 + 已构建前端同源），未在 waitress 下重跑。
- 未提交/未开始 #8 及之后的模块；未合并 PR、未关闭 Issue。

## 6 契约与共享代码变更

- 未改变 APIC 的路径与既有字段语义；E050/E051 按已合并文档实现。E048/E049 与 E052—E054 属 SPEC-012，本模块只读取。
- **Experiment 响应新增只读字段 `checkpoints`**：`[{index, step_no, inputs}]`，只含拍号与该拍输入，不含标准状态。预测界面需要知道要答几拍、每拍的输入是什么；若交给前端从 `input_sequence` 推算，等于在前端重算「哪些是有效沿」的规则。已在 CHG-RB 登记。
- **AttemptResult 新增只读字段 `experiment_id`**：E051 的跨实验历史需要标明每条记录属于哪个实验。已在 CHG-RB 登记。
- 新增迁移 `0007_spec013`，`down_revision = 0006_spec009`（本分支建立时的 head）。若并行的 #8 也从同一父版本新增迁移，合并后会出现两个 head；按约定由后合并方接续迁移链并复测。
- `frontend/src/router/index.js`、`frontend/src/navigation/index.js`、`frontend/src/views/HomeView.vue` 只做必要增量：追加三条路由、把学生「实验中心」由「待开放」改为可点击、把模块状态与班级说明改为含实验；教师「实验」入口的 `planned` 文案由 `SPEC-013` 改为 `SPEC-013 教师端`，以免在模块已实现后仍提示「SPEC-013 尚未实现」。未覆盖其他分支的改动。
- 模块代码各自独立：`experiment_service.py`、`models_attempt.py`、`api_attempt.py`；未改 `models.py`、`api_admin.py`、`api_content.py`、`api_attendance.py`、`api_assessment.py`。

## 7 实现期发现的取舍

- **判分顺序**：先校验 `experiment_version`，再取检查点，最后校验 `predictions`。这样旧版本请求得到的是 409（要求刷新），而不是因为拍数不符而报 422 —— 版本过期时学生手上的拍数本来就可能已经作废。
- **幂等的并发路径**：`UNIQUE(student_id, request_key)` 冲突时回滚并按「是否同内容」重新判断：同内容返回原记录，不同内容 409，避免并发下把重试误判为冲突。
- **前端 request_key 生命周期**：进入一次提交时生成，成功或收到业务错误后作废，只有网络类失败才保留同一个 key，使重试按规格幂等；版本冲突时同时清空已填答案并重新拉取实验。
