"""SPEC-008 备课与预习发布：T-008-01 至 T-008-04 及配套边界。

覆盖：四种条目的备课单与顺序、复制与引用稳定性、跨班隔离与题目答案隐藏、
发布快照不可变，以及引用可见性、权限与字段校验。

每个用例使用自己的临时数据库；预习快照是「发布时冻结」的，因此若干断言直接读
`preview_assignments.snapshot_json` 核对冻结内容。
"""

from __future__ import annotations

import json

import pytest

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

ADMIN_PASSWORD = "Adm1nPass!23"
STAMP = "2026-09-29T01:00:00Z"


def login_as(app, login_name: str, password: str = DEFAULT_PASSWORD):
    client = app.test_client()
    csrf = get_csrf(client)
    response = login(client, csrf, login_name=login_name, password=password)
    assert response.status_code == 200, response.get_data(as_text=True)
    return client, response.get_json()["data"]["csrf_token"]


def post_as(app, actor, method, path, payload=None):
    client, token = actor
    kwargs = {"json": payload} if payload is not None else {}
    return api_call(client, method, path, csrf_token=token, **kwargs)


def create_question(app, teacher, knowledge_id, *, published=True, stem="备课用题"):
    response = post_as(app, teacher, "post", f"{API}/questions", {
        "type": "single",
        "stem_md": stem,
        "options": [{"key": "A", "label": "正确"}, {"key": "B", "label": "错误"}],
        "answer": ["A"],
        "explanation_md": "这是解析，预习快照里不应出现。",
        "difficulty": 1,
        "knowledge_ids": [knowledge_id],
        "published": published,
    })
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def create_experiment(app, teacher, knowledge_id, *, published=True, title="备课用实验"):
    response = post_as(app, teacher, "post", f"{API}/experiments", {
        "title": title,
        "knowledge_id": knowledge_id,
        "simulator_type": "d",
        "config": {"initial_q": 0},
        "steps_md": "按下 CLK 观察 Q 的变化。",
        "input_sequence": [],
        "published": published,
    })
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def create_resource_with_version(app, teacher, knowledge_id, *, published=True, url="https://example.com/a.pdf"):
    resource = post_as(app, teacher, "post", f"{API}/resources", {
        "title": "备课用资料", "category": "slides",
        "knowledge_id": knowledge_id, "published": published,
    }).get_json()["data"]
    version = post_as(app, teacher, "post", f"{API}/resources/{resource['id']}/versions", {
        "external_url": url, "note": "第一版",
    })
    assert version.status_code == 201, version.get_data(as_text=True)
    return resource, version.get_json()["data"]


@pytest.fixture
def school(upgraded_app):
    app = upgraded_app
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", ADMIN_PASSWORD)
    actor_admin = (admin, admin_csrf)

    def new_teacher(login_name, display_name):
        return post_as(app, actor_admin, "post", f"{API}/users", {
            "login_name": login_name, "display_name": display_name,
            "password": DEFAULT_PASSWORD, "role": "teacher",
        }).get_json()["data"]

    teacher_a = new_teacher("teacher_aaa", "教师甲")
    teacher_b = new_teacher("teacher_bbb", "教师乙")
    class_a = post_as(app, actor_admin, "post", f"{API}/classes", {
        "name": "时序逻辑甲班", "teacher_id": teacher_a["id"],
    }).get_json()["data"]
    class_b = post_as(app, actor_admin, "post", f"{API}/classes", {
        "name": "时序逻辑乙班", "teacher_id": teacher_b["id"],
    }).get_json()["data"]

    ta = login_as(app, "teacher_aaa")
    tb = login_as(app, "teacher_bbb")

    chapter = post_as(app, ta, "post", f"{API}/chapters", {
        "title": "时序逻辑基础", "sort_order": 0, "published": True,
    }).get_json()["data"]
    point = post_as(app, ta, "post", f"{API}/knowledge-points", {
        "chapter_id": chapter["id"], "title": "同步复位",
        "body_md": "复位优先，" + "正文" * 120, "source_url": None,
        "sort_order": 0, "published": True,
    }).get_json()["data"]
    shared_point = post_as(app, ta, "post", f"{API}/knowledge-points", {
        "chapter_id": chapter["id"], "title": "异步复位",
        "body_md": "时钟无关", "source_url": None,
        "sort_order": 1, "published": True,
    }).get_json()["data"]

    students = {}
    for index, (login_name, number) in enumerate(
        [("stu_a1", "20241101"), ("stu_a2", "20241102"), ("stu_b1", "20241111")], start=1
    ):
        client = app.test_client()
        csrf = get_csrf(client)
        response = register(client, csrf, login_name=login_name, student_no=number)
        assert response.status_code == 201, response.get_data(as_text=True)
        students[login_name] = response.get_json()["data"]

    for login_name, class_id in (("stu_a1", class_a["id"]), ("stu_a2", class_a["id"]), ("stu_b1", class_b["id"])):
        post_as(app, actor_admin, "put", f"{API}/classes/{class_id}/enrollments", {
            "student_id": students[login_name]["id"], "active": True,
        })

    return {
        "app": app,
        "admin": actor_admin,
        "ta": ta,
        "tb": tb,
        "teacher_a": teacher_a,
        "teacher_b": teacher_b,
        "class_a": class_a,
        "class_b": class_b,
        "point": point,
        "shared_point": shared_point,
        "students": students,
        "sa1": login_as(app, "stu_a1"),
        "sa2": login_as(app, "stu_a2"),
        "sb1": login_as(app, "stu_b1"),
    }


