# SPEC-017 执行报告

日期：2026-10-02。对象：SPEC-017 时序逻辑识别辅助。提交：`65e3a0b`（分支 `feature/spec-017`，基线 `develop` `221afce`；报告随后续文档提交入库）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-017（E069/E070、recognition_tasks 与学生端识别页）。未实现或未执行的项在第 6 节逐条列出。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 新增后端依赖 | `opencv-python-headless==5.0.0.93`、`Pillow==12.3.0`（ADR-007 第 6 条要求 OpenCV/Pillow；服务端不需要 GUI 组件，故用体积更小的 headless 版） |
| 前端依赖 | 沿用既有锁定版本；本 Spec 未新增依赖 |

## 2 命令与结果

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend/test_spec017.py -q` | 0 | `20 passed` |
| 2 | `python -m pytest tests/backend -q` | 0 | `293 passed`（全量回归，整轮 1392.22 秒 ≈ 23 分 12 秒） |
| 3 | `npm run test:unit`（frontend） | 0 | 27 个测试文件、`170 passed`（SPEC-017 新增 11 条） |
| 4 | `npm run build`（frontend） | 0 | 构建成功，产物含 `StudentRecognitionView` 分块 |
| 5 | `git diff --check` | 0 | 无空白错误 |
| 6 | 文档一致性检查（项目外 `开发工作区/tools/check_docs.py`） | 0 | 未发现问题：接口 71 条、模块用例 72 条、相对链接 239 条有效 |

**迁移**：新增 `0011_spec017`（recognition_tasks），父 `0010_spec004`。合并后的升级链为 `…→0009_spec007→0010_spec004→0011_spec017`，已在新建库上实跑通过；`test_migration_round_trip` 只回退一步并断言前一个模块的 `warning_snapshots` 保留。

## 3 格式 v1 样例图片与人工核对表

样例图片：`docs/testing/样例-状态表格式v1-模6计数器.png`（27 589 字节，368×638 像素，白底黑线规则网格，4 列 × 7 行，每格一个印刷体数字）。它与测试输入由同一套绘制参数生成（`tests/backend/test_spec017.py` 的 `render_table()`：格边长 90px、网格线 3px、字号 2.2/线宽 5），因此可复现。

人工核对表（左四列是图片内容与人工推演，右两列是识别输出）：

| 拍 | 图片中的 Q3Q2Q1Q0 | 人工核对值 | 识别值 | 各格最高匹配度 | 一致 |
| --- | --- | --- | --- | --- | --- |
| 1 | 0000 | 0 | 0 | 0.89 | 是 |
| 2 | 0001 | 1 | 1 | 0.98（该位 1） | 是 |
| 3 | 0010 | 2 | 2 | 0.98 | 是 |
| 4 | 0011 | 3 | 3 | 0.98 | 是 |
| 5 | 0100 | 4 | 4 | 0.98 | 是 |
| 6 | 0101 | 5 | 5 | 0.98 | 是 |
| 7 | 0000 | 0 | 0 | 0.89 | 是 |

次态转换对（人工推演 = 识别结果，共 6 对）：`0000→0001`、`0001→0010`、`0010→0011`、`0011→0100`、`0100→0101`、`0101→0000`。整体置信度 `min` = **0.8933**，与逐格最小匹配度一致；`requires_review` 为 true。

界面上 0 的匹配度（约 0.89）略低于 1（约 0.98），因为 Hershey 字体的 “0” 笔画更细、归一化后与模板的像素重叠略少；两者与错误候选（约 0.37）差距很大，判定余量充足。

## 4 浏览器实际流程

以同源方式启动（`create_app()` 在 5062 端口同时提供 API 与已构建前端），用应用内浏览器驱动真实事件：表单填账号 → `requestSubmit()` 登录 → `history.pushState`/`popstate` 导航到 `/student/recognition` → 用 `DataTransfer` 把样例 PNG 塞进真实 file input 并派发 `change` → 点击「开始识别」。

| 观测 | 结果 |
| --- | --- |
| 登录（stu_0001） | `GET /api/v1/me` 200 |
| 导航高亮 | `a.nav-item--active` 文本为「状态表识别」 |
| 格式说明 | 页面显示「格式 v1……恰好 4 列、2—17 行」 |
| 上传样例（27 589 字节） | `识别完成 · 置信度 89.3% · 7 行 × 4 列` |
| 状态序列 | 0000 / 0001 / 0010 / 0011 / 0100 / 0101 / 0000，值 0—5、0 |
| 次态转换 | 六对与人工核对表一致 |
| 标注 | 页面显示「需人工核对」与「不采用识别结论或客户端字段」 |
| 失败路径（空白 PNG） | `识别失败 · 未检测到网格`，不显示状态表也不显示置信度 |
| 错误提示 | 无（`.error` 不存在） |

落库核对（直接查 SQLite）：`recognition_tasks` 两行——`done` 行有 `result_json`、`error_json` 为空；`failed` 行 `result_json` 为空、有 `error_json`，符合「失败任务不保留有效 result」。两张图片都以随机名落在 `UPLOAD_DIR/recognition/`（`00b4c02e….png`、`c12bd0d1….png`），文件名不含原始名。

方法学限制：应用内浏览器面板常为 0×0 或最小化，基于坐标的点击与截图不可靠，且**原生文件选择框无法驱动**；上述流程改用页面自身的处理函数与 `DataTransfer` 构造 File 驱动，与用户操作走同一条代码路径与同一组 HTTP 请求。**本轮没有可提供的截图**，不作已截图的记录。

## 5 逐条验收

### T-017-01 模 6 计数器 7 行状态表识别出 6 个次态对，位序 Q3Q2Q1Q0 一致

用例 `test_T017_01_recognizes_mod6_state_table`：识别值 `[0,1,2,3,4,5,0]`、行号 0—6、6 个次态对、`confidence` 在 (0,1]、`requires_review=true`、`error` 为空。
用例 `test_T017_01_bit_order_is_q3q2q1q0`：`1000` 读成 8、`0001` 读成 1，证明最左列是高位。
用例 `test_T017_01_two_row_minimum_is_accepted`：2 行（下界）可用。
第 3 节的样例图片与人工核对表给出同一结论。

### T-017-02 非表格/手写/格内非 0/1 → failed 且给出格式原因

| 场景 | 用例 | 观测 |
| --- | --- | --- |
| 空白图片 | `test_T017_02_non_table_image_fails_with_reason` | `failed`、`GRID_NOT_DETECTED`「未检测到网格」、`result=null` |
| 3 列表格 | `test_T017_02_wrong_column_count_fails` | `SHAPE_MISMATCH`，details 给出实际列数 |
| 格内画 “7” | `test_T017_02_out_of_alphabet_cell_fails` | `CELL_NOT_BINARY`／`CELL_UNCERTAIN`，details 给出具体行列 |
| 手写笔画 | `test_T017_02_handwritten_marks_fail` | 同上，不返回猜测状态 |
| 18 行 | `test_T017_02_too_many_rows_fails` | `SHAPE_MISMATCH`，details 给出实际行数 |

### T-017-03 GIF/超限与「不影响判分」

| 场景 | 用例 | 观测 |
| --- | --- | --- |
| `.gif` 扩展名 | `test_T017_03_gif_is_rejected` | 415 `FILE_TYPE_UNSUPPORTED` |
| 21 MiB | `test_T017_03_oversized_file_is_rejected` | 413 `FILE_TOO_LARGE`，且不产生任务记录 |
| 带 `passed`/`score` | `test_T017_03_client_grading_fields_are_ignored` | 201 正常识别；响应与 `result_json` 都不含这两个字段 |
| 与实验判分的关系 | `test_T017_03_recognition_does_not_touch_experiment_grading` | 识别前后 `experiment_attempts` 行数不变、已有尝试的 `passed` 不变 |

### T-017-04 班级归属、读取权限与人工核对标注

| 场景 | 用例 | 观测 |
| --- | --- | --- |
| 学生 | `test_T017_04_student_can_only_use_own_active_class` | 选他人班级 404；未入班学生选任意班级 404 |
| 教师 | `test_T017_04_teacher_can_only_use_own_class` | 选他人班级 404，选本人班级 201 |
| 读取 | `test_T017_04_read_permissions_and_review_note` | 创建者 200；本班教师 200；其他学生 404；其他班教师 404；不存在的 id 404 |
| 换教师 | `test_T017_04_teacher_change_moves_read_access` | 任务按保存的 class_id 判权：改派后新教师 200、旧教师 404 |
| 角色 | `test_T017_04_anonymous_and_admin` | 匿名 401；管理员 403（需教学账号） |
| 标注 | 同上 | `requires_review=true`、`confidence` 非空 |

### 其他边界

- `test_timeout_returns_503_and_keeps_nothing`：把 `RECOGNITION_TIMEOUT_SECONDS` 设为 0 → 503 `RECOGNITION_TIMEOUT`，`recognition_tasks` 无记录，`UPLOAD_DIR/recognition/` 不留文件。
- `test_validation_boundaries`：`kind` 非 state_table 422；无扩展名／内容不是图片 415；空文件 415/422；缺 `class_id` 422；缺 CSRF 403。
- `test_migration_round_trip`：upgrade → downgrade 一步 → upgrade，只回收本模块的表。

## 6 未执行／未完成项

- 未在生产 WSGI 同源之外的形态（局域网、HTTPS）重跑；未做课堂并发或延迟测试（属 NFR-02/03，留待集成）。
- **不识别任意手绘电路、卡诺图化简或照片透视**——SPEC-017 第 1 节列为非目标；只支持格式 v1 的白底黑线规则网格。
- 分辨率鲁棒性未做系统评测：格式 v1 要求格边长 ≥40 像素，跨分辨率只保证同一图片与同一参数可复现，不承诺绝对一致（SPEC-017 第 4 节第 4 条）。
- 未接任何外部服务，也未使用深度学习模型；识别结果不参与实验判分（只由 SPEC-013 后端重算）。
- 未合并 PR、未关闭 Issue、未开始下一个模块。

## 7 契约与共享文件变更

- **APIC 第 1 节**：503 增加 `RECOGNITION_TIMEOUT`。
- **APIC 第 7 节**：补 E069/E070 细节（multipart 字段名 `image`/`class_id`/`kind`、413/415、限时配置与 503、五个失败错误码、`states`/`transitions`/`confidence` 形状、读取权限口径）；并**显式写明 E069 忽略多余 multipart 字段**。
- **SPEC-017 第 4 节**新增第 8、9 条，写明「多余字段被忽略」与错误码/结果形状；状态改为已实现，验收用例状态改为已执行。
- **共享文件**：`app/__init__.py`（注册 blueprint）、`app/config.py`（新增配置项 `RECOGNITION_TIMEOUT_SECONDS`，默认 5 秒）、`app/errors.py`（新增错误码）、`backend/requirements.txt`（两个新依赖）、`frontend/src/router/index.js` 与 `frontend/src/navigation/index.js`（各新增一条学生入口）、`navigation.spec.js`（补路由与高亮断言）、`README.md`、`CHG-RB.md`、覆盖矩阵第 6 节的样例待办。
- 其中 `app/config.py` 与 `app/errors.py` 是 SPEC-000 所属文件，本次为**纯增量**改动（新增一个带默认值的配置项与一个错误码），未改变既有行为。
- 以上均记录在 [CHG-RB](../../CHG-RB.md) 第 1 节。
