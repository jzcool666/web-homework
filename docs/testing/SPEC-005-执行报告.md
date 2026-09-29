# SPEC-005 执行报告

日期：2026-09-29。对象：SPEC-005 课程知识与教学资源。提交：`e46035c`（分支 `feature/spec-005`，基线 `develop` `be65e1c`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-005（E011—E022、迁移 0003、课程种子与三个页面）。不包含 SPEC-016 的知识图谱读取接口，也不把设计意图记为运行通过。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用 SPEC-000 锁定版本（Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、waitress 3.0.2、python-dotenv 1.1.1、pytest 9.1.1）；本 Spec 未新增依赖 |
| 前端依赖 | 沿用 SPEC-000 锁定版本（vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、vitest 5.0.2 等）；本 Spec 未新增依赖 |

随机文件名用标准库 `secrets`，内容哈希用 `hashlib.sha256`，均未引入额外库。Markdown 渲染为自写的 `frontend/src/utils/markdown.js`（先整体转义、只生成白名单标签），没有引入 markdown 或 sanitize 依赖。

## 2 命令与结果

后端（仓库根目录）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend -q` | 0 | `52 passed`（SPEC-005 新增 17 条；SPEC-000/001 原有 35 条继续通过） |
| 2 | `flask --app app:create_app db upgrade`（工作目录 backend） | 0 | `Running upgrade 0002_spec001 -> 0003_spec005` |
| 3 | `flask --app app:create_app init-admin --login-name admin_root --password <口令>` | 0 | `已创建管理员：id=1 login_name=admin_root` |
| 4 | `flask --app app:create_app seed-content --owner-login teacher_aaa` | 0 | `课程种子：章节 +6，知识点 +12，先修关系 +15，资源 +1` |
| 5 | 同一 `seed-content` 命令再执行一次 | 0 | `章节 +0，知识点 +0，先修关系 +0，资源 +0`（幂等） |
| 6 | 一次性库迁移往返（脚本，见第 6 节） | 0 | `0003 → 0002 → 0003 → 0001`，各步表集合符合预期 |

前端（`frontend/`）：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 7 | `npm run test:unit` | 0 | 5 个测试文件、`26 passed`（SPEC-005 新增 1 个文件 9 条） |
| 8 | `npm run build` | 0 | `46 modules transformed`，产出 `dist/`（含三个新页面分块） |
| 9 | `git diff --check` | 0 | 无空白错误 |

## 3 浏览器实际流程

后端以 `wsgi.py`（开发配置，数据库 `backend/instance/app.sqlite`）监听 5000，前端 Vite dev server 监听 5173 并代理 `/api`。观测到的真实请求见各步骤的网络列。

### 3.1 教师内容管理

| 步骤 | 网络观测 | 界面结果 |
| --- | --- | --- |
| 以 `teacher_aaa` 登录 | `POST /auth/login` 200 | 导航出现「课程内容」（新增入口） |
| 打开 `/teacher/content` | `GET /me` 200 → `GET /chapters`、`/knowledge-points`、`/resources` 均 200 | 章节表 6 行（第一单元—第六单元，均「已发布」），知识点表 12 行，资源区显示种子外链资料 v1 |
| 新建资源「模6计数器状态表（课堂板书）」，类别 slides、关联「模 6 计数器与 5→0 回卷」、直接发布 | `GET /auth/csrf` 200 → `POST /resources` 201 | 提示「已创建资源…」，资源区出现该项，版本为空 |
| 选择 PNG 并上传 v1 | `POST /resources/2/versions` 201 | 提示「已追加…的版本 v1」；列表出现 `v1 · 模6计数器状态表-v1.png（image/png，98 字节）· 初版板书` |
| 再上传 v2 | `POST /resources/2/versions` 201 | 提示「已追加…的版本 v2」；v1 与 v2 同时列出，v1 内容未变 |
| 转为教师乙登录并打开 `/teacher/content` | `GET /chapters` 等 200 | 教师甲的内容显示「他人创建，只读」，没有发布/撤回按钮，也没有上传控件（0 个 file input） |
| 教师乙新建自己的资源后尝试上传 `payload.exe` | `POST /resources/{id}/versions` 415 | 界面提示「仅支持 PDF、PPTX、PNG、JPEG」 |
| 上传扩展名为 `.png`、文件头为 `MZ` 的文件 | `POST …/versions` 415 | 同样提示类型不支持（改后缀不能绕过） |
| 追加外链 `javascript:alert(1)` | `POST …/versions` 422 | 界面提示「请求字段不合法」 |
| 学生登录后打开 `/teacher/content` | 路由守卫 | 停留在首页 `/`；导航中无「课程内容」与「账号管理」 |

### 3.2 学生学习与收藏

| 步骤 | 网络观测 | 界面结果 |
| --- | --- | --- |
| 以 `stu_a0001` 登录并进入「学习与收藏」 | `GET /me`、`/chapters`、`/knowledge-points`、`/resources`、`/me/favorites`、`/me/learning-progress` 均 200 | 六个单元共 12 个知识点全部列出；草稿知识点「草稿：尚未发布的时序案例」不在列表中 |
| 首行点「收藏」→「取消收藏」→ 再「收藏」 | 三次 `PUT/DELETE /me/favorites/1` 均 200 | 按钮在「收藏 / 取消收藏」之间正确切换 |
| 首行点「标记完成」→「取消完成」→ 再「标记完成」 | `PUT /me/learning-progress` 200×3 | 徽标「已完成 / 未完成」切换，提示分别为「已标记为完成（自报数据）」与「已取消完成标记」 |
| 点资源「模6计数器状态表-v1.png」 | `POST /resource-versions/2/events` 200 | 提示「已记录本次访问」 |
| 同一天再点两次同一版本 | 两次 `POST` 返回 `{"recorded":false}` | 不再提示已记录（按 UTC 日去重） |
| 访问 `/student/knowledge/13`（教师草稿） | `GET /knowledge-points/13` 404 | 页面提示「知识点不存在」，DOM 中不含草稿正文 |
| 访问 `/student/knowledge/14`（正文含 `<script>` 与 `<img onerror>`） | `GET /knowledge-points/14` 200 | 标题、段落、列表、表格、引用、行内代码均正常渲染；`window.__pwned` 为 `undefined`，渲染容器内 script 元素 0 个、img 元素 0 个，原文以转义文本 `&lt;script&gt;…` 显示 |

方法学限制（浏览器自动化）：本轮的 Browser 面板为 0×0 且 `visibilityState=hidden`，因此**无法**做坐标级鼠标点击，也**无法**截图（截图在 5 秒内超时）。所有交互改为在页面内对应用自身的处理器派发真实 DOM `click` 事件、用真实 `input/change` 事件填写表单——走的是与用户点击相同的代码路径、相同的 HTTP 请求，但不是操作系统级鼠标输入。另外该面板在两次工具调用之间会间歇性丢失会话 Cookie；因此需要会话的流程改为在同一个页面会话内连续执行，并在重新登录后复跑。这是自动化环境的限制：同样请求在会话有效时均返回 200/201，见第 3 节各表。

文件上传的输入框由页面内构造的 `File` 对象填充（自动化无法打开系统文件对话框），其字节与磁盘样例 `模6计数器状态表-v1.png` / `-v2.png` 完全一致，仍以真实 multipart HTTP 请求上传；第 4 节用 sha256 对照了落库值与样例文件。

## 4 逐条验收

### T-005-01 上传新版本后旧版本下载内容哈希不变，非法扩展/路径文件名不能执行或越界

覆盖用例：`test_T005_01_new_version_leaves_old_download_unchanged`、`test_T005_01_rejects_illegal_extension_and_content`、`test_T005_01_path_like_filename_is_stored_under_random_name`、`test_T005_01_upload_limits_and_link_rules`。

| 观测 | 值 |
| --- | --- |
| 第二次上传后 `resource_versions` 行数 | 2（v1 与 v2 各一行，v1 未被改写） |
| v1 下载内容 sha256（上传 v2 之后） | `0e4257a878e98fd9c7753289f68a20039f5a2d23e6abb091a29eb58d76212632` |
| 磁盘样例 `模6计数器状态表-v1.png` 的 sha256 | `0e4257a878e98fd9c7753289f68a20039f5a2d23e6abb091a29eb58d76212632`（一致） |
| v2 的 sha256 | `141192322dc9389b37dc76f05d079677c73160627de3bb28a445cc786c2e6fd8` |
| 上传 `payload.exe` / `shell.php` / `notes.txt` / `diagram.svg` / `archive.zip` | 415 `FILE_TYPE_UNSUPPORTED`，且未留下版本记录与磁盘文件 |
| 上传扩展名 `.png`、文件头 `MZ` 的文件 | 415（扩展名与文件头同时校验） |
| 上传文件名 `../../../evil.png` | 201；响应 `original_name` 为 `evil.png` |
| 该版本的 `storage_key`（自动化断言） | 形如 `resources/<32 位十六进制>.png`，解析后落在上传根目录内，文件名与 `evil.png` 无关 |
| 浏览器上传的 v1 实际入库 `storage_key` | `resources/322eeb1ef9ed1ca1764d8bb725f9c361.png`（原始文件名只存 `original_name`，不参与磁盘路径） |
| `Content-Disposition` | 含 `evil.png` 且不含 `..`，磁盘路径不拼接用户文件名 |
| 上传 21 MiB 文件 | 413 `FILE_TOO_LARGE` |
| 外链版本 | `kind=link`、`external_url` 为 https；下载该版本返回 422 |
| 外链为 `javascript:` / `file:` / `ftp:` | 422 `VALIDATION_ERROR` |

浏览器侧另证：两次上传后界面同时列出 v1 与 v2，v1 的字节数、显示名与备注未变（第 3.1 节）。

### T-005-02 学生读草稿和越权修改返回404/403；含script内容渲染不执行

覆盖用例：`test_T005_02_student_cannot_read_draft_or_write_content`、`test_T005_02_script_markdown_is_returned_as_plain_data`、`test_T005_02_unenrolled_student_cannot_read_course_content`、`test_T005_02_anonymous_is_unauthenticated`、`test_T005_02_version_conflict_on_stale_patch`，以及前端 `frontend/src/utils/__tests__/markdown.spec.js`（9 条）。

| 场景 | 观测 |
| --- | --- |
| 学生 `GET /knowledge-points/{草稿}` | 404 `NOT_FOUND` |
| 学生列表接口 | 只返回已发布知识点，草稿不出现 |
| 学生 `PATCH /knowledge-points/{已发布}` | 403 `FORBIDDEN` |
| 学生 `POST /chapters`、`POST /knowledge-points`、`POST /resources` | 均 403 |
| 教师乙读教师甲的草稿 | 404；改教师甲的章节/知识点 | 403；但可读教师甲的已发布知识点（200） |
| 未入班学生的 `GET /chapters`、`/knowledge-points`、`/resources` | 均 403 `FORBIDDEN` |
| 匿名 `GET /chapters`、`/knowledge-points` | 401 |
| Markdown 含 `<script>` 的正文 | 后端以 JSON 字符串原样返回，`Content-Type: application/json`，不生成 HTML |
| 前端渲染 `<script>window.__pwned=1</script>`、`<img src=x onerror=alert(1)>` | 转义为文本；DOM 中 script/img 元素 0 个、无 `on*` 属性；`window.__pwned === undefined` |
| 链接 `[x](javascript:…)` / `data:` / `file:` / 含空白 | 不生成 `<a>`，原样显示为文本 |
| 过期 `version` 的 PATCH | 409 `VERSION_CONFLICT` |

### T-005-03 重复收藏只一条，取消后可重新收藏；完成与取消标记一致

覆盖用例：`test_T005_03_repeat_favorite_creates_one_row_and_unfavorite_can_return`、`test_T005_03_progress_completion_toggles_consistently`。

| 观测 | 值 |
| --- | --- |
| 连续两次 `PUT /me/favorites/{id}` | 均 200、`{"favorited":true}`；`favorites` 表 1 行 |
| `DELETE /me/favorites/{id}` 两次 | 均 200、`{"favorited":false}`（取消未收藏的内容同样幂等） |
| 再次 `PUT` | 1 行，可重新收藏 |
| 收藏草稿知识点 | 404 |
| 教师调用学生专属的收藏/进度接口 | 403 |
| `PUT /me/learning-progress` `completed=true` 重复执行 | `completed_at` 不变（幂等） |
| `PUT` `completed=false` | `completed=false`、`completed_at=null`（取消完成清空时间，见 DBD 第 3 节约定） |
| 再次 `completed=true` | 重新写入 `completed_at`；`learning_progress` 表始终 1 行 |

浏览器侧另证：界面按钮在有/无为之间正确往返，提示文案与 `completed` 一致（第 3.2 节）。

### T-005-04 一天重复打开同资源版本只计一个open事件；次日可新增

覆盖用例：`test_T005_04_resource_events_dedup_by_utc_day`。

| 观测 | 值 |
| --- | --- |
| 同一天 `POST /resource-versions/{id}/events {"event_kind":"open"}` 四次 | 首次 `{"recorded":true}`，其后三次 `{"recorded":false}` |
| `resource_events` 计数（学生+版本+open+当日） | 1 |
| 同日 `download` 事件 | `{"recorded":true}`（与 open 独立计数） |
| 把 UTC 日推进到次日再 `open` | `{"recorded":true}`，总行数 +1 |
| 另一名学生同日 `open` | `{"recorded":true}`（按学生独立） |
| 非法 `event_kind` | 422 |
| 草稿资源下版本的 open | 404 |

浏览器侧另证：同一天点两次资源链接，第二次起不再出现「已记录本次访问」（第 3.2 节）。

### 其他边界

- 未知字段注入：`POST /chapters` 携带 `owner_id` → 422，`details.unknown_fields` 含 `owner_id`（owner 只从会话取得）。
- 参数校验：`page_size=0`、`chapter_id=abc` → 400；`chapter_id=9999`、`category=video2`、`source_url=javascript:…` → 422。
- 资源可见性：学生列表只含已发布资源，草稿资源的版本下载返回 404；所有者教师下载同一版本 200。
- 课程种子：第二次执行全部 `+0`；`knowledge_edges` 15 条经 `find_cycle` 判定无环；知识点正文含 `Q3Q2Q1Q0`、`0000`、`同步高有效`、`上升沿`。
- 种子归属：`seed-content --owner-login stu_a0001` 退出码非 0，提示「不是有效的教师/管理员」。
- 路由守卫：学生访问 `/teacher/content`、`/admin/users` 均回到首页。

## 5 未执行／待后续模块集成验证

- **知识图谱读取**：E066—E068 与 `GET /knowledge-graph*` 属 SPEC-016（#23），本轮只交付 `knowledge_edges` 的种子与无环校验，未实现读取投影，也未验证 T-016-*。
- **上传超限的浏览器验证**：21 MiB 超大上传只在自动化测试中验证（413），未在浏览器上传真实大文件。
- **NFR-04 尺寸验收**：1366×768 与 390px 视口未验证——本轮无法截图，也没有真实鼠标输入，页面尺寸与遮挡需在能截图的会话中复验。
- **断线恢复（NFR-05）**：上传与收藏在断网下的表现未验证。
- **`seed-demo` 完整教学样例**：两教师两班加课堂活动的样例数据仍属各业务模块，未提供；本轮只提供课程内容种子。
- **迁移降级的数据保全**：0003 的 downgrade 在一次性空库验证（表按预期移除/恢复）；未在有数据副本上验证降级后重新升级的数据保全。
- **部署形态**：未在 `npm run build` + waitress 同源部署下重跑本节流程，本轮为开发形态（Vite dev server + Flask 开发服务器）。
- 未提交/未开始 #6 及之后的模块；未合并 PR、未关闭 Issue。

## 6 契约与共享代码变更

- 未改变 APIC 的路径、字段或状态码；E011—E022 按已合并文档实现。资源版本响应不含 `storage_key` 与 `sha256`，与 APIC 第 2 节一致。
- 新增迁移 `0003_spec005`，`down_revision = 0002_spec001`。八个模块并行时迁移链会在同一父版本分叉，合并顺序需在集成时统一（见 PR 说明）。
- `app/config.py`：`testing` 配置新增 `default_upload_dir()`，并把 `UPLOAD_DIR` 从环境继承中剔除，使测试不写入仓库内 `instance/uploads`。开发与生产路径不变。
- `tests/backend/test_migrations.py`：原有回退用例改用显式 `0001_baseline` 而非 `-1`。新增迁移后按步数回退不再表达原意，属必要的测试更新，未放宽任何验收条件。
- `frontend/src/api/client.js`：新增 `delete` 与 `postForm`（multipart）两个方法；`send` 的既有行为未变。
- 以上均记录在 [CHG-RB](../../CHG-RB.md) 第 1 节。