def snapshot_of(school, preview_id):
    raw = scalar(school["app"], "SELECT snapshot_json FROM preview_assignments WHERE id=?", (preview_id,))
    return json.loads(raw)


# ---- T-008-01 四种条目与顺序 ----

def test_T008_01_plan_with_four_target_kinds_is_returned_in_sort_order(school):
    app = school["app"]
    point = school["point"]["id"]
    shared = school["shared_point"]["id"]
    _resource, version = create_resource_with_version(app, school["ta"], point)
    question = create_question(app, school["ta"], point)
    experiment = create_experiment(app, school["ta"], point)

    # 故意乱序提交，验证返回按 sort_order 排列
    created = post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "第 3 周备课",
        "planned_at": STAMP,
        "notes": "先讲同步复位，再演示 D 触发器。",
        "items": [
            {"sort_order": 4, "target_type": "experiment", "target_id": experiment["id"]},
            {"sort_order": 1, "target_type": "knowledge", "target_id": shared},
            {"sort_order": 3, "target_type": "question", "target_id": question["id"]},
            {"sort_order": 2, "target_type": "resource_version", "target_id": version["id"]},
        ],
    })
    assert created.status_code == 201, created.get_data(as_text=True)
    body = created.get_json()["data"]
    assert body["title"] == "第 3 周备课"
    assert body["planned_at"] == STAMP
    assert body["owner_id"] == school["teacher_a"]["id"]
    assert [(item["sort_order"], item["target_type"], item["target_id"]) for item in body["items"]] == [
        (1, "knowledge", shared),
        (2, "resource_version", version["id"]),
        (3, "question", question["id"]),
        (4, "experiment", experiment["id"]),
    ]
    assert all(set(item) == {"sort_order", "target_type", "target_id"} for item in body["items"])

    # GET 与列表都按同一顺序
    fetched = post_as(app, school["ta"], "get", f"{API}/lesson-plans/{body['id']}").get_json()["data"]
    assert [item["sort_order"] for item in fetched["items"]] == [1, 2, 3, 4]
    listed = post_as(app, school["ta"], "get", f"{API}/lesson-plans?page_size=100").get_json()["data"]
    assert [plan["id"] for plan in listed] == [body["id"]]

    # 库内四列外键各只落一列
    rows = scalar(
        app,
        "SELECT COUNT(*) FROM lesson_plan_items WHERE plan_id=? AND "
        "((knowledge_id IS NOT NULL) + (resource_version_id IS NOT NULL) + "
        "(question_id IS NOT NULL) + (experiment_id IS NOT NULL)) = 1",
        (body["id"],),
    )
    assert rows == 4


def test_T008_01_item_structure_is_validated(school):
    app = school["app"]
    point = school["point"]["id"]

    def create(items):
        return post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
            "title": "校验用", "items": items,
        })

    duplicated = create([
        {"sort_order": 1, "target_type": "knowledge", "target_id": point},
        {"sort_order": 1, "target_type": "knowledge", "target_id": school["shared_point"]["id"]},
    ])
    assert duplicated.status_code == 422
    assert "sort_order" in duplicated.get_json()["error"]["details"]["fields"]["items"]

    bad_type = create([{"sort_order": 1, "target_type": "chapter", "target_id": 1}])
    assert bad_type.status_code == 422

    missing_target = create([{"sort_order": 1, "target_type": "knowledge"}])
    assert missing_target.status_code == 422

    unknown_field = create([
        {"sort_order": 1, "target_type": "knowledge", "target_id": point, "answer": ["A"]},
    ])
    assert unknown_field.status_code == 422

    nonexistent = create([{"sort_order": 1, "target_type": "knowledge", "target_id": 999999}])
    assert nonexistent.status_code == 422
    assert "items" in nonexistent.get_json()["error"]["details"]["fields"]

    bad_order = create([{"sort_order": 0, "target_type": "knowledge", "target_id": point}])
    assert bad_order.status_code == 422


