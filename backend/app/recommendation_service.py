"""SPEC-015 推荐排序的纯计算部分（E065）。

不依赖 Flask 与 SQLAlchemy：入参是调用方从库里取出的普通结构，出参是排好序的
推荐条目。口径来自 SPEC-015 第 4 节与 ADR-007 第 4 条（按错题、进度与实验表现
排序并给出原因，不训练复杂模型）：

- 每个知识点的三个信号：已公开首答错误率 e、明确未完成记录 p（未完成 1/完成 0）、
  实验失败比例 x。按 0.5/0.3/0.2 只对**可用**信号归一化；缺失信号既不当作失败，
  也不参与分母。
- 没有任何信号的学生按章节顺序给基础路径，条目 `score=null`、理由是入门路径，
  不编造个性化得分或错题次数。
- 理由全部来自实际可用的信号，不写不存在的错误次数。
"""

from __future__ import annotations

ALGORITHM_VERSION = "spec015-signals-v1"

WEIGHTS = {"error": 0.5, "progress": 0.3, "experiment": 0.2}
DEFAULT_LIMIT = 5
MIN_LIMIT = 1
MAX_LIMIT = 10

MASTERY_ACCURACY = 0.8
KIND_KNOWLEDGE = "knowledge"
KIND_QUESTION = "question"


def knowledge_signals(raw: dict | None) -> dict:
    """从原始计数算出三个可用信号；样本为 0 的信号视为不可用（None）。"""
    raw = raw or {}
    attempts = int(raw.get("attempts", 0) or 0)
    errors = int(raw.get("errors", 0) or 0)
    experiment_attempts = int(raw.get("experiment_attempts", 0) or 0)
    experiment_failures = int(raw.get("experiment_failures", 0) or 0)
    completed = raw.get("completed")

    error_rate = (errors / attempts) if attempts > 0 else None
    progress = (1.0 - float(completed)) if completed is not None else None
    experiment = (
        experiment_failures / experiment_attempts if experiment_attempts > 0 else None
    )
    return {
        "attempts": attempts,
        "errors": errors,
        "experiment_attempts": experiment_attempts,
        "experiment_failures": experiment_failures,
        "completed": completed,
        "error": error_rate,
        "progress": progress,
        "experiment": experiment,
    }


def score_of(signals: dict) -> float | None:
    """加权分（0—100）；三个信号都不可用时返回 None。"""
    available = {
        name: signals[name] for name in WEIGHTS if signals.get(name) is not None
    }
    if not available:
        return None
    total_weight = sum(WEIGHTS[name] for name in available)
    weighted = sum(WEIGHTS[name] * value for name, value in available.items())
    return round(100.0 * weighted / total_weight, 2)


def is_weak(signals: dict) -> bool:
    """有可用信号且分值为正：说明存在明确的薄弱面。"""
    score = score_of(signals)
    return score is not None and score > 0


def is_mastered(signals: dict) -> bool:
    """已完成 + 首答正确率 ≥ .8 + 没有未通过的实验 → 视为已掌握，不再推荐。"""
    if signals.get("completed") != 1:
        return False
    error_rate = signals.get("error")
    if error_rate is None or error_rate > (1.0 - MASTERY_ACCURACY):
        return False
    return not signals.get("experiment_failures")


def is_explicitly_incomplete(signals: dict) -> bool:
    """只看**明确记为未完成**的记录（completed=0）。

    第 4 节第 1 条的 p 同样只认明确记录，因此「未完成的先修知识点」也按同一口径：
    没有进度记录的先修不算「未完成」，否则任何薄弱知识点都会被一串从未打开过的
    先修挤到后面，学生看不到自己真正错在哪。
    """
    return signals.get("completed") == 0


