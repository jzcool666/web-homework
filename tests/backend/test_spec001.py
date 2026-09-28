"""SPEC-001 账号角色与班级权限：T-001-01 至 T-001-04 及配套边界。

覆盖本任务能实际验证的行为。依赖后续模块的跨班对象（如 SPEC-009 学生答案）
尚不存在，这里只验证可复用的权限机制（班级对象越权返回 404），
其余留待各模块集成验证，不作已通过的记录。
"""

from __future__ import annotations

from app import auth as auth_module
from helpers import (
    API,
    DEFAULT_PASSWORD,
    api_call,
    create_admin,
    get_csrf,
    login,
    register,
    scalar,
)


# ---- 公共夹具 ----

def login_as(app, login_name: str, password: str = DEFAULT_PASSWORD):
    """返回 (client, csrf_token)。登录会轮换 CSRF，必须取响应里的新值。"""
    client = app.test_client()
    csrf = get_csrf(client)
    response = login(client, csrf, login_name=login_name, password=password)
    assert response.status_code == 200, response.get_data(as_text=True)
    return client, response.get_json()["data"]["csrf_token"]


def create_teacher(app, admin_client, admin_csrf, login_name: str):
    response = api_call(
        admin_client,
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


def register_student(app, login_name: str = "stu_00001", student_no: str = "20240001"):
    """注册一名学生并返回其 User 响应对象。"""
    client = app.test_client()
    csrf = get_csrf(client)
    response = register(client, csrf, login_name=login_name, student_no=student_no)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def sid_of(client) -> str:
    cookie = client.get_cookie("sid")
    assert cookie is not None
    return cookie.value


def replay(app, sid_value: str, path: str = f"{API}/me"):
    """用旧 Cookie 重放请求，验证服务端是否真的让会话失效。"""
    fresh = app.test_client()
    return fresh.get(path, headers={"Cookie": f"sid={sid_value}"})


def seed_school(app):
    """管理员 + 两教师 + 两班；返回 id 映射。"""
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", "Adm1nPass!23")
    teacher_a = create_teacher(app, admin, admin_csrf, "teacher_aaa")
    teacher_b = create_teacher(app, admin, admin_csrf, "teacher_bbb")

    def new_class(name: str, teacher_id: int):
        response = api_call(
            admin,
            "post",
            f"{API}/classes",
            csrf_token=admin_csrf,
            json={"name": name, "teacher_id": teacher_id},
        )
        assert response.status_code == 201, response.get_data(as_text=True)
        return response.get_json()["data"]

    class_a = new_class("班甲", teacher_a["id"])
    class_b = new_class("班乙", teacher_b["id"])
    return {
        "admin": (admin, admin_csrf),
        "teacher_a": teacher_a,
        "teacher_b": teacher_b,
        "class_a": class_a,
        "class_b": class_b,
    }


# ---- T-001-01 ----

def test_T001_01_register_rejects_privileged_role(upgraded_app):
    """携带 role=admin 的注册被拒且不创建高权限账号。"""
    client = upgraded_app.test_client()
    csrf = get_csrf(client)
    response = api_call(
        client,
        "post",
        f"{API}/auth/register",
        csrf_token=csrf,
        json={
            "login_name": "hacker_001",
            "student_no": "20240099",
            "display_name": "冒充者",
            "password": DEFAULT_PASSWORD,
            "role": "admin",
        },
    )
    assert response.status_code in (400, 422), response.get_data(as_text=True)
    assert scalar(upgraded_app, "SELECT COUNT(*) FROM users WHERE role='admin'") == 0
    assert scalar(
        upgraded_app, "SELECT COUNT(*) FROM users WHERE login_name='hacker_001'"
    ) == 0


def test_T001_01_register_creates_plain_student(upgraded_app):
    """正常学生注册成功，固定为 student 且尚未入班。"""
    client = upgraded_app.test_client()
    csrf = get_csrf(client)
    response = register(
        client, csrf, login_name="stu_ok01", student_no="20240100", display_name="正常学生"
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    data = response.get_json()["data"]
    assert data["role"] == "student"
    assert data["active"] is True
    assert data["student_no"] == "20240100"
    assert "password_hash" not in data


def test_T001_01_register_rejects_unknown_and_duplicate(upgraded_app):
    client = upgraded_app.test_client()
    csrf = get_csrf(client)
    unknown = api_call(
        client,
        "post",
        f"{API}/auth/register",
        csrf_token=csrf,
        json={
            "login_name": "stu_ok02",
            "student_no": "20240101",
            "display_name": "x",
            "password": DEFAULT_PASSWORD,
            "active": True,
        },
    )
    assert unknown.status_code == 422

    first = register(client, csrf, login_name="stu_dup1", student_no="20240102")
    assert first.status_code == 201
    dup = register(client, csrf, login_name="stu_dup1", student_no="20240103")
    assert dup.status_code == 409


# ---- T-001-02 ----

def test_T001_02_teacher_cannot_reach_other_teachers_class(upgraded_app):
    """教师甲访问教师乙的班级对象得到 404；班级列表只含本人班级。"""
    ctx = seed_school(upgraded_app)
    teacher_a_client, _ = login_as(upgraded_app, "teacher_aaa")

    cross = teacher_a_client.get(f"{API}/classes/{ctx['class_b']['id']}/enrollments")
    assert cross.status_code == 404, cross.get_data(as_text=True)

    own = teacher_a_client.get(f"{API}/classes/{ctx['class_a']['id']}/enrollments")
    assert own.status_code == 200

    listed = teacher_a_client.get(f"{API}/classes").get_json()["data"]
    assert [c["id"] for c in listed] == [ctx["class_a"]["id"]]

    # 学生同样不能读别人班级的名单
    register_student(upgraded_app, "stu_cross", "20240200")
    student_client, _ = login_as(upgraded_app, "stu_cross")
    assert student_client.get(f"{API}/classes/{ctx['class_a']['id']}/enrollments").status_code == 403


def test_T001_02_admin_sees_all_classes(upgraded_app):
    ctx = seed_school(upgraded_app)
    admin_client, _ = ctx["admin"]
    listed = admin_client.get(f"{API}/classes?page_size=50").get_json()["data"]
    assert {c["id"] for c in listed} == {ctx["class_a"]["id"], ctx["class_b"]["id"]}


# ---- T-001-03 ----

def test_T001_03_missing_csrf_is_rejected(upgraded_app):
    client = upgraded_app.test_client()
    get_csrf(client)
    no_header = client.post(
        f"{API}/auth/register",
        json={
            "login_name": "stu_nocsr",
            "student_no": "20240104",
            "display_name": "无CSRF",
            "password": DEFAULT_PASSWORD,
        },
    )
    assert no_header.status_code == 403
    assert no_header.get_json()["error"]["code"] == "CSRF_FAILED"

    wrong = client.post(
        f"{API}/auth/register",
        headers={"X-CSRF-Token": "not-the-token"},
        json={
            "login_name": "stu_badcs",
            "student_no": "20240105",
            "display_name": "错CSRF",
            "password": DEFAULT_PASSWORD,
        },
    )
    assert wrong.status_code == 403


def test_T001_03_logout_invalidates_session(upgraded_app):
    ctx = seed_school(upgraded_app)
    client, csrf = login_as(upgraded_app, "teacher_aaa")
    sid = sid_of(client)

    assert api_call(client, "post", f"{API}/auth/logout", csrf_token=csrf).status_code == 200
    assert replay(upgraded_app, sid).status_code == 401
    assert client.get(f"{API}/me").status_code == 401


def test_T001_03_deactivation_invalidates_session(upgraded_app):
    ctx = seed_school(upgraded_app)
    admin_client, admin_csrf = ctx["admin"]
    teacher = ctx["teacher_a"]
    client, _ = login_as(upgraded_app, "teacher_aaa")
    sid = sid_of(client)
    assert client.get(f"{API}/me").status_code == 200

    response = api_call(
        admin_client,
        "patch",
        f"{API}/users/{teacher['id']}",
        csrf_token=admin_csrf,
        json={"version": teacher["version"], "active": False},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    assert replay(upgraded_app, sid).status_code == 401


def test_T001_03_password_change_invalidates_sessions(upgraded_app):
    register_student(upgraded_app, "stu_pwd01", "20240110")
    client, csrf = login_as(upgraded_app, "stu_pwd01")
    sid = sid_of(client)
    me = client.get(f"{API}/me").get_json()["data"]

    changed = api_call(
        client,
        "patch",
        f"{API}/me",
        csrf_token=csrf,
        json={
            "version": me["version"],
            "current_password": DEFAULT_PASSWORD,
            "new_password": "NewPassw0rd!24",
        },
    )
    assert changed.status_code == 200, changed.get_data(as_text=True)
    # 旧会话立即失效，必须重新登录
    assert replay(upgraded_app, sid).status_code == 401

    relogin = upgraded_app.test_client()
    token = get_csrf(relogin)
    assert login(relogin, token, login_name="stu_pwd01", password=DEFAULT_PASSWORD).status_code == 401
    assert (
        login(relogin, get_csrf(relogin), login_name="stu_pwd01", password="NewPassw0rd!24").status_code
        == 200
    )


def test_T001_03_change_password_requires_current_password(upgraded_app):
    register_student(upgraded_app, "stu_pwd02", "20240111")
    client, csrf = login_as(upgraded_app, "stu_pwd02")
    me = client.get(f"{API}/me").get_json()["data"]
    response = api_call(
        client,
        "patch",
        f"{API}/me",
        csrf_token=csrf,
        json={"version": me["version"], "new_password": "NewPassw0rd!24"},
    )
    assert response.status_code == 422


def test_T001_03_role_change_invalidates_session(upgraded_app):
    ctx = seed_school(upgraded_app)
    admin_client, admin_csrf = ctx["admin"]
    teacher = ctx["teacher_a"]
    client, _ = login_as(upgraded_app, "teacher_aaa")
    sid = sid_of(client)

    api_call(
        admin_client,
        "patch",
        f"{API}/users/{teacher['id']}",
        csrf_token=admin_csrf,
        json={"version": teacher["version"], "role": "student", "active": True},
    )
    assert replay(upgraded_app, sid).status_code == 401


# ---- T-001-04 ----

def test_T001_04_student_can_have_only_one_active_class(upgraded_app):
    ctx = seed_school(upgraded_app)
    admin_client, admin_csrf = ctx["admin"]
    student = register_student(upgraded_app, "stu_one", "20240300")

    first = api_call(
        admin_client,
        "put",
        f"{API}/classes/{ctx['class_a']['id']}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student["id"], "active": True},
    )
    assert first.status_code == 200, first.get_data(as_text=True)

    second = api_call(
        admin_client,
        "put",
        f"{API}/classes/{ctx['class_b']['id']}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student["id"], "active": True},
    )
    assert second.status_code == 409, second.get_data(as_text=True)

    # 先退出原班级后可以再加入另一班
    api_call(
        admin_client,
        "put",
        f"{API}/classes/{ctx['class_a']['id']}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student["id"], "active": False},
    )
    moved = api_call(
        admin_client,
        "put",
        f"{API}/classes/{ctx['class_b']['id']}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student["id"], "active": True},
    )
    assert moved.status_code == 200, moved.get_data(as_text=True)

    # 学生只能看到自己所在班级
    student_client, _ = login_as(upgraded_app, "stu_one")
    listed = student_client.get(f"{API}/classes").get_json()["data"]
    assert [c["id"] for c in listed] == [ctx["class_b"]["id"]]


def test_T001_04_teacher_change_takes_effect_immediately(upgraded_app):
    ctx = seed_school(upgraded_app)
    admin_client, admin_csrf = ctx["admin"]
    class_a = ctx["class_a"]

    old_teacher, _ = login_as(upgraded_app, "teacher_aaa")
    new_teacher, _ = login_as(upgraded_app, "teacher_bbb")
    assert old_teacher.get(f"{API}/classes/{class_a['id']}/enrollments").status_code == 200
    assert new_teacher.get(f"{API}/classes/{class_a['id']}/enrollments").status_code == 404

    swapped = api_call(
        admin_client,
        "patch",
        f"{API}/classes/{class_a['id']}",
        csrf_token=admin_csrf,
        json={"version": class_a["version"], "teacher_id": ctx["teacher_b"]["id"]},
    )
    assert swapped.status_code == 200, swapped.get_data(as_text=True)

    assert old_teacher.get(f"{API}/classes/{class_a['id']}/enrollments").status_code == 404
    assert new_teacher.get(f"{API}/classes/{class_a['id']}/enrollments").status_code == 200


# ---- 管理员保护与越权 ----

def test_last_admin_cannot_be_disabled_or_demoted(upgraded_app):
    create_admin(upgraded_app)
    admin_client, admin_csrf = login_as(upgraded_app, "admin_root", "Adm1nPass!23")
    me = admin_client.get(f"{API}/me").get_json()["data"]

    disabled = api_call(
        admin_client,
        "patch",
        f"{API}/users/{me['id']}",
        csrf_token=admin_csrf,
        json={"version": me["version"], "active": False},
    )
    assert disabled.status_code == 409, disabled.get_data(as_text=True)

    demoted = api_call(
        admin_client,
        "patch",
        f"{API}/users/{me['id']}",
        csrf_token=admin_csrf,
        json={"version": me["version"], "role": "teacher"},
    )
    assert demoted.status_code == 409

    # 有第二名管理员后即可降级其中一名
    second = api_call(
        admin_client,
        "post",
        f"{API}/users",
        csrf_token=admin_csrf,
        json={
            "login_name": "admin_two",
            "display_name": "第二管理员",
            "password": DEFAULT_PASSWORD,
            "role": "admin",
        },
    )
    assert second.status_code == 201
    now_ok = api_call(
        admin_client,
        "patch",
        f"{API}/users/{me['id']}",
        csrf_token=admin_csrf,
        json={"version": me["version"], "role": "teacher"},
    )
    assert now_ok.status_code == 200, now_ok.get_data(as_text=True)


def test_admin_endpoints_reject_non_admin(upgraded_app):
    register_student(upgraded_app, "stu_authz", "20240400")
    student_client, student_csrf = login_as(upgraded_app, "stu_authz")
    assert student_client.get(f"{API}/users").status_code == 403
    forbidden = api_call(
        student_client,
        "post",
        f"{API}/classes",
        csrf_token=student_csrf,
        json={"name": "学生建的班", "teacher_id": 1},
    )
    assert forbidden.status_code == 403


def test_anonymous_write_requires_session(upgraded_app):
    """未登录也没有匿名会话时，写请求按 CSRF 失败处理（403）。"""
    client = upgraded_app.test_client()
    response = client.post(f"{API}/auth/logout")
    assert response.status_code == 403


# ---- 凭据与令牌不泄露 ----

def test_password_hashed_and_secrets_never_exposed(upgraded_app):
    ctx = seed_school(upgraded_app)
    stored = scalar(
        upgraded_app,
        "SELECT password_hash FROM users WHERE login_name=?",
        ("teacher_aaa",),
    )
    assert stored and DEFAULT_PASSWORD not in stored
    assert stored != DEFAULT_PASSWORD

    admin_client, _ = ctx["admin"]
    listed = admin_client.get(f"{API}/users?page_size=50").get_json()
    for item in listed["data"]:
        assert "password_hash" not in item
    assert "password_hash" not in listed["data"][0]

    # 会话 Cookie 为 HttpOnly，且响应用户对象不含令牌字段
    client, _ = login_as(upgraded_app, "teacher_aaa")
    cookie = client.get_cookie("sid")
    assert cookie is not None
    assert cookie.http_only is True
    me = client.get(f"{API}/me").get_json()["data"]
    assert set(me) == {"id", "login_name", "student_no", "display_name", "role", "active", "version"}

    # 库里存的是散列，不是明文会话标识
    token_hashes = [
        row[0]
        for row in upgraded_app.extensions["db_engine"]
        .connect()
        .exec_driver_sql("SELECT token_hash FROM sessions")
    ]
    assert all(len(h) == 64 for h in token_hashes)


def test_login_session_is_rotated(upgraded_app):
    """登录成功后会话标识与匿名阶段不同（ADR-004 轮换）。"""
    register_student(upgraded_app, "stu_rot", "20240500")
    client = upgraded_app.test_client()
    csrf = get_csrf(client)
    anonymous_sid = sid_of(client)
    response = login(client, csrf, login_name="stu_rot")
    assert response.status_code == 200
    assert sid_of(client) != anonymous_sid


def test_login_rate_limited_after_repeated_failures(upgraded_app):
    auth_module._login_failures.clear()
    client = upgraded_app.test_client()
    for _ in range(auth_module.LOGIN_FAIL_LIMIT):
        csrf = get_csrf(client)
        assert login(client, csrf, login_name="nobody_x", password="WrongPass!23").status_code == 401
    csrf = get_csrf(client)
    limited = login(client, csrf, login_name="nobody_x", password="WrongPass!23")
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    auth_module._login_failures.clear()


# ---- 管理员初始化命令 ----

def test_init_admin_refuses_duplicate_login_name(upgraded_app):
    create_admin(upgraded_app)
    runner = upgraded_app.test_cli_runner()
    again = runner.invoke(args=["init-admin", "--login-name", "admin_root", "--password", "Adm1nPass!23"])
    assert again.exit_code != 0
    assert scalar(upgraded_app, "SELECT COUNT(*) FROM users WHERE role='admin'") == 1


def test_init_admin_rejects_short_password(upgraded_app):
    runner = upgraded_app.test_cli_runner()
    result = runner.invoke(args=["init-admin", "--login-name", "admin_x", "--password", "short"])
    assert result.exit_code != 0
    assert scalar(upgraded_app, "SELECT COUNT(*) FROM users WHERE role='admin'") == 0
