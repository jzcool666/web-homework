"""SPEC-004 学习预警的纯计算（E063/E064）。

不依赖 Flask 与 SQLAlchemy：入参是从库里取出的普通结构（每个学生的出勤率、
完成率、首答正确率与各自样本量），出参是每个学生的 Warning。规则来自
SPEC-004 第 4 节与 ADR-007 第 3 条：

- 风险因素 a=1-出勤率、p=1-完成率、e=1-知识点首答正确率，权重 0.3/0.2/0.5；
  只对**可用**因素按权重归一化，score=100×加权和，缺失因素不当作 0 分。
- 可用性门槛：出勤要有已结算的有效分母；进度要有明确完成/未完成记录且知识点
  分母大于 0；答题至少 3 次首答。可用项少于 2 个记 insufficient，不给 score。
- 等级是项目规则（<30 low、<60 medium、否则 high），**不是**经训练校准的学业
  风险概率，也不能读成挂科预测（SPEC-004 第 1 节非目标）。
- 只有三因素齐全的学生参与聚类；这类学生 n≥10 且不同向量≥3 时用
  KMeans(k=3, random_state=42, n_init=10) 分组，按各簇中心平均风险升序编号
  0/1/2。聚类只做班级分组的描述，不覆盖规则等级。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from .stats_assessment import ratio

ALGORITHM_VERSION = "warn-rules-v1"
DISCLAIMER = "等级由项目规则计算，不是经训练校准的学业风险概率"

# 插入顺序即聚类向量的列顺序，保持稳定
FACTOR_WEIGHTS = {"attendance": 0.3, "progress": 0.2, "accuracy": 0.5}
FACTOR_LABELS = {"attendance": "出勤", "progress": "学习进度", "accuracy": "知识点首答"}

MIN_AVAILABLE_FACTORS = 2
MIN_ACCURACY_ATTEMPTS = 3
LOW_THRESHOLD = 30.0
HIGH_THRESHOLD = 60.0

MIN_CLUSTER_STUDENTS = 10
MIN_CLUSTER_VECTORS = 3
CLUSTER_K = 3
CLUSTER_RANDOM_STATE = 42
CLUSTER_N_INIT = 10


def _risk(rate: float | None) -> float | None:
    """把「表现率」变成「风险值」：数值缺失即为不可用，不按 0 处理。"""
    if rate is None:
        return None
    return round(1.0 - rate, 4)


def build_factors(*, attendance_rate, completion_rate, first_accuracy) -> dict:
    return {
        "attendance": _risk(attendance_rate),
        "progress": _risk(completion_rate),
        "accuracy": _risk(first_accuracy),
    }


def score_factors(factors: dict) -> tuple[float | None, str, list[str]]:
    """按可用因素归一化打分；可用项不足 2 个返回 insufficient。"""
    available = [name for name in FACTOR_WEIGHTS if factors.get(name) is not None]
    if len(available) < MIN_AVAILABLE_FACTORS:
        return None, "insufficient", available
    total_weight = sum(FACTOR_WEIGHTS[name] for name in available)
    weighted = sum(FACTOR_WEIGHTS[name] * factors[name] for name in available)
    score = round(100.0 * weighted / total_weight, 2)
    if score < LOW_THRESHOLD:
        level = "low"
    elif score < HIGH_THRESHOLD:
        level = "medium"
    else:
        level = "high"
    return score, level, available


def build_reasons(*, factors: dict, samples: dict, available: list[str], level: str) -> list[str]:
    """逐项说明贡献与未计入的原因，便于教师核对而不是只看一个分数。"""
    reasons: list[str] = []
    for name in FACTOR_WEIGHTS:
        label = FACTOR_LABELS[name]
        value = factors.get(name)
        if value is None:
            if name == "attendance":
                reasons.append(f"{label}：没有已结算任务的有效分母，未计入")
            elif name == "progress":
                reasons.append(f"{label}：没有明确的完成/未完成记录，未计入")
            else:
                reasons.append(
                    f"{label}：首答样本 {samples.get(name, 0)} 次，少于 {MIN_ACCURACY_ATTEMPTS} 次，未计入"
                )
            continue
        reasons.append(
            f"{label}：风险 {value:.2f}（{label}表现 {1 - value:.2f}），权重 {FACTOR_WEIGHTS[name]:.1f}"
        )
    if level == "insufficient":
        reasons.append(f"可用因素只有 {len(available)} 项，少于 {MIN_AVAILABLE_FACTORS} 项，未评分")
    return reasons


def assign_clusters(rows: list[dict]) -> tuple[dict[int, int], str | None]:
    """按 SPEC-004 第 4 节第 4 条给三因素齐全的学生分组。

    rows 为 [{student_id, factors}]。返回 (student_id → cluster_label, 未聚类原因)。
    """
    complete = [
        row
        for row in rows
        if all(row["factors"].get(name) is not None for name in FACTOR_WEIGHTS)
    ]
    if len(complete) < MIN_CLUSTER_STUDENTS:
        return {}, f"三因素齐全的学生只有 {len(complete)} 名，少于 {MIN_CLUSTER_STUDENTS} 名，未分组"

    frame = pd.DataFrame(
        [[row["factors"][name] for name in FACTOR_WEIGHTS] for row in complete],
        columns=list(FACTOR_WEIGHTS),
    )
    if len(frame.drop_duplicates()) < MIN_CLUSTER_VECTORS:
        return {}, f"三因素向量只有 {len(frame.drop_duplicates())} 种，少于 {MIN_CLUSTER_VECTORS} 种，未分组"

    model = KMeans(
        n_clusters=CLUSTER_K,
        random_state=CLUSTER_RANDOM_STATE,
        n_init=CLUSTER_N_INIT,
    )
    labels = model.fit_predict(frame.to_numpy(dtype=float))
    # 按各簇中心的平均风险升序编号：0 风险最低、2 风险最高
    order = np.argsort(model.cluster_centers_.mean(axis=1), kind="stable")
    rank = {int(cluster): position for position, cluster in enumerate(order)}
    return {
        row["student_id"]: rank[int(label)] for row, label in zip(complete, labels)
    }, None


def summarize_warnings(*, students: list[dict]) -> tuple[list[dict], str | None]:
    """students: [{student_id, attendance_rate, completion_rate, first_accuracy, sample_counts}]。

    返回 (Warning 行, 未聚类原因)。sample_counts 是每名学生自己的样本量，
    键与 factors 一致（attendance/progress/accuracy）。
    """
    rows = []
    for student in students:
        factors = build_factors(
            attendance_rate=student["attendance_rate"],
            completion_rate=student["completion_rate"],
            first_accuracy=student["first_accuracy"],
        )
        samples = dict(student.get("sample_counts") or {})
        score, level, available = score_factors(factors)
        rows.append(
            {
                "student_id": student["student_id"],
                "factors": factors,
                "score": score,
                "level": level,
                "available_factors": available,
                "sample_counts": samples,
                "reasons": build_reasons(
                    factors=factors, samples=samples, available=available, level=level
                ),
            }
        )

    cluster_labels, cluster_reason = assign_clusters(rows=rows)
    for row in rows:
        row["cluster_label"] = cluster_labels.get(row["student_id"])
    rows.sort(key=lambda row: row["student_id"])
    return rows, cluster_reason


__all__ = [
    "ALGORITHM_VERSION",
    "DISCLAIMER",
    "FACTOR_LABELS",
    "FACTOR_WEIGHTS",
    "MIN_ACCURACY_ATTEMPTS",
    "MIN_CLUSTER_STUDENTS",
    "MIN_CLUSTER_VECTORS",
    "assign_clusters",
    "build_factors",
    "build_reasons",
    "ratio",
    "score_factors",
    "summarize_warnings",
]
