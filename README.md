# 学海通数字逻辑课程学习系统

本项目面向时序逻辑课堂，支持教师备课、逐拍演示、随堂测与讲评，并为学生提供练习、实验和课后复习。

当前版本为设计基线 1.0。工程骨架（SPEC-000）、账号角色与班级权限（SPEC-001）、考勤与请假（SPEC-002）、出勤与风险因素统计（SPEC-003，教师端）、学习预警与分组（SPEC-004，教师端）、课程知识与教学资源（SPEC-005）、学习进度与资源统计（SPEC-006，教师端）、课程检索问答（SPEC-007）、备课与预习发布（SPEC-008）、题库练习与错题（SPEC-009）、随堂测与测评统计（SPEC-010）、约束智能组卷（SPEC-011，教师端）、课堂演示与时序仿真（SPEC-012）、实验辅助与结果验证（SPEC-013，学生端）、实验学习统计（SPEC-014，教师端）、个性化复习推荐（SPEC-015，学生端）、时序逻辑知识图谱与可视化（SPEC-016，学生端与教师端）以及时序逻辑识别辅助（SPEC-017，学生端）已实现并实测通过；18 个模块全部实现，模块级结果见各执行报告，系统集成验收（E2E、权限、部署、负载、备份恢复）见 [D7 集成验收报告](docs/testing/D7-集成验收报告.md)，未执行的项在该报告第 12 节逐条列出。

实验箱逐引脚连线与过程模拟、Logisim电路在线测评（SPEC-018/019、FR-20/21）已实现并通过本机验收，见[实验扩展验收报告](docs/testing/实验扩展验收报告.md)。四个实验支持真实接线、服务器仿真、上传后由Logisim-evolution 5.0.0多拍判分及教师查看。运行方法见[实验箱与电路测评使用说明](docs/实验箱与电路测评使用说明.md)；新增PR仍待独立评审。

## 文档入口

- [实验箱接线与电路测评方案（新增必做，已实现）](docs/design/实验箱接线与电路测评方案.md)
- [实验扩展调研与Logisim运行探测](docs/research/实验箱与Logisim测评调研.md)
- [需求调研](docs/research/同类项目与需求调研.md)
- [产品需求 PRD](PRD.md)
- [接口契约 APIC](APIC.md)
- [数据库设计 DBD](DBD.md)
- [架构决策 ADR](ADR.md)
- [变更及回滚 CHG-RB](CHG-RB.md)
- [组员分工表](docs/组员分工表.md)
- [页面与课堂流程](docs/design/页面与课堂流程.md)
- [UI 设计基线](docs/design/UI设计基线.md)
- [实施计划](docs/design/实施计划.md)
- [Spec 索引](docs/specs/README.md)
- [测试计划与追溯](docs/testing/需求追溯与测试计划.md)
- [任务书功能覆盖矩阵](docs/testing/任务书功能覆盖矩阵.md)
- [设计检查记录](docs/checkpoints/checkpoint-1.md)
- [SPEC-000 执行报告](docs/testing/SPEC-000-执行报告.md)
- [SPEC-001 执行报告](docs/testing/SPEC-001-执行报告.md)
- [UI 基线检查记录](docs/testing/UI基线检查记录.md)
- [SPEC-002 执行报告](docs/testing/SPEC-002-执行报告.md)
- [SPEC-003 执行报告](docs/testing/SPEC-003-执行报告.md)
- [SPEC-004 执行报告](docs/testing/SPEC-004-执行报告.md)
- [SPEC-011 执行报告](docs/testing/SPEC-011-执行报告.md)
- [SPEC-005 执行报告](docs/testing/SPEC-005-执行报告.md)
- [SPEC-006 执行报告](docs/testing/SPEC-006-执行报告.md)
- [SPEC-007 执行报告](docs/testing/SPEC-007-执行报告.md)
- [SPEC-008 执行报告](docs/testing/SPEC-008-执行报告.md)
- [SPEC-009 执行报告](docs/testing/SPEC-009-执行报告.md)
- [SPEC-010 执行报告](docs/testing/SPEC-010-执行报告.md)
- [SPEC-012 执行报告](docs/testing/SPEC-012-执行报告.md)
- [SPEC-013 执行报告](docs/testing/SPEC-013-执行报告.md)
- [SPEC-014 执行报告](docs/testing/SPEC-014-执行报告.md)
- [SPEC-015 执行报告](docs/testing/SPEC-015-执行报告.md)
- [SPEC-016 执行报告](docs/testing/SPEC-016-执行报告.md)
- [SPEC-017 执行报告](docs/testing/SPEC-017-执行报告.md)
- [D7 集成验收报告](docs/testing/D7-集成验收报告.md)（E2E／权限／部署／负载／备份恢复，含未完成项）

