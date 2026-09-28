# SPEC-000 执行报告

日期：2026-09-28。对象：SPEC-000 公共工程与运行约定。提交：`e5f29e6`（分支 `feature/spec-000`）。
性质：本报告记录实际执行过的命令与结果，只覆盖 SPEC-000 的工程骨架，不代表整套系统已验收。

## 1 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.14.7 |
| Node / npm | v24.18.0 / 11.16.0 |
| 后端锁定依赖 | Flask 3.1.3、SQLAlchemy 2.1.1、alembic 1.20.0、waitress 3.0.2、python-dotenv 1.1.1、pytest 9.1.1 |
| 前端锁定依赖 | vue 3.5.43、vue-router 5.3.1、pinia 4.0.3、vite 8.3.1、@vitejs/plugin-vue 6.0.9、vitest 5.0.2、@vue/test-utils 2.5.1、jsdom 30.1.1 |

算法与统计库（NumPy/Pandas/scikit-learn/SciPy）与 Element Plus、ECharts 本阶段不引入，随对应模块追加。

## 2 新目录验证（T-000-04 主证据）

把已推送分支克隆到仓库外的新目录 `开发工作区/verify/spec-000`（`git clone --branch feature/spec-000`，HEAD `e5f29e6`），按 README 步骤执行：

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `python -m venv .venv` | 0 | 新虚拟环境 |
| 2 | `.venv/Scripts/python -m pip install -r backend/requirements.txt` | 0 | 19 个包安装成功，锁定版本与上表一致 |
| 3 | `cd backend && python -m flask --app app:create_app db upgrade` | 0 | `Running upgrade -> 0001_baseline` |
| 4 | `python -m pytest tests/backend`（仓库根） | 0 | 10 passed |
| 5 | `cd frontend && npm ci` | 0 | 按锁文件安装，0 vulnerabilities |
| 6 | `npm run test:unit` | 0 | 2 个测试文件、6 passed |
| 7 | `npm run build` | 0 | 28 modules transformed，产出 `dist/` |

生产启动与同源验证（新目录，`waitress-serve --listen=127.0.0.1:5002 wsgi:app`）：

| 请求 | 结果 |
| --- | --- |
| `GET /api/v1/health` | 200，`{"data":{"status":"ok","version":"0.1.0"},"meta":{"server_time":"..."}}` |
| `GET /` | 200，`text/html`（后端同源提供 `frontend/dist/index.html`） |
| `GET /assets/index-*.js` | 200 |
| `GET /teacher/classroom`（SPA 深链接） | 200，回落到 `index.html` |

浏览器实际流程：用应用内浏览器打开该服务，页面标题与正文渲染正常，健康区显示“服务正常（版本 0.1.0）”，浏览器控制台无日志输出。该结果同时验证了部署同源与前后端连通。

## 3 逐条验收

### T-000-01 新库 upgrade 后外键开启；再次 upgrade 不改变数据

命令：对不存在的 `t000-01.sqlite` 执行 `flask db upgrade`（等价路径见第 2 节第 3 步）。结果：

| 观测 | 值 |
| --- | --- |
| upgrade 前数据库文件存在 | 否 |
| upgrade 后 `PRAGMA foreign_keys` | 1 |
| upgrade 后 `PRAGMA busy_timeout` | 5000 |
| `alembic_version` | `0001_baseline` |
| 再次 upgrade 后 `alembic_version` | `0001_baseline`（与首次相同） |

结论：新空库 upgrade 后外键开启，第二次 upgrade 未改变数据。同时覆盖 `tests/backend/test_migrations.py` 的 3 条用例（含“启动不建表、不清表”）。

### T-000-02 testing 模式写入后正式库哈希与内容不变

覆盖用例：`tests/backend/test_isolation.py::test_testing_writes_leave_the_other_database_untouched`。步骤：先对一个“正式”库执行迁移并记录 SHA-256 与全表内容；再用 testing 配置对另一个临时库迁移并写入记录；最后比对正式库。

观测：正式库 SHA-256 与全表快照前后完全一致，且夹具表 `test_probe` 未出现在正式库中。
说明：SPEC-000 不创建业务表，写入使用测试自带的**最小隔离夹具表**，不进入应用 schema。

### T-000-03 /health 正常 200 且无密钥；数据库断开 503 及可读原因

| 场景 | 结果 |
| --- | --- |
| 正常 | 200，`data` 为 `{status:"ok",version:"0.1.0"}`，`meta.server_time` 为 RFC3339 UTC |
| 数据库不可用（URL 指向一个目录） | 503，`error.code = DB_BUSY`，`error.details.reason = "OperationalError: (sqlite3.OperationalError) unable to open database file"` |

泄漏检查：两种响应的原始文本均不含 `SECRET_KEY`、密钥默认值、`DATABASE_URL`、`sqlite:///`、数据库文件路径或 `instance`。另覆盖匿名可达与未知路径的 404 错误封装。

### T-000-04 工程初始化、迁移、构建与测试

见第 2 节，第 1—7 步退出码均为 0。本用例不验收管理员初始化与完整业务种子，二者分别归 SPEC-001 与各业务模块。

## 4 未执行／未完成项

- 未执行 `init-admin`、`seed-demo` 及任何账号业务：属 SPEC-001 与各业务模块。
- 未创建业务表：DBD 定义的表由各模块迁移追加（SPEC-000 第 3 节）。
- `tests/frontend/`、`tests/e2e/`、`scripts/` 仍为空目录状态：前端仿真逻辑测试属 SPEC-012/013（Vitest 无法从 `frontend/` 包外解析裸包依赖，届时需先确定回归测试的解析方式），端到端与备份脚本属后续 Spec。
- 前端依赖 Element Plus 与 ECharts 未安装；算法库未安装。
- 未在局域网、HTTPS 或真实课堂负载下运行；NFR-02/03 的负载与延迟目标未测。
- 备份恢复演练未执行（见 CHG-RB 第 6 节）。

以上未执行项不得记为通过。

## 5 PR 独立评审复测

评审发现：原实现的 testing 配置会继承环境变量 `DATABASE_URL`，当开发机已有正式库地址时可能误连正式库。已修改为 testing 模式忽略该环境变量；测试需要指定数据库时仍可通过 `create_app("testing", {"DATABASE_URL": ...})` 显式覆盖。

修正后在 PR 工作树执行 `python -m pytest tests/backend -q`：11 passed；新增用例验证环境中已有数据库地址时 testing 仍指向系统临时目录，正式地址对应的文件未创建。前端未因该修正改变，独立评审中 `npm run test:unit` 为 6 passed，`npm run build` 成功；`git diff --check` 通过。原第 2 节的新目录证据采于 `e5f29e6`，与本节的评审复测区分记录。
