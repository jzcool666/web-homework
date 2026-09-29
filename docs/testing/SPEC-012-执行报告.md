# SPEC-012 执行报告

日期：2026-09-29。对象：SPEC-012 课堂演示与时序仿真。提交：`fb0ded1`（分支 `feature/spec-012`，基线 `develop` `74e47ae`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-012（E048/E049、E052—E054、迁移 0005、四个预置实验与五张页面）。不包含 SPEC-013 的实验预测提交（E050/E051），也不把设计意图记为运行通过。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用 SPEC-000 锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、waitress 3.0.2、python-dotenv 1.1.1、pytest 9.1.1）；本 Spec 未新增依赖 |
| 前端依赖 | 沿用 SPEC-000 锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等）；本 Spec 未新增依赖 |

仿真逻辑为自写的纯函数（`backend/app/simulator.py`），波形为自绘 SVG，均未引入图形或仿真库。

## 2 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend -q` | 0 | `106 passed`（SPEC-012 新增 16 条；原有 90 条继续通过） |
| 2 | `flask --app app:create_app db upgrade`（工作目录 backend） | 0 | `Running upgrade 0004_spec002 -> 0005_spec012` |
| 3 | `flask --app app:create_app seed-content --owner-login teacher_aaa` | 0 | `课程种子：章节 +6，知识点 +12，先修关系 +15，资源 +1` |
| 4 | `flask --app app:create_app seed-experiments --owner-login teacher_aaa` | 0 | `预置实验：新增 4 个（共 4 个，已存在的跳过）` |
| 5 | 同一 `seed-experiments` 再执行一次 | 0 | `新增 0 个`（幂等） |
| 6 | 一次性库迁移往返 | 0 | `0005 → 0004 → 0005`，演示表移除与恢复、考勤表保留均符合预期 |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 7 | `npm run test:unit` | 0 | 9 个测试文件、`54 passed`（本 Spec 新增 2 个文件 15 条） |
| 8 | `npm run build` | 0 | `75 modules transformed`，产出 `dist/`（含五个新页面分块） |
| 9 | `python 开发工作区/tools/check_docs.py <worktree>` | 0 | `未发现问题`（链接 196 条、SPEC 18 份、接口 71 条） |
| 10 | `git diff --check` | 0 | 无空白错误 |

## 3 浏览器实际流程

后端以 `wsgi.py`（开发配置，数据库 `backend/instance/app.sqlite`）监听 5000，前端 Vite dev server 监听 5173 并代理 `/api`。观测到的真实请求见各步骤的数值列（服务器状态由同一会话直接读取 `GET /demo-sessions/{id}` 核对）。

### 3.1 D 触发器：只有有效上升沿更新（T-012-01）

教师登录 → 导航「课堂」（已由「待开放」变为可点击）→ `/teacher/classroom` 显示班级下拉与四个预置实验（D 触发器 / JK 触发器 / 4 位计数器 / 4 位移位寄存器）→ 开始演示（`POST /demo-sessions` 201）→ 进入控制台。

控制台输入按钮为 `D`、`RESET`（RESET 标注「同步高有效」）。初始 `clock=0 q=0 step_no=0`，版本 1，`reveal_next=false`、`next_q=null`。

| 操作 | 服务器状态 | 界面观测 |
| --- | --- | --- |
| clock=0 时 set D=1 | q=0 clock=0 step_no=0 历史 1 行 rising=false | 状态面板 Q=0；历史行 `1/设置输入/0/D=1RESET=0/0/0/否/0` |
| 切换时钟（0→1） | q=1 clock=1 step_no=1 rising=true | 波形出现 1 个有效沿标记「第 1 拍」 |
| 高电平期间 set D=0 | q=1 step_no=1 rising=false | Q 保持 1 |
| 切换时钟（1→0） | clock=0 q=1 step_no=1 rising=false | step_no 不增加 |
| 再切换时钟（0→1） | q=0 clock=1 step_no=2 rising=true | 历史 5 行，波形 2 个有效沿标记 |

### 3.2 模 6 计数器：5→0 回卷与 Q3Q2Q1Q0（T-012-03）