## 技术和目录约定

前端 Vue 3、Vite、Vue Router、Pinia、Element Plus、ECharts；后端 Flask、SQLAlchemy、Alembic；数据库统一 SQLite；统计与算法 NumPy、Pandas、scikit-learn、SciPy，识别辅助使用 OpenCV/Pillow，知识图谱用标准库与 NumPy 在 knowledge_edges 上遍历。不得引入 PyTorch、TensorFlow 或大模型权重。依赖精确版本在工程阶段完成兼容性检查后锁定。

```text
frontend/                 前端工程（SPEC-000 已建立骨架）
backend/app/              后端工程（SPEC-000 已建立骨架）
backend/migrations/       数据库迁移（SPEC-000 已建立，业务表由各模块追加，当前 head 0012_spec018）
tests/backend/            接口和领域测试（SPEC-000 已建立，358 条已收集用例，真实Java项需显式运行开关）
tests/e2e/                系统集成验收脚本（D7，对真实运行的服务发 HTTP）
tests/perf/               课堂负载脚本（D7，模拟数据）
frontend/src/**/__tests__/ 前端组件与仿真逻辑测试（205 条用例）
scripts/                  备份与恢复脚本（D7，OPS-02）
docs/                     设计、规格、测试与检查材料
```

## 环境和配置约定

首版使用可支持所选锁定依赖的 Python 与 Node LTS。已实测并记录：Windows 11（10.0.26200）、Python 3.14.7、Node v24.18.0、npm 11.16.0。运行数据存放在项目外或未跟踪的 `instance/`。文件测评还使用`LAB_JAVA`和`LAB_JAR`两个绝对路径配置，独立worker需与Web使用同一数据库和上传目录。配置项：`DATABASE_URL`、`UPLOAD_DIR`、`SECRET_KEY`、`APP_ENV`、`COOKIE_SECURE`、`RECOGNITION_TIMEOUT_SECONDS`（SPEC-017 的单张图片识别限时，默认 5 秒，超时返回 503 且不保留任务；在 `.env` 中留空即沿用默认值）；配置模板 `backend/.env.example` 不含真实密码。开发默认 localhost，局域网部署才设置监听地址。

SQLite 文件路径必须解析成绝对路径，启用外键、5 秒 busy_timeout；数据库迁移版本由 Alembic 管理。不提交数据库、上传文件、密钥、node_modules、虚拟环境或缓存。

`testing` 模式默认使用系统临时目录中的数据库，不继承环境变量 `DATABASE_URL`；测试夹具需要独立数据库时，通过 `create_app("testing", {"DATABASE_URL": ...})` 显式指定。

## 运行步骤

以下步骤已在仓库外的新目录实测，命令、退出码与结果见 [SPEC-000 执行报告](docs/testing/SPEC-000-执行报告.md)。