def test_T008_01_only_visible_content_can_be_referenced(school):
    app = school["app"]
    # 甲班教师把知识点撤回为草稿，另一位教师不可引用
    draft_point = post_as(app, school["ta"], "post", f"{API}/knowledge-points", {
        "chapter_id": school["point"]["chapter_id"], "title": "甲班草稿知识点",
        "body_md": "草稿", "source_url": None, "sort_order": 5, "published": False,
    }).get_json()["data"]

    mine = post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "引用本人草稿", "items": [
            {"sort_order": 1, "target_type": "knowledge", "target_id": draft_point["id"]},
        ],
    })
    assert mine.status_code == 201, mine.get_data(as_text=True)

    other = post_as(app, school["tb"], "post", f"{API}/lesson-plans", {
        "title": "引用他人草稿", "items": [
            {"sort_order": 1, "target_type": "knowledge", "target_id": draft_point["id"]},
        ],
    })
    assert other.status_code == 422
    assert "items" in other.get_json()["error"]["details"]["fields"]

    shared = post_as(app, school["tb"], "post", f"{API}/lesson-plans", {
        "title": "引用共享已发布", "items": [
            {"sort_order": 1, "target_type": "knowledge", "target_id": school["point"]["id"]},
        ],
    })
    assert shared.status_code == 201


# ---- T-008-02 复制与引用稳定性 ----

def test_T008_02_copy_is_independent_and_edit_does_not_touch_source(school):
    app = school["app"]
    point = school["point"]["id"]
    _resource, version = create_resource_with_version(app, school["ta"], point)
    question = create_question(app, school["ta"], point)

    source = post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "原计划", "notes": "原备注",
        "items": [
            {"sort_order": 1, "target_type": "knowledge", "target_id": point},
            {"sort_order": 2, "target_type": "resource_version", "target_id": version["id"]},
            {"sort_order": 3, "target_type": "question", "target_id": question["id"]},
        ],
    }).get_json()["data"]

    copy = post_as(app, school["ta"], "post", f"{API}/lesson-plans/{source['id']}/copies", {
        "title": "副本计划",
    })
    assert copy.status_code == 201, copy.get_data(as_text=True)
    copied = copy.get_json()["data"]
    assert copied["id"] != source["id"]
    assert copied["title"] == "副本计划"
    assert [(item["sort_order"], item["target_type"], item["target_id"]) for item in copied["items"]] == [
        (item["sort_order"], item["target_type"], item["target_id"]) for item in source["items"]
    ]
    assert copied["version"] == 1

    # 改副本不改变原单
    patched = post_as(app, school["ta"], "patch", f"{API}/lesson-plans/{copied['id']}", {
        "version": copied["version"],
        "title": "副本改名",
        "items": [{"sort_order": 1, "target_type": "knowledge", "target_id": school["shared_point"]["id"]}],
    })
    assert patched.status_code == 200, patched.get_data(as_text=True)

    original = post_as(app, school["ta"], "get", f"{API}/lesson-plans/{source['id']}").get_json()["data"]
    assert original["title"] == "原计划"
    assert original["notes"] == "原备注"
    assert [item["target_id"] for item in original["items"]] == [point, version["id"], question["id"]]
    assert original["version"] == source["version"]


def test_T008_02_new_resource_version_does_not_change_reference_or_snapshot(school):
    app = school["app"]
    point = school["point"]["id"]
    resource, version = create_resource_with_version(app, school["ta"], point)

    plan = post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "引用资源版本", "items": [
            {"sort_order": 1, "target_type": "resource_version", "target_id": version["id"]},
        ],
    }).get_json()["data"]
    preview = post_as(app, school["ta"], "post", f"{API}/preview-assignments", {
        "class_id": school["class_a"]["id"], "plan_id": plan["id"],
    }).get_json()["data"]

    # 追加一个新版本
    second = post_as(app, school["ta"], "post", f"{API}/resources/{resource['id']}/versions", {
        "external_url": "https://example.com/b.pdf", "note": "第二版",
    })
    assert second.status_code == 201, second.get_data(as_text=True)

    # 计划仍指向旧版本，已发布快照也仍是旧版本号
    current = post_as(app, school["ta"], "get", f"{API}/lesson-plans/{plan['id']}").get_json()["data"]
    assert current["items"][0]["target_id"] == version["id"]
    assert snapshot_of(school, preview["id"])["items"][0]["content"]["version_no"] == version["version_no"]


