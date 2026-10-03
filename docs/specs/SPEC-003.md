# SPEC-003 出勤与风险因素统计

版本：设计基线 1.0，2026-10-02。状态：已实现，执行结果见[报告](../testing/SPEC-003-执行报告.md)。模块对应：吴亚峰。关联需求：FR-10。前置依赖：SPEC-002、SPEC-006、SPEC-010。

## 1 范围

出勤分布、学生明细、出勤与成绩相关分析及CSV。非目标：因果结论和纪律处罚。

## 2 接口契约

E055 GET /analytics/attendance，class_id/from/to/format；返回 AttendanceStats 和相关系数样本量。

接口完整字段、角色缩写、状态码和公共错误定义见 [APIC](../../APIC.md)。所有写操作按公共规则校验会话、CSRF和对象权限；列表/导出同样不能越权。匿名401、角色拒绝403、跨班对象404、字段错误422、状态/版本冲突409；本模块特有错误以 APIC 为准。

## 3 数据结构

attendance_records/tasks、enrollments、submissions/assessments；查询同班历史名单，不新建重复统计表。

各字段类型、可空性、唯一键、外键、索引和删除策略见 [DBD](../../DBD.md)。涉及新表及索引时以迁移实现，不运行时自动建表覆盖已有数据。

## 4 业务规则

1. 窗口按任务opens_at选择，先结算已结束任务；只纳入settled任务，进行中不进分母。
2. 出勤率=(present+late)/(present+late+absent)，leave排除；分母零返回null。
3. 按学生计算同窗口非practice测评百分制均分；仅两列都有值的n≥5且方差非零时由Pandas计算Pearson，否则null和原因。
4. CSV与JSON使用相同过滤条件；仅本班教师可导出，文本做公式转义。
5. `students` 是**窗口内出现过考勤记录**的学生（该窗口的历史名单），不是当前在册名单；响应同时给出只读的 `student_no`/`display_name` 供教师识别学生（与 SPEC-002 同一理由，见 CHG-RB 登记）。
6. 成绩列只取本班非 practice 测评中 `submitted_at` 落入窗口的已提交记录，按学生取百分制均值。CSV 列顺序与 `summary`/`student`/`correlation` 三个 section 在 APIC 第 7 节固定。本模块只读 `attendance_tasks`/`attendance_records`/`enrollments`/`submissions`/`assessments`，没有新迁移。

## 5 验收用例

| 编号 | 操作及预期结果 | 当前状态 |
| --- | --- | --- |
| T-003-01 | present=2、late=1、leave=1、absent=1得到出勤率0.75。 | 已执行，见报告 |
| T-003-02 | 全部请假或无结束任务返回null，不显示0%出勤率。 | 已执行，见报告 |
| T-003-03 | 4个共同样本或恒定列返回相关系数null；5个完全同向非恒定样本返回约1。 | 已执行，见报告 |
| T-003-04 | 跨班访问拒绝，CSV各状态计数与JSON一致，恶意表格公式被转义。 | 已执行，见报告 |

测试使用固定数据和独立数据库；实际命令、结果与未覆盖项见[执行报告](../testing/SPEC-003-执行报告.md)。

## 6 交付与变更

交付包括本 Spec 对应页面或服务、后端规则、必要种子数据、测试和运行说明。分支建议为 `feature/spec-003`，提交关联 `spec-003`。若实现需要改变字段、算法、状态或范围，先更新 APIC/DBD/本 Spec，并在 [CHG-RB](../../CHG-RB.md)登记。

