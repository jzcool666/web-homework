"""SPEC-010 测评统计的纯计算部分（E057）。

这里不依赖 Flask 与 SQLAlchemy：入参是从库里取出的普通结构，出参是
AssessmentStats 的各个块；知识点首答使用 Pandas 分组聚合。口径来自 SPEC-010 第 4 节：

- 提交率分母是**发布时固定的名单**，不是当前在班人数。
- 平均分与分数段只统计**已提交**的提交（白卷也算已提交，得 0 分）。
- 每道题的机会数分母是已提交人数（**含漏答**）；空答案不增计任何选项，
  漏答单独给数，便于与选项分布对账。
- 知识点首答取该学生该题目**全历史最早**的已提交作答，再按其 submitted_at
  是否落在窗口内筛选——不是「窗口内第一次」。
"""

from __future__ import annotations

import csv
import io

import pandas as pd

# 分数段：0—<60、60—<70、70—<80、80—<90、90—100
SCORE_BUCKETS = (
    ("0-<60", 0, 60),
    ("60-<70", 60, 70),
    ("70-<80", 70, 80),
    ("80-<90", 80, 90),
    ("90-100", 90, 101),
)
RATIO_DIGITS = 4
PERCENT_DIGITS = 2


def percent_of(score: int | None, total: int | None) -> float | None:
    """百分制得分；总分缺失或为 0 时返回 null，不假造 0%。"""
    if score is None or not total:
        return None
    return round(score * 100.0 / total, PERCENT_DIGITS)


def ratio(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(numerator / denominator, RATIO_DIGITS)


def mean(values) -> float | None:
    items = [value for value in values if value is not None]
    if not items:
        return None
    return round(sum(items) / len(items), PERCENT_DIGITS)


def bucket_label(percent: float | None) -> str | None:
    """按分数段落桶；无百分制得分时不落任何桶。"""
    if percent is None:
        return None
    for label, low, high in SCORE_BUCKETS:
        if low <= percent < high:
            return label
    # 100 分（或理论上的溢出）归入最高段
    return SCORE_BUCKETS[-1][0] if percent >= SCORE_BUCKETS[-1][1] else SCORE_BUCKETS[0][0]


def summarize_assessment(*, assessment_id: int, roster_count: int, percents, blank_count: int) -> dict:
    """单个测评的名单/提交/白卷/提交率/平均分。"""
    submitted_count = len(percents)
    return {
        "id": assessment_id,
        "roster_count": roster_count,
        "submitted_count": submitted_count,
        "blank_count": blank_count,
        "submission_rate": ratio(submitted_count, roster_count),
        "mean_percent": mean(percents),
    }


def summarize_item(*, item_id: int, responses) -> dict:
    """单道题的选项分布与正确率。

    responses 是已提交提交中该题的 (selected, correct) 列表，漏答按 selected=[] 计入
    机会数（分母）但不给任何选项加数。
    """
    answered_count = len(responses)
    unanswered_count = 0
    correct_count = 0
    option_counts: dict[str, int] = {}
    for selected, correct in responses:
        if not selected:
            unanswered_count += 1
        if correct:
            correct_count += 1
        for key in selected:
            option_counts[key] = option_counts.get(key, 0) + 1
    return {
        "item_id": item_id,
        "answered_count": answered_count,
        "unanswered_count": unanswered_count,
        "correct_count": correct_count,
        "correct_rate": ratio(correct_count, answered_count),
        "option_counts": option_counts,
    }


def score_bucket_rows(percents) -> list[dict]:
    counts = {label: 0 for label, _low, _high in SCORE_BUCKETS}
    for percent in percents:
        label = bucket_label(percent)
        if label is not None:
            counts[label] += 1
    return [{"range": label, "count": counts[label]} for label, _low, _high in SCORE_BUCKETS]


def summarize_knowledge(rows) -> list[dict]:
    """rows 是窗口内的首答记录 (knowledge_id, correct)。"""
    if not rows:
        return []
    frame = pd.DataFrame(rows, columns=["knowledge_id", "correct"])
    frame["correct"] = frame["correct"].astype(int)
    grouped = frame.groupby("knowledge_id", sort=True).agg(
        first_attempt_count=("correct", "size"),
        first_correct_count=("correct", "sum"),
    )
    result = []
    for knowledge_id, row in grouped.iterrows():
        attempts = int(row["first_attempt_count"])
        correct_count = int(row["first_correct_count"])
        result.append(
            {
                "knowledge_id": int(knowledge_id),
                "first_attempt_count": attempts,
                "first_correct_count": correct_count,
                "first_accuracy": ratio(correct_count, attempts),
            }
        )
    return result


def csv_safe(value) -> str:
    """CSV 公式注入防护（APIC 第 7 节）：以 =、+、-、@ 开头的文本加安全前缀。"""
    text = "" if value is None else str(value)
    if text[:1] in {"=", "+", "-", "@"}:
        return "'" + text
    return text


def to_csv(columns, rows) -> str:
    """UTF-8 BOM + 统一列；列名与行值都过公式注入防护。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(list(columns))
    for row in rows:
        writer.writerow([csv_safe(row.get(column)) for column in columns])
    return "﻿" + buffer.getvalue()