# ---- T-008-03 跨班隔离与答案隐藏 ----

def test_T008_03_preview_is_class_scoped_and_question_snapshot_hides_answers(school):
    app = school["app"]
    point = school["point"]["id"]
    question = create_question(app, school["ta"], point, stem="预习题干")
    plan = post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "预习计划", "items": [
            {"sort_order": 1, "target_type": "question", "target_id": question["id"]},
            {"sort_order": 2, "target_type": "knowledge", "target_id": point},
        ],
    }).get_json()["data"]
    created = post_as(app, school["ta"], "post", f"{API}/preview-assignments", {
        "class_id": school["class_a"]["id"], "plan_id": plan["id"], "due_at": STAMP,
    })
    assert created.status_code == 201, created.get_data(as_text=True)
    preview = created.get_json()["data"]
    assert preview["class_id"] == school["class_a"]["id"]
    assert preview["due_at"] == STAMP
    assert len(preview["items"]) == 2

    # 甲班学生看得到；题目条目只有题干，没有答案或解析
    mine = post_as(app, school["sa1"], "get", f"{API}/preview-assignments?class_id={school['class_a']['id']}")
    assert mine.status_code == 200
    items = mine.get_json()["data"][0]["items"]
    question_item = next(item for item in items if item["target_type"] == "question")
    assert question_item["content"] == {"stem_md": "预习题干"}
    serialized = json.dumps(items, ensure_ascii=False)
    assert "answer" not in serialized and "explanation" not in serialized and "解析" not in serialized

    # 快照本身也不含答案
    raw = scalar(app, "SELECT snapshot_json FROM preview_assignments WHERE id=?", (preview["id"],))
    assert "answer" not in raw and "explanation" not in raw and "这是解析" not in raw

    # 乙班学生查甲班预习 → 404；查自己班 → 空列表
    other_class = post_as(app, school["sb1"], "get",
                          f"{API}/preview-assignments?class_id={school['class_a']['id']}")
    assert other_class.status_code == 404
    own_class = post_as(app, school["sb1"], "get",
                        f"{API}/preview-assignments?class_id={school['class_b']['id']}")
    assert own_class.status_code == 200
    assert own_class.get_json()["data"] == []

    # 乙班教师同样按跨班对象 404；甲班教师可读
    assert post_as(app, school["tb"], "get",
                   f"{API}/preview-assignments?class_id={school['class_a']['id']}").status_code == 404
    assert post_as(app, school["ta"], "get",
                   f"{API}/preview-assignments?class_id={school['class_a']['id']}").status_code == 200


def test_T008_03_publishing_revalidates_references(school):
    """另一名教师的共享题目被其本人撤回为草稿后，发布预习应因引用不可见而 422。"""
    app = school["app"]
    point = school["point"]["id"]
    mine = create_question(app, school["ta"], point, stem="本人的题")
    shared = create_question(app, school["tb"], point, stem="乙的共享题")

    plan = post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "含共享引用", "items": [
            {"sort_order": 1, "target_type": "question", "target_id": mine["id"]},
            {"sort_order": 2, "target_type": "question", "target_id": shared["id"]},
        ],
    }).get_json()["data"]

    can_publish = post_as(app, school["ta"], "post", f"{API}/preview-assignments", {
        "class_id": school["class_a"]["id"], "plan_id": plan["id"],
    })
    assert can_publish.status_code == 201, can_publish.get_data(as_text=True)

    withdrew = post_as(app, school["tb"], "patch", f"{API}/questions/{shared['id']}", {
        "version": shared["version"], "published": False,
    })
    assert withdrew.status_code == 200, withdrew.get_data(as_text=True)

    blocked = post_as(app, school["ta"], "post", f"{API}/preview-assignments", {
        "class_id": school["class_a"]["id"], "plan_id": plan["id"],
    })
    assert blocked.status_code == 422
    assert "items" in blocked.get_json()["error"]["details"]["fields"]


# ---- T-008-04 已发布快照不可变 ----

