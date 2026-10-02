"""SPEC-016 时序逻辑知识图谱：T-016-01 至 T-016-04 及配套边界。

固定数据与独立数据库。主图用 SPEC-005 的 `seed-content` 写入（六单元 12 知识点、
15 条先修关系），保证被测的就是真实课程种子；环、超限与草稿排除等边界用 ORM
直接构造，因为本模块按规格不提供先修关系的写接口。
"""

from __future__ import annotations

import pytest

from app.models_content import KnowledgeEdge, KnowledgePoint
from helpers import (
    API,
    DEFAULT_PASSWORD,
    api_call,
    create_admin,
    get_csrf,
    login,
    register,
)

ADMIN_PASSWORD = "Adm1nPass!23"


def login_as(app, login_name, password=DEFAULT_PASSWORD):
    client = app.test_client()
    csrf = get_csrf(client)
    response = login(client, csrf, login_name=login_name, password=password)
    assert response.status_code == 200, response.get_data(as_text=True)
    return client, response.get_json()["data"]["csrf_token"]


def api_get(app, actor, path):
    client, _token = actor
    return client.get(path)


def with_session(app, work):
    """在应用上下文里用 ORM 直接构造边界数据；返回 work 的结果。"""
    with app.app_context():
        session = app.extensions["db_session"]()
        try:
            result = work(session)
            session.commit()
            return result
        finally:
            session.close()


@pytest.fixture
def school(upgraded_app):
    """教师、两个班、甲班一名在班学生与乙班一名在班学生；课程种子已写入。"""
    app = upgraded_app
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", ADMIN_PASSWORD)
    teacher = api_call(
        admin, "post", f"{API}/users", csrf_token=admin_csrf,
        json={"login_name": "teacher_aaa", "display_name": "教师甲",
              "password": DEFAULT_PASSWORD, "role": "teacher"},
    ).get_json()["data"]
    class_a = api_call(
        admin, "post", f"{API}/classes", csrf_token=admin_csrf,
        json={"name": "时序逻辑甲班", "teacher_id": teacher["id"]},
    ).get_json()["data"]

    student = None
    client = app.test_client()
    csrf = get_csrf(client)
    response = register(client, csrf, login_name="stu_a0001", student_no="20241111",
                        display_name="在班学生")
    assert response.status_code == 201, response.get_data(as_text=True)
    student = response.get_json()["data"]
    api_call(admin, "put", f"{API}/classes/{class_a['id']}/enrollments",
             csrf_token=admin_csrf, json={"student_id": student["id"], "active": True})

    other = app.test_client()
    other_csrf = get_csrf(other)
    response = register(other, other_csrf, login_name="stu_b0001", student_no="20242222",
                        display_name="未入班学生")
    assert response.status_code == 201, response.get_data(as_text=True)
    outsider = response.get_json()["data"]

    runner = app.test_cli_runner()
    seeded = runner.invoke(args=["seed-content", "--owner-login", "teacher_aaa"])
    assert seeded.exit_code == 0, seeded.output

    return {
        "app": app,
        "admin": (admin, admin_csrf),
        "teacher": login_as(app, "teacher_aaa"),
        "student": login_as(app, "stu_a0001"),
        "outsider": login_as(app, "stu_b0001"),
        "class_a": class_a,
        "student_id": student["id"],
        "outsider_id": outsider["id"],
        "teacher_id": teacher["id"],
    }


def points_by_title(app) -> dict[str, dict]:
    with app.app_context():
        session = app.extensions["db_session"]()
        try:
            return {
                point.title: {"id": point.id, "chapter_id": point.chapter_id}
                for point in session.query(KnowledgePoint).all()
            }
        finally:
            session.close()


def add_points(app, *, chapter_id, owner_id, titles, prefix="", published=1, start_order=50):
    """直接插入知识点，返回 [{"id", "title"}]。"""
    def work(session):
        created = []
        for index, title in enumerate(titles):
            point = KnowledgePoint(
                chapter_id=chapter_id, title=f"{prefix}{title}", body_md=f"{title}说明",
                source_url=None, sort_order=start_order + index, published=published,
                owner_id=owner_id,
            )
            session.add(point)
            session.flush()
            created.append({"id": point.id, "title": point.title})
        return created

    return with_session(app, work)


