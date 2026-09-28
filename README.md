# 学海通数字逻辑课程学习系统

本项目面向时序逻辑课堂，支持教师备课、逐拍演示、随堂测与讲评，并为学生提供练习、实验和课后复习。

当前版本为设计基线 1.0，仅包含设计文档，尚无可运行应用。以下环境、命令和部署方式是实现约定，不能作为已经启动或测试通过的证据。

## 文档入口

- [需求调研](docs/research/同类项目与需求调研.md)
- [产品需求 PRD](PRD.md)
- [接口契约 APIC](APIC.md)
- [数据库设计 DBD](DBD.md)
- [架构决策 ADR](ADR.md)
- [变更及回滚 CHG-RB](CHG-RB.md)
- [组员分工表](docs/组员分工表.md)
- [页面与课堂流程](docs/design/页面与课堂流程.md)
- [实施计划](docs/design/实施计划.md)
- [Spec 索引](docs/specs/README.md)
- [测试计划与追溯](docs/testing/需求追溯与测试计划.md)
- [设计检查记录](docs/checkpoints/checkpoint-1.md)

## 技术和目录约定

前端 Vue 3、Vite、Vue Router、Pinia、Element Plus、ECharts；后端 Flask、SQLAlchemy、Alembic；数据库统一 SQLite；统计与算法 NumPy、Pandas、scikit-learn、SciPy。不得引入 PyTorch、TensorFlow 或大模型权重。依赖精确版本在工程阶段完成兼容性检查后锁定。

```text
frontend/                 前端工程，待创建
backend/app/              后端工程，待创建
backend/migrations/       数据库迁移，待创建
tests/backend/            接口和领域测试，待创建
tests/frontend/           仿真逻辑测试，待创建
tests/e2e/                页面流程测试，待创建
scripts/                  初始化及备份脚本，待创建
docs/                     设计、规格、测试与检查材料
```

## 环境和配置约定

首版使用可支持所选锁定依赖的 Python 与 Node LTS，工程阶段记录精确版本和系统平台。运行数据存放在项目外或未跟踪的 `instance/`。配置项：`DATABASE_URL`、`UPLOAD_DIR`、`SECRET_KEY`、`APP_ENV`、`COOKIE_SECURE`；配置模板不含真实密码。开发默认 localhost，局域网部署才设置监听地址。

SQLite 文件路径必须解析成绝对路径，启用外键、5 秒 busy_timeout；数据库迁移版本由 Alembic 管理。不提交数据库、上传文件、密钥、node_modules、虚拟环境或缓存。

## 计划运行步骤

以下是后续工程需要提供的命令契约，当前不可执行：

1. 创建 Python 虚拟环境并安装 `backend/requirements.txt`；前端使用 `npm ci` 安装锁文件对应依赖。
2. 配置环境变量，执行 `python -m flask --app app:create_app db upgrade`（工作目录 backend）。
3. 执行 `python -m flask --app app:create_app init-admin`，交互输入管理员密码；再执行 `seed-demo` 创建标明模拟数据的教学样例。种子命令必须幂等且不得覆盖正式数据。
4. 开发时后端监听 localhost:5000，前端 `npm run dev` 使用 Vite 代理 `/api`；测试命令为根目录 `python -m pytest tests/backend`、前端 `npm run test:unit` 和 `npm run build`。工程阶段补齐 pytest 路径配置。
5. 部署时构建前端，后端通过 Waitress 等生产 WSGI 服务启动，提供同源静态文件；不使用 Flask 开发服务器承担实际课堂访问。具体命令和版本需运行核实后替换本节。

## 测试和部署验收

以[测试计划](docs/testing/需求追溯与测试计划.md)验证两班权限、答题截止、统计分母、状态仿真和新环境启动。SQLite 写操作用短事务，课堂并发以实测确定。安装依赖需要网络；安装完成后核心内容、仿真和题库应不依赖外部服务。

普通 HTTP 局域网仅用于受控演示；需要真实账号数据的部署应配置 HTTPS 与 Secure Cookie。首次实际课堂使用前完成备份恢复演练。详细回滚步骤见 [CHG-RB](CHG-RB.md)。

## 版本管理与提交

开发仓库：[web-homework](https://github.com/jzcool666/web-homework)。课程交付时同步 Gitea；地址由项目组补充。采用 main、develop、feature/spec-* 和 hotfix/*，提交及测试关联 Spec 编号。源代码推送不会自动复制平台上的 PR 和 Issue，需要的检查材料应存入 docs。

班级、组号及最终报告模板待补。组长提交成员名单、大作业报告、源码及设计文件；组员设计报告按 `学号_姓名_设计报告.docx` 命名。正式材料依实际实现更新，当前文档不代表功能已验收。