def test_T008_04_published_snapshot_survives_plan_edits(school):
    app = school["app"]
    point = school["point"]["id"]
    question = create_question(app, school["ta"], point, stem="原始预习题干")
    plan = post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "发布前标题", "notes": "发布前备注", "items": [
            {"sort_order": 1, "target_type": "question", "target_id": question["id"]},
            {"sort_order": 2, "target_type": "knowledge", "target_id": point},
        ],
    }).get_json()["data"]
    preview = post_as(app, school["ta"], "post", f"{API}/preview-assignments", {
        "class_id": school["class_a"]["id"], "plan_id": plan["id"],
    }).get_json()["data"]
    before = snapshot_of(school, preview["id"])

    # 改标题、改备注、换条目、改题干预习题干
    patched = post_as(app, school["ta"], "patch", f"{API}/lesson-plans/{plan['id']}", {
        "version": plan["version"],
        "title": "发布后标题",
        "notes": "发布后备注",
        "items": [{"sort_order": 1, "target_type": "knowledge", "target_id": school["shared_point"]["id"]}],
    })
    assert patched.status_code == 200, patched.get_data(as_text=True)
    post_as(app, school["ta"], "patch", f"{API}/questions/{question['id']}", {
        "version": question["version"], "stem_md": "改后的题干",
    })

    after = snapshot_of(school, preview["id"])
    assert after == before, "已发布预习快照不得随原计划或题库修改而变化"
    assert after["plan_title"] == "发布前标题"
    assert after["items"][0]["content"]["stem_md"] == "原始预习题干"

    # 学生读到的仍是旧内容
    seen = post_as(app, school["sa1"], "get",
                   f"{API}/preview-assignments?class_id={school['class_a']['id']}")
    items = seen.get_json()["data"][0]["items"]
    assert items[0]["content"]["stem_md"] == "原始预习题干"
    assert len(items) == 2


# ---- 权限与字段 ----

def test_plan_is_owner_scoped(school):
    app = school["app"]
    plan = post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "甲的计划", "items": [],
    }).get_json()["data"]

    assert post_as(app, school["tb"], "get", f"{API}/lesson-plans/{plan['id']}").status_code == 404
    assert post_as(app, school["tb"], "patch", f"{API}/lesson-plans/{plan['id']}", {
        "version": plan["version"], "title": "越权改名",
    }).status_code == 404
    assert post_as(app, school["tb"], "post", f"{API}/lesson-plans/{plan['id']}/copies", {
        "title": "越权复制",
    }).status_code == 404
    # 自己的列表里也只有自己的
    assert post_as(app, school["tb"], "get", f"{API}/lesson-plans").get_json()["data"] == []


def test_permissions_and_field_validation(school):
    app = school["app"]
    plan = post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "权限用", "items": [],
    }).get_json()["data"]

    # 角色：备课接口仅教师
    assert post_as(app, school["admin"], "get", f"{API}/lesson-plans").status_code == 403
    assert post_as(app, school["sa1"], "get", f"{API}/lesson-plans").status_code == 403
    anonymous = app.test_client()
    assert anonymous.get(f"{API}/lesson-plans").status_code == 401
    no_csrf = school["ta"][0].post(f"{API}/lesson-plans", json={"title": "无 CSRF"})
    assert no_csrf.status_code == 403
    assert no_csrf.get_json()["error"]["code"] == "CSRF_FAILED"

    # version 冲突
    conflict = post_as(app, school["ta"], "patch", f"{API}/lesson-plans/{plan['id']}", {
        "version": plan["version"] + 3, "title": "过期版本",
    })
    assert conflict.status_code == 409
    assert conflict.get_json()["error"]["code"] == "VERSION_CONFLICT"

    # 字段：标题空、notes 超长、时间格式
    assert post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "", "items": [],
    }).status_code == 422
    assert post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "长备注", "notes": "x" * 5001, "items": [],
    }).status_code == 422
    assert post_as(app, school["ta"], "post", f"{API}/lesson-plans", {
        "title": "坏时间", "planned_at": "2026-09-29 01:00:00", "items": [],
    }).status_code == 422

    # 预习发布：班级必须是本人任教，班级缺参
    assert post_as(app, school["tb"], "post", f"{API}/preview-assignments", {
        "class_id": school["class_a"]["id"], "plan_id": plan["id"],
    }).status_code == 404
    assert post_as(app, school["ta"], "post", f"{API}/preview-assignments", {
        "class_id": 9999, "plan_id": plan["id"],
    }).status_code == 404
    assert post_as(app, school["ta"], "get", f"{API}/preview-assignments").status_code == 400
    assert post_as(app, school["sa1"], "post", f"{API}/preview-assignments", {
        "class_id": school["class_a"]["id"], "plan_id": plan["id"],
    }).status_code == 403