控制台输入按钮为 `EN`（标注「0 保持」）、`RESET`；波形 5 条信号线（CLK + Q3Q2Q1Q0）；初态显示 `Q3Q2Q1Q0 = 0000（0）`。

连续 12 次「切换时钟半周期」＝ 6 个有效上升沿：

| 拍 | 1 | 2 | 3 | 4 | 5 | 6 |
| --- | --- | --- | --- | --- | --- | --- |
| Q | 0001 | 0010 | 0011 | 0100 | 0101 | 0000 |
| 十进制 | 1 | 2 | 3 | 4 | 5 | 0 |

观测：`step_no=6`、`q=0`；历史行 `11/切换时钟/1/EN=1RESET=0/0101/0000/是/6`（旧 Q→新 Q 按 Q3Q2Q1Q0 显示）；波形标记「第 1 拍」…「第 6 拍」。随后令 `enable=0` 再走一拍：`q` 保持 0，`step_no` 仍递增到 7（有效沿存在但状态保持）。

### 3.3 4 位移位寄存器：串行输入右移（T-012-03）

输入按钮 `EN`、`SI`（标注「进入 Q3」）、`RESET`。初态 `Q3Q2Q1Q0 = 1010（10）`。

令 `serial_in=1` 并走一个有效上升沿：`q` 由 `1010` 变为 `1101`（13），历史行 `2/切换时钟/1/EN=1RESET=0SI=1/1010/1101/是/1`，与验收用例「shift Q1010 输入 1 后 Q1101」一致。

### 3.4 预测隐藏与揭示（T-012-04）

| 操作 | 服务器 | 界面 |
| --- | --- | --- |
| 初始（未揭示） | `reveal_next=false`、`next_q=null` | 「下一状态 Q(t+1)」显示「待揭示」 |
| 点击「揭示下一状态」（q=0、D=1） | `reveal_next=true`、`next_q=1` | 面板显示 Q=1 |
| 点击「隐藏下一状态」 | `reveal_next=false`、`next_q=null` | 回到「待揭示」 |

隐藏期间学生与教师两个响应都验证为 `"next_q":null`（响应字节中直接匹配），未揭示的下一状态不出现在任何角色可见的数据里。

### 3.5 版本冲突（T-012-04）

用同一会话在页面外提交一次 `toggle_clock`（`expected_version` 为当前值），服务器版本由 9 递增到 10；界面仍持有旧版本，此时点击控制台按钮得到：

- 响应 409，界面提示「演示已更新，请刷新后再操作」，并自动重新拉取状态，面板版本文案更新为「版本 10」。
- 未自动重放过期请求，符合 ADR-006。

### 3.6 学生只读与班级隔离（T-012-04）

以 `stu_a0001` 登录后：

| 操作 | 观测 |
| --- | --- |
| 「我的课堂」 | 列出本班进行中的演示（标题、模型、已执行拍数、版本）与「进入观看」入口 |
| 观看页 | 输入切换按钮 **0 个**，页面按钮只有外壳的「退出」；状态面板、波形（2 条信号线）、历史（7 行）、`同步于` 时间均正常 |
| 学生 `POST /demo-sessions/{id}/actions` | 403 `FORBIDDEN` |
| 学生读他班演示列表 `GET /demo-sessions?class_id=2` | 404 `NOT_FOUND` |
| 学生 `GET /experiments` | 只返回已发布实验（草稿实验不在列表，直读 404） |

### 3.7 投屏页

`/teacher/demos/4/present`：大字号标题与模型名；输入行 `输入： EN=1 SI=1 RESET=0`；头部「进行中 | 版本 3 · 同步于 11:39:31」；可编辑控件 **0 个**；状态面板 `Q3Q2Q1Q0 = 1101（13）`、下一状态「待揭示」；波形 5 条信号线、历史表 2 行；页脚「离散逻辑演示，不包含传播延迟和亚稳态。」。页面不含任何学生姓名或成绩。

方法学限制（浏览器自动化）：与 SPEC-005 同一轮的限制——Browser 面板为 0×0 且隐藏，无法做坐标级鼠标点击，也无法截图（截图 5 秒超时）；面板还会在两次工具调用之间间歇性丢失会话 Cookie。因此交互改为在页面内对应用自身处理器派发真实 DOM 事件，需要会话的流程在同一个页面会话内连续执行，并且整段流程复跑过多次。这是自动化环境的限制：同一请求在会话有效时均返回预期状态码，见各表。

