"""SPEC-014 实验统计的纯计算部分（E058）。

不依赖 Flask 与 SQLAlchemy：入参是从库里取出的普通结构，出参是 ExperimentStats
的各块；按实验与学生聚合使用 Pandas。口径来自 SPEC-014 第 4 节：

- 参与人数：窗口内**至少提交过一次预测**的本班在册学生数。同一学生同一实验
  多次尝试只算一个参与者。
- 通过人数：窗口内**至少有一次通过**的同类学生数；任一次通过即计入。
- 尝试数：逐条计数、不去重（幂等重试在写入时已不新增记录，见 SPEC-013）。
- 单实验通过率 = 该实验通过学生 / 该实验参与学生；无参与返回 null，不写 0。
- 顶层通过人数指**至少通过一个实验**的学生，与逐实验口径分开给出，
  不把「通过过某个实验」误写成「通过了全部实验」。
"""

from __future__ import annotations

import pandas as pd

from .stats_assessment import ratio, to_csv

# CSV 列顺序固定，供测试与使用说明引用（APIC 第 7 节）
CSV_COLUMNS = (
    "section",
    "experiment_id",
    "experiment_title",
    "window_from",
    "window_to",
    "published_count",
    "participants",
    "passed_students",
    "pass_rate",
    "attempt_count",
)

EMPTY_EXPERIMENT_ROW = {
    "participants": 0,
    "passed_students": 0,
    "attempt_count": 0,
    "pass_rate": None,
}


def summarize_experiment_stats(*, experiments, attempt_rows) -> dict:
    """experiments 为作用域内的 (id, title)；attempt_rows 为窗口内的
    (experiment_id, student_id, passed) 三元组，且已限定为本班在册学生。
    """
    frame = pd.DataFrame(
        list(attempt_rows), columns=["experiment_id", "student_id", "passed"]
    )
    if not frame.empty:
        frame["passed"] = frame["passed"].astype(int)

    per_experiment: dict[int, dict] = {}
    if not frame.empty:
        grouped = frame.groupby("experiment_id").agg(
            participants=("student_id", "nunique"),
            attempt_count=("passed", "size"),
        )
        passed_counts = (
            frame.loc[frame["passed"] == 1].groupby("experiment_id")["student_id"].nunique()
        )
        for experiment_id, row in grouped.iterrows():
            key = int(experiment_id)
            participants = int(row["participants"])
            passed_students = int(passed_counts.get(key, 0))
            per_experiment[key] = {
                "participants": participants,
                "passed_students": passed_students,
                "attempt_count": int(row["attempt_count"]),
                "pass_rate": ratio(passed_students, participants),
            }

    experiment_rows = []
    for experiment_id, title in experiments:
        block = per_experiment.get(int(experiment_id), EMPTY_EXPERIMENT_ROW)
        experiment_rows.append({"experiment_id": int(experiment_id), "title": title, **block})
    # 易错/参与排行：参与人数多的在前，同人参与按 experiment_id 稳定排序
    experiment_rows.sort(key=lambda row: (-row["participants"], row["experiment_id"]))

    if frame.empty:
        participants = passed_students = attempt_count = 0
    else:
        participants = int(frame["student_id"].nunique())
        passed_students = int(frame.loc[frame["passed"] == 1, "student_id"].nunique())
        attempt_count = int(len(frame))

    return {
        "published_count": len(experiments),
        "participants": participants,
        "passed_students": passed_students,
        "pass_rate": ratio(passed_students, participants),
        "attempt_count": attempt_count,
        "experiments": experiment_rows,
    }


def to_csv_rows(payload: dict) -> list[dict]:
    """CSV 明细：summary 一行给出总量，experiment 若干行为逐实验展开。

    两个 section 的数字与 JSON 同名段一一对应，便于导出后对账。
    """
    window = payload["window"]
    rows = [
        {
            "section": "summary",
            "window_from": window["from"],
            "window_to": window["to"],
            "published_count": payload["published_count"],
            "participants": payload["participants"],
            "passed_students": payload["passed_students"],
            "pass_rate": payload["pass_rate"],
            "attempt_count": payload["attempt_count"],
        }
    ]
    for block in payload["experiments"]:
        rows.append(
            {
                "section": "experiment",
                "experiment_id": block["experiment_id"],
                "experiment_title": block["title"],
                "window_from": window["from"],
                "window_to": window["to"],
                "participants": block["participants"],
                "passed_students": block["passed_students"],
                "pass_rate": block["pass_rate"],
                "attempt_count": block["attempt_count"],
            }
        )
    return rows


def csv_body(payload: dict) -> str:
    return to_csv(CSV_COLUMNS, to_csv_rows(payload))