def reasons_for(signals: dict) -> list[str]:
    """按实际可用信号生成可读理由，顺序固定为 错题 → 进度 → 实验。"""
    reasons: list[str] = []
    if signals.get("error") is not None and signals["errors"] > 0:
        percent = round(signals["error"] * 100)
        reasons.append(
            f"{signals['errors']}/{signals['attempts']} 道相关题目首答错误（错误率 {percent}%）"
        )
    if signals.get("progress") == 1.0:
        reasons.append("知识点标记为未完成")
    if signals.get("experiment") is not None and signals["experiment_failures"] > 0:
        reasons.append(
            f"{signals['experiment_failures']}/{signals['experiment_attempts']} 次相关实验未通过"
        )
    return reasons


def _order_key(point: dict):
    return (point["chapter_sort"], point["sort_order"], point["id"])


def rank(*, points, edges, signals_by_point, questions_by_point, limit=DEFAULT_LIMIT) -> list[dict]:
    """返回最多 limit 条推荐，不重复、不凑数。

    points：已发布知识点，元素含 id/title/chapter_id/chapter_sort/sort_order。
    edges：(先修 id, 后继 id)，只含两端都已发布的边。
    signals_by_point：知识点 id → 原始信号计数。
    questions_by_point：知识点 id → 候选练习（已过滤掉屏蔽题与已答对的题）。
    """
    by_id = {point["id"]: point for point in points}
    ordered = sorted(points, key=_order_key)
    signals = {point["id"]: knowledge_signals(signals_by_point.get(point["id"])) for point in points}
    scores = {point_id: score_of(value) for point_id, value in signals.items()}

    prerequisites: dict[int, list[int]] = {}
    for prerequisite_id, target_id in edges:
        if prerequisite_id in by_id and target_id in by_id:
            prerequisites.setdefault(target_id, []).append(prerequisite_id)
    for target_id in prerequisites:
        prerequisites[target_id].sort(key=lambda pid: _order_key(by_id[pid]))

    items: list[dict] = []
    seen: set[tuple[str, int]] = set()

    def push(kind: str, resource_id: int, knowledge_id: int, title: str, score, reasons):
        if len(items) >= limit:
            return False
        key = (kind, resource_id)
        if key in seen:
            return False
        seen.add(key)
        items.append(
            {
                "kind": kind,
                "resource_id": resource_id,
                "knowledge_id": knowledge_id,
                "title": title,
                "score": score,
                "reasons": list(reasons),
            }
        )
        return True

    weak = [
        point
        for point in ordered
        if is_weak(signals[point["id"]]) and not is_mastered(signals[point["id"]])
    ]
    weak.sort(key=lambda point: (-scores[point["id"]],) + _order_key(point))

    for point in weak:
        if len(items) >= limit:
            break
        point_id = point["id"]
        # 1) 先给该薄弱知识点的未完成先修
        for prerequisite_id in prerequisites.get(point_id, ()):
            prerequisite = by_id[prerequisite_id]
            if not is_explicitly_incomplete(signals[prerequisite_id]):
                continue
            push(
                KIND_KNOWLEDGE,
                prerequisite_id,
                prerequisite_id,
                prerequisite["title"],
                scores[prerequisite_id],
                [f"“{point['title']}”的先修知识点，尚未完成"],
            )
        # 2) 再给薄弱知识点本身
        push(
            KIND_KNOWLEDGE,
            point_id,
            point_id,
            point["title"],
            scores[point_id],
            reasons_for(signals[point_id]),
        )
        # 3) 最后给它还没答对的练习
        for question in questions_by_point.get(point_id, ()):
            push(
                KIND_QUESTION,
                question["id"],
                point_id,
                question["title"],
                scores[point_id],
                [f"“{point['title']}”的相关练习，尚未答对"],
            )

    # 补足基础路径：按章节顺序给其余非已掌握知识点；这些条目没有个性化信号，score 为 null
    for point in ordered:
        if len(items) >= limit:
            break
        point_id = point["id"]
        if is_mastered(signals[point_id]):
            continue
        push(
            KIND_KNOWLEDGE,
            point_id,
            point_id,
            point["title"],
            scores[point_id],
            ["按章节顺序的基础路径"],
        )

    return items
