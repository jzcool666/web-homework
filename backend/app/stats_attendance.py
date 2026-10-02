"""SPEC-003 出勤与风险因素统计的纯计算（E055）。

不依赖 Flask 与 SQLAlchemy：入参是从库里取出的普通结构，出参是 AttendanceStats
的各块；分组与相关系数用 Pandas 完成。口径来自 SPEC-003 第 4 节：

- 窗口按任务的 `opens_at` 选择，且只纳入**已结算**任务；进行中的任务不进分母。
- 出勤率 = (present + late) / (present + late + absent)：请假从分母中排除，
  未结算的 pending 也不计入。分子分母都为 0 时返回 null，不写 0%。
- 相关系数只用「同窗口出勤率与百分制平均测评分数**都有值**」的学生；
  共同样本 n ≥ 5 且两列取值都非恒定，才用 Pandas 计算 Pearson，否则返回 null
  并给出原因。相关不代表因果（SPEC-003 第 1 节非目标）。
"""

from __future__ import annotations

import math

import pandas as pd

from .stats_assessment import ratio, to_csv

COUNT_KEYS = ("present", "late", "leave", "absent")
MIN_CORRELATION_SAMPLE = 5

CSV_COLUMNS = (
    "section",
    "student_id",
    "student_no",
    "display_name",
    "settled_tasks",
    "present",
    "late",
    "leave",
    "absent",
    "attendance_rate",
    "coefficient",
    "n",
    "reason",
    "window_from",
    "window_to",
)

EMPTY_COUNTS = {key: 0 for key in COUNT_KEYS}


def attendance_rate(counts: dict) -> float | None:
    """请假排除、缺席计入分母；分母为 0 返回 null。"""
    attended = counts.get("present", 0) + counts.get("late", 0)
    return ratio(attended, attended + counts.get("absent", 0))


def summarize_attendance(*, settled_tasks, records, student_meta) -> dict:
    """settled_tasks：窗口内已结算任务数；records：[task_id, student_id, status]；
    student_meta：student_id → 含 student_no/display_name 的对象（可为空）。
    """
    frame = pd.DataFrame(
        list(records or []), columns=["task_id", "student_id", "status"]
    )
    if not frame.empty:
        # 只统计四种终态；理论上已结算任务不该再有 pending，出现也不计入
        frame = frame[frame["status"].isin(COUNT_KEYS)]

    counts = dict(EMPTY_COUNTS)
    students: list[dict] = []
    if not frame.empty:
        for key in COUNT_KEYS:
            counts[key] = int((frame["status"] == key).sum())
        grouped = frame.groupby(["student_id", "status"]).size().unstack(fill_value=0)
        for student_id, row in grouped.iterrows():
            student_counts = {key: int(row.get(key, 0)) for key in COUNT_KEYS}
            meta = student_meta.get(int(student_id))
            students.append(
                {
                    "student_id": int(student_id),
                    "student_no": getattr(meta, "student_no", None),
                    "display_name": getattr(meta, "display_name", None),
                    "counts": student_counts,
                    "attendance_rate": attendance_rate(student_counts),
                }
            )
        students.sort(key=lambda item: item["student_id"])

    return {
        "settled_tasks": int(settled_tasks),
        "counts": counts,
        "attendance_rate": attendance_rate(counts),
        "students": students,
    }


def pearson_correlation(*, pairs) -> dict:
    """pairs：[student_id, attendance_rate, mean_percent]，只含两列都有值的学生。"""
    frame = pd.DataFrame(
        list(pairs or []), columns=["student_id", "attendance_rate", "mean_percent"]
    )
    n = int(len(frame))
    if n < MIN_CORRELATION_SAMPLE:
        return {
            "coefficient": None,
            "n": n,
            "reason": f"同时具备出勤与成绩的学生只有 {n} 名，少于 {MIN_CORRELATION_SAMPLE} 名",
        }
    if frame["attendance_rate"].nunique() < 2 or frame["mean_percent"].nunique() < 2:
        return {
            "coefficient": None,
            "n": n,
            "reason": "至少一列取值恒定，无法计算相关系数",
        }
    coefficient = float(frame["attendance_rate"].corr(frame["mean_percent"]))
    if math.isnan(coefficient):  # 理论上已被上面的方差检查挡住，这里兜底
        return {
            "coefficient": None,
            "n": n,
            "reason": "至少一列取值恒定，无法计算相关系数",
        }
    return {"coefficient": round(coefficient, 4), "n": n, "reason": None}


def mean_percent_by_student(*, rows) -> dict[int, float | None]:
    """rows：[student_id, percent]。同一学生有多条取平均；全为 null 记 null。"""
    frame = pd.DataFrame(list(rows or []), columns=["student_id", "percent"])
    if frame.empty:
        return {}
    frame = frame[frame["percent"].notna()]
    if frame.empty:
        return {}
    grouped = frame.groupby("student_id")["percent"].mean()
    return {int(student_id): round(float(value), 2) for student_id, value in grouped.items()}


def to_csv_rows(payload: dict) -> list[dict]:
    """CSV 明细：summary、student、correlation 三个 section，列固定为 CSV_COLUMNS。"""
    window = payload["window"]
    shared = {"window_from": window["from"], "window_to": window["to"]}
    correlation = payload["correlation"]
    rows = [
        {
            "section": "summary",
            **shared,
            "settled_tasks": payload["settled_tasks"],
            **payload["counts"],
            "attendance_rate": payload["attendance_rate"],
            **correlation,
        }
    ]
    rows += [
        {
            "section": "student",
            **shared,
            "student_id": student["student_id"],
            "student_no": student["student_no"],
            "display_name": student["display_name"],
            **student["counts"],
            "attendance_rate": student["attendance_rate"],
        }
        for student in payload["students"]
    ]
    rows.append({"section": "correlation", **shared, **correlation})
    return rows


def csv_body(payload: dict) -> str:
    return to_csv(CSV_COLUMNS, to_csv_rows(payload))