def add_edge(app, prerequisite_id, target_id):
    with_session(
        app,
        lambda session: session.add(
            KnowledgeEdge(prerequisite_id=prerequisite_id, target_id=target_id)
        ),
    )


def drop_edge(app, prerequisite_id, target_id):
    def work(session):
        session.query(KnowledgeEdge).filter(
            KnowledgeEdge.prerequisite_id == prerequisite_id,
            KnowledgeEdge.target_id == target_id,
        ).delete()

    with_session(app, work)


def graph(school, query="", *, who="student"):
    return api_get(school["app"], school[who], f"{API}/knowledge-graph{query}")


# ---- T-016-01 以 root 为中心的子图与草稿排除 ----

def test_T016_01_root_subgraph_depth_one_excludes_draft(school):
    titles = points_by_title(school["app"])
    binary = titles["二进制计数器与模值"]
    equation = titles["次态推导与状态方程"]
    mod6 = titles["模 6 计数器与 5→0 回卷"]

    response = graph(school, f"?root_id={mod6['id']}&depth=1")
    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()["data"]

    # 种子里 模6计数器 的先修是 二进制计数器（k09）与 次态推导（k06）
    node_ids = {node["knowledge_id"] for node in data["nodes"]}
    assert node_ids == {mod6["id"], binary["id"], equation["id"]}
    edge_pairs = {(edge["prerequisite_id"], edge["target_id"]) for edge in data["edges"]}
    assert edge_pairs == {(binary["id"], mod6["id"]), (equation["id"], mod6["id"])}
    depths = {node["knowledge_id"]: node["depth"] for node in data["nodes"]}
    assert depths[mod6["id"]] == 0 and depths[binary["id"]] == 1
    dimensions = {node["knowledge_id"]: node["dimension"] for node in data["nodes"]}
    assert dimensions[mod6["id"]] == 1 and dimensions[binary["id"]] == 0
    assert data["has_cycle"] is False and data["truncated"] is False

    # depth=2 沿两个方向继续扩展，但仍然保持先修→后继方向的边
    deeper = graph(school, f"?root_id={mod6['id']}&depth=2").get_json()["data"]
    assert len(deeper["nodes"]) > len(data["nodes"])
    assert {node["knowledge_id"] for node in data["nodes"]} <= {
        node["knowledge_id"] for node in deeper["nodes"]
    }
    for edge in deeper["edges"]:
        assert edge["prerequisite_id"] != edge["target_id"]

    # 草稿知识点与它连出的边都不进入响应
    draft = add_points(school["app"], chapter_id=mod6["chapter_id"],
                       owner_id=school["teacher_id"], prefix="草稿：",
                       titles=["模6计数器复位细节"], published=0)[0]
    add_edge(school["app"], mod6["id"], draft["id"])
    after = graph(school, f"?root_id={mod6['id']}&depth=2").get_json()["data"]
    assert draft["id"] not in {node["knowledge_id"] for node in after["nodes"]}
    assert all(edge["target_id"] != draft["id"] for edge in after["edges"])

    # 全图（无 root）同样不含草稿点
    whole = graph(school).get_json()["data"]
    assert draft["id"] not in {node["knowledge_id"] for node in whole["nodes"]}
    assert whole["truncated"] is False


# ---- T-016-02 环检测与唯一拓扑序 ----