## 4 逐条验收

### T-012-01 D初态0，clock0时set D=1仍Q0，上升沿Q1，下降沿与高电平期间改D保持Q1

覆盖用例：`test_T012_01_d_flip_flop_only_updates_on_rising_edge`（纯逻辑）、`test_T012_01_d_sequence_through_api`（接口），以及第 3.1 节的浏览器流程。

| 观测 | 值 |
| --- | --- |
| 初态 | `{clock:0, inputs:{d:0,reset:0}, q:0, step_no:0}`，历史 `[]` |
| clock=0 时 set D=1 | q=0、step_no=0、历史行 `rising=false` |
| 上升沿 | q=1、step_no=1、历史行 `rising=true`、`q_before=0` |
| 高电平期间 set D=0 | q=1、step_no=1 |
| 下降沿 | clock=0、q=1、step_no=1 |
| 再一个上升沿 | q=0、step_no=2 |
| 同步复位 | 高电平期间 `reset=1` 不清零；下一个上升沿 q=0 |

### T-012-02 JK依次00/01/10/11验证保持、清零、置位、翻转；同步reset仅上升沿生效

覆盖用例：`test_T012_02_jk_hold_clear_set_toggle`。

按 00 → 10 → 01 → 11 → 00 的顺序，各有效上升沿后的 Q 序列为 `[0, 1, 0, 1, 1]`（保持 0 → 置位 1 → 清零 0 → 翻转 1 → 保持 1）。同步复位：`reset=1` 在高电平期间不改变 Q，在下一个有效上升沿优先清零。

### T-012-03 M=6，Q5下一有效沿Q0；shift Q1010输入1后Q1101；enable0保持

覆盖用例：`test_T012_03_counter_modulus_and_shift_order`、`test_T012_03_counter_and_shift_through_api`，以及第 3.2、3.3 节的浏览器流程。

| 观测 | 值 |
| --- | --- |
| 模 6 的下一状态（Q=0..5） | `[1,2,3,4,5,0]` |
| 无效状态 Q=7（≥M） | 下一个有效沿回 0 |
| enable=0（计数器） | 保持当前 Q |
| shift Q=1010 且 serial_in=1 | Q'=1101 |
| shift enable=0 | 保持当前 Q |
| 接口连走 6 个有效沿 | 轨迹 `[1,2,3,4,5,0]`，step_no=6 |
| reset_view | 状态回到初态、历史清空、step_no 归零，输入的 enable 恢复为 1 |

### T-012-04 两次相同expected_version只有首次成功，另一次409；学生不能修改，隐藏预测不出现在响应中

覆盖用例：`test_T012_04_version_conflict_student_readonly_and_hidden_prediction`、`test_action_rejects_client_supplied_state`、`test_demo_isolation_between_classes_and_roles`，以及第 3.4—3.6 节的浏览器流程。

| 观测 | 值 |
| --- | --- |
| 相同 `expected_version` 两次 | 第一次 200，第二次 409，`details={expected_version, current_version}` |
| 学生 `POST /actions` | 403 `FORBIDDEN` |
| 学生 `POST /demo-sessions` | 403 |
| 隐藏预测 | 教师与学生响应的 `next_q` 均为 `null`，且服务端不计算该值 |
| 请求携带 `q` / `state` | 422（未知字段），状态未被改变 |
| 跨班教师读演示 | 404；管理员读演示 | 403；未入班学生读课程内容 | 403 |

### 其他边界

- **事件上限**：连续 128 个事件后第 129 个返回 409（`details.max_events=128`）；`reset_view` 在满额时仍然可用，否则演示会彻底卡死（该缺陷由测试发现并修复）。
- **每班一个进行中演示**：第二次 `POST /demo-sessions` 返回 409 `STATE_CONFLICT`；关闭后可重新开。
- **关闭后**：`active=false`，保留最终状态；再发动作返回 409。
- **配置校验**：`initial_q` 超出 0—15、D/JK 初态非 0/1、模数不在 2—16、非计数器带模数、未知配置字段均 422。
- **事件校验**：未知 op、空 inputs、非该模型引脚、值非 0/1（含布尔 true）、多余字段均 422。
- **快照隔离**：演示创建后把实验改成模 10 并撤回为草稿，进行中的演示仍按模 6 与初态 0 运行；学生读该实验定义 404，但仍能继续观看演示。
- **种子**：`seed-experiments` 幂等；四个预置实验的输入序列各自提供不少于 4 个有效上升沿；移位寄存器预置初态即 1010。

