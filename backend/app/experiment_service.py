"""SPEC-013 第 4 节：把实验的固定输入序列重放成检查点，并生成逐拍说明。

状态转移规则**全部**来自 `simulator.py`：这里只负责按顺序走一遍实验的输入序列、
挑出其中的有效上升沿，以及把结果写成给学生看的文字。任何一处都不再实现第二套
仿真规则，避免标准答案与演示/仿真出现分歧。

检查点的 `index` 从 0 开始，与 AttemptResult.first_error_index 对齐；
界面显示的「第 N 拍」由 index + 1 得到（SPEC-013 第 4 节第 3 条）。
"""

from __future__ import annotations

from .simulator import (
    SIMULATOR_COUNTER,
    SIMULATOR_D,
    SIMULATOR_JK,
    SIMULATOR_SHIFT,
    SimulationError,
    apply_event,
    initial_state,
    q_bits,
    validate_event,
)

INPUT_LABELS = {"d": "D", "j": "J", "k": "K", "enable": "EN", "serial_in": "SI", "reset": "RESET"}

# 只描述规则，不复算状态：具体数值一律来自 simulator.py 的推演结果
MODEL_HINTS = {
    SIMULATOR_D: "D 触发器只在有效上升沿把 D 送入 Q，其他时刻保持。",
    SIMULATOR_JK: "JK 触发器在有效上升沿按 J/K 更新：00 保持、01 清零、10 置位、11 翻转。",
    SIMULATOR_COUNTER: "计数器每个有效上升沿加 1，到达模数后回到 0；enable=0 时保持。",
    SIMULATOR_SHIFT: "移位寄存器每个有效上升沿把串行输入移入 Q3 并向 Q0 方向移动；enable=0 时保持。",
}

BINARY_TYPES = (SIMULATOR_D, SIMULATOR_JK)


class CheckpointError(ValueError):
    """实验定义本身无法用于预测（例如输入序列没有有效上升沿）。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def state_range(simulator_type: str) -> tuple[int, int]:
    """该模型可取的状态范围：D/JK 为 0—1，计数器与移位寄存器为 0—15。"""
    return (0, 1) if simulator_type in BINARY_TYPES else (0, 15)


def q_text(value: int, simulator_type: str) -> str:
    bits = "".join(str(bit) for bit in q_bits(value, simulator_type))
    return f"{bits}（{value}）" if simulator_type not in BINARY_TYPES else bits


def inputs_text(inputs: dict) -> str:
    parts = [f"{INPUT_LABELS.get(name, name)}={value}" for name, value in inputs.items()]
    return " ".join(parts) if parts else "（无输入）"


def replay_checkpoints(
    simulator_type: str, config: dict, input_sequence: list
) -> list[dict]:
    """按固定输入序列重放，返回每个有效上升沿的检查点。

    与 SPEC-012 的历史口径一致：`reset_view` 会清空已累计的检查点与计数，
    因此出现在输入序列里时，它之前的拍不参与本实验的预测。
    """
    state = initial_state(simulator_type, config)
    checkpoints: list[dict] = []
    for seq, raw in enumerate(input_sequence, start=1):
        try:
            event = validate_event(simulator_type, raw)
        except SimulationError as exc:  # 迁移或历史数据损坏时给出可读错误
            raise CheckpointError(f"实验输入序列第 {seq} 个事件无效：{exc.rule}") from exc
        state, row = apply_event(simulator_type, config, state, event, seq=seq)
        if row is None:
            checkpoints = []
            continue
        if row["rising"]:
            checkpoints.append(
                {
                    "index": len(checkpoints),
                    "step_no": row["step_no"],
                    "inputs": dict(row["inputs"]),
                    "q_before": row["q_before"],
                    "q": row["q"],
                }
            )
    return checkpoints


def checkpoint_contexts(checkpoints: list[dict]) -> list[dict]:
    """给学生端的检查点上下文：只有拍号与该拍输入，**不含**标准答案。"""
    return [
        {"index": cp["index"], "step_no": cp["step_no"], "inputs": dict(cp["inputs"])}
        for cp in checkpoints
    ]


def expected_states(checkpoints: list[dict]) -> list[int]:
    return [cp["q"] for cp in checkpoints]


def first_difference(expected: list[int], actual: list[int]) -> int | None:
    """返回第一个不一致的下标；全部一致返回 None。下标从 0 开始。"""
    for index, want in enumerate(expected):
        if index >= len(actual) or actual[index] != want:
            return index
    return None


def explain(
    simulator_type: str, checkpoints: list[dict], actual: list[int]
) -> list[str]:
    """逐拍说明：给出该拍输入与 Q 的变化；答错的一拍写出正确答案与规则提示。"""
    lines: list[str] = []
    for cp in checkpoints:
        index = cp["index"]
        guessed = actual[index] if index < len(actual) else None
        head = (
            f"第 {index + 1} 拍：{inputs_text(cp['inputs'])}，"
            f"Q 由 {q_text(cp['q_before'], simulator_type)} 变为 {q_text(cp['q'], simulator_type)}"
        )
        if guessed == cp["q"]:
            lines.append(f"{head}；预测正确。")
        else:
            shown = "（空）" if guessed is None else q_text(guessed, simulator_type)
            lines.append(
                f"{head}；正确答案 {q_text(cp['q'], simulator_type)}，你填了 {shown}。"
                f"{MODEL_HINTS.get(simulator_type, '')}"
            )
    return lines


def require_checkpoints(simulator_type: str, config: dict, input_sequence: list) -> list[dict]:
    """取出检查点；没有有效上升沿的实验不能用于预测。"""
    checkpoints = replay_checkpoints(simulator_type, config, input_sequence)
    if not checkpoints:
        raise CheckpointError("该实验的固定输入序列没有有效上升沿，无法进行预测")
    return checkpoints
