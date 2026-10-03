"""SPEC-007 课程检索问答：T-007-01 至 T-007-04 及配套边界。

固定种子数据 + 独立测试库：夹具用 `tmp_path` 显式指定 DATABASE_URL 与 UPLOAD_DIR，
不触碰仓库内的 instance/。检索语料来自 SPEC-005 的课程种子与 SPEC-007 的 16 条问答。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app import create_app
from app import api_qa
from app import retrieval
from app.retrieval import SIMILARITY_THRESHOLD, build_count, reset_index_cache
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

# ---- 固定评价集（SPEC-007 第 4 节第 5 条：20 条人工标注查询，其中 5 条域外）----

IN_DOMAIN = (
    ("组合逻辑和时序逻辑有什么不同", "组合逻辑与时序逻辑的区别"),
    ("什么时候状态才会更新", "时钟信号与有效时钟沿"),
    ("时钟上升沿的作用是什么", "时钟信号与有效时钟沿"),
    ("D 触发器在时钟沿做什么", "D 触发器与有效沿"),
    ("为什么时钟高电平期间改 D 不影响 Q", "D 触发器与有效沿"),
    ("JK 触发器什么时候翻转", "JK 触发器的四种组合"),
    ("JK 触发器的四种输入组合", "JK 触发器的四种组合"),
    ("状态表应该怎么读", "状态表与状态图"),
    ("怎么从当前状态求次态", "次态推导与状态方程"),
    ("移位寄存器的位序约定", "4 位移位寄存器与位序"),
    ("串行输入从哪一位进入", "4 位移位寄存器与位序"),
    ("寄存器使能端为 0 会怎样", "寄存器使能与保持"),
    ("4 位计数器能表示多少个状态", "二进制计数器与模值"),
    ("模 6 计数器数到 5 之后是什么", "模 6 计数器与 5→0 回卷"),
    ("多个触发器共用一个时钟怎么同步", "多触发器同步与初态约定"),
)

OUT_OF_DOMAIN = (
    "今天天气怎么样",
    "推荐几家附近的餐馆",
    "怎么用 Python 读取 Excel 文件",
    "这首诗的作者是谁",
    "明天股市会涨吗",
)

# T-007-04 的目标：域内至少 12/15 命中，域外 5/5 拒答
IN_DOMAIN_TARGET = 12


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


def _register_student(app, login_name: str, student_no: str):
    client = app.test_client()
    csrf = get_csrf(client)
    response = register(client, csrf, login_name=login_name, student_no=student_no)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


@pytest.fixture(autouse=True)
def _isolate_retrieval_state():
    """索引缓存与查询限流都是进程内状态，用例之间必须隔离。"""
    reset_index_cache()
    api_qa.reset_query_limits()
    yield
    reset_index_cache()
    api_qa.reset_query_limits()


@pytest.fixture
def lab(tmp_path: Path):
    """管理员 + 两教师 + 一班（含入班与未入班学生）+ 课程语料 + 16 条问答。"""
    app = create_app(
        "testing",
        {
            "DATABASE_URL": sqlite_url(tmp_path / "qa.sqlite"),
            "UPLOAD_DIR": str(tmp_path / "uploads"),
        },
    )
    upgrade(app)
    runner = app.test_cli_runner()
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", "Adm1nPass!23")
    teacher = _create_teacher(app, admin, admin_csrf, "teacher_aaa")
    other_teacher = _create_teacher(app, admin, admin_csrf, "teacher_bbb")

    school_class = api_call(
        admin,
        "post",
        f"{API}/classes",
        csrf_token=admin_csrf,
        json={"name": "软件工程示例班", "teacher_id": teacher["id"]},
    ).get_json()["data"]
    student = _register_student(app, "stu_a0001", "20240001")
    outsider = _register_student(app, "stu_x0001", "20240003")
    api_call(
        admin,
        "put",
        f"{API}/classes/{school_class['id']}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student["id"], "active": True},
    )

    for command, owner in (("seed-content", "teacher_aaa"), ("seed-qa", "teacher_aaa")):
        result = runner.invoke(args=[command, "--owner-login", owner])
        assert result.exit_code == 0, result.output

    try:
        yield {
            "app": app,
            "admin": (admin, admin_csrf),
            "teacher": login_as(app, "teacher_aaa"),
            "other_teacher": login_as(app, "teacher_bbb"),
            "student": login_as(app, "stu_a0001"),
            "outsider": login_as(app, "stu_x0001"),
            "teacher_id": teacher["id"],
            "other_teacher_id": other_teacher["id"],
        }
    finally:
        app.extensions["db_engine"].dispose()


@pytest.fixture
def bare_app(tmp_path: Path):
    """空语料库：只有一个管理员，没有任何知识点与问答。"""
    app = create_app(
        "testing",
        {
            "DATABASE_URL": sqlite_url(tmp_path / "bare.sqlite"),
            "UPLOAD_DIR": str(tmp_path / "uploads"),
        },
    )
    upgrade(app)
    create_admin(app)
    try:
        yield app
    finally:
        app.extensions["db_engine"].dispose()


def ask(client, csrf, query: str = None, **payload):
    body = {"query": query} if query is not None else dict(payload)
    return api_call(client, "post", f"{API}/qa/queries", csrf_token=csrf, json=body)


def ask_with_body(client, csrf, payload):
    """按给定 JSON 原样提交，用于构造未知字段等非法载荷。"""
    return api_call(client, "post", f"{API}/qa/queries", csrf_token=csrf, json=payload)


def create_entry(client, csrf, knowledge_id: int, **over):
    payload = {
        "knowledge_id": knowledge_id,
        "question": "默认问题",
        "answer_md": "默认回答。",
        "published": True,
    }
    payload.update(over)
    return api_call(client, "post", f"{API}/qa-entries", csrf_token=csrf, json=payload)


def point_id(app, title: str) -> int:
    return scalar(app, "SELECT id FROM knowledge_points WHERE title = ?", (title,))


# ---- T-007-01 表达相近的问题能检索到知识点并返回来源 ----

def test_T007_01_similar_question_retrieves_knowledge_point(lab):
    student, csrf = lab["student"]
    response = ask(student, csrf, "模 6 计数器数到 5 之后会发生什么")
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()["data"]

    assert body["matched"] is True
    assert len(body["matches"]) <= 3
    top = body["matches"][0]
    assert top["knowledge_id"] == point_id(lab["app"], "模 6 计数器与 5→0 回卷")
    assert top["title"] == "模 6 计数器与 5→0 回卷"
    assert top["excerpt"] and len(top["excerpt"]) <= 300
    assert 0 < top["similarity"] <= 1
    assert body["corpus_version"].startswith("v1-")

    # 换一个话题应命中另一个知识点，说明结果来自语料匹配而不是固定答案数组
    other = ask(student, csrf, "移位寄存器的串行输入从哪一位进入").get_json()["data"]
    assert other["matches"][0]["knowledge_id"] == point_id(lab["app"], "4 位移位寄存器与位序")
    assert other["matches"][0]["knowledge_id"] != top["knowledge_id"]

    # 响应里没有直接给出答案文本的字段，只有摘要与来源
    assert set(top) == {"knowledge_id", "title", "excerpt", "source_url", "similarity"}


def test_T007_01_qa_entries_are_part_of_the_corpus(lab):
    """问答条目的正文也参与检索，且不改变命中的知识点归属。"""
    teacher, csrf = lab["teacher"]
    point = point_id(lab["app"], "同步复位与异步复位")
    created = create_entry(
        teacher,
        csrf,
        point,
        question="异步复位会不会等时钟？",
        answer_md="异步复位一旦有效就立即清零，不需要等待有效时钟沿。",
    )
    assert created.status_code == 201

    body = ask(teacher, csrf, "异步复位会不会等时钟").get_json()["data"]
    assert body["matched"] is True
    assert body["matches"][0]["knowledge_id"] == point


# ---- T-007-02 空查询 422；域外与空语料 matched=false ----

def test_T007_02_empty_query_is_rejected(lab):
    student, csrf = lab["student"]
    for bad in ("", " ", "   ", "a", "\n\t"):
        response = ask(student, csrf, bad)
        assert response.status_code == 422, bad
        assert response.get_json()["error"]["details"]["fields"]["query"]

    assert ask(student, csrf, "x" * 201).status_code == 422
    assert ask(student, csrf, "问" * 200).status_code in (200, 429)
    # query 必须是字符串
    assert ask_with_body(student, csrf, {"query": 123}).status_code == 422
    assert ask_with_body(student, csrf, {"query": None}).status_code == 422
    # 未知字段被拒
    unknown = ask_with_body(student, csrf, {"query": "计数器", "top_k": 10})
    assert unknown.status_code == 422
    assert "top_k" in unknown.get_json()["error"]["details"]["unknown_fields"]


def test_T007_02_out_of_domain_is_refused_not_explained(lab):
    student, csrf = lab["student"]
    for query in OUT_OF_DOMAIN:
        body = ask(student, csrf, query).get_json()["data"]
        assert body["matched"] is False, query
        assert body["matches"] == [], query
        assert body["corpus_version"], "拒答也要给出语料版本，便于追溯"


def test_T007_02_empty_corpus_returns_unmatched(bare_app):
    client, csrf = login_as(bare_app, "admin_root", "Adm1nPass!23")
    response = ask(client, csrf, "模 6 计数器数到 5")
    assert response.status_code == 200
    body = response.get_json()["data"]
    assert body["matched"] is False
    assert body["matches"] == []
    assert body["corpus_version"].startswith("v1-")


# ---- T-007-03 下架知识点后索引更新 ----

def test_T007_03_unpublishing_removes_text_from_index(lab):
    teacher, csrf = lab["teacher"]
    point = point_id(lab["app"], "状态表与状态图")

    before = ask(teacher, csrf, "状态表和状态图有什么区别").get_json()["data"]
    assert before["matched"] is True
    assert before["matches"][0]["knowledge_id"] == point
    version_before = before["corpus_version"]
    builds_before = build_count()

    # 同一指纹下重复查询不重建索引
    again = ask(teacher, csrf, "状态表和状态图有什么区别").get_json()["data"]
    assert again["corpus_version"] == version_before
    assert build_count() == builds_before

    # 下架该知识点
    updated = api_call(
        teacher,
        "patch",
        f"{API}/knowledge-points/{point}",
        csrf_token=csrf,
        json={"version": scalar(lab["app"], "SELECT version FROM knowledge_points WHERE id = ?", (point,)), "published": False},
    )
    assert updated.status_code == 200, updated.get_data(as_text=True)

    after = ask(teacher, csrf, "状态表和状态图有什么区别").get_json()["data"]
    assert after["corpus_version"] != version_before, "语料指纹必须随语料变化"
    assert build_count() > builds_before, "指纹变化后应重建索引"
    assert point not in [match["knowledge_id"] for match in after["matches"]]

    # 该知识点下的问答条目同样不再参与检索
    assert scalar(
        lab["app"],
        "SELECT COUNT(*) FROM qa_entries WHERE knowledge_id = ? AND published = 1",
        (point,),
    ) > 0
    body = ask(teacher, csrf, "状态表应该怎么读").get_json()["data"]
    assert point not in [match["knowledge_id"] for match in body["matches"]]


def test_T007_03_corpus_version_tracks_edits(lab):
    teacher, csrf = lab["teacher"]
    point = point_id(lab["app"], "二进制计数器与模值")
    first = ask(teacher, csrf, "4 位计数器有多少状态").get_json()["data"]["corpus_version"]

    entries = api_call(
        teacher, "get", f"{API}/qa-entries?knowledge_id={point}", csrf_token=csrf
    ).get_json()["data"]
    assert entries, "种子里该知识点应有问答条目"
    target = entries[0]

    edited = api_call(
        teacher,
        "patch",
        f"{API}/qa-entries/{target['id']}",
        csrf_token=csrf,
        json={"version": target["version"], "answer_md": "4 位二进制计数器共有 16 个状态。"},
    )
    assert edited.status_code == 200, edited.get_data(as_text=True)

    after = ask(teacher, csrf, "4 位计数器有多少状态").get_json()["data"]["corpus_version"]
    assert after != first


# ---- T-007-04 固定 20 条评价集 ----

def test_T007_04_evaluation_set(lab):
    """逐项记录 15 条域内与 5 条域外的结果；未达目标应视为需要调整或记为限制。"""
    teacher, csrf = lab["teacher"]
    app = lab["app"]

    rows = []
    hits = 0
    for query, expected_title in IN_DOMAIN:
        body = ask(teacher, csrf, query).get_json()["data"]
        expected_id = point_id(app, expected_title)
        titles = [match["title"] for match in body["matches"]]
        hit = expected_id in [match["knowledge_id"] for match in body["matches"]]
        hits += 1 if hit else 0
        rows.append((query, expected_title, hit, titles))

    refused = 0
    for query in OUT_OF_DOMAIN:
        body = ask(teacher, csrf, query).get_json()["data"]
        refused += 0 if body["matched"] else 1
        rows.append((query, "（域外）", body["matched"] is False, [m["title"] for m in body["matches"]]))

    report = "\n".join(
        f"{'命中' if ok else '未命中'} | {query} | 期望 {expected} | 实际 {titles}"
        for query, expected, ok, titles in rows
    )
    print(f"\n[SPEC-007 评价集] 阈值={SIMILARITY_THRESHOLD}\n{report}")

    assert refused == len(OUT_OF_DOMAIN), "域外问题必须全部拒答"
    assert hits >= IN_DOMAIN_TARGET, f"域内只命中 {hits}/{len(IN_DOMAIN)}，低于目标 {IN_DOMAIN_TARGET}"


# ---- E061 权限与限流 ----

def test_query_permissions_and_rate_limit(lab):
    student, csrf = lab["student"]
    teacher, teacher_csrf = lab["teacher"]
    outsider, outsider_csrf = lab["outsider"]
    admin, admin_csrf = lab["admin"]

    fresh = lab["app"].test_client()
    assert fresh.post(f"{API}/qa/queries").status_code == 403  # 缺 CSRF
    anon_csrf = get_csrf(fresh)
    assert ask(fresh, anon_csrf, "计数器").status_code == 401

    # 未入班学生没有课程访问权
    assert ask(outsider, outsider_csrf, "计数器").status_code == 403
    # 教师与管理员可检索
    assert ask(teacher, teacher_csrf, "计数器").status_code == 200
    assert ask(admin, admin_csrf, "计数器").status_code == 200

    # 单用户每分钟 20 次
    for _ in range(20):
        assert ask(student, csrf, "计数器").status_code == 200
    limited = ask(student, csrf, "计数器")
    assert limited.status_code == 429
    assert limited.get_json()["error"]["code"] == "RATE_LIMITED"
    assert int(limited.headers["Retry-After"]) >= 1
    # 限流按用户区分：另一个用户不受影响
    assert ask(teacher, teacher_csrf, "计数器").status_code == 200


# ---- E059/E060 语料管理 ----

def test_qa_entry_management_permissions_and_validation(lab):
    teacher, csrf = lab["teacher"]
    other, other_csrf = lab["other_teacher"]
    student, student_csrf = lab["student"]
    point = point_id(lab["app"], "D 触发器与有效沿")

    assert api_call(student, "get", f"{API}/qa-entries", csrf_token=student_csrf).status_code == 403
    assert create_entry(student, student_csrf, point).status_code == 403
    assert api_call(
        lab["app"].test_client(), "get", f"{API}/qa-entries"
    ).status_code == 401

    created = create_entry(teacher, csrf, point, question="D 触发器在上升沿做什么？")
    assert created.status_code == 201
    entry = created.get_json()["data"]
    assert entry["knowledge_id"] == point and entry["published"] is True and entry["version"] == 1

    # 未知字段（含 owner_id）被拒
    injected = create_entry(teacher, csrf, point, owner_id=99)
    assert injected.status_code == 422
    assert "owner_id" in injected.get_json()["error"]["details"]["unknown_fields"]

    # 字段校验
    assert create_entry(teacher, csrf, point, question="问" * 201).status_code == 422
    assert create_entry(teacher, csrf, point, question="   ").status_code == 422
    assert create_entry(teacher, csrf, point, answer_md="").status_code == 422
    # 指向不存在的知识点：直接构造载荷，避免与助手形参重名
    missing = api_call(
        teacher,
        "post",
        f"{API}/qa-entries",
        csrf_token=csrf,
        json={"knowledge_id": 99999, "question": "问题", "answer_md": "回答", "published": True},
    )
    assert missing.status_code == 422
    assert create_entry(teacher, csrf, point, source_url="javascript:alert(1)").status_code == 422
    assert create_entry(teacher, csrf, point, source_url="https://example.org/x").status_code == 201

    # 他人不能修改
    assert api_call(
        other, "patch", f"{API}/qa-entries/{entry['id']}", csrf_token=other_csrf,
        json={"version": 1, "question": "改个名"},
    ).status_code == 403

    # 版本冲突
    assert api_call(
        teacher, "patch", f"{API}/qa-entries/{entry['id']}", csrf_token=csrf,
        json={"version": 1, "question": "改名后"},
    ).status_code == 200
    stale = api_call(
        teacher, "patch", f"{API}/qa-entries/{entry['id']}", csrf_token=csrf,
        json={"version": 1, "question": "再改"},
    )
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "VERSION_CONFLICT"

    # 没有物理删除接口
    assert api_call(teacher, "delete", f"{API}/qa-entries/{entry['id']}", csrf_token=csrf).status_code == 405


def test_entry_can_only_link_visible_knowledge_points(lab):
    teacher, csrf = lab["teacher"]
    other, other_csrf = lab["other_teacher"]

    # 教师乙建一个未发布的知识点
    chapter = api_call(
        other, "post", f"{API}/chapters", csrf_token=other_csrf,
        json={"title": "乙的章节", "sort_order": 1, "published": True},
    ).get_json()["data"]
    draft = api_call(
        other, "post", f"{API}/knowledge-points", csrf_token=other_csrf,
        json={"chapter_id": chapter["id"], "title": "乙的草稿知识点", "body_md": "内容",
              "sort_order": 1, "published": False},
    ).get_json()["data"]

    # 教师甲不能把问答挂到别人未发布的知识点上
    assert create_entry(teacher, csrf, draft["id"]).status_code == 403
    # 但可以挂到已发布的知识点上（含他人的已发布内容）
    published = api_call(
        other, "post", f"{API}/knowledge-points", csrf_token=other_csrf,
        json={"chapter_id": chapter["id"], "title": "乙的已发布知识点", "body_md": "内容",
              "sort_order": 2, "published": True},
    ).get_json()["data"]
    assert create_entry(teacher, csrf, published["id"]).status_code == 201

    # 列表按知识点过滤
    listed = api_call(
        teacher, "get", f"{API}/qa-entries?knowledge_id={published['id']}", csrf_token=csrf
    ).get_json()
    assert listed["meta"]["total"] == 1


def test_seed_is_idempotent_and_covers_all_units(lab):
    app = lab["app"]
    runner = app.test_cli_runner()
    assert scalar(app, "SELECT COUNT(*) FROM qa_entries WHERE published = 1") == 16

    again = runner.invoke(args=["seed-qa", "--owner-login", "teacher_aaa"])
    assert again.exit_code == 0, again.output
    assert "新增 0 条" in again.output
    assert scalar(app, "SELECT COUNT(*) FROM qa_entries") == 16

    # 每条语料都挂在一个已发布知识点上，且六个单元都有覆盖
    orphans = scalar(
        app,
        "SELECT COUNT(*) FROM qa_entries q LEFT JOIN knowledge_points k ON k.id = q.knowledge_id "
        "WHERE k.id IS NULL OR k.published = 0",
    )
    assert orphans == 0
    assert scalar(app, "SELECT COUNT(DISTINCT k.chapter_id) FROM qa_entries q "
                       "JOIN knowledge_points k ON k.id = q.knowledge_id") == 6
    assert scalar(app, "SELECT COUNT(DISTINCT q.knowledge_id) FROM qa_entries q") >= 12


def test_seed_requires_course_content(bare_app):
    """没有课程内容时给出可读提示，而不是写出一批无主语料。"""
    result = bare_app.test_cli_runner().invoke(
        args=["seed-qa", "--owner-login", "admin_root"]
    )
    assert result.exit_code != 0
    assert "seed-content" in result.output
    assert scalar(bare_app, "SELECT COUNT(*) FROM qa_entries") == 0


def test_concurrent_queries_build_index_once(lab):
    """并发请求只让一个线程构建索引（SPEC-007 第 4 节第 3 条）。"""
    import threading

    factory = lab["app"].extensions["db_session"]
    reset_index_cache()
    versions: list[str] = []
    errors: list[BaseException] = []

    def worker():
        session = factory()
        try:
            versions.append(retrieval.search(session, "计数器数到 5 之后")[0])
        except BaseException as exc:  # noqa: BLE001 - 线程内异常需要在主线程复现
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, errors
    assert build_count() == 1, "四个并发请求只应触发一次构建"
    assert len(set(versions)) == 1


def test_index_build_failure_reports_explicitly(lab, monkeypatch):
    """构建失败时保留旧索引并显式报错，不返回混合版本。"""
    teacher, csrf = lab["teacher"]
    ok = ask(teacher, csrf, "计数器数到 5 之后")
    assert ok.status_code == 200
    good_version = ok.get_json()["data"]["corpus_version"]

    # 让下一次构建失败（指纹变化后才会触发重建）
    def boom(_session):
        raise RuntimeError("读取语料失败")

    monkeypatch.setattr(retrieval, "load_corpus", boom)
    point = point_id(lab["app"], "状态表与状态图")
    teacher_client, teacher_csrf = teacher, csrf
    api_call(
        teacher_client, "patch", f"{API}/knowledge-points/{point}", csrf_token=teacher_csrf,
        json={"version": scalar(lab["app"], "SELECT version FROM knowledge_points WHERE id = ?", (point,)),
              "title": "状态表与状态图（改名）"},
    )

    failed = ask(teacher, csrf, "状态表应该怎么读")
    assert failed.status_code == 503
    assert failed.get_json()["error"]["code"] == "INDEX_UNAVAILABLE"

    # 旧索引仍在缓存里，恢复后同一指纹可以继续使用
    monkeypatch.undo()
    recovered = ask(teacher, csrf, "状态表应该怎么读")
    assert recovered.status_code == 200
    assert recovered.get_json()["data"]["corpus_version"] != good_version
    assert build_count() >= 2


# ---- 摘要 ----

def test_excerpt_bounds_and_centering():
    long_text = "无关内容" * 200 + "模六计数器在状态五之后回到零" + "结尾" * 200
    text = retrieval.excerpt(long_text, "计数器状态五之后", limit=300)
    assert len(text) <= 300
    assert "回到零" in text, "摘要应落在查询命中的位置附近，而不是固定取开头"

    short = retrieval.excerpt("很短的内容", "计数器", limit=300)
    assert short == "很短的内容"

    assert len(retrieval.excerpt("内容" * 500, "找不到的词", limit=300)) == 300


def test_corpus_excludes_assessment_answers(lab):
    """语料只含已发布知识点与问答，不含测评题目与答案（SPEC-007 第 4 节第 1 条）。"""
    teacher, csrf = lab["teacher"]
    api_call(
        teacher, "post", f"{API}/questions", csrf_token=csrf,
        json={
            "type": "single",
            "stem_md": "独特考题：模六计数器状态五之后是什么？",
            "options": [{"key": "A", "label": "零"}, {"key": "B", "label": "一"}],
            "answer": ["A"],
            "explanation_md": "独特解析文本",
            "difficulty": 1,
            "knowledge_ids": [point_id(lab["app"], "模 6 计数器与 5→0 回卷")],
            "published": True,
        },
    )
    body = ask(teacher, csrf, "独特考题独特解析").get_json()["data"]
    assert body["matched"] is False, "测评题目与答案不应进入检索语料"
