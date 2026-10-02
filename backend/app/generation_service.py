"""SPEC-011 约束智能组卷的纯计算部分（E062）。

不依赖 Flask 与 SQLAlchemy：入参是从库里取出的普通结构，出参是选题结果与
求解元数据。口径来自 SPEC-011 第 4 节。

算法选型（见 PR 与 CHG-RB）：设计基线原本写 SciPy `milp`，本实现改用**确定性
分支定界**（深度优先 + 递减上界剪枝），因为本工程不引入外部求解器依赖，而二元
选题的约束（题量、难度配额、知识点覆盖、同题唯一）用回溯即可精确判定：

- 候选按 (优先级降序, 题目 ID 升序) 的固定顺序遍历，深度优先先走「选中」分支，
  因此第一个可行解就是贪心解，随后继续搜索证明最优或直到限时。
- 剪枝：剩余名额与剩余候选数、每个难度的剩余配额、每个知识点剩余覆盖需求、
  以及「当前值 + 剩余上界 ≤ 已知最优」；上界取各难度剩余优先级的前 k 大之和。
- 相同候选集、题库版本、历史首答分布与种子必然得到同一选题：随机项由
  `random.Random(seed)` 按固定候选顺序生成，遍历顺序与平局判定（题目 ID 升序）
  也都固定。

求解状态：
- `optimal`：搜索完整结束，返回的是目标函数最优解。
- `feasible`：限时结束时已找到通过全部约束校验的可行解，但不保证最优。
- 无解分两种：**证明无解**（搜索完整结束且无解，或必要条件的预检失败）→
  `Infeasible`（422）；**限时结束仍无解**→ `SolverTimeout`（503），不叫无解。
"""

from __future__ import annotations

import hashlib
import random
import time

MAX_CANDIDATES = 500
MAX_KNOWLEDGE_MINIMUMS = 18
TIME_LIMIT_SECONDS = 2.0
ALGORITHM_VERSION = "spec011-bnb-v1"
ALGORITHM_NAME = "deterministic-branch-and-bound"

DIFFICULTY_NAMES = {1: "easy", 2: "medium", 3: "hard"}
DIFFICULTY_KEYS = {"easy": 1, "medium": 2, "hard": 3}

_EPS = 1e-9


class Infeasible(Exception):
    """证明题库在给定约束下无解；constraints 为结构化约束列表。"""

    def __init__(self, constraints: list[dict]):
        super().__init__("题库无法满足当前条件")
        self.constraints = constraints


class SolverTimeout(Exception):
    """限时结束且尚未找到可行解；调用方按 503 SOLVER_TIMEOUT 处理。"""


