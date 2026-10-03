# 实验箱与 Logisim 电路测评调研

日期：2026-10-03。目的：落实实验箱连线过程模拟与电路文件在线测评。以下为资料核对和技术探测，不是全班访谈，也不是新增模块验收通过。

## 1 调研来源与结论

| 来源 | 核对内容 | 本项目选择 |
| --- | --- | --- |
| [清华数字逻辑实验器材介绍](https://lab.cs.tsinghua.edu.cn/digital-logic-lab/doc/equip_intro/) | 教学实验箱及 74 系列元件，包括 74LS74、74LS161 和常见门电路 | 通用 74 系列箱，供电/开关/时钟/芯片/指示灯布局；不声称唯一最常用商用型号 |
| [TI SN74LS74A 手册](https://www.ti.com/lit/ds/symlink/sn74ls74a.pdf)第 1 页 | DIP 顶视引脚、上升沿、低有效异步 PRE/CLR 和两者同时低的非正常状态 | 新芯片引擎按手册实现；原同步复位演示保持原语义 |
| [TI SN74LS161A 手册](https://www.ti.com/lit/ds/symlink/sn74ls161a.pdf)第 1 页及功能说明 | 4 位二进制计数、异步清零、同步装载和两个使能 | 用 161 与译码门做模 6；不混用 163 的同步清零 |
| [TI SN74LS194A 手册](https://www.ti.com/lit/ds/symlink/sn74ls194a.pdf)第 1—2 页 | 异步清零、并行装载、保持、双向移位及 mode 表 | 四模式均需测试，明确 QA→QD 右移与显示位序 |
| [Logisim-evolution 5.0.0 发行](https://github.com/logisim-evolution/logisim-evolution/releases/tag/v5.0.0) | 官方当前稳定发行，2026-09-12；包含 TTL 元件和测试向量修复 | 固定 5.0.0，不跟随自动升级；未调查版本市场份额 |
| [5.0.0 测试向量文档](https://github.com/logisim-evolution/logisim-evolution/blob/v5.0.0/docs/test_vector.md) | `--test-vector`、端口标签/位宽、`<set>`/`<seq>` 保留状态 | 服务器私有向量逐拍测评，独立序列先复位 |
| [5.0.0 Startup 源码](https://github.com/logisim-evolution/logisim-evolution/blob/v5.0.0/src/main/java/com/cburch/logisim/gui/start/Startup.java)及 [Java 运行说明](https://github.com/logisim-evolution/logisim-evolution/blob/v5.0.0/docs/developers.md) | 命令启动与 Java 运行要求 | Java 21，Windows 首次支持；真实探测优先于文档的退出码概述 |

## 2 核对后的 DIP 引脚

均为顶视图，缺口在上，左侧从 1 向下，右侧从末脚向上；`_N` 表示低有效。前端图由这些事实自行绘制，实现时逐脚测试编号和连线端点。门芯片另从原厂手册核对后进入冻结目录，不从通用名称猜脚位。

| 器件 | 1 起顺序的信号名 |
| --- | --- |
| 74LS74 DIP14 | 1CLR_N、1D、1CLK、1PRE_N、1Q、1Q_N、GND、2Q_N、2Q、2PRE_N、2CLK、2D、2CLR_N、VCC |
| 74LS161 DIP16 | CLR_N、CLK、A、B、C、D、ENP、GND、LOAD_N、ENT、QD、QC、QB、QA、RCO、VCC |
| 74LS194 DIP16 | CLR_N、SR、A、B、C、D、SL、GND、S0、S1、CLK、QD、QC、QB、QA、VCC |

## 3 命令行可行性探测

环境：Windows，Microsoft OpenJDK 21.0.7，官方 `logisim-evolution-5.0.0-all.jar`。下载文件 SHA-256 为 `6b368e894742c04cc83aa9830f869bcab0190ede4df43ad6fecdb89b3a23a41c`，与官方 release asset digest 相同。探测文件、JAR、原厂 PDF 和原始日志保留在项目外 `开发工作区/调研/实验扩展/`，未加入源码包。

| 样例 | 实际结果 | 结论 |
| --- | --- | --- |
| 单线 D→Q，两行正确向量 | Passed: 2, Failed: 0，退出码 0 | 能运行标准端口比较 |
| 单线 D→Q，故意写反期望 | Passed: 0, Failed: 2，退出码仍为 0 | 不能用退出码代替判分 |
| D 触发器，含复位、上升/下降沿及第二个独立 set，共 9 行 | Passed: 9, Failed: 0，退出码 0 | `<seq>` 状态保持与跨 set 初始化可运行 |
| 同一触发器故意改错第 3 行 | Passed: 8, Failed: 1，并列出 Q=1 expected 0，退出码仍为 0 | 有可解析的失败位置与值 |
| 加 `-Djava.awt.headless=true` | HeadlessException，退出码 1 | 此命令路径不能未经验证直接部署到无显示 Linux |

普通命令使用固定参数数组：`java -Xmx256m -jar <固定JAR> --no-splash --locale en --test-vector main <私有向量> <作业circ>`。文件名是应用生成的绝对路径，不拼 shell 字符串。样例未弹出主电路编辑窗口。

本轮仅验证测试向量入口和小型 D 触发器序列；尚未验证四个正式任务、TTL 供电属性、上传权限、复杂子电路、超时终止、服务运行账号或课堂负载。这些是实施任务验收，不能依据本轮样例宣称新模块已实现。官方文档描述失败退出非零与本轮观察不一致，工作进程必须以实际输出、计数完整性和测试集数量共同判断。
