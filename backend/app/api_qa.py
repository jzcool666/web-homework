"""E059/E060 问答语料管理、E061 课程检索问答（SPEC-007 第 4 节）。

- 语料由教师维护：每条问答挂在一个知识点上，学生与教师都能检索**已发布**内容。
- 检索在库内语料上做字符 2—4 gram 的 TF-IDF 余弦匹配，不调用任何外部大模型服务；
  相似度表示文本相近程度，不是正确概率（ADR-007 第 1 条）。
- 命中为空或全部低于阈值时返回 matched=false，不编造解释。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import Blueprint, request
from sqlalchemy import func, select

from .auth import current_user, require_course_access, roles_required
from .errors import ApiError, success
from .models_content import KnowledgePoint
from .models_qa import ANSWER_MD_MAX, QUESTION_MAX, QAEntry, qa_entry_public
from .retrieval import IndexUnavailable, QUERY_MAX, QUERY_MIN, search
from .store import db_session
from .validation import json_object, pagination, text_field

bp = Blueprint("qa", __name__)

MAX_URL_LEN = 2000
Q_MAX = 100

# 单用户每分钟 20 次查询（SPEC-007 第 4 节第 4 条）；进程内计数，单实例重启清空
QUERY_LIMIT = 20
QUERY_WINDOW = timedelta(minutes=1)
_query_hits: dict[int, list[datetime]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fields_error(field: str, rule: str):
    raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {field: rule}})


def _int_field(body: dict, name: str, *, minimum: int = 1) -> int:
    value = body.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        _fields_error(name, "必须是正整数")
    return value


def _question_field(body: dict, name: str = "question") -> str:
    value = text_field(
        body, name, rule=f"1—{QUESTION_MAX} 个字符", min_len=1, max_len=QUESTION_MAX
    ).strip()
    if not value:
        _fields_error(name, f"1—{QUESTION_MAX} 个字符")
    return value


def _answer_field(body: dict, name: str = "answer_md") -> str:
    value = body.get(name)
    if not isinstance(value, str) or not (1 <= len(value) <= ANSWER_MD_MAX):
        _fields_error(name, f"1—{ANSWER_MD_MAX} 个字符")
    return value


def _optional_http_url(body: dict, name: str) -> str | None:
    """外链只允许 http/https 且要有主机名（ADR-008）。None 表示显式置空。"""
    if name not in body or body[name] is None:
        return None
    value = body[name]
    if not isinstance(value, str):
        _fields_error(name, "必须是字符串")
    url = value.strip()
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
    except ValueError:
        parsed, host = None, None
    if (
        not url
        or len(url) > MAX_URL_LEN
        or parsed is None
        or parsed.scheme.lower() not in {"http", "https"}
        or not host
        or any(char.isspace() for char in url)
    ):
        _fields_error(name, "只允许 http/https 链接且不超过 2000 个字符")
    return url


def _published_field(body: dict) -> bool:
    value = body.get("published")
    if not isinstance(value, bool):
        _fields_error("published", "必须是布尔值")
    return value


def _query_text() -> str | None:
    raw = request.args.get("q")
    if raw is None or raw == "":
        return None
    if len(raw) > Q_MAX:
        raise ApiError("INVALID_REQUEST", f"q 最长 {Q_MAX} 个字符")
    return raw


def _int_arg(name: str, *, required: bool) -> int | None:
    raw = request.args.get(name)
    if raw is None or raw == "":
        if required:
            raise ApiError("INVALID_REQUEST", f"{name} 必填")
        return None
    try:
        value = int(raw)
    except ValueError:
        raise ApiError("INVALID_REQUEST", f"{name} 必须是整数") from None
    if value < 1:
        raise ApiError("INVALID_REQUEST", f"{name} 必须是正整数")
    return value


def _paginate(session, stmt, page: int, page_size: int):
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return rows, total


def _visible_point(session, knowledge_id: int, user) -> KnowledgePoint:
    """条目只能挂在该教师可见的知识点上：已发布，或本人草稿。"""
    point = session.get(KnowledgePoint, knowledge_id)
    if point is None:
        _fields_error("knowledge_id", "知识点不存在")
    if not point.published and point.owner_id != user.id:
        raise ApiError("FORBIDDEN", "不能把问答条目挂到他人未发布的知识点上")
    return point


def _own_entry(session, entry_id: int, user) -> QAEntry:
    entry = session.get(QAEntry, entry_id)
    if entry is None:
        raise ApiError("NOT_FOUND", "问答条目不存在")
    if entry.owner_id != user.id:
        raise ApiError("FORBIDDEN", "只能修改本人创建的问答条目")
    return entry


# ---- E059 /qa-entries ----

@bp.get("/qa-entries")
@roles_required("teacher")
def list_qa_entries():
    page, page_size = pagination()
    session = db_session()
    stmt = select(QAEntry)

    knowledge_id = _int_arg("knowledge_id", required=False)
    if knowledge_id is not None:
        stmt = stmt.where(QAEntry.knowledge_id == knowledge_id)

    q = _query_text()
    if q:
        stmt = stmt.where(QAEntry.question.contains(q, autoescape=True))

    stmt = stmt.order_by(QAEntry.created_at.desc(), QAEntry.id.desc())
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [qa_entry_public(entry) for entry in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@bp.post("/qa-entries")
@roles_required("teacher")
def create_qa_entry():
    user = current_user()
    body = json_object(
        ["knowledge_id", "question", "answer_md", "source_url", "published"]
    )
    session = db_session()
    point = _visible_point(session, _int_field(body, "knowledge_id"), user)

    entry = QAEntry(
        knowledge_id=point.id,
        question=_question_field(body),
        answer_md=_answer_field(body),
        source_url=_optional_http_url(body, "source_url"),
        published=1 if _published_field(body) else 0,
        owner_id=user.id,
    )
    session.add(entry)
    session.commit()
    return success(qa_entry_public(entry), 201)


# ---- E060 /qa-entries/{id} ----

@bp.patch("/qa-entries/<int:entry_id>")
@roles_required("teacher")
def patch_qa_entry(entry_id: int):
    user = current_user()
    body = json_object(
        ["version", "knowledge_id", "question", "answer_md", "source_url", "published"]
    )
    session = db_session()
    entry = _own_entry(session, entry_id, user)

    version = body.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        _fields_error("version", "必须是整数")
    if version != entry.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "问答条目已被修改，请刷新后重试",
            {"expected_version": version, "current_version": entry.version},
        )

    editable = {"knowledge_id", "question", "answer_md", "source_url", "published"}
    if not editable & set(body):
        raise ApiError("VALIDATION_ERROR", "没有可更新的字段")

    if "knowledge_id" in body:
        entry.knowledge_id = _visible_point(
            session, _int_field(body, "knowledge_id"), user
        ).id
    if "question" in body:
        entry.question = _question_field(body)
    if "answer_md" in body:
        entry.answer_md = _answer_field(body)
    if "source_url" in body:
        entry.source_url = _optional_http_url(body, "source_url")
    if "published" in body:
        entry.published = 1 if _published_field(body) else 0

    # 版本递增使语料指纹随之变化，下一次查询会重建索引（SPEC-007 第 4 节第 3 条）
    entry.version += 1
    session.commit()
    return success(qa_entry_public(entry))


# ---- E061 /qa/queries ----

def check_query_rate(user_id: int) -> None:
    now = _now()
    stamps = [stamp for stamp in _query_hits.get(user_id, []) if now - stamp < QUERY_WINDOW]
    _query_hits[user_id] = stamps
    if len(stamps) >= QUERY_LIMIT:
        retry_after = int((QUERY_WINDOW - (now - min(stamps))).total_seconds()) + 1
        raise ApiError(
            "RATE_LIMITED",
            "查询过于频繁，请稍后再试",
            details={"retry_after": retry_after, "limit": QUERY_LIMIT},
            headers={"Retry-After": str(retry_after)},
        )
    stamps.append(now)


def reset_query_limits() -> None:
    """清空进程内查询计数；测试用它隔离用例，运行时不调用。"""
    _query_hits.clear()


@bp.post("/qa/queries")
def query_qa_corpus():
    user = require_course_access()
    body = json_object(["query"])
    raw = body.get("query")
    if not isinstance(raw, str):
        _fields_error("query", f"必须是 {QUERY_MIN}—{QUERY_MAX} 个字符")
    query = raw.strip()
    if not (QUERY_MIN <= len(query) <= QUERY_MAX):
        _fields_error("query", f"必须是 {QUERY_MIN}—{QUERY_MAX} 个字符")

    check_query_rate(user.id)

    try:
        corpus_version, matches = search(db_session(), query)
    except IndexUnavailable as exc:
        # 索引重建失败：显式报错，不拿旧指纹的结果回答新语料的问题
        raise ApiError("INDEX_UNAVAILABLE", str(exc) or "检索索引暂时不可用") from exc

    return success(
        {
            "matched": bool(matches),
            "corpus_version": corpus_version,
            "matches": [match.as_dict() for match in matches],
        }
    )