def test_T016_02_cycle_is_reported_and_fixed_graph_gives_unique_order(school):
    titles = points_by_title(school["app"])
    mod6 = titles["模 6 计数器与 5→0 回卷"]
    binary = titles["二进制计数器与模值"]

    seeded = api_get(school["app"], school["student"], f"{API}/knowledge-graph/topological")
    assert seeded.status_code == 200, seeded.get_data(as_text=True)
    baseline = seeded.get_json()["data"]
    assert baseline["has_cycle"] is False and baseline["cycle_edges"] == []
    assert len(baseline["order"]) == 12

    # 造一个环：二进制→模6 已存在，再加 模6→二进制
    add_edge(school["app"], mod6["id"], binary["id"])
    looped = api_get(school["app"], school["student"],
                     f"{API}/knowledge-graph/topological").get_json()["data"]
    assert looped["has_cycle"] is True
    assert "order" not in looped, "有环时不得返回拓扑序"
    assert {(edge["prerequisite_id"], edge["target_id"]) for edge in looped["cycle_edges"]} == {
        (binary["id"], mod6["id"]), (mod6["id"], binary["id"])
    }

    # E066 同样报告环状态
    assert graph(school).get_json()["data"]["has_cycle"] is True

    # 修正为无环后恢复唯一拓扑序：先修一定排在后继之前，且顺序可重复
    drop_edge(school["app"], mod6["id"], binary["id"])
    fixed = api_get(school["app"], school["student"],
                    f"{API}/knowledge-graph/topological").get_json()["data"]
    assert fixed["has_cycle"] is False and fixed["cycle_edges"] == []
    assert fixed["order"] == baseline["order"]
    position = {node: index for index, node in enumerate(fixed["order"])}
    assert position[binary["id"]] < position[mod6["id"]]


# ---- T-016-03 先修路径 ----

def test_T016_03_shortest_path_and_no_path_is_not_fabricated(school):
    titles = points_by_title(school["app"])
    trigger = titles["D 触发器与有效沿"]
    binary = titles["二进制计数器与模值"]
    mod6 = titles["模 6 计数器与 5→0 回卷"]
    basics = titles["组合逻辑与时序逻辑的区别"]

    # 触发器 → 计数器：k03 → k09 → k10
    response = api_get(school["app"], school["student"],
                       f"{API}/knowledge-graph/path?from={trigger['id']}&to={mod6['id']}")
    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()["data"]
    assert data["matched"] is True
    assert [node["knowledge_id"] for node in data["nodes"]] == [
        trigger["id"], binary["id"], mod6["id"]
    ]
    assert [(edge["prerequisite_id"], edge["target_id"]) for edge in data["edges"]] == [
        (trigger["id"], binary["id"]), (binary["id"], mod6["id"])
    ]

    # 反方向没有先修链：matched=false 且节点为空，不编造中间节点
    reverse = api_get(school["app"], school["student"],
                      f"{API}/knowledge-graph/path?from={mod6['id']}&to={basics['id']}")
    assert reverse.get_json()["data"] == {"matched": False, "nodes": [], "edges": []}

    # 直接邻居就返回一条边
    direct = api_get(school["app"], school["student"],
                     f"{API}/knowledge-graph/path?from={binary['id']}&to={mod6['id']}")
    assert len(direct.get_json()["data"]["edges"]) == 1


# ---- T-016-04 访问控制、depth 校验、超限裁剪与章节过滤 ----

def test_T016_04_access_control_and_argument_errors(school):
    anonymous = school["app"].test_client()
    for path in ("/knowledge-graph", "/knowledge-graph/topological",
                 "/knowledge-graph/path?from=1&to=2"):
        response = anonymous.get(f"{API}{path}")
        assert response.status_code == 401, path
        assert response.get_json()["error"]["code"] == "UNAUTHENTICATED"

    # 未入班学生有登录但无课程访问权
    blocked = graph(school, "", who="outsider")
    assert blocked.status_code == 403
    assert blocked.get_json()["error"]["code"] == "FORBIDDEN"

    # 在班学生可读已发布图
    assert graph(school, "", who="student").status_code == 200
    assert graph(school, "", who="teacher").status_code == 200

    # depth 越界是字段错误 422；非整数是格式错误 400
    out_of_range = graph(school, "?depth=99")
    assert out_of_range.status_code == 422
    assert "depth" in out_of_range.get_json()["error"]["details"]["fields"]
    assert graph(school, "?depth=0").status_code == 422
    assert graph(school, "?depth=abc").status_code == 400

    # 不存在的对象返回 404，不返回空图冒充
    assert graph(school, "?root_id=999999").status_code == 404
    assert graph(school, "?chapter_id=999999").status_code == 404
    assert api_get(school["app"], school["student"],
                   f"{API}/knowledge-graph/path?from=999999&to=1").status_code == 404
    assert api_get(school["app"], school["student"],
                   f"{API}/knowledge-graph/path?from=1").status_code == 400


