# 演示文件

这些文件用于展示系统如何处理正确输入和错误输入，不是学生作业，也不是正式验收成绩。全套操作顺序见[课堂演示与验收示例](../docs/课堂演示与验收示例.md)。

## Logisim 电路

使用 Logisim-evolution 5.0.0，入口电路 `main`，端口按四个公开任务的要求命名。`correct` 是人工构造的完整演示电路；`wrong` 保留合法格式和端口，但改变计数模值或触发器输出连线，展示“文件合法、功能仍可能错误”。下载页提供的模板只有器件/端口，和完整示例不是同一文件。

| 任务 | 正确示例 | 错误示例 |
| --- | --- | --- |
| D触发器 | [LAB-D-correct.circ](logisim/LAB-D-correct.circ) | [LAB-D-wrong.circ](logisim/LAB-D-wrong.circ) |
| 模6计数器 | [LAB-C6-correct.circ](logisim/LAB-C6-correct.circ) | [LAB-C6-wrong.circ](logisim/LAB-C6-wrong.circ) |
| 4位双向移位寄存器 | [LAB-S4-correct.circ](logisim/LAB-S4-correct.circ) | [LAB-S4-wrong.circ](logisim/LAB-S4-wrong.circ) |
| 状态转换电路 | [LAB-FSM-correct.circ](logisim/LAB-FSM-correct.circ) | [LAB-FSM-wrong.circ](logisim/LAB-FSM-wrong.circ) |

正确示例使用原生器件实现同样功能，不要求与实验箱TTL连线一模一样。示例不通过生产API分发为标准答案，上传测评仍运行真实引擎多拍验证，不比较XML相似度。

## 状态表识别

- [counter-state-table.png](recognition/counter-state-table.png)：格式v1，7行4列，Q3Q2Q1Q0从左到右，状态为0→1→2→3→4→5→0。正常应识别出6个相邻次态对，结果须人工核对。
- [blank-invalid.png](recognition/blank-invalid.png)：故意不带网格的空白图片，用于展示格式失败，不能当作全0状态表。

识别不负责判断实验通过，也不接受任意电路图或手写状态表。样例图片与电路的真实检查结果见演示验收记录。
