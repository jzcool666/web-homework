"""SPEC-013 实验辅助与结果验证：T-013-01 至 T-013-04 及配套边界。

固定数据 + 独立数据库：夹具用 `tmp_path` 显式指定 DATABASE_URL 与 UPLOAD_DIR，
不触碰仓库内的 instance/。标准状态一律由 simulator.py 重放得到，测试断言的是
规格人工推演的结果。
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app import create_app
from app.experiment_service import (
    CheckpointError,
    checkpoint_contexts,
    expected_states,
    first_difference,
    replay_checkpoints,
    state_range,
)
from helpers import (
    API,
    DEFAULT_PASSWORD,
    api_call,
    create_admin,
    get_csrf,
    login,
    register,
    scalar,
    sqlite_url,
    upgrade,
)

# ---- 纯逻辑：检查点重放 ----

COUNTER_M6_FROM_4 = {"initial_q": 4, "modulus": 6}


def cycles(count: int) -> list[dict]:
    """count 个完整时钟周期 = count 个有效上升沿。"""
    return [{"op": op} for _ in range(count) for op in ("toggle_clock", "toggle_clock")]


def test_replay_checkpoints_uses_simulator_rules():
    checkpoints = replay_checkpoints("counter", COUNTER_M6_FROM_4, cycles(4))
    assert [cp["index"] for cp in checkpoints] == [0, 1, 2, 3]
    assert [cp["step_no"] for cp in checkpoints] == [1, 2, 3, 4]
    assert [cp["q_before"] for cp in checkpoints] == [4, 5, 0, 1]
    assert expected_states(checkpoints) == [5, 0, 1, 2], "T-013-01 的标准序列"
    # 上下文只含输入，不含标准答案
    for context in checkpoint_contexts(checkpoints):
        assert set(context) == {"index", "step_no", "inputs"}

    # 下降沿与单独改输入不产生检查点
    mixed = replay_checkpoints(
        "d", {"initial_q": 0}, [{"op": "set", "inputs": {"d": 1}}, {"op": "toggle_clock"}]
    )
    assert len(mixed) == 1 and mixed[0]["q"] == 1

    # reset_view 之前的拍不计入
    reset = replay_checkpoints(
        "d",
        {"initial_q": 0},
        [{"op": "toggle_clock"}, {"op": "reset_view"}, {"op": "toggle_clock"}, {"op": "toggle_clock"}],
    )
    assert len(reset) == 1 and reset[0]["q"] == 0

    assert replay_checkpoints("d", {"initial_q": 0}, [{"op": "set", "inputs": {"d": 1}}]) == []


def test_first_difference_and_state_range():
    assert first_difference([5, 0, 1, 2], [5, 0, 1, 2]) is None
    assert first_difference([5, 0, 1, 2], [5, 6, 1, 2]) == 1
    assert first_difference([5, 0], []) == 0
    assert state_range("d") == (0, 1)
    assert state_range("jk") == (0, 1)
    assert state_range("counter") == (0, 15)
    assert state_range("shift") == (0, 15)


# ---- 接口夹具 ----

def login_as(app, login_name: str, password: str = DEFAULT_PASSWORD):
    client = app.test_client()
    csrf = get_csrf(client)
    response = login(client, csrf, login_name=login_name, password=password)
    assert response.status_code == 200, response.get_data(as_text=True)
    return client, response.get_json()["data"]["csrf_token"]


def _create_teacher(app, admin, admin_csrf, login_name: str):
    response = api_call(
        admin,
        "post",
        f"{API}/users",
        csrf_token=admin_csrf,
        json={
            "login_name": login_name,
            "display_name": login_name,
            "password": DEFAULT_PASSWORD,
            "role": "teacher",
        },
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def _register_student(app, login_name: str, student_no: str):
    client = app.test_client()
    csrf = get_csrf(client)
    response = register(client, csrf, login_name=login_name, student_no=student_no)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def create_knowledge(client, csrf) -> dict:
    chapter = api_call(
        client,
        "post",
        f"{API}/chapters",
        csrf_token=csrf,
        json={"title": "第五单元 计数器", "sort_order": 5, "published": True},
    ).get_json()["data"]
    return api_call(
        client,
        "post",
        f"{API}/knowledge-points",
        csrf_token=csrf,
        json={
            "chapter_id": chapter["id"],
            "title": "模 6 计数器与 5→0 回卷",
            "body_md": "模 6 计数器状态为 0000—0101。",
            "sort_order": 1,
            "published": True,
        },
    ).get_json()["data"]


def create_experiment(client, csrf, knowledge_id: int, **over):
    payload = {
        "title": "模 6 计数器：从 4 开始的四拍",
        "knowledge_id": knowledge_id,
        "simulator_type": "counter",
        "config": dict(COUNTER_M6_FROM_4),
        "steps_md": "初态 0100，连续切换时钟四拍。",
        "input_sequence": cycles(4),
        "published": True,
    }
    payload.update(over)
    return api_call(client, "post", f"{API}/experiments", csrf_token=csrf, json=payload)


def submit(client, csrf, experiment_id: int, version: int, predictions, key=None, **extra):
    payload = {
        "experiment_version": version,
        "predictions": predictions,
        "request_key": key or str(uuid.uuid4()),
    }
    payload.update(extra)
    return api_call(
        client, "post", f"{API}/experiments/{experiment_id}/attempts", csrf_token=csrf, json=payload
    )


@pytest.fixture
def lab(tmp_path: Path):
    """管理员 + 教师 + 一个班（两名已入班学生）+ 未入班学生 + 一个可预测实验。"""
    app = create_app(
        "testing",
        {
            "DATABASE_URL": sqlite_url(tmp_path / "attempt.sqlite"),
            "UPLOAD_DIR": str(tmp_path / "uploads"),
        },
    )
    upgrade(app)
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", "Adm1nPass!23")
    teacher = _create_teacher(app, admin, admin_csrf, "teacher_aaa")

    school_class = api_call(
        admin,
        "post",
        f"{API}/classes",
        csrf_token=admin_csrf,
        json={"name": "软件工程示例班", "teacher_id": teacher["id"]},
    ).get_json()["data"]

    student_a = _register_student(app, "stu_a0001", "20240001")
    student_b = _register_student(app, "stu_b0001", "20240002")
    outsider = _register_student(app, "stu_x0001", "20240003")
    for student in (student_a, student_b):
        response = api_call(
            admin,
            "put",
            f"{API}/classes/{school_class['id']}/enrollments",
            csrf_token=admin_csrf,
            json={"student_id": student["id"], "active": True},
        )
        assert response.status_code == 200, response.get_data(as_text=True)

    teacher_client, teacher_csrf = login_as(app, "teacher_aaa")
    knowledge = create_knowledge(teacher_client, teacher_csrf)
    experiment = create_experiment(
        teacher_client, teacher_csrf, knowledge["id"]
    ).get_json()["data"]

    try:
        yield {
            "app": app,
            "teacher": (teacher_client, teacher_csrf),
            "student_a": login_as(app, "stu_a0001"),
            "student_b": login_as(app, "stu_b0001"),
            "outsider": login_as(app, "stu_x0001"),
            "admin": (admin, admin_csrf),
            "knowledge": knowledge,
            "experiment": experiment,
            "student_ids": {
                "a": student_a["id"],
                "b": student_b["id"],
                "x": outsider["id"],
            },
        }
    finally:
        app.extensions["db_engine"].dispose()


# ---- T-013-01 完全匹配通过 ----

def test_T013_01_correct_predictions_pass(lab):
    student, csrf = lab["student_a"]
    experiment = lab["experiment"]

    assert len(experiment["checkpoints"]) == 4
    assert experiment["config"] == COUNTER_M6_FROM_4

    response = submit(student, csrf, experiment["id"], experiment["version"], [5, 0, 1, 2])
    assert response.status_code == 201, response.get_data(as_text=True)
    result = response.get_json()["data"]

    assert result["passed"] is True
    assert result["first_error_index"] is None
    assert result["expected"] == [5, 0, 1, 2]
    assert result["actual"] == [5, 0, 1, 2]
    assert result["experiment_id"] == experiment["id"], "历史页需要知道记录属于哪个实验"
    assert result["experiment_version"] == experiment["version"]
    assert len(result["explanations"]) == 4
    assert all("预测正确" in line for line in result["explanations"])

    # 通过记录计一次完整尝试，且标准答案不被学生改动
    assert scalar(lab["app"], "SELECT COUNT(*) FROM experiment_attempts") == 1
    assert scalar(lab["app"], "SELECT passed FROM experiment_attempts") == 1


# ---- T-013-02 首错下标从 0 开始并指出正确值 ----

def test_T013_02_first_error_index_is_zero_based(lab):
    student, csrf = lab["student_a"]
    experiment = lab["experiment"]

    response = submit(student, csrf, experiment["id"], experiment["version"], [5, 6, 1, 2])
    assert response.status_code == 201, response.get_data(as_text=True)
    result = response.get_json()["data"]

    assert result["passed"] is False
    assert result["first_error_index"] == 1, "首错下标从 0 开始，第二拍即 index=1"
    assert result["expected"] == [5, 0, 1, 2]
    assert result["actual"] == [5, 6, 1, 2]

    # 界面据此显示「第 2 拍」；说明文字要写出正确答案
    second = result["explanations"][1]
    assert "第 2 拍" in second
    assert "0000" in second, "第二拍应回到 0"
    assert "0110" in second, "同时给出学生填错的值"
    assert "预测正确" in result["explanations"][0]

    # 后续拍仍然逐拍给出，便于对照
    assert len(result["explanations"]) == 4


# ---- T-013-03 不能伪造判分 ----

def test_T013_03_forged_fields_are_rejected_and_grading_stays_server_side(lab):
    student, csrf = lab["student_a"]
    experiment = lab["experiment"]
    version = experiment["version"]

    before = scalar(lab["app"], "SELECT COUNT(*) FROM experiment_attempts")

    for extra in (
        {"passed": True},
        {"expected": [5, 0, 1, 2]},
        {"actual": [5, 0, 1, 2]},
        {"input_sequence": []},
        {"first_error_index": None},
        {"student_id": lab["student_ids"]["b"]},
        {"experiment_id": experiment["id"]},
    ):
        # 直接构造 JSON，避免与助手的 experiment_id 形参重名
        payload = {
            "experiment_version": version,
            "predictions": [5, 0, 1, 2],
            "request_key": str(uuid.uuid4()),
            **extra,
        }
        response = api_call(
            student,
            "post",
            f"{API}/experiments/{experiment['id']}/attempts",
            csrf_token=csrf,
            json=payload,
        )
        assert response.status_code == 422, extra
        assert response.get_json()["error"]["details"]["unknown_fields"], extra

    assert scalar(lab["app"], "SELECT COUNT(*) FROM experiment_attempts") == before, "伪造请求不落库"

    # 带伪造成绩的请求被拒后，正常提交仍由服务器判分
    forged_wrong = submit(student, csrf, experiment["id"], version, [9, 9, 9, 9], passed=True)
    assert forged_wrong.status_code == 422

    honest = submit(student, csrf, experiment["id"], version, [9, 9, 9, 9])
    assert honest.status_code == 201
    assert honest.get_json()["data"]["passed"] is False, "预测全错就不能通过"

    # 客户端自带的输入序列不参与计算：标准答案仍来自实验快照
    tampered = submit(
        student, csrf, experiment["id"], version, [5, 0, 1, 2], input_sequence=cycles(1)
    )
    assert tampered.status_code == 422


# ---- T-013-04 request_key 幂等与本人历史 ----

def test_T013_04_request_key_idempotency(lab):
    student, csrf = lab["student_a"]
    experiment = lab["experiment"]
    version = experiment["version"]
    key = str(uuid.uuid4())

    first = submit(student, csrf, experiment["id"], version, [5, 0, 1, 2], key=key)
    assert first.status_code == 201
    attempt_id = first.get_json()["data"]["id"]

    # 同 key 同内容：返回原结果，不新增记录
    replay = submit(student, csrf, experiment["id"], version, [5, 0, 1, 2], key=key)
    assert replay.status_code == 200, "重试返回原对象而不是再建一条"
    assert replay.get_json()["data"]["id"] == attempt_id
    assert replay.get_json()["data"] == first.get_json()["data"]
    assert scalar(lab["app"], "SELECT COUNT(*) FROM experiment_attempts") == 1

    # 同 key 不同内容：409
    conflicting = submit(student, csrf, experiment["id"], version, [5, 6, 1, 2], key=key)
    assert conflicting.status_code == 409
    assert conflicting.get_json()["error"]["code"] == "DUPLICATE"
    assert scalar(lab["app"], "SELECT COUNT(*) FROM experiment_attempts") == 1

    # 换 key 提交新内容：新增一条
    second = submit(student, csrf, experiment["id"], version, [5, 6, 1, 2])
    assert second.status_code == 201
    assert second.get_json()["data"]["id"] != attempt_id
    assert scalar(lab["app"], "SELECT COUNT(*) FROM experiment_attempts") == 2

    # 已用于本实验的 key 拿去别的实验提交：内容不同 → 409
    other = create_experiment(
        *lab["teacher"], lab["knowledge"]["id"], title="另一个实验"
    ).get_json()["data"]
    moved = submit(student, csrf, other["id"], other["version"], [5, 0, 1, 2], key=key)
    assert moved.status_code == 409


def test_T013_04_history_is_own_records_only(lab):
    student_a, csrf_a = lab["student_a"]
    student_b, csrf_b = lab["student_b"]
    teacher, teacher_csrf = lab["teacher"]
    experiment = lab["experiment"]

    attempt = submit(student_a, csrf_a, experiment["id"], experiment["version"], [5, 6, 1, 2])
    assert attempt.status_code == 201
    attempt_id = attempt.get_json()["data"]["id"]

    mine = student_a.get(f"{API}/me/experiment-attempts?experiment_id={experiment['id']}")
    assert mine.status_code == 200
    assert [row["id"] for row in mine.get_json()["data"]] == [attempt_id]

    # 另一名学生看不到这条记录
    other = student_b.get(f"{API}/me/experiment-attempts?experiment_id={experiment['id']}")
    assert other.status_code == 200
    assert other.get_json()["data"] == []
    assert other.get_json()["meta"]["total"] == 0

    # 也没有按 id 读取他人尝试的入口：尝试必须属于自己才出现在历史里
    assert attempt_id not in [row["id"] for row in other.get_json()["data"]]

    # 教师没有个人实验记录
    assert teacher.get(f"{API}/me/experiment-attempts").status_code == 403

    # 学生 B 提交自己的记录后只看得到自己的
    submit(student_b, csrf_b, experiment["id"], experiment["version"], [5, 0, 1, 2])
    only_b = student_b.get(f"{API}/me/experiment-attempts").get_json()["data"]
    assert len(only_b) == 1
    assert student_a.get(f"{API}/me/experiment-attempts").get_json()["meta"]["total"] == 1


# ---- 其他边界 ----

def test_submission_validation_boundaries(lab):
    student, csrf = lab["student_a"]
    experiment = lab["experiment"]
    version = experiment["version"]

    # 长度必须等于检查点数
    short = submit(student, csrf, experiment["id"], version, [5, 0, 1])
    assert short.status_code == 422
    assert "4" in short.get_json()["error"]["details"]["fields"]["predictions"]

    long = submit(student, csrf, experiment["id"], version, [5, 0, 1, 2, 3])
    assert long.status_code == 422

    # 状态范围：计数器 0—15
    assert submit(student, csrf, experiment["id"], version, [5, 16, 1, 2]).status_code == 422
    assert submit(student, csrf, experiment["id"], version, [5, -1, 1, 2]).status_code == 422
    assert submit(student, csrf, experiment["id"], version, [5, True, 1, 2]).status_code == 422
    assert submit(student, csrf, experiment["id"], version, [5, "0", 1, 2]).status_code == 422
    assert submit(student, csrf, experiment["id"], version, "5012").status_code == 422

    # D/JK 只允许 0/1
    d_experiment = create_experiment(
        *lab["teacher"],
        lab["knowledge"]["id"],
        title="D 触发器实验",
        simulator_type="d",
        config={"initial_q": 0},
        input_sequence=cycles(2),
    ).get_json()["data"]
    assert submit(student, csrf, d_experiment["id"], d_experiment["version"], [1, 2]).status_code == 422
    assert submit(student, csrf, d_experiment["id"], d_experiment["version"], [1, 0]).status_code == 201

    # request_key 必须是 UUID
    assert submit(
        student, csrf, experiment["id"], version, [5, 0, 1, 2], key="not-a-uuid"
    ).status_code == 422

    # 旧版本 409，并要求刷新
    stale = submit(student, csrf, experiment["id"], version + 3, [5, 0, 1, 2])
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "VERSION_CONFLICT"
    assert stale.get_json()["error"]["details"]["current_version"] == version


def test_attempt_permissions(lab):
    student, csrf = lab["student_a"]
    teacher, teacher_csrf = lab["teacher"]
    admin, admin_csrf = lab["admin"]
    outsider, outsider_csrf = lab["outsider"]
    experiment = lab["experiment"]

    # 教师与管理员不能提交学生预测
    assert submit(teacher, teacher_csrf, experiment["id"], experiment["version"], [5, 0, 1, 2]).status_code == 403
    assert submit(admin, admin_csrf, experiment["id"], experiment["version"], [5, 0, 1, 2]).status_code == 403
    # 未入班学生没有课程访问权
    assert submit(outsider, outsider_csrf, experiment["id"], experiment["version"], [5, 0, 1, 2]).status_code == 403
    assert outsider.get(f"{API}/me/experiment-attempts").status_code == 403

    # 匿名：读接口 401；写接口先过 CSRF 再判身份，带匿名 CSRF 令牌后同样是 401
    fresh = lab["app"].test_client()
    assert fresh.get(f"{API}/me/experiment-attempts").status_code == 401
    anon_csrf = get_csrf(fresh)
    assert api_call(
        fresh,
        "post",
        f"{API}/experiments/{experiment['id']}/attempts",
        csrf_token=anon_csrf,
        json={"experiment_version": experiment["version"], "predictions": [5, 0, 1, 2],
              "request_key": str(uuid.uuid4())},
    ).status_code == 401
    # 无 CSRF 令牌的写请求按 SPEC-001 的公共规则返回 403
    assert fresh.post(f"{API}/experiments/{experiment['id']}/attempts").status_code == 403

    # 草稿实验学生不可见
    draft = create_experiment(
        teacher, teacher_csrf, lab["knowledge"]["id"], title="草稿实验", published=False
    ).get_json()["data"]
    assert submit(student, csrf, draft["id"], draft["version"], [5, 0, 1, 2]).status_code == 404
    assert student.get(f"{API}/experiments/{draft['id']}").status_code == 404

    # 不存在的实验
    assert submit(student, csrf, 99999, 1, [5, 0, 1, 2]).status_code == 404


def test_checkpoints_do_not_leak_expected_states(lab):
    student, _ = lab["student_a"]
    experiment = lab["experiment"]

    detail = student.get(f"{API}/experiments/{experiment['id']}").get_json()["data"]
    assert len(detail["checkpoints"]) == 4
    for context in detail["checkpoints"]:
        assert set(context) == {"index", "step_no", "inputs"}
        assert "q" not in context and "q_before" not in context

    # 未提交前，响应里不出现标准状态序列
    listed = student.get(f"{API}/experiments?page_size=100").get_json()["data"]
    target = next(item for item in listed if item["id"] == experiment["id"])
    for context in target["checkpoints"]:
        assert "q" not in context


def test_attempt_snapshot_isolates_from_experiment_edits(lab):
    student, csrf = lab["student_a"]
    teacher, teacher_csrf = lab["teacher"]
    experiment = lab["experiment"]

    first = submit(student, csrf, experiment["id"], experiment["version"], [5, 6, 1, 2])
    assert first.status_code == 201
    stored = first.get_json()["data"]

    # 教师把实验改成从 0 开始的模 10：新提交按新配置判分
    updated = api_call(
        teacher,
        "patch",
        f"{API}/experiments/{experiment['id']}",
        csrf_token=teacher_csrf,
        json={
            "version": experiment["version"],
            "config": {"initial_q": 0, "modulus": 10},
            "input_sequence": cycles(4),
        },
    )
    assert updated.status_code == 200, updated.get_data(as_text=True)
    new_version = updated.get_json()["data"]["version"]

    second = submit(student, csrf, experiment["id"], new_version, [1, 2, 3, 4])
    assert second.status_code == 201
    assert second.get_json()["data"]["expected"] == [1, 2, 3, 4]
    assert second.get_json()["data"]["passed"] is True

    # 旧记录不因实验改动而变化
    history = student.get(f"{API}/me/experiment-attempts?experiment_id={experiment['id']}").get_json()["data"]
    by_id = {row["id"]: row for row in history}
    assert by_id[stored["id"]]["expected"] == [5, 0, 1, 2]
    assert by_id[stored["id"]]["passed"] is False
    assert by_id[stored["id"]]["experiment_version"] == experiment["version"]
    assert by_id[stored["id"]]["explanations"] == stored["explanations"]

    # 用旧版本号再提交要刷新
    stale = submit(student, csrf, experiment["id"], experiment["version"], [1, 2, 3, 4])
    assert stale.status_code == 409


def test_experiment_without_effective_edges_is_rejected(lab):
    teacher, teacher_csrf = lab["teacher"]
    student, csrf = lab["student_a"]

    flat = create_experiment(
        teacher,
        teacher_csrf,
        lab["knowledge"]["id"],
        title="只有电平变化没有时钟的实验",
        input_sequence=[{"op": "set", "inputs": {"enable": 0}}],
    ).get_json()["data"]
    assert flat["checkpoints"] == []

    response = submit(student, csrf, flat["id"], flat["version"], [])
    assert response.status_code == 422
    assert "有效上升沿" in response.get_json()["error"]["message"]


def test_malformed_input_sequence_raises_checkpoint_error(lab):
    """实验定义若被写坏，重放时给出可读错误而不是静默算出错误答案。"""
    with pytest.raises(CheckpointError):
        replay_checkpoints("counter", COUNTER_M6_FROM_4, [{"op": "bogus"}])