def test_T016_04_node_limit_truncates_without_silent_drop(school):
    titles = points_by_title(school["app"])
    chapter_id = titles["组合逻辑与时序逻辑的区别"]["chapter_id"]
    created = add_points(
        school["app"], chapter_id=chapter_id, owner_id=school["teacher_id"],
        titles=[f"批量知识点 {index}" for index in range(260)],
    )
    assert len(created) == 260

    response = graph(school, "", who="student")
    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()["data"]
    assert data["truncated"] is True, "超过 200 个节点必须显式标记裁剪"
    assert len(data["nodes"]) == 200
    node_ids = {node["knowledge_id"] for node in data["nodes"]}
    assert all(edge["prerequisite_id"] in node_ids and edge["target_id"] in node_ids
               for edge in data["edges"]), "裁剪后不得留下悬空边"

    # 没有超过上限的章节不受影响，truncated 保持 false
    small_chapter = titles["D 触发器与有效沿"]["chapter_id"]
    small = graph(school, f"?chapter_id={small_chapter}").get_json()["data"]
    assert small["truncated"] is False
    assert len(small["nodes"]) == 2


def test_T016_04_chapter_filter_keeps_edges_inside_the_chapter(school):
    titles = points_by_title(school["app"])
    mod6 = titles["模 6 计数器与 5→0 回卷"]
    binary = titles["二进制计数器与模值"]
    chapter_id = mod6["chapter_id"]
    assert binary["chapter_id"] == chapter_id, "前置假设：计数与模值同属第五单元"

    response = graph(school, f"?chapter_id={chapter_id}")
    data = response.get_json()["data"]
    assert {node["knowledge_id"] for node in data["nodes"]} == {binary["id"], mod6["id"]}
    assert data["edges"] == [{"prerequisite_id": binary["id"], "target_id": mod6["id"]}]

    # 跨章边在按章过滤时被排除：k09 → k12 跨第五、第六单元
    register = titles["多触发器同步与初态约定"]
    outside = graph(school, f"?chapter_id={register['chapter_id']}").get_json()["data"]
    outside_pairs = {(edge["prerequisite_id"], edge["target_id"]) for edge in outside["edges"]}
    assert (binary["id"], register["id"]) not in outside_pairs, "跨章边不得进入单章子图"
    assert (titles["同步复位与异步复位"]["id"], register["id"]) in outside_pairs

    # 拓扑序同样按章收窄，且只含该章节点
    scoped = api_get(school["app"], school["student"],
                     f"{API}/knowledge-graph/topological?chapter_id={chapter_id}")
    scoped_data = scoped.get_json()["data"]
    assert scoped_data["has_cycle"] is False
    assert set(scoped_data["order"]) == {binary["id"], mod6["id"]}
    assert scoped_data["order"].index(binary["id"]) < scoped_data["order"].index(mod6["id"])

    # 跨章边不进入按章子图，但进入全图
    whole = graph(school).get_json()["data"]
    assert {"prerequisite_id": binary["id"], "target_id": register["id"]} in whole["edges"]


def test_T016_04_no_write_endpoints(school):
    """只读投影：本模块不提供先修关系的写入口。"""
    client, token = school["student"]
    rules = {str(rule) for rule in school["app"].url_map.iter_rules()}
    graph_rules = {rule for rule in rules if "knowledge-graph" in rule}
    assert graph_rules == {
        "/api/v1/knowledge-graph",
        "/api/v1/knowledge-graph/path",
        "/api/v1/knowledge-graph/topological",
    }
    for rule in school["app"].url_map.iter_rules():
        if "knowledge-graph" in str(rule):
            assert "GET" in rule.methods, f"{rule} 不应有写方法"
            assert "POST" not in rule.methods
    posted = api_call(client, "post", f"{API}/knowledge-graph", csrf_token=token, json={})
    assert posted.status_code == 405
