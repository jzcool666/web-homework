"""SPEC-005 课程知识与教学资源：T-005-01 至 T-005-04 及配套边界。

固定数据 + 独立数据库与独立上传目录：夹具用 `tmp_path` 显式指定
DATABASE_URL 与 UPLOAD_DIR，不触碰仓库内的 instance/。
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from app import api_content, create_app
from app.seed_content import SEED_EDGES, find_cycle
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

# 文件头正确的最小样例：类型校验同时看扩展名与文件头
PNG_V1 = b"\x89PNG\r\n\x1a\n" + b"first version body"
PNG_V2 = b"\x89PNG\r\n\x1a\n" + b"second version body"


# ---- 公共夹具 ----

def login_as(app, login_name: str, password: str = DEFAULT_PASSWORD):
    """返回 (client, csrf_token)；登录会轮换 CSRF，必须取响应里的新值。"""
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


@pytest.fixture
def school(tmp_path: Path):
    """管理员 + 两教师 + 两班（各一名已入班学生）+ 一名未入班学生。"""
    app = create_app(
        "testing",
        {
            "DATABASE_URL": sqlite_url(tmp_path / "content.sqlite"),
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

    try:
        yield {
            "app": app,
            "admin": (admin, admin_csrf),
            "teacher_a": teacher_a,
            "teacher_b": teacher_b,
            "class_a": class_a,
            "class_b": class_b,
            "student_a": student_a,
            "student_b": student_b,
            "outsider": outsider,
            "uploads": tmp_path / "uploads",
        }
    finally:
        app.extensions["db_engine"].dispose()


# ---- 内容构造助手 ----

def create_chapter(client, csrf, *, title="第一单元 时序基础", sort_order=1, published=True):
    return api_call(
        client,
        "post",
        f"{API}/chapters",
        csrf_token=csrf,
        json={"title": title, "sort_order": sort_order, "published": published},
    )


def create_knowledge(
    client,
    csrf,
    chapter_id: int,
    *,
    title="组合逻辑与时序逻辑的区别",
    body_md="组合逻辑只看当前输入。",
    published=True,
    sort_order=1,
    source_url=None,
):
    payload = {
        "chapter_id": chapter_id,
        "title": title,
        "body_md": body_md,
        "sort_order": sort_order,
        "published": published,
    }
    if source_url is not None:
        payload["source_url"] = source_url
    return api_call(
        client, "post", f"{API}/knowledge-points", csrf_token=csrf, json=payload
    )


def create_resource(client, csrf, **over):
    payload = {"title": "模6计数器讲义", "category": "slides", "published": True}
    payload.update(over)
    return api_call(client, "post", f"{API}/resources", csrf_token=csrf, json=payload)


def upload_version(client, csrf, resource_id: int, filename: str, payload: bytes, note="v1"):
    return api_call(
        client,
        "post",
        f"{API}/resources/{resource_id}/versions",
        csrf_token=csrf,
        data={"file": (io.BytesIO(payload), filename), "note": note},
        content_type="multipart/form-data",
    )


def knowledge_edges(app) -> list[tuple[int, int]]:
    """直接从库里读出先修边，供无环校验使用。"""
    with app.extensions["db_engine"].connect() as connection:
        return [
            (row[0], row[1])
            for row in connection.exec_driver_sql(
                "SELECT prerequisite_id, target_id FROM knowledge_edges"
            )
        ]


# ---- T-005-01：资源版本不可覆盖、非法文件名不能执行或越界 ----

def test_T005_01_new_version_leaves_old_download_unchanged(school):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    resource = create_resource(teacher, csrf).get_json()["data"]

    first = upload_version(teacher, csrf, resource["id"], "讲义.png", PNG_V1)
    assert first.status_code == 201, first.get_data(as_text=True)
    v1 = first.get_json()["data"]
    assert v1["version_no"] == 1 and v1["kind"] == "file"
    assert v1["original_name"] == "讲义.png"
    assert v1["size_bytes"] == len(PNG_V1)
    assert "storage_key" not in v1 and "sha256" not in v1

    old_hash_before = hashlib.sha256(PNG_V1).hexdigest()

    second = upload_version(teacher, csrf, resource["id"], "讲义.png", PNG_V2, note="v2")
    assert second.status_code == 201
    v2 = second.get_json()["data"]
    assert v2["version_no"] == 2, "新版本必须追加，不覆盖旧版本号"

    # 旧版本仍指向原文件，下载内容哈希不变
    download = teacher.get(f"{API}/resource-versions/{v1['id']}/download")
    assert download.status_code == 200, download.get_data(as_text=True)
    assert hashlib.sha256(download.data).hexdigest() == old_hash_before
    assert download.data == PNG_V1
    assert download.headers["Content-Type"].startswith("image/png")

    # 版本记录本身没有被改写
    assert scalar(
        app, "SELECT COUNT(*) FROM resource_versions WHERE resource_id = ?", (resource["id"],)
    ) == 2
    assert scalar(app, "SELECT version_no FROM resource_versions WHERE id = ?", (v1["id"],)) == 1


def test_T005_01_rejects_illegal_extension_and_content(school):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    resource = create_resource(teacher, csrf).get_json()["data"]

    for filename in ("payload.exe", "shell.php", "notes.txt", "diagram.svg", "archive.zip"):
        response = upload_version(teacher, csrf, resource["id"], filename, PNG_V1)
        assert response.status_code == 415, filename
        assert response.get_json()["error"]["code"] == "FILE_TYPE_UNSUPPORTED"

    # 扩展名合法但文件头不符：改后缀不能绕过类型校验
    renamed = upload_version(teacher, csrf, resource["id"], "fake.png", b"MZ\x90\x00 not an image")
    assert renamed.status_code == 415

    # 失败的上传不留下版本记录，也不留下磁盘文件
    assert scalar(
        app, "SELECT COUNT(*) FROM resource_versions WHERE resource_id = ?", (resource["id"],)
    ) == 0
    resource_dir = school["uploads"] / "resources"
    assert not resource_dir.exists() or not any(resource_dir.iterdir())


def test_T005_01_path_like_filename_is_stored_under_random_name(school):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    resource = create_resource(teacher, csrf).get_json()["data"]

    response = upload_version(teacher, csrf, resource["id"], "../../../evil.png", PNG_V1)
    assert response.status_code == 201, response.get_data(as_text=True)
    version = response.get_json()["data"]
    # 显示名只保留最后一段，磁盘路径不被原始文件名影响
    assert version["original_name"] == "evil.png"

    storage_key = scalar(
        app, "SELECT storage_key FROM resource_versions WHERE id = ?", (version["id"],)
    )
    root = (school["uploads"] / "resources").resolve()
    stored = (school["uploads"] / storage_key).resolve()
    assert stored.is_relative_to(root), "落盘路径必须在上传根目录之内"
    assert stored.parent == root and stored.name != "evil.png"
    assert stored.name.endswith(".png") and len(stored.stem) == 32, "随机文件名"

    # 下载响应的文件名同样不携带路径
    download = teacher.get(f"{API}/resource-versions/{version['id']}/download")
    assert download.status_code == 200
    disposition = download.headers["Content-Disposition"]
    assert "evil.png" in disposition and ".." not in disposition


def test_T005_01_upload_limits_and_link_rules(school):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    resource = create_resource(teacher, csrf).get_json()["data"]

    oversized = upload_version(
        teacher, csrf, resource["id"], "big.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * (21 * 1024 * 1024)
    )
    assert oversized.status_code == 413
    assert oversized.get_json()["error"]["code"] == "FILE_TOO_LARGE"

    linked = api_call(
        teacher,
        "post",
        f"{API}/resources/{resource['id']}/versions",
        csrf_token=csrf,
        json={"external_url": "https://computationstructures.org/notes/sequential_logic/notes.html"},
    )
    assert linked.status_code == 201, linked.get_data(as_text=True)
    version = linked.get_json()["data"]
    assert version["kind"] == "link" and version["external_url"].startswith("https://")

    # 链接类不提供文件下载
    download = teacher.get(f"{API}/resource-versions/{version['id']}/download")
    assert download.status_code == 422

    # 外链只允许 http/https；javascript: 与 file: 一律拒绝
    for bad in ("javascript:alert(1)", "file:///etc/passwd", "ftp://example.org/x", "http:///missing-host"):
        rejected = api_call(
            teacher,
            "post",
            f"{API}/resources/{resource['id']}/versions",
            csrf_token=csrf,
            json={"external_url": bad},
        )
        assert rejected.status_code == 422, bad


def test_invalid_upload_note_does_not_leave_orphan_file(school):
    teacher, csrf = login_as(school["app"], "teacher_aaa")
    resource = create_resource(teacher, csrf).get_json()["data"]
    upload_dir = school["uploads"] / "resources"
    before = set(upload_dir.iterdir()) if upload_dir.exists() else set()
    rejected = upload_version(teacher, csrf, resource["id"], "讲义.png", PNG_V1, note="x" * 201)
    assert rejected.status_code == 422
    after = set(upload_dir.iterdir()) if upload_dir.exists() else set()
    assert after == before


# ---- T-005-02：草稿可见性与越权 ----

def test_T005_02_student_cannot_read_draft_or_write_content(school):
    app = school["app"]
    teacher, teacher_csrf = login_as(app, "teacher_aaa")
    chapter = create_chapter(teacher, teacher_csrf).get_json()["data"]
    published = create_knowledge(teacher, teacher_csrf, chapter["id"]).get_json()["data"]
    draft = create_knowledge(
        teacher, teacher_csrf, chapter["id"], title="草稿知识点", published=False
    ).get_json()["data"]

    student, student_csrf = login_as(app, "stu_a0001")

    # 学生读草稿：按不存在处理
    assert student.get(f"{API}/knowledge-points/{draft['id']}").status_code == 404
    listed = student.get(f"{API}/knowledge-points?page_size=100").get_json()["data"]
    assert [item["id"] for item in listed] == [published["id"]]

    # 越权修改：学生不是内容所有者
    assert api_call(
        student,
        "patch",
        f"{API}/knowledge-points/{published['id']}",
        csrf_token=student_csrf,
        json={"version": published["version"], "title": "改个名"},
    ).status_code == 403
    assert create_chapter(student, student_csrf).status_code == 403
    assert create_knowledge(student, student_csrf, chapter["id"]).status_code == 403
    assert create_resource(student, student_csrf).status_code == 403

    # 教师乙也看不到教师甲的草稿，改不了教师甲的内容
    teacher_b, teacher_b_csrf = login_as(app, "teacher_bbb")
    assert teacher_b.get(f"{API}/knowledge-points/{draft['id']}").status_code == 404
    assert api_call(
        teacher_b,
        "patch",
        f"{API}/knowledge-points/{published['id']}",
        csrf_token=teacher_b_csrf,
        json={"version": published["version"], "title": "改个名"},
    ).status_code == 403
    assert api_call(
        teacher_b,
        "patch",
        f"{API}/chapters/{chapter['id']}",
        csrf_token=teacher_b_csrf,
        json={"version": chapter["version"], "title": "改个名"},
    ).status_code == 403
    # 但可以引用已发布内容
    assert teacher_b.get(f"{API}/knowledge-points/{published['id']}").status_code == 200


def test_T005_02_script_markdown_is_returned_as_plain_data(school):
    """渲染由前端净化；后端只以 JSON 字符串原样返回，不生成可执行 HTML。"""
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    chapter = create_chapter(teacher, csrf).get_json()["data"]
    payload = "正常内容\n\n<script>window.__pwned = 1</script>\n\n<img src=x onerror=alert(1)>"
    point = create_knowledge(teacher, csrf, chapter["id"], body_md=payload).get_json()["data"]

    response = teacher.get(f"{API}/knowledge-points/{point['id']}")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/json")
    # 原文保留，但只作为 JSON 字符串字段出现
    assert response.get_json()["data"]["body_md"] == payload
    assert b"<script" in response.data and b"text/html" not in response.data


def test_T005_02_unenrolled_student_cannot_read_course_content(school):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    chapter = create_chapter(teacher, csrf).get_json()["data"]
    point = create_knowledge(teacher, csrf, chapter["id"]).get_json()["data"]

    outsider, outsider_csrf = login_as(app, "stu_x0001")
    for path in ("/chapters", "/knowledge-points", "/resources"):
        response = outsider.get(f"{API}{path}")
        assert response.status_code == 403, path
        assert response.get_json()["error"]["code"] == "FORBIDDEN"
    assert outsider.get(f"{API}/knowledge-points/1").status_code == 403
    assert api_call(
        outsider, "put", f"{API}/me/favorites/{point['id']}", csrf_token=outsider_csrf,
        json={},
    ).status_code == 403
    assert api_call(
        outsider, "put", f"{API}/me/learning-progress", csrf_token=outsider_csrf,
        json={"knowledge_id": point["id"], "completed": True},
    ).status_code == 403


def test_T005_02_anonymous_is_unauthenticated(school):
    fresh = school["app"].test_client()
    assert fresh.get(f"{API}/chapters").status_code == 401
    assert fresh.get(f"{API}/knowledge-points").status_code == 401


def test_T005_02_version_conflict_on_stale_patch(school):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    chapter = create_chapter(teacher, csrf).get_json()["data"]

    ok = api_call(
        teacher,
        "patch",
        f"{API}/chapters/{chapter['id']}",
        csrf_token=csrf,
        json={"version": chapter["version"], "title": "改名后"},
    )
    assert ok.status_code == 200 and ok.get_json()["data"]["version"] == chapter["version"] + 1

    stale = api_call(
        teacher,
        "patch",
        f"{API}/chapters/{chapter['id']}",
        csrf_token=csrf,
        json={"version": chapter["version"], "title": "再改"},
    )
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "VERSION_CONFLICT"


# ---- T-005-03：收藏与进度幂等 ----

def test_T005_03_repeat_favorite_creates_one_row_and_unfavorite_can_return(school):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    chapter = create_chapter(teacher, csrf).get_json()["data"]
    point = create_knowledge(teacher, csrf, chapter["id"]).get_json()["data"]

    student, student_csrf = login_as(app, "stu_a0001")
    path = f"{API}/me/favorites/{point['id']}"

    for _ in range(2):
        response = api_call(student, "put", path, csrf_token=student_csrf)
        assert response.status_code == 200
        assert response.get_json()["data"] == {"knowledge_id": point["id"], "favorited": True}

    assert scalar(
        app,
        "SELECT COUNT(*) FROM favorites WHERE student_id = ? AND knowledge_id = ?",
        (school["student_a"]["id"], point["id"]),
    ) == 1, "重复收藏只保留一条"

    listed = student.get(f"{API}/me/favorites").get_json()["data"]
    assert [item["id"] for item in listed] == [point["id"]]

    removed = api_call(student, "delete", path, csrf_token=student_csrf)
    assert removed.status_code == 200
    assert removed.get_json()["data"] == {"knowledge_id": point["id"], "favorited": False}
    assert student.get(f"{API}/me/favorites").get_json()["data"] == []

    # 取消未收藏的内容同样幂等成功
    assert api_call(student, "delete", path, csrf_token=student_csrf).status_code == 200

    again = api_call(student, "put", path, csrf_token=student_csrf)
    assert again.status_code == 200 and again.get_json()["data"]["favorited"] is True
    assert scalar(
        app,
        "SELECT COUNT(*) FROM favorites WHERE student_id = ? AND knowledge_id = ?",
        (school["student_a"]["id"], point["id"]),
    ) == 1

    # 收藏草稿知识点按不存在处理
    draft = create_knowledge(
        teacher, csrf, chapter["id"], title="草稿知识点", published=False
    ).get_json()["data"]
    assert api_call(
        student, "put", f"{API}/me/favorites/{draft['id']}", csrf_token=student_csrf
    ).status_code == 404

    # 教师不能使用学生专属的学习记录接口
    other_teacher, other_csrf = login_as(app, "teacher_bbb")
    assert api_call(
        other_teacher, "put", path, csrf_token=other_csrf
    ).status_code == 403


def test_T005_03_progress_completion_toggles_consistently(school):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    chapter = create_chapter(teacher, csrf).get_json()["data"]
    point = create_knowledge(teacher, csrf, chapter["id"]).get_json()["data"]

    student, student_csrf = login_as(app, "stu_a0001")
    path = f"{API}/me/learning-progress"

    first = api_call(
        student, "put", path, csrf_token=student_csrf,
        json={"knowledge_id": point["id"], "completed": True},
    )
    assert first.status_code == 200
    body = first.get_json()["data"]
    assert body["completed"] is True and body["completed_at"] is not None

    repeat = api_call(
        student, "put", path, csrf_token=student_csrf,
        json={"knowledge_id": point["id"], "completed": True},
    )
    assert repeat.get_json()["data"] == body, "重复标记完成不应改变 completed_at"

    cancelled = api_call(
        student, "put", path, csrf_token=student_csrf,
        json={"knowledge_id": point["id"], "completed": False},
    )
    assert cancelled.get_json()["data"] == {
        "knowledge_id": point["id"],
        "completed": False,
        "completed_at": None,
    }, "取消完成应清空 completed_at"

    redone = api_call(
        student, "put", path, csrf_token=student_csrf,
        json={"knowledge_id": point["id"], "completed": True},
    )
    assert redone.get_json()["data"]["completed_at"] is not None

    assert scalar(
        app,
        "SELECT COUNT(*) FROM learning_progress WHERE student_id = ? AND knowledge_id = ?",
        (school["student_a"]["id"], point["id"]),
    ) == 1, "同一学生对同一知识点只保留一条进度"

    listed = student.get(f"{path}?chapter_id={chapter['id']}").get_json()["data"]
    assert len(listed) == 1 and listed[0]["completed"] is True

    # 进度与收藏互相独立：进度不影响收藏列表
    assert student.get(f"{API}/me/favorites").get_json()["data"] == []


# ---- T-005-04：资源事件按 UTC 日去重 ----

def test_T005_04_resource_events_dedup_by_utc_day(school, monkeypatch):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    resource = create_resource(teacher, csrf).get_json()["data"]
    version = upload_version(teacher, csrf, resource["id"], "讲义.png", PNG_V1).get_json()["data"]

    student, student_csrf = login_as(app, "stu_a0001")
    path = f"{API}/resource-versions/{version['id']}/events"

    monkeypatch.setattr(api_content, "utc_day", lambda: "2026-09-29")
    first = api_call(student, "post", path, csrf_token=student_csrf, json={"event_kind": "open"})
    assert first.get_json()["data"] == {"recorded": True}

    for _ in range(3):
        again = api_call(student, "post", path, csrf_token=student_csrf, json={"event_kind": "open"})
        assert again.get_json()["data"] == {"recorded": False}

    assert scalar(
        app,
        "SELECT COUNT(*) FROM resource_events WHERE resource_version_id = ? AND event_kind = 'open'",
        (version["id"],),
    ) == 1, "一天内重复打开同版本只计一次"

    # 同一天下载是另一个种类，独立计数
    download = api_call(
        student, "post", path, csrf_token=student_csrf, json={"event_kind": "download"}
    )
    assert download.get_json()["data"] == {"recorded": True}

    # 次日可新增
    monkeypatch.setattr(api_content, "utc_day", lambda: "2026-09-30")
    next_day = api_call(student, "post", path, csrf_token=student_csrf, json={"event_kind": "open"})
    assert next_day.get_json()["data"] == {"recorded": True}

    # 另一名学生独立计数
    other, other_csrf = login_as(app, "stu_b0001")
    assert api_call(
        other, "post", path, csrf_token=other_csrf, json={"event_kind": "open"}
    ).get_json()["data"] == {"recorded": True}

    assert scalar(
        app, "SELECT COUNT(*) FROM resource_events WHERE resource_version_id = ?", (version["id"],)
    ) == 4  # 甲: open 两日 + download 一日；乙: open 一日

    # 非法种类与不可见版本
    bad = api_call(student, "post", path, csrf_token=student_csrf, json={"event_kind": "view"})
    assert bad.status_code == 422
    draft_resource = create_resource(teacher, csrf, title="草稿资源", published=False).get_json()["data"]
    draft_version = upload_version(
        teacher, csrf, draft_resource["id"], "草稿.png", PNG_V1
    ).get_json()["data"]
    assert api_call(
        student,
        "post",
        f"{API}/resource-versions/{draft_version['id']}/events",
        csrf_token=student_csrf,
        json={"event_kind": "open"},
    ).status_code == 404


# ---- 课程种子与先修关系 ----

def test_seed_content_is_idempotent_and_acyclic(school):
    app = school["app"]
    owner_login = "teacher_aaa"
    runner = app.test_cli_runner()

    first = runner.invoke(args=["seed-content", "--owner-login", owner_login])
    assert first.exit_code == 0, first.output
    assert "知识点 +12" in first.output and "先修关系 +15" in first.output

    # 六单元 12 知识点
    assert scalar(app, "SELECT COUNT(*) FROM chapters") == 6
    assert scalar(app, "SELECT COUNT(*) FROM knowledge_points WHERE published = 1") == 12
    assert scalar(app, "SELECT COUNT(*) FROM resources") == 1

    edges = knowledge_edges(app)
    assert len(edges) == len(SEED_EDGES) == 15
    assert find_cycle(edges) is None, "课程种子必须无环"

    second = runner.invoke(args=["seed-content", "--owner-login", owner_login])
    assert second.exit_code == 0, second.output
    assert "章节 +0，知识点 +0，先修关系 +0，资源 +0" in second.output
    assert scalar(app, "SELECT COUNT(*) FROM chapters") == 6
    assert scalar(app, "SELECT COUNT(*) FROM knowledge_points") == 12
    assert scalar(app, "SELECT COUNT(*) FROM knowledge_edges") == 15

    # 计数器案例的位序/初态/复位/有效沿必须写进正文
    body = scalar(
        app,
        "SELECT body_md FROM knowledge_points WHERE title LIKE '%模 6 计数器%'",
    )
    for keyword in ("Q3Q2Q1Q0", "0000", "同步高有效", "上升沿"):
        assert keyword in body, keyword


def test_seed_content_requires_a_teacher(school):
    app = school["app"]
    runner = app.test_cli_runner()
    missing = runner.invoke(args=["seed-content", "--owner-login", "stu_a0001"])
    assert missing.exit_code != 0
    assert "不是有效的教师/管理员" in missing.output


def test_find_cycle_detects_a_loop():
    assert find_cycle([(1, 2), (2, 3)]) is None
    assert find_cycle([]) is None
    assert find_cycle([(1, 2), (2, 3), (3, 1)]) is not None


# ---- 资源与章节的列表接口 ----

def test_resource_listing_hides_drafts_from_students(school):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    published = create_resource(teacher, csrf, title="已发布讲义").get_json()["data"]
    create_resource(teacher, csrf, title="草稿讲稿", category="guide", published=False)

    teacher_list = teacher.get(f"{API}/resources?page_size=100").get_json()
    assert {r["title"] for r in teacher_list["data"]} == {"已发布讲义", "草稿讲稿"}
    assert teacher_list["meta"]["total"] == 2

    student, _ = login_as(app, "stu_a0001")
    student_list = student.get(f"{API}/resources?page_size=100").get_json()
    assert [r["title"] for r in student_list["data"]] == ["已发布讲义"]
    assert student_list["data"][0]["id"] == published["id"]
    assert student_list["data"][0]["versions"] == []

    # 学生下载草稿资源的版本按不存在处理
    draft = teacher.get(f"{API}/resources?category=guide").get_json()["data"][0]
    version = upload_version(teacher, csrf, draft["id"], "草稿.png", PNG_V1).get_json()["data"]
    assert student.get(f"{API}/resource-versions/{version['id']}/download").status_code == 404
    assert teacher.get(f"{API}/resource-versions/{version['id']}/download").status_code == 200


def test_unknown_fields_and_bad_arguments_are_rejected(school):
    app = school["app"]
    teacher, csrf = login_as(app, "teacher_aaa")
    chapter = create_chapter(teacher, csrf).get_json()["data"]

    injected = api_call(
        teacher,
        "post",
        f"{API}/chapters",
        csrf_token=csrf,
        json={"title": "越权尝试", "sort_order": 1, "published": True, "owner_id": 99},
    )
    assert injected.status_code == 422
    assert "owner_id" in injected.get_json()["error"]["details"]["unknown_fields"]

    assert teacher.get(f"{API}/knowledge-points?page_size=0").status_code == 400
    assert teacher.get(f"{API}/knowledge-points?chapter_id=abc").status_code == 400

    bad_url = create_knowledge(
        teacher, csrf, chapter["id"], source_url="javascript:alert(1)"
    )
    assert bad_url.status_code == 422
    assert "source_url" in bad_url.get_json()["error"]["details"]["fields"]

    missing_chapter = api_call(
        teacher,
        "post",
        f"{API}/knowledge-points",
        csrf_token=csrf,
        json={
            "chapter_id": 9999,
            "title": "无主知识点",
            "body_md": "内容",
            "sort_order": 1,
            "published": True,
        },
    )
    assert missing_chapter.status_code == 422

    bad_category = create_resource(teacher, csrf, category="video2")
    assert bad_category.status_code == 422