def candidate_fingerprint(candidates) -> str:
    """候选题目版本指纹：按 ID 升序拼接 `题目ID:版本号` 后取 SHA-256 前 16 位。"""
    payload = ";".join(
        f"{item['id']}:{item['version']}" for item in sorted(candidates, key=lambda c: c["id"])
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compute_priorities(candidates, history, seed: int) -> dict[int, float]:
    """目标优先级 0.8*p_i + 0.2*seed随机项（SPEC-011 第 4 节规则 3）。

    p_i 为拉普拉斯平滑后的错误率 (错误数+1)/(机会数+2)：无历史的题取 0.5。
    随机项按**固定候选顺序**（调用方保证 candidates 已按 ID 升序）从
    `random.Random(seed)` 依次取，保证相同 seed 映射到相同题目。
    """
    rng = random.Random(seed)
    priorities: dict[int, float] = {}
    for item in candidates:
        errors, opportunities = history.get(item["id"], (0, 0))
        smoothed = (errors + 1) / (opportunities + 2)
        priorities[item["id"]] = 0.8 * smoothed + 0.2 * rng.random()
    return priorities


def _necessary_constraints(candidates, difficulty_counts, knowledge_minimums) -> list[dict]:
    """必要条件的失败清单；命中任一即已证明无解，无需进入搜索。"""
    constraints: list[dict] = []
    for difficulty in (1, 2, 3):
        required = difficulty_counts.get(difficulty, 0)
        available = sum(1 for item in candidates if item["difficulty"] == difficulty)
        if available < required:
            constraints.append(
                {
                    "kind": "difficulty",
                    "difficulty": DIFFICULTY_NAMES[difficulty],
                    "required": required,
                    "available": available,
                }
            )
    for knowledge_id in sorted(knowledge_minimums):
        required = knowledge_minimums[knowledge_id]
        if required <= 0:
            continue
        available = sum(1 for item in candidates if knowledge_id in item["knowledge_ids"])
        if available < required:
            constraints.append(
                {
                    "kind": "knowledge",
                    "knowledge_id": knowledge_id,
                    "required": required,
                    "available": available,
                }
            )
    return constraints


def _selection_key(ids):
    return tuple(sorted(ids))


def solve(
    candidates,
    difficulty_counts,
    knowledge_minimums,
    priorities,
    *,
    time_limit: float = TIME_LIMIT_SECONDS,
    clock=time.monotonic,
):
    """在约束下选题；返回 (selected_ids, solver_status, elapsed_seconds)。

    candidates：`[{id, version, difficulty, knowledge_ids}]`，须按 ID 升序。
    difficulty_counts：`{1: n1, 2: n2, 3: n3}`；knowledge_minimums：`{kid: min_count}`。
    """
    candidates = list(candidates)
    difficulty_counts = dict(difficulty_counts)
    knowledge_minimums = {
        kid: int(count) for kid, count in dict(knowledge_minimums).items() if int(count) > 0
    }

    constraints = _necessary_constraints(candidates, difficulty_counts, knowledge_minimums)
    if constraints:
        raise Infeasible(constraints)

    total_required = sum(difficulty_counts.get(d, 0) for d in (1, 2, 3))
    if total_required == 0:
        return [], "optimal", 0.0

    # 固定遍历顺序：优先级降序、题目 ID 升序
    ordered = sorted(candidates, key=lambda c: (-priorities[c["id"]], c["id"]))
    n = len(ordered)

    # 后缀可用数：编号 i 及其之后还剩多少候选，用于剪枝
    diff_suffix = [[0, 0, 0] for _ in range(n + 1)]
    kn_suffix = {kid: [0] * (n + 1) for kid in knowledge_minimums}
    for i in range(n - 1, -1, -1):
        item = ordered[i]
        previous = diff_suffix[i + 1]
        current = list(previous)
        current[item["difficulty"] - 1] += 1
        diff_suffix[i] = current
        for kid in knowledge_minimums:
            kn_suffix[kid][i] = kn_suffix[kid][i + 1] + (1 if kid in item["knowledge_ids"] else 0)

    # 各难度按优先级降序的排名表，供快速计算剩余上界
    ranked = {1: [], 2: [], 3: []}
    for index, item in enumerate(ordered):
        ranked[item["difficulty"]].append((priorities[item["id"]], index))
    for difficulty in ranked:
        ranked[difficulty].sort(key=lambda pair: (-pair[0], ordered[pair[1]]["id"]))

    def upper_bound(index: int, slots_left) -> float:
        total = 0.0
        for difficulty in (1, 2, 3):
            remaining_slots = slots_left[difficulty - 1]
            if remaining_slots <= 0:
                continue
            taken = 0
            for priority, position in ranked[difficulty]:
                if position >= index:
                    total += priority
                    taken += 1
                    if taken == remaining_slots:
                        break
        return total

    started_at = clock()
    deadline = started_at + max(time_limit, 0.0)
    state = {"timed_out": False, "best_value": None, "best": None}

    slots_left = [difficulty_counts.get(1, 0), difficulty_counts.get(2, 0), difficulty_counts.get(3, 0)]
    covered = {kid: 0 for kid in knowledge_minimums}
    chosen: list[int] = []

    def record(value: float) -> None:
        selection = list(chosen)
        best = state["best"]
        if best is None or value > best[0] + _EPS or (
            abs(value - best[0]) <= _EPS and _selection_key(selection) < _selection_key(best[1])
        ):
            state["best"] = (value, selection)

    def search(index: int, value: float) -> None:
        if state["timed_out"]:
            return
        if clock() > deadline:
            state["timed_out"] = True
            return
        if sum(slots_left) == 0:
            if all(covered[kid] >= need for kid, need in knowledge_minimums.items()):
                record(value)
            return
        if index >= n or sum(slots_left) > n - index:
            return
        for difficulty in (1, 2, 3):
            if slots_left[difficulty - 1] > diff_suffix[index][difficulty - 1]:
                return
        for kid, need in knowledge_minimums.items():
            if covered[kid] < need and kn_suffix[kid][index] < need - covered[kid]:
                return
        best = state["best"]
        if best is not None and value + upper_bound(index, slots_left) <= best[0] + _EPS:
            return

        item = ordered[index]
        difficulty = item["difficulty"]
        if slots_left[difficulty - 1] > 0:
            slots_left[difficulty - 1] -= 1
            chosen.append(item["id"])
            for kid in item["knowledge_ids"]:
                if kid in covered:
                    covered[kid] += 1
            search(index + 1, value + priorities[item["id"]])
            for kid in item["knowledge_ids"]:
                if kid in covered:
                    covered[kid] -= 1
            chosen.pop()
            slots_left[difficulty - 1] += 1
            if state["timed_out"]:
                return
        search(index + 1, value)

    search(0, 0.0)
    elapsed = clock() - started_at

    if state["best"] is None:
        if state["timed_out"]:
            raise SolverTimeout("组卷求解超时，请稍后重试或放宽约束")
        raise Infeasible([{"kind": "coverage", "message": "不存在满足全部约束的选题组合"}])

    selected_ids, status = state["best"][1], ("feasible" if state["timed_out"] else "optimal")
    return selected_ids, status, elapsed


def build_coverage(selected_ids, candidates, knowledge_minimums) -> list[dict]:
    """每个知识点需求与实选覆盖数，按 knowledge_id 升序。"""
    tags = {item["id"]: set(item["knowledge_ids"]) for item in candidates}
    rows = []
    for knowledge_id in sorted(knowledge_minimums):
        required = knowledge_minimums[knowledge_id]
        covered = sum(1 for qid in selected_ids if knowledge_id in tags.get(qid, ()))
        rows.append(
            {
                "knowledge_id": knowledge_id,
                "min_count": required,
                "selected_count": covered,
                "satisfied": covered >= required,
            }
        )
    return rows
