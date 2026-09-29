"""SPEC-012 第 4 节：四类预置同步时序模型的纯逻辑实现。

本模块不依赖数据库或 Flask：共享演示的每次动作都由后端调用这里的函数从旧状态
重算，预测用的「下一个有效上升沿状态」也由同一个函数给出，保证演示、预测与
后端校验共用一套规则。测试向量的期望值按规格人工推演，不由本实现生成。

规则（SPEC-012 第 4 节）：
1. 初始 clock=0，Q 由 config 指定；set 只改输入，toggle_clock 翻转时钟。
   只有 0→1 计算新 Q；1→0 与单独改输入都不改变 Q。
2. reset 为同步高有效：在上升沿优先 Q=0；否则 D 为 Q'=D，
   JK 为 00 保持 / 01 置 0 / 10 置 1 / 11 翻转。
3. counter：enable=0 保持，否则 Q'=(Q+1) mod M，M 为 2—16；
   无效状态 Q≥M 在下个有效沿回 0。shift 右移：Q'=(serial_in<<3)|(Q>>1)，
   enable=0 保持，显示 Q3Q2Q1Q0。
4. 默认 enable=1，其余输入 0；最多 128 个事件。
"""

from __future__ import annotations

SIMULATOR_D = "d"
SIMULATOR_JK = "jk"
SIMULATOR_COUNTER = "counter"
SIMULATOR_SHIFT = "shift"
SIMULATOR_TYPES = (SIMULATOR_D, SIMULATOR_JK, SIMULATOR_COUNTER, SIMULATOR_SHIFT)

SINGLE_BIT_TYPES = (SIMULATOR_D, SIMULATOR_JK)
NIBBLE_TYPES = (SIMULATOR_COUNTER, SIMULATOR_SHIFT)

# 各模型的输入引脚；APIC 第 2 节 SimEvent 只允许对应模型字段
MODEL_INPUTS: dict[str, tuple[str, ...]] = {
    SIMULATOR_D: ("d", "reset"),
    SIMULATOR_JK: ("j", "k", "reset"),
    SIMULATOR_COUNTER: ("enable", "reset"),
    SIMULATOR_SHIFT: ("enable", "serial_in", "reset"),
}

# 默认 enable=1，其余输入 0（SPEC-012 第 4 节第 4 条）
INPUT_DEFAULTS = {"d": 0, "j": 0, "k": 0, "enable": 1, "serial_in": 0, "reset": 0}

EVENT_OPS = ("set", "toggle_clock", "reset_view")
CLOCK_OPS = ("toggle_clock", "reset_view")
DEMO_OPS = ("set_reveal", "close")

DEFAULT_MODULUS = 16
MIN_MODULUS = 2
MAX_MODULUS = 16
MAX_Q = 15
MAX_EVENTS = 128


class SimulationError(ValueError):
    """字段级校验失败；接口层据此返回 422 VALIDATION_ERROR。"""

    def __init__(self, field: str, rule: str):
        super().__init__(f"{field}: {rule}")
        self.field = field
        self.rule = rule


def _binary(value: object, field: str) -> int:
    """0/1 输入值。注意 bool 也是 int，需显式排除，避免 True 被当成 1 静默通过。"""
    if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
        raise SimulationError(field, "必须是 0 或 1")
    return value