1. 创建 Python 虚拟环境并安装 `backend/requirements.txt`；前端使用 `npm ci` 安装锁文件对应依赖。
2. 配置环境变量（模板见 `backend/.env.example`），执行 `python -m flask --app app:create_app db upgrade`（工作目录 backend）。
3. 开发时后端监听 localhost:5000，前端 `npm run dev` 使用 Vite 代理 `/api`；测试命令为根目录 `python -m pytest tests/backend`、前端 `npm run test:unit` 和 `npm run build`（pytest 路径已在 `pytest.ini` 配置）。
4. 部署时先 `npm run build`，再以 `waitress-serve --listen=0.0.0.0:5000 wsgi:app`（工作目录 backend）启动，后端同源提供 `frontend/dist`；不使用 Flask 开发服务器承担实际课堂访问。`APP_ENV=production` 时必须提供 `DATABASE_URL` 与 `SECRET_KEY`。
5. 管理员初始化（SPEC-001，已提供）：迁移后在工作目录 backend 执行 `python -m flask --app app:create_app init-admin --login-name <登录名> --password <口令>`。公开注册只允许学生，首个管理员的登录名一经占用即拒绝重建。课程内容种子（SPEC-005，已提供）：`python -m flask --app app:create_app seed-content --owner-login <教师登录名>`，写入六单元 12 知识点、先修关系与一份外链资料，可重复执行且不会重置已有内容。预置实验（SPEC-012，已提供）：`python -m flask --app app:create_app seed-experiments --owner-login <教师登录名>`，写入 D、JK、模 6 计数器与 4 位移位寄存器四个实验定义，需先有课程知识点。问答语料（SPEC-007，已提供）：`python -m flask --app app:create_app seed-qa --owner-login <教师登录名>`，写入 16 条已发布问答条目，需先有课程知识点。实验箱任务种子：`python -m flask --app app:create_app seed-labs`，写入四个公开任务、端口模板和服务器测试集，需先有已发布知识点，重复执行不改历史或版本。文件测评另启`python -m flask --app app:create_app lab-worker`；Java/JAR部署与两进程运行见使用说明。面向课堂的完整样例命令 `seed-demo` 尚未提供。

## 测试和部署验收

以[测试计划](docs/testing/需求追溯与测试计划.md)验证两班权限、答题截止、统计分母、状态仿真和新环境启动。SQLite 写操作用短事务，课堂并发以实测确定：D7 用 60 个模拟客户端 3 秒轮询 10 分钟测得普通接口 p95 最差 423 ms、统计 37 ms、组卷 25 ms，0 错误、0 数据错写（[D7 集成验收报告](docs/testing/D7-集成验收报告.md) 第 7 节，数据为模拟）。安装依赖需要网络；安装完成后核心内容、仿真和题库应不依赖外部服务。

普通 HTTP 局域网仅用于受控演示；需要真实账号数据的部署应配置 HTTPS 与 Secure Cookie（`APP_ENV=production` 默认 `COOKIE_SECURE=1`，此时必须 HTTPS 才能完成登录）。首次实际课堂使用前完成备份恢复演练：`python scripts/backup.py --backend backend` 与 `python scripts/restore.py --backup <备份目录> --backend backend`（备份用 SQLite backup API，不复制写入中的主文件）。详细回滚步骤见 [CHG-RB](CHG-RB.md)，已执行的演练结果见 [D7 集成验收报告](docs/testing/D7-集成验收报告.md) 第 9 节。

## 版本管理与提交

开发仓库：[web-homework](https://github.com/jzcool666/web-homework)。课程交付时同步 Gitea；地址由项目组补充。采用 main、develop、feature/spec-* 和 hotfix/*，提交及测试关联 Spec 编号。源代码推送不会自动复制平台上的 PR 和 Issue，需要的检查材料应存入 docs。

班级、组号及最终报告模板待补。组长提交成员名单、大作业报告、源码及设计文件；组员设计报告按 `学号_姓名_设计报告.docx` 命名。技术验收（模块与系统集成）已完成，结果见 [D7 集成验收报告](docs/testing/D7-集成验收报告.md)；课程报告、班级组号、Gitea 迁移与独立用户手册仍未完成，该报告第 12 节如实列出。
