# SPEC-004 执行报告

日期：2026-10-02。对象：SPEC-004 学习预警与分组。提交：`29b1ed2`（分支 `feature/spec-004`，基线 `develop` `5c5eae7`；报告随后续文档提交入库）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-004（E063/E064、warning_snapshots 与教师端预警页）。未实现或未执行的项在第 5 节逐条列出。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端依赖 | 沿用既有锁定版本；scikit-learn 1.9.1 由并行的 SPEC-007 先引入（ADR-007 第 1 条 TF-IDF），本模块复用其 KMeans（ADR-007 第 3 条），**未再新增依赖** |
| 前端依赖 | 沿用既有锁定版本；本 Spec 未新增依赖 |

## 2 命令与结果

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/backend/test_spec004.py -q` | 0 | `18 passed` |
| 2 | `python -m pytest tests/backend -q` | 0 | `273 passed`（全量回归，整轮 1114.20 秒 ≈ 18 分 34 秒） |
| 3 | `npm run test:unit`（frontend） | 0 | 25 个测试文件、`160 passed`（SPEC-004 新增 12 条；含并行合入的 SPEC-007 用例） |
| 4 | `npm run build`（frontend） | 0 | 构建成功，产物含 `TeacherWarningsView` 分块 |
| 5 | `git diff --check` | 0 | 无空白错误 |
| 6 | 文档一致性检查（项目外 `开发工作区/tools/check_docs.py`） | 0 | 未发现问题：接口 71 条、模块用例 72 条、相对链接 233 条有效 |

**迁移**：新增 `0010_spec004`（warning_snapshots）。开工时 `develop` 为 `47630e4`，实现完成后远端前移到 `5c5eae7`（并行合入 SPEC-007）；SPEC-007 的迁移同样以 `0008_spec008` 为父并占用 `0009` 号，因此本模块已同步最新 develop 并把迁移改接为 `0010_spec004`（父 `0009_spec007`），避免同父双 head。合并后的实际升级链为 `0008_spec008 → 0009_spec007 → 0010_spec004`，已在新建库上实跑通过。

**关于整轮耗时**：与上一轮相同量级的既有成本（scrypt 口令散列约 0.34 秒/次 + 每个用例跑完整迁移链），不是本模块引入的；本轮迁移链又多一步，成本略增。

## 3 浏览器实际流程

以同源方式启动（`create_app()` 在 5059 端口同时提供 API 与已构建前端），用应用内浏览器驱动**真实 DOM 事件**：在 `/login` 用真实 `input`/`change` 事件填入教师账号后 `requestSubmit()`，再以 `history.pushState` + `popstate` 做 SPA 导航到 `/teacher/warnings`，点击「生成快照」，最后断言页面与接口。

固定种子：1 个班、10 名在册学生，三组不同的风险向量（低/中/高三组）。

| 观测 | 结果 |
| --- | --- |
| 登录（teacher_aaa） | `GET /api/v1/me` 200 |
| 导航高亮 | `a.nav-item--active` 文本为「学习预警」 |
| 生成前 | 显示「该窗口还没有预警批次」，不假造数据 |
| 生成后名单 | 10 行：等级 低×4 / 中×3 / 高×3；分数 0.0 / 50.0 / 100.0 |
| 分组 | 组 0 / 组 1 / 组 2 各对应低/中/高一组 |
| 证据列 | 每行给出「出勤：风险 0.00（出勤表现 1.00），权重 0.3」式的逐项说明 |
| 口径说明 | 页面显示「不是经训练校准的学业风险概率」与 KMeans 分组说明 |
| E064 同窗口 | `total=10`，等级集合 low/medium/high，与生成结果一致 |
| E064 其他窗口 | `data` 为 `[]`（窗口隔离，不返回别批快照） |
| 页面「刷新」 | 重新读到同一批次的 10 行，等级不变 |
| 错误提示 | 无（`.error` 不存在） |

方法学限制：应用内浏览器面板常为 0×0 或最小化，基于坐标的点击与截图不可靠。上述流程改用页面自身的处理函数（真实输入事件 + `submit`/`click` + 路由事件）驱动，与用户操作走同一条代码路径与同一组 HTTP 请求；**本轮没有可提供的截图**，不作已截图的记录。

## 4 逐条验收

### T-004-01 a=.5、p=.25、e=1 → score 70 且 high

单元测试 `test_T004_01_score_matches_the_spec_example` 固定公式：`build_factors(attendance_rate=0.5, completion_rate=0.75, first_accuracy=0.0)` → `{attendance:0.5, progress:0.25, accuracy:1.0}`；逐项贡献 15 + 5 + 50 = 70.0，等级 high。`test_T004_01_level_thresholds` 覆盖 7.5/30.0/58.75/60.0/100.0 五个点，验证 `<30 low、<60 medium、否则 high`。

整条管线的接口测试 `test_T004_01_pipeline_scores_and_levels` 用固定种子（2 条已结算考勤任务 → 出勤率 .5；4 个已发布知识点完成 3 个 → 完成率 .75；3 次首答全错 → 正确率 0）得到同样的 `score=70.0`、`level=high`、`available_factors` 三项齐全、`sample_counts={attendance:2, progress:4, accuracy:3}`，并核对 `evidence_json` 里保存的正是这组数字。

### T-004-02 只有一类记录 insufficient；缺答题时重归一化

| 场景 | 用例 | 观测 |
| --- | --- | --- |
| 只有出勤记录 | `test_T004_02_only_one_usable_factor_is_insufficient` | `level=insufficient`、`score=null`、`available_factors=["attendance"]`，原因列表含「少于 2 项」 |
| 纯计算单因素 | `test_T004_02_single_factor_is_insufficient` | 同上 |
| 无答题、其余两因素可用 | `test_T004_02_missing_accuracy_is_renormalized_not_zero` | `100×(0.3×0.5+0.2×0.25)/0.5 = 40.0`，并显式断言 **≠ 20.0**（若把缺失当 0 分才会得到 20） |
| 首答 2 次（<3） | `test_T004_02_insufficient_when_accuracy_below_threshold` | 该因素不可用、`sample_counts.accuracy=2`、其余两项归一化后 `score=50.0`、原因含「首答样本 2 次」 |

### T-004-03 9 名不聚类；≥10 名且 3 类向量时调用 KMeans 并稳定分组

| 场景 | 用例 | 观测 |
| --- | --- | --- |
| 9 名三因素齐全 | `test_T004_03_nine_complete_students_are_not_clustered` | `cluster_label` 全部为 null，原因说明「只有 9 名，少于 10 名」 |
| 10 名、3 类向量（4/3/3） | `test_T004_03_ten_students_with_three_vectors_are_clustered_and_stable` | 三个簇齐全；风险最低的一组得标签 0、中间得 1、最高得 2；重复调用结果完全一致（`random_state=42, n_init=10`） |
| 12 名但只有 2 类向量 | `test_T004_03_two_distinct_vectors_are_not_clustered` | 不分组，原因说明向量种类不足 |
| 整条管线 | `test_T004_03_pipeline_clusters_ten_complete_students` | 10 名学生生成后 `cluster_reason=null`、标签集合 {0,1,2}，库中 10 行的 `cluster_label` 均非空；规则等级不被聚类覆盖 |

浏览器实测中三组学生的标签与风险等级一一对应（组 0 ↔ 低、组 2 ↔ 高）。

### T-004-04 只可生成本班快照；批次保留且查询最新完整批次

| 场景 | 用例 | 观测 |
| --- | --- | --- |
| 跨班 | `test_T004_04_only_own_class_and_roles` | 教师乙对班甲 E063/E064 均 404；学生 403；匿名 401；本人班级 200 |
| 写操作 CSRF | `test_T004_04_write_requires_csrf` | 缺 `X-CSRF-Token` → 403 `CSRF_FAILED` |
| 无批次 | `test_T004_04_no_batch_returns_empty_list` | `data: []`、`total: 0`，不自动生成 |
| 重复生成 | `test_T004_04_repeated_generations_keep_distinct_batches_and_return_latest` | 两次生成写入 batch_no 1 与 2；E064 只返回 1 行且取自第二个批次（第二次前删掉进度记录，因此可用因素变为 attendance+accuracy，与首批不同） |
| 窗口隔离 | `test_T004_04_different_windows_are_isolated` | 换窗口查询不返回其他窗口的批次 |
| 参数边界 | `test_invalid_parameters_are_rejected` | 只给 from、from≥to、>366 天、非 RFC3339 时间（422）、未知字段（422）、缺 class_id（400）均按预期拒绝 |
| 迁移往返 | `test_migration_round_trip` | upgrade → downgrade 一步（回 `0009_spec007`）→ upgrade：本模块表与索引随迁移回收重建，且前一个模块的 `qa_entries` 保留 |

## 5 未执行／未完成项

- 未在生产 WSGI 同源之外的形态（局域网、HTTPS）重跑；未做课堂并发或延迟测试（属 NFR-02/03，留待集成）。
- 预警不产出因果结论、挂科概率或纪律处罚——SPEC-004 第 1 节把这些列为非目标；等级只是项目规则档位。
- 名单取「当前有效在册学生」，退班学生不进入新快照；历史批次仍按生成时的名单规模判定完整性。
- KMeans 只用于班级分组描述，未做参数调优或聚类质量评估（SPEC-004 未要求，也不宜据此判断教学效果）。
- 未合并 PR、未关闭 Issue、未开始下一个模块。

## 6 契约与共享文件变更

- **APIC 第 7 节**：`Warning` 的 `available_factors` 定为可用因素**名称数组**、`sample_counts` 定为逐因素样本量对象；新增一段 E063/E064 口径补充，固定权重与归一化规则、三项可用门槛、level 是项目规则档位而非校准概率、批次号与名单规模的存法、E064 的返回形状与分页。
- **SPEC-004 第 4 节**新增第 6、7 条，写明同样的口径与「三因素复用既有统计口径」。
- **迁移改号**：`0009_spec004` → `0010_spec004`，父改为 `0009_spec007`；原因是并行合入的 SPEC-007 已用 `0009` 且同为 `0008_spec008` 的子节点，不改号会形成双 head。已实跑升级验证。
- **依赖**：scikit-learn 由 SPEC-007 先引入，本模块只在 `requirements.txt` 注释里补记 SPEC-004 的用途，版本行未变。
- **复用而不重造**：出勤复用 SPEC-003 的 `summarize_attendance` 与 `_settle_task` 幂等结算；进度复用 SPEC-006 的 `summarize_progress`；首答正确率沿用 SPEC-010「全历史最早已提交作答、再按 submitted_at 落窗」的规则并按学生分组（SPEC-010 的私有函数会丢掉 `student_id`，因此本模块保留它）。未修改 `api_attendance.py`／`api_learning.py`／`api_assessment.py`。
- **前端共享文件**：`router/index.js` 与 `navigation/index.js` 各新增一条教师「学习预警」入口（并入 SPEC-007 改名的「课程问答」条目之后）；`navigation.spec.js` 补该路由与高亮断言；rebase 时与 SPEC-007 的同文件改动已合并。
- 以上均记录在 [CHG-RB](../../CHG-RB.md) 第 1 节。