def _int_in_range(value: object, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise SimulationError(field, f"必须是 {low}—{high} 的整数")
    return value


def model_inputs(simulator_type: str) -> tuple[str, ...]:
    if simulator_type not in MODEL_INPUTS:
        raise SimulationError("simulator_type", "/".join(SIMULATOR_TYPES))
    return MODEL_INPUTS[simulator_type]


def default_inputs(simulator_type: str) -> dict:
    return {name: INPUT_DEFAULTS[name] for name in model_inputs(simulator_type)}


def normalize_config(simulator_type: str, raw: object) -> dict:
    """校验并规范化 SimulatorConfig；只保留该模型真正使用的字段。"""
    model_inputs(simulator_type)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise SimulationError("config", "必须是对象")
    unknown = sorted(set(raw) - {"initial_q", "modulus"})
    if unknown:
        raise SimulationError("config", f"不支持的字段 {', '.join(unknown)}")

    initial_q = _int_in_range(raw.get("initial_q", 0), "config.initial_q", 0, MAX_Q)
    if simulator_type in SINGLE_BIT_TYPES and initial_q not in (0, 1):
        raise SimulationError("config.initial_q", "D/JK 触发器初态只能是 0 或 1")

    config: dict = {"initial_q": initial_q}
    if simulator_type == SIMULATOR_COUNTER:
        config["modulus"] = _int_in_range(
            raw.get("modulus", DEFAULT_MODULUS), "config.modulus", MIN_MODULUS, MAX_MODULUS
        )
    elif "modulus" in raw:
        # 只有计数器有模数，静默忽略会让配置与行为不一致
        raise SimulationError("config.modulus", "只有计数器支持模数")
    return config


def initial_state(simulator_type: str, config: dict) -> dict:
    """初始 clock=0、默认输入、Q 取 config.initial_q、step_no=0。"""
    return {
        "clock": 0,
        "inputs": default_inputs(simulator_type),
        "q": config["initial_q"],
        "step_no": 0,
    }


def compute_next_q(simulator_type: str, config: dict, q: int, inputs: dict) -> int:
    """按当前输入计算「下一个有效上升沿」后的 Q。"""
    if inputs.get("reset"):
        # 同步高有效复位在有效沿优先（SPEC-012 第 4 节第 2 条）
        return 0

    if simulator_type == SIMULATOR_D:
        return int(inputs["d"])

    if simulator_type == SIMULATOR_JK:
        j, k = inputs["j"], inputs["k"]
        if j and k:
            return 0 if q else 1
        if j:
            return 1
        if k:
            return 0
        return q

    if simulator_type == SIMULATOR_COUNTER:
        if not inputs["enable"]:
            return q
        modulus = config["modulus"]
        if q >= modulus:
            # 无效状态 Q≥M 在下个有效沿回 0
            return 0
        nxt = q + 1
        return 0 if nxt >= modulus else nxt

    if not inputs["enable"]:
        return q
    return ((int(inputs["serial_in"]) & 1) << 3) | ((q >> 1) & 0b0111)


def validate_event(simulator_type: str, raw: object) -> dict:
    """校验 SimEvent；请求不能携带 q，服务端按规则重算。"""
    if not isinstance(raw, dict):
        raise SimulationError("event", "必须是对象")
    op = raw.get("op")
    if op not in EVENT_OPS:
        raise SimulationError("event.op", "/".join(EVENT_OPS))

    if op == "set":
        inputs = raw.get("inputs")
        if not isinstance(inputs, dict) or not inputs:
            raise SimulationError("event.inputs", "set 必须给出至少一个输入")
        allowed = set(model_inputs(simulator_type))
        unknown = sorted(set(inputs) - allowed)
        if unknown:
            raise SimulationError("event.inputs", f"该模型不支持 {', '.join(unknown)}")
        normalized = {name: _binary(value, f"event.inputs.{name}") for name, value in inputs.items()}
        extra = sorted(set(raw) - {"op", "inputs"})
        if extra:
            raise SimulationError("event", f"不支持的字段 {', '.join(extra)}")
        return {"op": op, "inputs": normalized}

    extra = sorted(set(raw) - {"op"})
    if extra:
        raise SimulationError("event", f"不支持的字段 {', '.join(extra)}")
    return {"op": op}


def validate_demo_action(raw: object) -> dict:
    """E054 的 set_reveal / close；与 SimEvent 互斥，不与 q 同传。"""
    if not isinstance(raw, dict):
        raise SimulationError("action", "必须是对象")
    op = raw.get("op")
    if op not in DEMO_OPS:
        raise SimulationError("action.op", "/".join(DEMO_OPS))
    if op == "set_reveal":
        value = raw.get("value")
        if not isinstance(value, bool):
            raise SimulationError("action.value", "必须是布尔值")
        extra = sorted(set(raw) - {"op", "value"})
        if extra:
            raise SimulationError("action", f"不支持的字段 {', '.join(extra)}")
        return {"op": op, "value": value}
    extra = sorted(set(raw) - {"op"})
    if extra:
        raise SimulationError("action", f"不支持的字段 {', '.join(extra)}")
    return {"op": op}


def history_row(
    *, seq: int, op: str, state: dict, q_before: int, rising: bool
) -> dict:
    """历史行：记录时钟、输入、旧 Q、新 Q 与是否有效沿（SPEC-012 第 4 节第 5 条）。

    seq 为事件序号，step_no 为该行执行后的有效上升沿计数，供界面按拍展示。
    """
    return {
        "seq": seq,
        "op": op,
        "clock": state["clock"],
        "inputs": dict(state["inputs"]),
        "q_before": q_before,
        "q": state["q"],
        "rising": rising,
        "step_no": state["step_no"],
    }


def apply_event(
    simulator_type: str, config: dict, state: dict, event: dict, *, seq: int
) -> tuple[dict, dict | None]:
    """在旧状态上执行一个 SimEvent，返回 (新状态, 历史行)。

    reset_view 会恢复初态并清空历史，因此不产生历史行（返回 None）。
    """
    op = event["op"]
    q_before = state["q"]

    if op == "reset_view":
        return initial_state(simulator_type, config), None

    if op == "set":
        # 只改输入：clock 与 Q 都不变，不产生有效沿
        inputs = dict(state["inputs"])
        inputs.update(event["inputs"])
        new_state = {
            "clock": state["clock"],
            "inputs": inputs,
            "q": q_before,
            "step_no": state["step_no"],
        }
        return new_state, history_row(
            seq=seq, op=op, state=new_state, q_before=q_before, rising=False
        )

    clock = 1 - int(state["clock"])
    rising = clock == 1
    q = (
        compute_next_q(simulator_type, config, q_before, state["inputs"])
        if rising
        else q_before
    )
    new_state = {
        "clock": clock,
        "inputs": dict(state["inputs"]),
        "q": q,
        "step_no": state["step_no"] + (1 if rising else 0),
    }
    return new_state, history_row(
        seq=seq, op=op, state=new_state, q_before=q_before, rising=rising
    )


def q_bits(state_q: int, simulator_type: str) -> list[int]:
    """显示用位序：D/JK 为 Q；计数器与移位寄存器为 Q3Q2Q1Q0（Q3 最高位）。"""
    if simulator_type in NIBBLE_TYPES:
        return [(state_q >> shift) & 1 for shift in (3, 2, 1, 0)]
    return [state_q & 1]