## 5 未执行／待后续模块集成验证

- **SPEC-013（E050/E051）**：实验预测提交、`AttemptResult`、`first_error_index` 与个人历史属 #9，本模块只提供 `experiments` 定义与输入序列，未实现也未验证 T-013-*。
- **NFR-04 尺寸验收**：1366×768 与 390px 视口未验证——本轮无法截图，也没有真实鼠标输入；投屏页大字号与手机端横向滚动需在能截图的会话中复验。
- **NFR-05 断线恢复**：页面隐藏时停止轮询、回到前台立即刷新、连续失败显示断线提示与最后同步时间均已实现并在代码层可见，但本轮**未真正断网**验证，只验证了正常刷新路径。
- **轮询周期**：学生页按 3 秒轮询，本轮只验证了挂载即取到状态与手动刷新，未测量 3 秒节拍。
- **性能（NFR-02/03）**：未做课堂并发或延迟测试。
- **部署形态**：未在 `npm run build` + waitress 同源部署下重跑本节流程，本轮为开发形态（Vite dev server + Flask 开发服务器）。
- **演示种子数据**：预置实验是真实定义而非模拟数据；课堂级样例（`seed-demo`）仍属集成阶段。
- 未提交/未开始 #6 及之后的模块；未合并 PR、未关闭 Issue。

## 6 契约与共享代码变更

- 未改变 APIC 的路径、状态码与既有字段语义；E048/E049、E052—E054 按已合并文档实现。E050/E051 未实现。
- **Demo 响应新增只读字段 `experiment`**（创建演示时固定的快照：`id/title/simulator_type/config/steps_md`）。APIC 第 2 节的 Demo 没有模型类型，学生端无法据此渲染；该字段同时避免依赖可能事后被撤回为草稿的实验定义。已在 CHG-RB 登记。
- **固定 `history` 状态行口径**：`seq/op/clock/inputs/q_before/q/rising/step_no`（APIC 只写「状态行[]」）。已在 CHG-RB 登记。
- **演示初始 `reveal_next=false`**：预测先隐藏，教师显式揭示后才返回 `next_q`（SPEC-012 第 4 节第 5 条与页面设计「下一状态 [待揭示]」）。
- 新增迁移 `0005_spec012`，`down_revision = 0004_spec002`（当前 develop 的迁移 head）。若并行的 #6 也从同一父版本新增迁移，合并后会出现两个 head，需由后合并方改写 `down_revision`。
- `app/auth.py` 新增 `require_course_access()`：纯新增函数，实验与演示复用与 SPEC-005 相同的课程读取门槛；未改变既有接口行为。
- `frontend/src/router/index.js`、`frontend/src/navigation/index.js` 追加课堂/演示路由与入口并把两处「待开放」改为可点击；`frontend/src/views/HomeView.vue` 把「课堂演示与时序仿真」标记为已开放。三者都是与其他模块相邻的公共文件。
- 以上均记录在 [CHG-RB](../../CHG-RB.md) 第 1 节。

## 7 实现期发现的缺陷

浏览器联调发现「教师控制台点击按钮后请求根本没发出」：动作处理函数引用了已在清理中删除的 `notice` 变量，运行期抛 `ReferenceError`，`pending` 停在 true，界面只剩禁用按钮。已修复，并补充了 `frontend/src/views/__tests__/teacher-demo-view.spec.js`（6 条）挂载真实组件点击真实按钮。为确认该回归测试有效，临时把缺陷注入回组件后重跑：`4 failed | 50 passed`；恢复后 `54 passed`。

另由后端测试发现：事件达到 128 上限后 `reset_view` 也被拒绝，演示无法复位；已改为上限只拦截非 `reset_view` 的事件。
