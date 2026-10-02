"""SPEC-017 时序逻辑识别辅助：T-017-01 至 T-017-04 及配套边界。

测试图片用 OpenCV 按格式 v1 现画（白底黑线规则网格 + 印刷体 0/1），因此输入完全
可复现；断言的是规格人工推演的结果（模 6 计数器 0000→0101→0000 共 6 个次态对）。
识别只读图片、只写 recognition_tasks，不参与实验判分——这一点单独有一条用例核对。
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import cv2
import numpy as np
import pytest

from app import create_app
from app.models import Enrollment, SchoolClass, User
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
    downgrade,
)

MOD6_SEQUENCE = ["0000", "0001", "0010", "0011", "0100", "0101", "0000"]


# ---- 图片生成（格式 v1）----

def render_table(
    rows: list[str],
    *,
    cell: int = 90,
    grid_thickness: int = 3,
    digit_scale: float = 2.2,
    digit_thickness: int = 5,
    overrides: dict[tuple[int, int], str] | None = None,
    columns: int = 4,
) -> bytes:
    """画一张格式 v1 的状态表并编码成 PNG 字节。overrides 可改写某格内容。"""
    margin = 4
    width = columns * cell + 2 * margin
    height = len(rows) * cell + 2 * margin
    canvas = np.full((height, width), 255, dtype=np.uint8)
    for column in range(columns + 1):
        x = margin + column * cell
        cv2.line(canvas, (x, margin), (x, height - margin), 0, grid_thickness)
    for row in range(len(rows) + 1):
        y = margin + row * cell
        cv2.line(canvas, (margin, y), (width - margin, y), 0, grid_thickness)
    for row_index, row in enumerate(rows):
        for column_index, bit in enumerate(row):
            text = (overrides or {}).get((row_index, column_index), bit)
            cx = margin + column_index * cell + cell // 2
            cy = margin + row_index * cell + cell // 2
            (text_width, text_height), _ = cv2.getTextSize(
                text, cv2.FONT_HERSHEY_SIMPLEX, digit_scale, digit_thickness
            )
            cv2.putText(
                canvas,
                text,
                (cx - text_width // 2, cy + text_height // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                digit_scale,
                0,
                digit_thickness,
                cv2.LINE_AA,
            )
    ok, buffer = cv2.imencode(".png", canvas)
    assert ok
    return buffer.tobytes()


def blank_image() -> bytes:
    canvas = np.full((300, 400), 255, dtype=np.uint8)
    ok, buffer = cv2.imencode(".png", canvas)
    assert ok
    return buffer.tobytes()


def scribbled_image() -> bytes:
    """在表格里手写一团笔画，模拟「含手写」的输入。"""
    payload = render_table(MOD6_SEQUENCE)
    array = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    points = np.array([[60, 70], [90, 110], [110, 70], [95, 120], [70, 100]], dtype=np.int32)
    cv2.polylines(array, [points], False, (0, 0, 0), 4)
    ok, buffer = cv2.imencode(".png", array)
    assert ok
    return buffer.tobytes()


# ---- 夹具 ----

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


def _create_class(app, admin, admin_csrf, name: str, teacher_id: int):
    response = api_call(
        admin,
        "post",
        f"{API}/classes",
        csrf_token=admin_csrf,
        json={"name": name, "teacher_id": teacher_id},
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def _register_student(app, login_name: str, student_no: str):
    client = app.test_client()
    csrf = get_csrf(client)
    response = register(client, csrf, login_name=login_name, student_no=student_no)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def _enroll(admin, admin_csrf, class_id: int, student_id: int):
    return api_call(
        admin,
        "put",
        f"{API}/classes/{class_id}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student_id, "active": True},
    )


def submit_image(client, csrf, *, class_id, payload: bytes, filename="state.png",
                 kind="state_table", extra=None):
    data = {
        "image": (io.BytesIO(payload), filename),
        "class_id": str(class_id),
        "kind": kind,
    }
    data.update(extra or {})
    return client.post(
        f"{API}/recognition-tasks",
        data=data,
        headers={"X-CSRF-Token": csrf},
        content_type="multipart/form-data",
    )


@pytest.fixture
def lab(tmp_path: Path):
    """教师甲/乙各带一班；班甲有 1 名在册学生与 1 名未入班学生。"""
    app = create_app(
        "testing",
        {
            "DATABASE_URL": sqlite_url(tmp_path / "recognition.sqlite"),
            "UPLOAD_DIR": str(tmp_path / "uploads"),
        },
    )
    upgrade(app)
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", "Adm1nPass!23")
    teacher_a = _create_teacher(app, admin, admin_csrf, "teacher_aaa")
    teacher_b = _create_teacher(app, admin, admin_csrf, "teacher_bbb")
    class_a = _create_class(app, admin, admin_csrf, "软件工程示例班", teacher_a["id"])
    class_b = _create_class(app, admin, admin_csrf, "网络工程示例班", teacher_b["id"])
    student_a = _register_student(app, "stu_0001", "20240001")
    outsider = _register_student(app, "stu_9000", "20249900")
    assert _enroll(admin, admin_csrf, class_a["id"], student_a["id"]).status_code == 200

    try:
        yield {
            "app": app,
            "admin": (admin, admin_csrf),
            "teacher_a": login_as(app, "teacher_aaa"),
            "teacher_b": login_as(app, "teacher_bbb"),
            "student_a": login_as(app, "stu_0001"),
            "outsider": login_as(app, "stu_9000"),
            "class_a": class_a,
            "class_b": class_b,
            "student_id": student_a["id"],
        }
    finally:
        app.extensions["db_engine"].dispose()


# ---- T-017-01 识别一致 ----

def test_T017_01_recognizes_mod6_state_table(lab):
    png = render_table(MOD6_SEQUENCE)
    client, csrf = lab["student_a"]
    response = submit_image(client, csrf, class_id=lab["class_a"]["id"], payload=png)
    assert response.status_code == 201, response.get_data(as_text=True)
    task = response.get_json()["data"]

    assert task["status"] == "done"
    assert task["kind"] == "state_table"
    assert task["class_id"] == lab["class_a"]["id"]
    result = task["result"]
    assert result["rows"] == 7
    assert result["cols"] == 4
    assert [item["value"] for item in result["states"]] == [0, 1, 2, 3, 4, 5, 0]
    assert [item["row"] for item in result["states"]] == list(range(7))
    assert result["transitions"] == [
        {"from": 0, "to": 1},
        {"from": 1, "to": 2},
        {"from": 2, "to": 3},
        {"from": 3, "to": 4},
        {"from": 4, "to": 5},
        {"from": 5, "to": 0},
    ]
    assert len(result["transitions"]) == 6
    assert 0 < result["confidence"] <= 1
    assert result["requires_review"] is True, "识别结果必须标注需人工核对"
    assert task["error"] is None


def test_T017_01_bit_order_is_q3q2q1q0(lab):
    """最左列是 Q3：`1000` 必须读成 8，`0001` 读成 1。"""
    png = render_table(["1000", "0001"])
    client, csrf = lab["student_a"]
    response = submit_image(client, csrf, class_id=lab["class_a"]["id"], payload=png)
    values = [item["value"] for item in response.get_json()["data"]["result"]["states"]]
    assert values == [8, 1]
    assert response.get_json()["data"]["result"]["transitions"] == [{"from": 8, "to": 1}]


def test_T017_01_two_row_minimum_is_accepted(lab):
    """格式 v1 允许 2 行（最少）。"""
    png = render_table(["0000", "0001"])
    client, csrf = lab["student_a"]
    response = submit_image(client, csrf, class_id=lab["class_a"]["id"], payload=png)
    assert response.status_code == 201
    assert response.get_json()["data"]["status"] == "done"


# ---- T-017-02 失败与格式原因 ----

def test_T017_02_non_table_image_fails_with_reason(lab):
    client, csrf = lab["student_a"]
    response = submit_image(
        client, csrf, class_id=lab["class_a"]["id"], payload=blank_image()
    )
    assert response.status_code == 201, "格式失败仍是一张创建成功的任务"
    task = response.get_json()["data"]
    assert task["status"] == "failed"
    assert task["result"] is None, "失败任务不保留有效 result"
    assert task["error"]["code"] == "GRID_NOT_DETECTED"
    assert task["error"]["message"] == "未检测到网格"


def test_T017_02_wrong_column_count_fails(lab):
    png = render_table(["000", "001"], columns=3)
    client, csrf = lab["student_a"]
    task = submit_image(
        client, csrf, class_id=lab["class_a"]["id"], payload=png
    ).get_json()["data"]
    assert task["status"] == "failed"
    assert task["error"]["code"] == "SHAPE_MISMATCH"
    assert task["error"]["details"]["columns"] in (0, 2, 3)


def test_T017_02_out_of_alphabet_cell_fails(lab):
    """格内画一个 7：不在 0/1 模板内，必须失败且不猜测。"""
    png = render_table(MOD6_SEQUENCE, overrides={(3, 2): "7"})
    client, csrf = lab["student_a"]
    task = submit_image(
        client, csrf, class_id=lab["class_a"]["id"], payload=png
    ).get_json()["data"]
    assert task["status"] == "failed"
    assert task["error"]["code"] in ("CELL_NOT_BINARY", "CELL_UNCERTAIN")
    assert task["result"] is None
    assert task["error"]["details"]["row"] == 3
    assert task["error"]["details"]["column"] == 2


def test_T017_02_handwritten_marks_fail(lab):
    client, csrf = lab["student_a"]
    task = submit_image(
        client, csrf, class_id=lab["class_a"]["id"], payload=scribbled_image()
    ).get_json()["data"]
    assert task["status"] == "failed"
    assert task["error"]["code"] in ("CELL_NOT_BINARY", "CELL_UNCERTAIN")


def test_T017_02_too_many_rows_fails(lab):
    """18 行超出 2—17 的范围。"""
    png = render_table(["0000"] * 18)
    client, csrf = lab["student_a"]
    task = submit_image(
        client, csrf, class_id=lab["class_a"]["id"], payload=png
    ).get_json()["data"]
    assert task["status"] == "failed"
    assert task["error"]["code"] == "SHAPE_MISMATCH"
    assert task["error"]["details"]["rows"] == 18


# ---- T-017-03 类型/大小与「不参与判分」 ----

def test_T017_03_gif_is_rejected(lab):
    client, csrf = lab["student_a"]
    response = submit_image(
        client,
        csrf,
        class_id=lab["class_a"]["id"],
        payload=render_table(MOD6_SEQUENCE),
        filename="state.gif",
    )
    assert response.status_code == 415
    assert response.get_json()["error"]["code"] == "FILE_TYPE_UNSUPPORTED"


def test_T017_03_oversized_file_is_rejected(lab):
    client, csrf = lab["student_a"]
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (21 * 1024 * 1024)
    response = submit_image(
        client, csrf, class_id=lab["class_a"]["id"], payload=oversized
    )
    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "FILE_TOO_LARGE"
    assert scalar(lab["app"], "SELECT COUNT(*) FROM recognition_tasks") == 0


def test_T017_03_client_grading_fields_are_ignored(lab):
    """请求里带 passed/score 一律忽略：既不落库，也不出现在响应里。"""
    client, csrf = lab["student_a"]
    response = submit_image(
        client,
        csrf,
        class_id=lab["class_a"]["id"],
        payload=render_table(MOD6_SEQUENCE),
        extra={"passed": "true", "score": "100"},
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    body = response.get_json()["data"]
    assert "score" not in body
    assert "passed" not in body
    stored = scalar(lab["app"], "SELECT result_json FROM recognition_tasks")
    assert "passed" not in stored and "score" not in stored


def test_T017_03_recognition_does_not_touch_experiment_grading(lab):
    """识别确实不参与实验判分：只写 recognition_tasks，不改动已有实验尝试。"""
    client, csrf = lab["teacher_a"]
    knowledge = api_call(
        client,
        "post",
        f"{API}/knowledge-points",
        csrf_token=csrf,
        json={
            "chapter_id": api_call(
                client,
                "post",
                f"{API}/chapters",
                csrf_token=csrf,
                json={"title": "第五单元 计数器", "sort_order": 5, "published": True},
            ).get_json()["data"]["id"],
            "title": "模 6 计数器",
            "body_md": "模 6 计数器状态为 0000—0101。",
            "sort_order": 1,
            "published": True,
        },
    ).get_json()["data"]
    experiment = api_call(
        client,
        "post",
        f"{API}/experiments",
        csrf_token=csrf,
        json={
            "title": "模 6 计数器：从 4 开始的四拍",
            "knowledge_id": knowledge["id"],
            "simulator_type": "counter",
            "config": {"initial_q": 4, "modulus": 6},
            "steps_md": "初态 0100，连续切换时钟四拍。",
            "input_sequence": [
                {"op": op} for _ in range(4) for op in ("toggle_clock", "toggle_clock")
            ],
            "published": True,
        },
    ).get_json()["data"]

    student, student_csrf = lab["student_a"]
    attempt = api_call(
        student,
        "post",
        f"{API}/experiments/{experiment['id']}/attempts",
        csrf_token=student_csrf,
        json={
            "experiment_version": experiment["version"],
            "predictions": [5, 0, 1, 2],
            "request_key": str(uuid.uuid4()),
        },
    ).get_json()["data"]
    assert attempt["passed"] is True
    before = scalar(lab["app"], "SELECT COUNT(*) FROM experiment_attempts")

    submit_image(student, student_csrf, class_id=lab["class_a"]["id"],
                 payload=render_table(MOD6_SEQUENCE))

    assert scalar(lab["app"], "SELECT COUNT(*) FROM experiment_attempts") == before, (
        "识别不写实验尝试表"
    )
    assert scalar(
        lab["app"], "SELECT passed FROM experiment_attempts WHERE id = ?", (attempt["id"],)
    ) == 1, "已有判分不被识别改变"


# ---- T-017-04 权限与标注 ----

def test_T017_04_student_can_only_use_own_active_class(lab):
    client, csrf = lab["student_a"]
    png = render_table(MOD6_SEQUENCE)
    assert submit_image(client, csrf, class_id=lab["class_b"]["id"], payload=png).status_code == 404

    outsider, outsider_csrf = lab["outsider"]
    assert (
        submit_image(outsider, outsider_csrf, class_id=lab["class_a"]["id"], payload=png).status_code
        == 404
    ), "未入班学生不能对任意班级创建任务"


def test_T017_04_teacher_can_only_use_own_class(lab):
    png = render_table(MOD6_SEQUENCE)
    teacher_b, csrf_b = lab["teacher_b"]
    assert (
        submit_image(teacher_b, csrf_b, class_id=lab["class_a"]["id"], payload=png).status_code
        == 404
    )
    assert (
        submit_image(teacher_b, csrf_b, class_id=lab["class_b"]["id"], payload=png).status_code
        == 201
    )


def test_T017_04_read_permissions_and_review_note(lab):
    client, csrf = lab["student_a"]
    task = submit_image(
        client, csrf, class_id=lab["class_a"]["id"], payload=render_table(MOD6_SEQUENCE)
    ).get_json()["data"]

    # 创建者本人可读，且带置信度与人工核对标注
    mine = client.get(f"{API}/recognition-tasks/{task['id']}")
    assert mine.status_code == 200
    assert mine.get_json()["data"]["result"]["requires_review"] is True
    assert mine.get_json()["data"]["result"]["confidence"] is not None

    # 本班教师（按任务保存的 class_id 核对）可读
    teacher_a, _ = lab["teacher_a"]
    assert teacher_a.get(f"{API}/recognition-tasks/{task['id']}").status_code == 200

    # 其他学生、其他班教师一律 404
    outsider, _ = lab["outsider"]
    assert outsider.get(f"{API}/recognition-tasks/{task['id']}").status_code == 404
    teacher_b, _ = lab["teacher_b"]
    assert teacher_b.get(f"{API}/recognition-tasks/{task['id']}").status_code == 404
    assert teacher_a.get(f"{API}/recognition-tasks/{task['id'] + 999}").status_code == 404


def test_T017_04_teacher_change_moves_read_access(lab):
    """任务按保存的 class_id 判权：换教师后，新教师可读、旧教师不可读。"""
    client, csrf = lab["student_a"]
    task = submit_image(
        client, csrf, class_id=lab["class_a"]["id"], payload=render_table(MOD6_SEQUENCE)
    ).get_json()["data"]

    admin, admin_csrf = lab["admin"]
    teacher_b_id = scalar(lab["app"], "SELECT id FROM users WHERE login_name = 'teacher_bbb'")
    swapped = api_call(
        admin,
        "patch",
        f"{API}/classes/{lab['class_a']['id']}",
        csrf_token=admin_csrf,
        json={"version": lab["class_a"]["version"], "teacher_id": teacher_b_id},
    )
    assert swapped.status_code == 200, swapped.get_data(as_text=True)

    teacher_b, _ = lab["teacher_b"]
    assert teacher_b.get(f"{API}/recognition-tasks/{task['id']}").status_code == 200
    teacher_a, _ = lab["teacher_a"]
    assert teacher_a.get(f"{API}/recognition-tasks/{task['id']}").status_code == 404


def test_T017_04_anonymous_and_admin(lab):
    client, csrf = lab["student_a"]
    task = submit_image(
        client, csrf, class_id=lab["class_a"]["id"], payload=render_table(MOD6_SEQUENCE)
    ).get_json()["data"]

    anonymous = lab["app"].test_client()
    assert anonymous.get(f"{API}/recognition-tasks/{task['id']}").status_code == 401
    admin, _ = lab["admin"]
    assert admin.get(f"{API}/recognition-tasks/{task['id']}").status_code == 403, (
        "管理员默认不是课堂角色，需教学账号才能读"
    )


# ---- 其他边界 ----

def test_timeout_returns_503_and_keeps_nothing(lab):
    """把限时设为 0 复现超时：503、无任务记录、上传文件被清理。"""
    app = create_app(
        "testing",
        {
            "DATABASE_URL": lab["app"].config["DATABASE_URL"],
            "UPLOAD_DIR": lab["app"].config["UPLOAD_DIR"],
            "RECOGNITION_TIMEOUT_SECONDS": 0,
        },
    )
    try:
        client, csrf = login_as(app, "stu_0001")
        response = submit_image(
            client, csrf, class_id=lab["class_a"]["id"], payload=render_table(MOD6_SEQUENCE)
        )
        assert response.status_code == 503
        assert response.get_json()["error"]["code"] == "RECOGNITION_TIMEOUT"
        assert scalar(app, "SELECT COUNT(*) FROM recognition_tasks") == 0, "超时不保留任务"
        upload_root = Path(app.config["UPLOAD_DIR"])
        stored = (
            list((upload_root / "recognition").glob("*"))
            if (upload_root / "recognition").exists()
            else []
        )
        assert stored == [], "超时任务不留下图片"
    finally:
        app.extensions["db_engine"].dispose()


def test_validation_boundaries(lab):
    client, csrf = lab["student_a"]
    png = render_table(MOD6_SEQUENCE)

    assert submit_image(client, csrf, class_id=lab["class_a"]["id"], payload=png,
                        kind="circuit").status_code == 422, "只接受 state_table"
    assert submit_image(client, csrf, class_id=lab["class_a"]["id"], payload=png,
                        filename="noext").status_code == 415
    # 文件名是 PNG 但内容不是图片
    assert submit_image(client, csrf, class_id=lab["class_a"]["id"],
                        payload=b"not-an-image").status_code == 415
    # 空文件
    assert submit_image(client, csrf, class_id=lab["class_a"]["id"],
                        payload=b"").status_code in (415, 422)
    # 缺 class_id
    response = client.post(
        f"{API}/recognition-tasks",
        data={"image": (io.BytesIO(png), "state.png"), "kind": "state_table"},
        headers={"X-CSRF-Token": csrf},
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    # 缺 CSRF
    no_csrf = client.post(
        f"{API}/recognition-tasks",
        data={
            "image": (io.BytesIO(png), "state.png"),
            "class_id": str(lab["class_a"]["id"]),
            "kind": "state_table",
        },
        content_type="multipart/form-data",
    )
    assert no_csrf.status_code == 403


def test_migration_round_trip(tmp_path: Path):
    """upgrade → downgrade 一步（回 0010_spec004）→ upgrade：只回收本模块的表。"""
    app = create_app("testing", {"DATABASE_URL": sqlite_url(tmp_path / "roundtrip.sqlite")})

    def table_exists(name: str) -> bool:
        return scalar(
            app, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ) == 1

    try:
        upgrade(app)
        assert table_exists("recognition_tasks")

        downgrade(app, "0010_spec004")
        assert not table_exists("recognition_tasks"), "本模块的表随迁移回收"
        assert table_exists("warning_snapshots"), "只回退一步，前一个模块的表保留"

        upgrade(app)
        assert table_exists("recognition_tasks")
        assert table_exists("warning_snapshots")
    finally:
        app.extensions["db_engine"].dispose()
