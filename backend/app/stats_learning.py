"""SPEC-006 学习进度与资源统计的纯计算（E056）。

用 Pandas 完成分组与去重；入参是从库里取出的普通结构，出参是 LearningStats，
便于直接对口径做单测。口径来自 SPEC-006 第 4 节：

- 完成率 = 当前仍标记完成且 `completed_at < to` 的**已发布**知识点数 / 当前已发布
  知识点数；分母为 0 返回 null。这是「当前快照近似」，不重建历史撤销记录，
  也不代表学习时长或掌握度。
- `from` 只过滤资源事件，不改变进度快照的口径。
- 资源访问按事件 UTC 日窗口聚合：同人、同版本、同类型、同 UTC 日只算一个去重事件；
  同一人访问两个版本是 2 个事件、1 个人。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pandas as pd

# CSV 落盘与比例口径复用既有实现，避免出现第二份公式注入防护
from .stats_assessment import ratio, to_csv

DAY_STAMP_FORMAT = "%Y-%m-%dT00:00:00Z"
DAY_FORMAT = "%Y-%m-%d"
DAY_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T00:00:00Z$")

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 366

PROGRESS_BASIS = "current_completed_before_to"

CSV_COLUMNS = (
    "section",
    "student_id",
    "completed_count",
    "completion_rate",
    "published_knowledge_count",
    "resource_id",
    "unique_students",
    "dedup_events",
    "window_from",
    "window_to",
    "progress_basis",
)


def parse_day_boundary(raw, name: str) -> datetime:
    """只接受 UTC 整日边界 `YYYY-MM-DDT00:00:00Z`；非整日由调用方转 422。"""
    if not isinstance(raw, str) or not DAY_STAMP_RE.match(raw):
        raise ValueError(name)
    return datetime.strptime(raw, DAY_STAMP_FORMAT).replace(tzinfo=timezone.utc)


def default_window(now: datetime) -> tuple[datetime, datetime]:
    """默认最近 30 个 UTC 自然日，截止到当前 UTC 日的下一日 00:00。

    右端取「下一日 00:00」而不是「此刻」：资源事件按 UTC 日记录，用时刻做右界
    会把当日记录当成精确访问时刻处理。
    """
    today = now.astimezone(timezone.utc).date()
    to_dt = datetime.combine(
        today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )
    from_dt = to_dt - timedelta(days=DEFAULT_WINDOW_DAYS)
    return from_dt, to_dt


def stamp(moment: datetime) -> str:
    return moment.strftime(DAY_STAMP_FORMAT)


def day_of(moment: datetime) -> str:
    return moment.strftime(DAY_FORMAT)


def summarize_progress(*, student_ids, published_knowledge_ids, records, to_stamp: str) -> dict:
    """当前在册学生的完成情况快照。

    student_ids：当前有效在册学生（已退班者不在内）。
    published_knowledge_ids：当前已发布知识点（可带章节筛选）。
    records：[{student_id, knowledge_id, completed, completed_at}]。
    """
    published = set(published_knowledge_ids)
    denominator = len(published)
    frame = pd.DataFrame(
        list(records or []),
        columns=["student_id", "knowledge_id", "completed", "completed_at"],
    )
    if not frame.empty and published:
        frame = frame[frame["knowledge_id"].isin(published)]
        frame = frame[frame["completed"] == 1]
        # 先剔除没有完成时间的记录，再比较时间字符串，避免空值与字符串比较
        frame = frame[frame["completed_at"].notna()]
        frame = frame[frame["completed_at"].astype(str) < to_stamp]
    else:
        frame = frame.iloc[0:0]
    grouped = (
        frame.groupby("student_id")["knowledge_id"].nunique().to_dict()
        if not frame.empty
        else {}
    )
    students = []
    for student_id in student_ids:
        completed_count = int(grouped.get(student_id, 0))
        students.append(
            {
                "student_id": student_id,
                "completed_count": completed_count,
                "completion_rate": ratio(completed_count, denominator),
            }
        )
    return {"published_knowledge_count": denominator, "students": students}


def summarize_resources(*, events, resource_of_version) -> list[dict]:
    """资源访问分布：按资料聚合去重人数与去重事件数。

    events：已按 UTC 日窗口（与章节）过滤的
    [{student_id, resource_version_id, event_kind, event_day}]。
    """
    frame = pd.DataFrame(
        list(events or []),
        columns=["student_id", "resource_version_id", "event_kind", "event_day"],
    )
    if frame.empty:
        return []
    frame = frame.assign(resource_id=frame["resource_version_id"].map(resource_of_version))
    frame = frame[frame["resource_id"].notna()]
    if frame.empty:
        return []
    frame = frame.assign(resource_id=frame["resource_id"].astype(int))
    frame = frame.drop_duplicates(
        subset=["student_id", "resource_version_id", "event_kind", "event_day"]
    )
    grouped = frame.groupby("resource_id").agg(
        unique_students=("student_id", "nunique"),
        dedup_events=("student_id", "size"),
    )
    return [
        {
            "resource_id": int(resource_id),
            "unique_students": int(row["unique_students"]),
            "dedup_events": int(row["dedup_events"]),
        }
        for resource_id, row in grouped.sort_index().iterrows()
    ]


def to_csv_rows(payload: dict) -> list[dict]:
    """CSV 明细：进度与资源两个 section，列固定为 CSV_COLUMNS。"""
    window = payload["window"]
    shared = {
        "published_knowledge_count": payload["published_knowledge_count"],
        "window_from": window["from"],
        "window_to": window["to"],
        "progress_basis": payload["progress_basis"],
    }
    rows = [{"section": "progress", **shared, **student} for student in payload["students"]]
    rows += [{"section": "resource", **shared, **resource} for resource in payload["resources"]]
    return rows


def csv_body(payload: dict) -> str:
    return to_csv(CSV_COLUMNS, to_csv_rows(payload))
