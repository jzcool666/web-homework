"""SPEC-012 课堂演示与时序仿真：T-012-01 至 T-012-04 及配套边界。

前三个用例先用确定性向量核对纯仿真函数（期望值按规格人工推演），再用接口
走同一组动作，证明接口确实调用同一套规则；第四个用例覆盖版本冲突、学生只读
和隐藏预测三点。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from app import create_app
from app.simulator import (
    MAX_EVENTS,
    SimulationError,
    apply_event,
    compute_next_q,
    initial_state,
    normalize_config,
    validate_event,
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

# ---- 纯仿真：确定性向量 ----

D_CONFIG = {"initial_q": 0}
COUNTER_6 = {"initial_q": 0, "modulus": 6}
SHIFT_1010 = {"initial_q": 0b1010}


def run(simulator_type, config, events, state=None):
    """按顺序执行事件，返回 (末状态, 历史行列表)。"""
    state = state or initial_state(simulator_type, config)
    history = []
    for index, event in enumerate(events, start=1):
        state, row = apply_event(simulator_type, config, state, event, seq=index)
        history = [] if row is None else [*history, row]
    return state, history


def test_T012_01_d_flip_flop_only_updates_on_rising_edge():
    config = normalize_config("d", D_CONFIG)
    state = initial_state("d", config)
    assert state == {"clock": 0, "inputs": {"d": 0, "reset": 0}, "q": 0, "step_no": 0}

    # clock=0 时 set D=1：Q 不变
    state, _ = apply_event("d", config, state, {"op": "set", "inputs": {"d": 1}}, seq=1)
    assert state["q"] == 0 and state["clock"] == 0 and state["step_no"] == 0

    # 上升沿：Q=1
    state, row = apply_event("d", config, state, {"op": "toggle_clock"}, seq=2)
    assert state["q"] == 1 and state["clock"] == 1 and state["step_no"] == 1
    assert row["rising"] is True and row["q_before"] == 0 and row["q"] == 1

    # 高电平期间改 D=0：Q 保持 1
    state, row = apply_event("d", config, state, {"op": "set", "inputs": {"d": 0}}, seq=3)
    assert state["q"] == 1 and state["step_no"] == 1 and row["rising"] is False

    # 下降沿：Q 仍为 1，step_no 不增加
    state, row = apply_event("d", config, state, {"op": "toggle_clock"}, seq=4)
    assert state["clock"] == 0 and state["q"] == 1 and state["step_no"] == 1
    assert row["rising"] is False

    # 下一个上升沿才把 D=0 送入：Q=0
    state, _ = apply_event("d", config, state, {"op": "toggle_clock"}, seq=5)
    assert state["q"] == 0 and state["step_no"] == 2

    # 同步复位也只在有效上升沿生效，且在上升沿优先清零
    state, _ = run(
        "d",
        config,
        [
            {"op": "set", "inputs": {"d": 1}},
            {"op": "toggle_clock"},  # 上升沿 → Q=1
            {"op": "set", "inputs": {"reset": 1}},
        ],
    )
    assert state["q"] == 1, "同步复位不在高电平期间立即生效"
    state, _ = run(
        "d",
        config,
        [
            {"op": "toggle_clock"},  # 下降沿
            {"op": "toggle_clock"},  # 上升沿 → 复位优先 Q=0
        ],
        state=state,
    )
    assert state["q"] == 0, "复位在有效上升沿优先清零"


def test_T012_02_jk_hold_clear_set_toggle():
    config = normalize_config("jk", {"initial_q": 0})

    # 依次给出 00 / 10 / 01 / 11，再回到 00：每次只看有效上升沿后的 Q
    _, history = run(
        "jk",
        config,
        [
            {"op": "set", "inputs": {"j": 0, "k": 0}},  # 保持
            {"op": "toggle_clock"},
            {"op": "toggle_clock"},
            {"op": "set", "inputs": {"j": 1, "k": 0}},  # 置位
            {"op": "toggle_clock"},
            {"op": "toggle_clock"},
            {"op": "set", "inputs": {"j": 0, "k": 1}},  # 清零
            {"op": "toggle_clock"},
            {"op": "toggle_clock"},
            {"op": "set", "inputs": {"j": 1, "k": 1}},  # 翻转
            {"op": "toggle_clock"},
            {"op": "toggle_clock"},
            {"op": "set", "inputs": {"j": 0, "k": 0}},  # 保持（当前为 1）
            {"op": "toggle_clock"},
        ],
    )
    assert [row["q"] for row in history if row["rising"]] == [0, 1, 0, 1, 1]

    # 同步 reset 只在有效上升沿生效，且在上升沿优先清零
    state, _ = run(
        "jk",
        config,
        [
            {"op": "set", "inputs": {"j": 1, "k": 0}},
            {"op": "toggle_clock"},  # 上升沿 → 置 1
            {"op": "set", "inputs": {"reset": 1}},
        ],
    )
    assert state["q"] == 1, "同步复位不在高电平期间立即生效"
    state, _ = run(
        "jk",
        config,
        [
            {"op": "set", "inputs": {"j": 1, "k": 0}},
            {"op": "toggle_clock"},
            {"op": "set", "inputs": {"reset": 1}},
            {"op": "toggle_clock"},  # 下降沿
            {"op": "toggle_clock"},  # 上升沿 → 复位优先
        ],
    )
    assert state["q"] == 0


def test_T012_03_counter_modulus_and_shift_order():
    counter = normalize_config("counter", COUNTER_6)
    # M=6，Q=5 的下一个有效沿回到 0
    assert compute_next_q("counter", counter, 5, {"enable": 1, "reset": 0}) == 0
    # 0..5 循环
    assert [compute_next_q("counter", counter, q, {"enable": 1, "reset": 0}) for q in range(6)] == [
        1, 2, 3, 4, 5, 0
    ]
    # 无效状态 Q≥M 在下个有效沿回 0
    assert compute_next_q("counter", counter, 7, {"enable": 1, "reset": 0}) == 0
    # enable=0 保持
    assert compute_next_q("counter", counter, 3, {"enable": 0, "reset": 0}) == 3

    state, _ = run("counter", counter, [{"op": "toggle_clock"}] * 12)
    assert state["q"] == 0 and state["step_no"] == 6, "模 6 走 6 拍回到 0"

    shift = normalize_config("shift", SHIFT_1010)
    # Q=1010，输入 1 → Q'=1101
    assert compute_next_q("shift", shift, 0b1010, {"enable": 1, "serial_in": 1, "reset": 0}) == 0b1101
    # enable=0 保持
    assert compute_next_q("shift", shift, 0b1010, {"enable": 0, "serial_in": 1, "reset": 0}) == 0b1010
    # 串行输入从 Q3 进入、向 Q0 方向移动
    state, _ = run(
        "shift",
        shift,
        [{"op": "set", "inputs": {"serial_in": 1}}, {"op": "toggle_clock"}],
    )
    assert state["q"] == 0b1101


def test_reset_view_restores_initial_state_and_clears_history():
    config = normalize_config("counter", COUNTER_6)
    state, history = run(
        "counter",
        config,
        [
            {"op": "set", "inputs": {"enable": 0}},
            {"op": "toggle_clock"},
            {"op": "toggle_clock"},
            {"op": "reset_view"},
        ],
    )
    assert state == {"clock": 0, "inputs": {"enable": 1, "reset": 0}, "q": 0, "step_no": 0}
    assert history == [], "reset_view 清空历史"
    assert state["step_no"] == 0, "reset_view 把 step_no 归零"


def test_config_and_event_validation_rejects_bad_input():
    # D/JK 初态只能是 0/1
    with pytest.raises(SimulationError):
        normalize_config("d", {"initial_q": 2})
    # 模数范围 2—16，且只有计数器支持
    with pytest.raises(SimulationError):
        normalize_config("counter", {"modulus": 1})
    with pytest.raises(SimulationError):
        normalize_config("counter", {"modulus": 17})
    with pytest.raises(SimulationError):
        normalize_config("shift", {"modulus": 6})
    with pytest.raises(SimulationError):
        normalize_config("d", {"bogus": 1})
    # 输入只允许对应模型的引脚
    with pytest.raises(SimulationError):
        validate_event("counter", {"op": "set", "inputs": {"j": 1}})
    # 输入值必须是 0/1；bool 不算
    with pytest.raises(SimulationError):
        validate_event("d", {"op": "set", "inputs": {"d": 2}})
    with pytest.raises(SimulationError):
        validate_event("d", {"op": "set", "inputs": {"d": True}})
    # 未知 op、空输入、多余字段
    with pytest.raises(SimulationError):
        validate_event("d", {"op": "step"})
    with pytest.raises(SimulationError):
        validate_event("d", {"op": "set", "inputs": {}})
    with pytest.raises(SimulationError):
        validate_event("d", {"op": "toggle_clock", "q": 3})


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


def _new_class(admin, admin_csrf, name: str, teacher_id: int):
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
    response = api_call(
        admin,
        "put",
        f"{API}/classes/{class_id}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student_id, "active": True},
    )
    assert response.status_code == 200, response.get_data(as_text=True)


def create_chapter(client, csrf, **over):
    payload = {"title": "第五单元 计数器", "sort_order": 5, "published": True}
    payload.update(over)
    return api_call(client, "post", f"{API}/chapters", csrf_token=csrf, json=payload)


def create_knowledge(client, csrf, chapter_id: int, **over):
    payload = {
        "chapter_id": chapter_id,
        "title": "模 6 计数器与 5→0 回卷",
        "body_md": "模 6 计数器状态为 0000—0101。",
        "sort_order": 1,
        "published": True,
    }
    payload.update(over)
    return api_call(client, "post", f"{API}/knowledge-points", csrf_token=csrf, json=payload)


def create_experiment(client, csrf, knowledge_id: int, **over):
    payload = {
        "title": "模 6 计数器：0—5 循环",
        "knowledge_id": knowledge_id,
        "simulator_type": "counter",
        "config": {"initial_q": 0, "modulus": 6},
        "steps_md": "初态 0000，连续切换时钟观察 Q 的变化。",
        "input_sequence": [],
        "published": True,
    }
    payload.update(over)
    return api_call(client, "post", f"{API}/experiments", csrf_token=csrf, json=payload)


def start_demo(client, csrf, class_id: int, experiment_id: int):
    return api_call(
        client,
        "post",
        f"{API}/demo-sessions",
        csrf_token=csrf,
        json={"class_id": class_id, "experiment_id": experiment_id},
    )


def act(client, csrf, demo_id: int, version: int, **payload):
    body = {"expected_version": version, **payload}
    return api_call(
        client, "post", f"{API}/demo-sessions/{demo_id}/actions", csrf_token=csrf, json=body
    )


@pytest.fixture
def lab(tmp_path: Path):
    """管理员 + 两教师 + 两班（各一名已入班学生）+ 未入班学生 + 知识点。"""
    app = create_app(
        "testing",
        {
            "DATABASE_URL": sqlite_url(tmp_path / "demo.sqlite"),
            "UPLOAD_DIR": str(tmp_path / "uploads"),
        },
    )
    upgrade(app)
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", "Adm1nPass!23")
    teacher_a = _create_teacher(app, admin, admin_csrf, "teacher_aaa")
    teacher_b = _create_teacher(app, admin, admin_csrf, "teacher_bbb")
    class_a = _new_class(admin, admin_csrf, "班甲", teacher_a["id"])
    class_b = _new_class(admin, admin_csrf, "班乙", teacher_b["id"])
    student_a = _register_student(app, "stu_a0001", "20240001")
    student_b = _register_student(app, "stu_b0001", "20240002")
    outsider = _register_student(app, "stu_x0001", "20240003")
    _enroll(admin, admin_csrf, class_a["id"], student_a["id"])
    _enroll(admin, admin_csrf, class_b["id"], student_b["id"])

    teacher_client, teacher_csrf = login_as(app, "teacher_aaa")
    chapter = create_chapter(teacher_client, teacher_csrf).get_json()["data"]
    point = create_knowledge(teacher_client, teacher_csrf, chapter["id"]).get_json()["data"]

    try:
        yield {
            "app": app,
            "teacher_a": (teacher_client, teacher_csrf),
            "teacher_b": login_as(app, "teacher_bbb"),
            "student_a": login_as(app, "stu_a0001"),
            "student_b": login_as(app, "stu_b0001"),
            "outsider": login_as(app, "stu_x0001"),
            "admin": (admin, admin_csrf),
            "class_a": class_a,
            "class_b": class_b,
            "knowledge": point,
        }
    finally:
        app.extensions["db_engine"].dispose()


# ---- T-012-01..03 走接口 ----

def test_T012_01_d_sequence_through_api(lab):
    teacher, csrf = lab["teacher_a"]
    experiment = create_experiment(
        teacher,
        csrf,
        lab["knowledge"]["id"],
        title="D 触发器演示",
        simulator_type="d",
        config={"initial_q": 0},
    ).get_json()["data"]
    demo = start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"]).get_json()["data"]

    state = demo["state"]
    assert state == {"clock": 0, "inputs": {"d": 0, "reset": 0}, "q": 0, "step_no": 0}
    assert demo["history"] == []
    assert demo["reveal_next"] is False and demo["next_q"] is None

    version = demo["version"]
    first = act(teacher, csrf, demo["id"], version, event={"op": "set", "inputs": {"d": 1}})
    assert first.status_code == 200, first.get_data(as_text=True)
    body = first.get_json()["data"]
    assert body["state"]["q"] == 0 and body["state"]["step_no"] == 0
    assert body["history"][0]["rising"] is False

    second = act(teacher, csrf, demo["id"], body["version"], event={"op": "toggle_clock"})
    body = second.get_json()["data"]
    assert body["state"] == {"clock": 1, "inputs": {"d": 1, "reset": 0}, "q": 1, "step_no": 1}
    assert body["history"][1]["rising"] is True

    third = act(teacher, csrf, demo["id"], body["version"], event={"op": "set", "inputs": {"d": 0}})
    body = third.get_json()["data"]
    assert body["state"]["q"] == 1 and body["state"]["step_no"] == 1

    fourth = act(teacher, csrf, demo["id"], body["version"], event={"op": "toggle_clock"})
    body = fourth.get_json()["data"]
    assert body["state"]["clock"] == 0 and body["state"]["q"] == 1 and body["state"]["step_no"] == 1
    assert [row["rising"] for row in body["history"]] == [False, True, False, False]


def test_T012_03_counter_and_shift_through_api(lab):
    teacher, csrf = lab["teacher_a"]
    counter = create_experiment(teacher, csrf, lab["knowledge"]["id"]).get_json()["data"]
    demo = start_demo(teacher, csrf, lab["class_a"]["id"], counter["id"]).get_json()["data"]

    version = demo["version"]
    seen = []
    # 每个完整周期一次有效上升沿，6 个周期覆盖 0—5 再回到 0
    for _ in range(12):
        response = act(teacher, csrf, demo["id"], version, event={"op": "toggle_clock"})
        body = response.get_json()["data"]
        version = body["version"]
        if body["history"][-1]["rising"]:
            seen.append(body["state"]["q"])
    assert seen == [1, 2, 3, 4, 5, 0], "模 6 计数器 6 个有效沿循环回 0"

    # enable=0 保持
    held = act(teacher, csrf, demo["id"], version, event={"op": "set", "inputs": {"enable": 0}})
    version = held.get_json()["data"]["version"]
    before = teacher.get(f"{API}/demo-sessions/{demo['id']}").get_json()["data"]["state"]["q"]
    for _ in range(2):  # 走一个完整周期
        after = act(teacher, csrf, demo["id"], version, event={"op": "toggle_clock"}).get_json()["data"]
        version = after["version"]
    assert after["state"]["q"] == before

    # reset_view 清空历史并把 step_no 归零
    reset = act(teacher, csrf, demo["id"], after["version"], event={"op": "reset_view"}).get_json()["data"]
    assert reset["state"] == {
        "clock": 0,
        "inputs": {"enable": 1, "reset": 0},
        "q": 0,
        "step_no": 0,
    }
    assert reset["history"] == []


def test_T012_04_version_conflict_student_readonly_and_hidden_prediction(lab):
    teacher, csrf = lab["teacher_a"]
    student, student_csrf = lab["student_a"]
    experiment = create_experiment(teacher, csrf, lab["knowledge"]["id"]).get_json()["data"]
    demo = start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"]).get_json()["data"]
    version = demo["version"]

    # 两次相同 expected_version：只有首次成功
    first = act(teacher, csrf, demo["id"], version, event={"op": "toggle_clock"})
    assert first.status_code == 200
    second = act(teacher, csrf, demo["id"], version, event={"op": "toggle_clock"})
    assert second.status_code == 409
    details = second.get_json()["error"]["details"]
    assert details == {"expected_version": version, "current_version": version + 1}

    # 学生不能修改
    assert act(student, student_csrf, demo["id"], version, event={"op": "toggle_clock"}).status_code == 403
    assert start_demo(student, student_csrf, lab["class_a"]["id"], experiment["id"]).status_code == 403

    # 隐藏预测：教师与学生响应都不含下一状态
    for client in (teacher, student):
        body = client.get(f"{API}/demo-sessions/{demo['id']}").get_json()["data"]
        assert body["reveal_next"] is False
        assert body["next_q"] is None
    assert b'"next_q":null' in teacher.get(f"{API}/demo-sessions/{demo['id']}").data

    # 揭示后才给出下一状态，且与规格推演一致（模 6 计数器：Q=1 的下一有效沿为 2）
    revealed = act(teacher, csrf, demo["id"], version + 1, action={"op": "set_reveal", "value": True})
    assert revealed.status_code == 200, revealed.get_data(as_text=True)
    body = revealed.get_json()["data"]
    assert body["state"]["q"] == 1
    assert body["reveal_next"] is True and body["next_q"] == 2, "模 6 计数器 Q=1 的下一有效沿为 2"

    student_view = student.get(f"{API}/demo-sessions/{demo['id']}").get_json()["data"]
    assert student_view["reveal_next"] is True and student_view["next_q"] == 2


# ---- 权限与边界 ----

def test_demo_isolation_between_classes_and_roles(lab):
    teacher_a, csrf_a = lab["teacher_a"]
    teacher_b, csrf_b = lab["teacher_b"]
    student_a, csrf_a_s = lab["student_a"]
    student_b, _ = lab["student_b"]
    admin, admin_csrf = lab["admin"]

    experiment = create_experiment(teacher_a, csrf_a, lab["knowledge"]["id"]).get_json()["data"]
    demo = start_demo(teacher_a, csrf_a, lab["class_a"]["id"], experiment["id"]).get_json()["data"]

    # 教师乙跨班：404
    assert teacher_b.get(f"{API}/demo-sessions/{demo['id']}").status_code == 404
    assert teacher_b.get(f"{API}/demo-sessions?class_id={lab['class_a']['id']}").status_code == 404
    assert act(teacher_b, csrf_b, demo["id"], demo["version"], event={"op": "toggle_clock"}).status_code == 404
    # 班乙学生：404
    assert student_b.get(f"{API}/demo-sessions/{demo['id']}").status_code == 404
    # 本班学生：200
    assert student_a.get(f"{API}/demo-sessions/{demo['id']}").status_code == 200
    # 管理员不参与课堂操作
    assert admin.get(f"{API}/demo-sessions/{demo['id']}").status_code == 403
    assert api_call(
        admin,
        "post",
        f"{API}/demo-sessions/{demo['id']}/actions",
        csrf_token=admin_csrf,
        json={"expected_version": demo["version"], "event": {"op": "toggle_clock"}},
    ).status_code == 403
    # 未入班学生看不到课程内容
    outsider, _ = lab["outsider"]
    assert outsider.get(f"{API}/experiments").status_code == 403
    assert outsider.get(f"{API}/demo-sessions/{demo['id']}").status_code == 403
    # 学生不能建实验、不能开演示
    assert create_experiment(student_a, csrf_a_s, lab["knowledge"]["id"]).status_code == 403


def test_one_active_demo_per_class_and_close(lab):
    teacher, csrf = lab["teacher_a"]
    experiment = create_experiment(teacher, csrf, lab["knowledge"]["id"]).get_json()["data"]
    demo = start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"]).get_json()["data"]

    again = start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"])
    assert again.status_code == 409
    assert again.get_json()["error"]["code"] == "STATE_CONFLICT"
    assert scalar(lab["app"], "SELECT COUNT(*) FROM demo_sessions WHERE active = 1") == 1

    closed = act(teacher, csrf, demo["id"], demo["version"], action={"op": "close"})
    assert closed.status_code == 200
    body = closed.get_json()["data"]
    assert body["active"] is False
    assert body["state"]["q"] == 0, "关闭保留最终状态供回顾"

    # 关闭后不能再操作
    after = act(teacher, csrf, demo["id"], body["version"], event={"op": "toggle_clock"})
    assert after.status_code == 409
    assert after.get_json()["error"]["code"] == "STATE_CONFLICT"

    # 关闭后可以重新开一个
    assert start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"]).status_code == 201


def test_action_rejects_client_supplied_state(lab):
    teacher, csrf = lab["teacher_a"]
    experiment = create_experiment(teacher, csrf, lab["knowledge"]["id"]).get_json()["data"]
    demo = start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"]).get_json()["data"]
    version = demo["version"]

    # 客户端不能直接指定 q
    injected = act(
        teacher, csrf, demo["id"], version,
        event={"op": "toggle_clock", "q": 15, "state": {"q": 15}},
    )
    assert injected.status_code == 422
    unknown = injected.get_json()["error"]["details"]
    assert unknown.get("fields") or unknown.get("unknown_fields")

    # 该模型不支持的引脚
    bad_pin = act(teacher, csrf, demo["id"], version, event={"op": "set", "inputs": {"j": 1}})
    assert bad_pin.status_code == 422
    # 未知 op
    assert act(teacher, csrf, demo["id"], version, event={"op": "run"}).status_code == 422
    # event 与 action 互斥，且必须给其一
    assert act(teacher, csrf, demo["id"], version).status_code == 422
    assert act(
        teacher, csrf, demo["id"], version,
        event={"op": "toggle_clock"}, action={"op": "close"},
    ).status_code == 422
    # action 校验
    assert act(teacher, csrf, demo["id"], version, action={"op": "open"}).status_code == 422
    assert act(teacher, csrf, demo["id"], version, action={"op": "set_reveal", "value": 1}).status_code == 422

    # 失败请求没有改变状态
    current = teacher.get(f"{API}/demo-sessions/{demo['id']}").get_json()["data"]
    assert current["version"] == version and current["state"]["q"] == 0


def test_demo_snapshot_isolates_from_experiment_edits(lab):
    teacher, csrf = lab["teacher_a"]
    experiment = create_experiment(teacher, csrf, lab["knowledge"]["id"]).get_json()["data"]
    demo = start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"]).get_json()["data"]
    assert demo["experiment"]["config"] == {"initial_q": 0, "modulus": 6}

    # 教师事后把实验改成模 10 并撤回发布
    updated = api_call(
        teacher,
        "patch",
        f"{API}/experiments/{experiment['id']}",
        csrf_token=csrf,
        json={"version": experiment["version"], "config": {"initial_q": 2, "modulus": 10}, "published": False},
    )
    assert updated.status_code == 200, updated.get_data(as_text=True)

    # 进行中的演示仍使用创建时的快照
    body = teacher.get(f"{API}/demo-sessions/{demo['id']}").get_json()["data"]
    assert body["experiment"]["config"] == {"initial_q": 0, "modulus": 6}
    assert body["state"]["q"] == 0

    # 学生读不到已撤回的实验定义，但仍能看进行中的演示
    student, _ = lab["student_a"]
    assert student.get(f"{API}/experiments/{experiment['id']}").status_code == 404
    assert student.get(f"{API}/demo-sessions/{demo['id']}").status_code == 200


def test_experiment_validation_and_visibility(lab):
    teacher, csrf = lab["teacher_a"]
    student, _ = lab["student_a"]

    # 未知字段（含 owner_id）被拒
    injected = create_experiment(
        teacher, csrf, lab["knowledge"]["id"], owner_id=99
    )
    assert injected.status_code == 422
    assert "owner_id" in injected.get_json()["error"]["details"]["unknown_fields"]

    # 配置与输入序列校验
    assert create_experiment(teacher, csrf, lab["knowledge"]["id"], simulator_type="cpu").status_code == 422
    assert create_experiment(teacher, csrf, lab["knowledge"]["id"], config={"initial_q": 99}).status_code == 422
    assert create_experiment(
        teacher, csrf, lab["knowledge"]["id"], simulator_type="d", config={"initial_q": 0, "modulus": 6}
    ).status_code == 422, "只有计数器支持模数"
    missing = api_call(
        teacher,
        "post",
        f"{API}/experiments",
        csrf_token=csrf,
        json={
            "title": "指向不存在的知识点",
            "knowledge_id": 99999,
            "simulator_type": "d",
            "config": {"initial_q": 0},
            "steps_md": "步骤说明",
            "input_sequence": [],
            "published": True,
        },
    )
    assert missing.status_code == 422
    assert create_experiment(
        teacher, csrf, lab["knowledge"]["id"],
        input_sequence=[{"op": "toggle_clock"}] * (MAX_EVENTS + 1),
    ).status_code == 422
    assert create_experiment(
        teacher, csrf, lab["knowledge"]["id"], input_sequence=[{"op": "set", "inputs": {"j": 1}}]
    ).status_code == 422

    # 合法序列可入库
    ok = create_experiment(
        teacher, csrf, lab["knowledge"]["id"], input_sequence=[{"op": "toggle_clock"}] * 2
    )
    assert ok.status_code == 201
    assert len(ok.get_json()["data"]["input_sequence"]) == 2

    # 草稿实验学生不可见
    draft = create_experiment(teacher, csrf, lab["knowledge"]["id"], title="草稿实验", published=False)
    draft_id = draft.get_json()["data"]["id"]
    assert student.get(f"{API}/experiments/{draft_id}").status_code == 404
    listed = student.get(f"{API}/experiments?page_size=100").get_json()["data"]
    assert draft_id not in [item["id"] for item in listed]
    # 教师乙看不到教师甲的草稿实验，也改不了
    teacher_b, csrf_b = lab["teacher_b"]
    assert teacher_b.get(f"{API}/experiments/{draft_id}").status_code == 404
    assert api_call(
        teacher_b,
        "patch",
        f"{API}/experiments/{draft_id}",
        csrf_token=csrf_b,
        json={"version": draft.get_json()["data"]["version"], "title": "改个名"},
    ).status_code == 403

    # 版本冲突
    stale = api_call(
        teacher,
        "patch",
        f"{API}/experiments/{draft_id}",
        csrf_token=csrf,
        json={"version": draft.get_json()["data"]["version"], "title": "改名后"},
    )
    assert stale.status_code == 200
    assert api_call(
        teacher,
        "patch",
        f"{API}/experiments/{draft_id}",
        csrf_token=csrf,
        json={"version": draft.get_json()["data"]["version"], "title": "再改"},
    ).status_code == 409


def test_event_cap_requires_reset(lab):
    teacher, csrf = lab["teacher_a"]
    experiment = create_experiment(teacher, csrf, lab["knowledge"]["id"]).get_json()["data"]
    demo = start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"]).get_json()["data"]

    version = demo["version"]
    for _ in range(MAX_EVENTS):
        body = act(teacher, csrf, demo["id"], version, event={"op": "toggle_clock"}).get_json()["data"]
        version = body["version"]
    assert len(body["history"]) == MAX_EVENTS

    over = act(teacher, csrf, demo["id"], version, event={"op": "toggle_clock"})
    assert over.status_code == 409
    assert over.get_json()["error"]["details"]["max_events"] == MAX_EVENTS

    # 复位到初态后可继续
    reset = act(teacher, csrf, demo["id"], version, event={"op": "reset_view"})
    assert reset.status_code == 200
    after = reset.get_json()["data"]
    assert after["history"] == []
    assert act(teacher, csrf, demo["id"], after["version"], event={"op": "toggle_clock"}).status_code == 200


def test_seed_experiments_is_idempotent(lab):
    app = lab["app"]
    runner = app.test_cli_runner()
    content = runner.invoke(args=["seed-content", "--owner-login", "teacher_aaa"])
    assert content.exit_code == 0, content.output

    first = runner.invoke(args=["seed-experiments", "--owner-login", "teacher_aaa"])
    assert first.exit_code == 0, first.output
    assert "新增 4 个" in first.output
    assert scalar(app, "SELECT COUNT(*) FROM experiments") == 4
    types = scalar(app, "SELECT COUNT(DISTINCT simulator_type) FROM experiments")
    assert types == 4
    assert scalar(app, "SELECT COUNT(*) FROM experiments WHERE published = 1") == 4

    second = runner.invoke(args=["seed-experiments", "--owner-login", "teacher_aaa"])
    assert second.exit_code == 0, second.output
    assert "新增 0 个" in second.output
    assert scalar(app, "SELECT COUNT(*) FROM experiments") == 4

    # 预置实验的输入序列都提供不少于 4 个有效上升沿
    teacher, csrf = lab["teacher_a"]
    for experiment in teacher.get(f"{API}/experiments?page_size=100").get_json()["data"]:
        sequence = experiment["input_sequence"]
        config = experiment["config"]
        state = initial_state(experiment["simulator_type"], config)
        risings = 0
        for index, event in enumerate(sequence, start=1):
            event = validate_event(experiment["simulator_type"], event)
            state, row = apply_event(experiment["simulator_type"], config, state, event, seq=index)
            if row and row["rising"]:
                risings += 1
        assert risings >= 4, (experiment["title"], risings)

    # 移位寄存器预置的初态就是验收用例里的 1010
    shift = next(
        e for e in teacher.get(f"{API}/experiments?page_size=100").get_json()["data"]
        if e["simulator_type"] == "shift"
    )
    assert shift["config"]["initial_q"] == 0b1010


# ---- 演示列表 ----

def test_demo_list_filters_by_class_and_active(lab):
    teacher, csrf = lab["teacher_a"]
    experiment = create_experiment(teacher, csrf, lab["knowledge"]["id"]).get_json()["data"]
    first = start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"]).get_json()["data"]
    act(teacher, csrf, first["id"], first["version"], action={"op": "close"})
    start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"])

    listing = teacher.get(f"{API}/demo-sessions?class_id={lab['class_a']['id']}&page_size=100").get_json()
    assert listing["meta"]["total"] == 2

    active = teacher.get(
        f"{API}/demo-sessions?class_id={lab['class_a']['id']}&active=true"
    ).get_json()["data"]
    assert len(active) == 1 and active[0]["active"] is True

    closed = teacher.get(
        f"{API}/demo-sessions?class_id={lab['class_a']['id']}&active=false"
    ).get_json()["data"]
    assert len(closed) == 1 and closed[0]["active"] is False


def test_parallel_demo_actions_reject_stale_version(lab, monkeypatch):
    """两个请求都读到相同版本时，也只能提交一次状态变更。"""
    import app.api_experiment as experiment_api

    teacher, csrf = lab["teacher_a"]
    experiment = create_experiment(teacher, csrf, lab["knowledge"]["id"]).get_json()["data"]
    demo = start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"]).get_json()["data"]
    other_teacher, other_csrf = login_as(lab["app"], "teacher_aaa")
    barrier = Barrier(2)
    original_apply = experiment_api.apply_event

    def same_old_state(*args, **kwargs):
        barrier.wait(timeout=10)
        return original_apply(*args, **kwargs)

    monkeypatch.setattr(experiment_api, "apply_event", same_old_state)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(act, teacher, csrf, demo["id"], demo["version"], event={"op": "toggle_clock"})
        second = pool.submit(act, other_teacher, other_csrf, demo["id"], demo["version"], event={"op": "toggle_clock"})
        statuses = sorted([first.result().status_code, second.result().status_code])
    assert statuses == [200, 409]
    current = teacher.get(f"{API}/demo-sessions/{demo['id']}").get_json()["data"]
    assert current["version"] == demo["version"] + 1
    assert len(current["history"]) == 1


def test_changing_experiment_type_keeps_valid_config_and_events(lab):
    teacher, csrf = lab["teacher_a"]
    experiment = create_experiment(
        teacher, csrf, lab["knowledge"]["id"], simulator_type="d", config={"initial_q": 0}
    ).get_json()["data"]
    response = api_call(
        teacher, "patch", f"{API}/experiments/{experiment['id']}", csrf_token=csrf,
        json={"version": experiment["version"], "simulator_type": "counter"},
    )
    assert response.status_code == 200
    changed = response.get_json()["data"]
    assert changed["config"]["modulus"] == 16
    demo = start_demo(teacher, csrf, lab["class_a"]["id"], experiment["id"]).get_json()["data"]
    rising = act(teacher, csrf, demo["id"], demo["version"], event={"op": "toggle_clock"})
    assert rising.status_code == 200
    assert rising.get_json()["data"]["state"]["q"] == 1


def test_inactive_class_stops_new_demo_activity_but_allows_close(lab):
    teacher, csrf = lab["teacher_a"]
    admin, admin_csrf = lab["admin"]
    experiment = create_experiment(teacher, csrf, lab["knowledge"]["id"]).get_json()["data"]
    school_class = lab["class_a"]
    demo = start_demo(teacher, csrf, school_class["id"], experiment["id"]).get_json()["data"]
    disabled = api_call(
        admin, "patch", f"{API}/classes/{school_class['id']}", csrf_token=admin_csrf,
        json={"version": school_class["version"], "active": False},
    )
    assert disabled.status_code == 200
    assert start_demo(teacher, csrf, school_class["id"], experiment["id"]).status_code == 409
    assert act(teacher, csrf, demo["id"], demo["version"], event={"op": "toggle_clock"}).status_code == 409
    closed = act(teacher, csrf, demo["id"], demo["version"], action={"op": "close"})
    assert closed.status_code == 200
    assert closed.get_json()["data"]["active"] is False
    assert teacher.get(f"{API}/demo-sessions/{demo['id']}").status_code == 200
