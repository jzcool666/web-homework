"""E011—E022：章节、知识点、资源版本、收藏、进度与资源事件（SPEC-005）。

权限要点：
- 课程内容在本系统内共享（DBD 第 3 节）：教师/管理员，或有有效选课的学生才能读取。
  未入班学生只能访问 /me，读课程集合返回 403。
- 学生只能看到已发布内容；草稿对非所有者一律按 404 处理，不泄露其存在。
- 写操作限「内容所有者」（teacher/admin），且只能改本人创建的内容；
  非所有者的写请求返回 403，因为内容对象不按班级隔离，不属于跨班 404 的场景。
"""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import Blueprint, current_app, request, send_file
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from .auth import current_user, login_required, roles_required
from .errors import ApiError, success
from .models import Enrollment
from .models_content import (
    BODY_MD_MAX,
    NOTE_MAX,
    RESOURCE_CATEGORIES,
    RESOURCE_EVENT_KINDS,
    Chapter,
    Favorite,
    KnowledgePoint,
    LearningProgress,
    Resource,
    ResourceEvent,
    ResourceVersion,
    chapter_public,
    knowledge_public,
    now_utc,
    progress_public,
    resource_public,
    resource_version_public,
    utc_day,
)
from .storage import (
    FILE_SIZE_RULE,
    FILE_TYPE_RULE,
    MAX_UPLOAD_BYTES,
    display_name,
    resolve_storage_path,
    store_file,
    upload_root,
    validate_upload,
)
from .store import db_session
from .validation import json_object, pagination, text_field

bp = Blueprint("content", __name__)

STAFF_ROLES = ("teacher", "admin")
MAX_URL_LEN = 2000
# multipart 的分隔与头部有额外开销，先按请求体粗略挡一次，精确上限在读取后判定。
MULTIPART_SLACK = 1024 * 1024

Q_MAX = 100


# ---- 公共校验与权限 ----

def _int_field(body: dict, name: str, *, minimum: int = 0) -> int:
    value = body.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ApiError(
            "VALIDATION_ERROR", "请求字段不合法", {"fields": {name: f"必须是 ≥{minimum} 的整数"}}
        )
    return value


def _bool_field(body: dict, name: str) -> bool:
    value = body.get(name)
    if not isinstance(value, bool):
        raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {name: "必须是布尔值"}})
    return value


def _title(body: dict, name: str = "title") -> str:
    value = text_field(body, name, rule="1—100 个字符", min_len=1, max_len=100).strip()
    if not value:
        raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {name: "1—100 个字符"}})
    return value


def _optional_http_url(body: dict, name: str, *, required: bool) -> str | None:
    """外链只允许 http/https（ADR-008）。None 表示显式置空。"""
    if name not in body:
        if required:
            raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {name: "必填"}})
        return None
    value = body[name]
    if value is None:
        if required:
            raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {name: "必填"}})
        return None
    if not isinstance(value, str):
        raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {name: "必须是字符串"}})
    url = value.strip()
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
    except ValueError:
        host = None
        parsed = None
    if (
        not url or len(url) > MAX_URL_LEN or parsed is None
        or parsed.scheme.lower() not in {"http", "https"}
        or not host or any(char.isspace() for char in url)
    ):
        raise ApiError(
            "VALIDATION_ERROR",
            "请求字段不合法",
            {"fields": {name: "只允许 http/https 链接且不超过 2000 字符"}},
        )
    return url


def _query_text() -> str | None:
    raw = request.args.get("q")
    if raw is None or raw == "":
        return None
    if len(raw) > Q_MAX:
        raise ApiError("INVALID_REQUEST", f"q 最长 {Q_MAX} 个字符")
    return raw


def _bool_arg(name: str) -> bool | None:
    raw = request.args.get(name)
    if raw is None:
        return None
    if raw not in {"true", "false", "1", "0"}:
        raise ApiError("INVALID_REQUEST", f"{name} 取值不合法", {"allowed": ["true", "false"]})
    return raw in {"true", "1"}


def _require_reader():
    """课程公开内容的读取门槛：教师/管理员，或有有效选课的学生。"""
    user = current_user()
    if user is None:
        raise ApiError("UNAUTHENTICATED", "请先登录")
    if user.role in STAFF_ROLES:
        return user
    enrolled = db_session().scalar(
        select(Enrollment.student_id)
        .where(Enrollment.student_id == user.id, Enrollment.active == 1)
        .limit(1)
    )
    if enrolled is None:
        raise ApiError("FORBIDDEN", "尚未分配班级，暂不能查看课程内容")
    return user


def _require_staff():
    user = current_user()
    if user is None:
        raise ApiError("UNAUTHENTICATED", "请先登录")
    if user.role not in STAFF_ROLES:
        raise ApiError("FORBIDDEN", "只有教师或管理员可以维护课程内容")
    return user


def _visible(stmt, model, user):
    """教师/管理员看「已发布 + 本人草稿」；学生只看已发布。"""
    if user.role == "student":
        return stmt.where(model.published == 1)
    return stmt.where(or_(model.published == 1, model.owner_id == user.id))


def _can_view(obj, user) -> bool:
    """教师/管理员可读「已发布 + 本人草稿」；学生只读已发布。

    不可见时与不存在同样返回 404，不泄露草稿的存在性。
    """
    if obj is None:
        return False
    if user.role == "student":
        return bool(obj.published)
    return bool(obj.published) or obj.owner_id == user.id


def _require_own(obj, user, label: str):
    """仅内容所有者可写；非所有者 403，内容对象不按班级隔离。"""
    if obj is None:
        raise ApiError("NOT_FOUND", f"{label}不存在")
    if obj.owner_id != user.id:
        raise ApiError("FORBIDDEN", "只能修改本人创建的内容")
    return obj


def _require_chapter_ref(chapter_id: int) -> Chapter:
    session = db_session()
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ApiError(
            "VALIDATION_ERROR", "请求字段不合法", {"fields": {"chapter_id": "章节不存在"}}
        )
    return chapter


def _require_knowledge_ref(knowledge_id: int) -> KnowledgePoint:
    point = db_session().get(KnowledgePoint, knowledge_id)
    if point is None:
        raise ApiError(
            "VALIDATION_ERROR", "请求字段不合法", {"fields": {"knowledge_id": "知识点不存在"}}
        )
    return point


def _paginate(session, stmt, page: int, page_size: int):
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return rows, total


def _resource_versions(session, resource_id: int) -> list[ResourceVersion]:
    return list(
        session.scalars(
            select(ResourceVersion)
            .where(ResourceVersion.resource_id == resource_id)
            .order_by(ResourceVersion.version_no.asc())
        ).all()
    )


def _visible_resource_version(version_id: int, user) -> ResourceVersion:
    """按版本所属资源的可见性判定；不可见时与不存在同样返回 404。"""
    session = db_session()
    version = session.get(ResourceVersion, version_id)
    resource = None if version is None else session.get(Resource, version.resource_id)
    if resource is None or not _can_view(resource, user):
        raise ApiError("NOT_FOUND", "资源版本不存在")
    return version


# ---- E011 /chapters ----

@bp.get("/chapters")
@login_required
def list_chapters():
    user = _require_reader()
    page, page_size = pagination()
    session = db_session()
    stmt = _visible(select(Chapter), Chapter, user)

    published = _bool_arg("published")
    if published is not None:
        stmt = stmt.where(Chapter.published == (1 if published else 0))
    q = _query_text()
    if q:
        stmt = stmt.where(Chapter.title.contains(q, autoescape=True))

    stmt = stmt.order_by(Chapter.sort_order.asc(), Chapter.id.asc())
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [chapter_public(c) for c in rows], page=page, page_size=page_size, total=total
    )


@bp.post("/chapters")
@roles_required(*STAFF_ROLES)
def create_chapter():
    user = _require_staff()
    body = json_object(["title", "sort_order", "published"])
    chapter = Chapter(
        title=_title(body),
        sort_order=_int_field(body, "sort_order"),
        published=1 if _bool_field(body, "published") else 0,
        owner_id=user.id,
    )
    session = db_session()
    session.add(chapter)
    session.commit()
    return success(chapter_public(chapter), 201)


# ---- E012 /chapters/{id} ----

@bp.patch("/chapters/<int:chapter_id>")
@roles_required(*STAFF_ROLES)
def patch_chapter(chapter_id: int):
    user = _require_staff()
    body = json_object(["version", "title", "sort_order", "published"])
    session = db_session()
    chapter = _require_own(session.get(Chapter, chapter_id), user, "章节")

    version = body.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ApiError("VALIDATION_ERROR", "version 必须是整数", {"fields": {"version": "必填"}})
    if version != chapter.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "章节已被修改，请刷新后重试",
            {"expected_version": version, "current_version": chapter.version},
        )

    if "title" in body:
        chapter.title = _title(body)
    if "sort_order" in body:
        chapter.sort_order = _int_field(body, "sort_order")
    if "published" in body:
        chapter.published = 1 if _bool_field(body, "published") else 0
    if not {"title", "sort_order", "published"} & set(body):
        raise ApiError("VALIDATION_ERROR", "没有可更新的字段")

    chapter.version += 1
    session.commit()
    return success(chapter_public(chapter))


# ---- E013 /knowledge-points ----

def _knowledge_write_fields(body: dict) -> dict:
    if "body_md" not in body:
        raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {"body_md": "必填"}})
    body_md = text_field(body, "body_md", rule=f"1—{BODY_MD_MAX} 个字符", min_len=1, max_len=BODY_MD_MAX)
    return {
        "title": _title(body),
        "body_md": body_md,
        "source_url": _optional_http_url(body, "source_url", required=False),
        "sort_order": _int_field(body, "sort_order"),
        "published": 1 if _bool_field(body, "published") else 0,
    }


@bp.get("/knowledge-points")
@login_required
def list_knowledge_points():
    user = _require_reader()
    page, page_size = pagination()
    session = db_session()
    stmt = _visible(select(KnowledgePoint), KnowledgePoint, user).join(
        Chapter, Chapter.id == KnowledgePoint.chapter_id
    )

    chapter_id = request.args.get("chapter_id")
    if chapter_id is not None:
        try:
            value = int(chapter_id)
        except ValueError:
            raise ApiError("INVALID_REQUEST", "chapter_id 必须是整数")
        if value < 1:
            raise ApiError("INVALID_REQUEST", "chapter_id 必须是正整数")
        stmt = stmt.where(KnowledgePoint.chapter_id == value)

    published = _bool_arg("published")
    if published is not None:
        stmt = stmt.where(KnowledgePoint.published == (1 if published else 0))

    q = _query_text()
    if q:
        stmt = stmt.where(
            or_(
                KnowledgePoint.title.contains(q, autoescape=True),
                KnowledgePoint.body_md.contains(q, autoescape=True),
            )
        )

    stmt = stmt.order_by(
        Chapter.sort_order.asc(), KnowledgePoint.sort_order.asc(), KnowledgePoint.id.asc()
    )
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [knowledge_public(p) for p in rows], page=page, page_size=page_size, total=total
    )


@bp.post("/knowledge-points")
@roles_required(*STAFF_ROLES)
def create_knowledge_point():
    user = _require_staff()
    body = json_object(
        ["chapter_id", "title", "body_md", "source_url", "sort_order", "published"]
    )
    chapter_id = _int_field(body, "chapter_id", minimum=1)
    session = db_session()
    chapter = _require_chapter_ref(chapter_id)
    # 只能挂到本人草稿或已发布章节上（DBD 第 3 节：教师可引用已发布材料）
    if not chapter.published and chapter.owner_id != user.id:
        raise ApiError("FORBIDDEN", "不能向他人未发布的章节添加内容")

    point = KnowledgePoint(chapter_id=chapter_id, owner_id=user.id, **_knowledge_write_fields(body))
    session.add(point)
    session.commit()
    return success(knowledge_public(point), 201)


# ---- E014 /knowledge-points/{id} ----

@bp.get("/knowledge-points/<int:knowledge_id>")
@login_required
def get_knowledge_point(knowledge_id: int):
    user = _require_reader()
    session = db_session()
    point = session.get(KnowledgePoint, knowledge_id)
    if not _can_view(point, user):
        raise ApiError("NOT_FOUND", "知识点不存在")
    return success(knowledge_public(point))


@bp.patch("/knowledge-points/<int:knowledge_id>")
@roles_required(*STAFF_ROLES)
def patch_knowledge_point(knowledge_id: int):
    user = _require_staff()
    body = json_object(
        ["version", "chapter_id", "title", "body_md", "source_url", "sort_order", "published"]
    )
    session = db_session()
    point = _require_own(session.get(KnowledgePoint, knowledge_id), user, "知识点")

    version = body.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ApiError("VALIDATION_ERROR", "version 必须是整数", {"fields": {"version": "必填"}})
    if version != point.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "知识点已被修改，请刷新后重试",
            {"expected_version": version, "current_version": point.version},
        )

    if "chapter_id" in body:
        chapter_id = _int_field(body, "chapter_id", minimum=1)
        chapter = _require_chapter_ref(chapter_id)
        if not chapter.published and chapter.owner_id != user.id:
            raise ApiError("FORBIDDEN", "不能把内容移入他人未发布的章节")
        point.chapter_id = chapter_id
    if "title" in body:
        point.title = _title(body)
    if "body_md" in body:
        point.body_md = text_field(
            body, "body_md", rule=f"1—{BODY_MD_MAX} 个字符", min_len=1, max_len=BODY_MD_MAX
        )
    if "source_url" in body:
        point.source_url = _optional_http_url(body, "source_url", required=False)
    if "sort_order" in body:
        point.sort_order = _int_field(body, "sort_order")
    if "published" in body:
        point.published = 1 if _bool_field(body, "published") else 0

    if not {"chapter_id", "title", "body_md", "source_url", "sort_order", "published"} & set(body):
        raise ApiError("VALIDATION_ERROR", "没有可更新的字段")

    point.version += 1
    session.commit()
    return success(knowledge_public(point))


# ---- E015 /me/favorites/{knowledge_id} ----

def _require_student():
    user = current_user()
    if user is None:
        raise ApiError("UNAUTHENTICATED", "请先登录")
    if user.role != "student":
        raise ApiError("FORBIDDEN", "只有学生可以使用学习记录功能")
    _require_reader()  # 未入班学生不能通过个人写接口绕过课程读取门槛
    return user


def _published_point(knowledge_id: int) -> KnowledgePoint:
    """收藏与进度只针对学生可见的已发布知识点；草稿按 404 处理。"""
    point = db_session().get(KnowledgePoint, knowledge_id)
    if point is None or not point.published:
        raise ApiError("NOT_FOUND", "知识点不存在")
    return point


@bp.put("/me/favorites/<int:knowledge_id>")
@login_required
def add_favorite(knowledge_id: int):
    user = _require_student()
    _published_point(knowledge_id)
    session = db_session()
    # 幂等：重复 PUT 不新增行
    if session.get(Favorite, (user.id, knowledge_id)) is None:
        session.add(Favorite(student_id=user.id, knowledge_id=knowledge_id))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
    return success({"knowledge_id": knowledge_id, "favorited": True})


@bp.delete("/me/favorites/<int:knowledge_id>")
@login_required
def remove_favorite(knowledge_id: int):
    user = _require_student()
    session = db_session()
    # 幂等：取消未收藏的内容同样返回成功；收藏允许物理删除（DBD 第 3 节）
    session.execute(
        delete(Favorite).where(
            Favorite.student_id == user.id, Favorite.knowledge_id == knowledge_id
        )
    )
    session.commit()
    return success({"knowledge_id": knowledge_id, "favorited": False})


# ---- E016 /me/favorites ----

@bp.get("/me/favorites")
@login_required
def list_favorites():
    user = _require_student()
    page, page_size = pagination()
    session = db_session()
    # 只列当前仍可见（已发布）的收藏；关联表无 created_at，按 knowledge_id 稳定倒序
    stmt = (
        select(KnowledgePoint)
        .join(Favorite, Favorite.knowledge_id == KnowledgePoint.id)
        .where(Favorite.student_id == user.id, KnowledgePoint.published == 1)
        .order_by(KnowledgePoint.id.desc())
    )
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [knowledge_public(p) for p in rows], page=page, page_size=page_size, total=total
    )


# ---- E017 /me/learning-progress ----

@bp.get("/me/learning-progress")
@login_required
def list_learning_progress():
    user = _require_student()
    page, page_size = pagination()
    session = db_session()
    stmt = select(LearningProgress).where(LearningProgress.student_id == user.id)

    chapter_id = request.args.get("chapter_id")
    if chapter_id is not None:
        try:
            value = int(chapter_id)
        except ValueError:
            raise ApiError("INVALID_REQUEST", "chapter_id 必须是整数")
        if value < 1:
            raise ApiError("INVALID_REQUEST", "chapter_id 必须是正整数")
        stmt = stmt.join(
            KnowledgePoint, KnowledgePoint.id == LearningProgress.knowledge_id
        ).where(KnowledgePoint.chapter_id == value)

    stmt = stmt.order_by(LearningProgress.knowledge_id.asc())
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [progress_public(p) for p in rows], page=page, page_size=page_size, total=total
    )


@bp.put("/me/learning-progress")
@login_required
def set_learning_progress():
    user = _require_student()
    body = json_object(["knowledge_id", "completed"])
    knowledge_id = _int_field(body, "knowledge_id", minimum=1)
    completed = _bool_field(body, "completed")
    _published_point(knowledge_id)

    session = db_session()
    row = session.get(LearningProgress, (user.id, knowledge_id))
    if row is None:
        row = LearningProgress(student_id=user.id, knowledge_id=knowledge_id)
        session.add(row)

    # 完成为自报数据：重复标记同一状态不改变 completed_at（幂等）
    if completed and not row.completed:
        row.completed = 1
        row.completed_at = now_utc()
    elif not completed:
        row.completed = 0
        row.completed_at = None

    session.commit()
    return success(progress_public(row))


# ---- E018 /resources ----

def _resource_write_fields(body: dict) -> dict:
    category = body.get("category")
    if category not in RESOURCE_CATEGORIES:
        raise ApiError(
            "VALIDATION_ERROR",
            "请求字段不合法",
            {"fields": {"category": "/".join(RESOURCE_CATEGORIES)}},
        )
    return {
        "title": _title(body),
        "category": category,
        "published": 1 if _bool_field(body, "published") else 0,
    }


@bp.get("/resources")
@login_required
def list_resources():
    user = _require_reader()
    page, page_size = pagination()
    session = db_session()
    stmt = _visible(select(Resource), Resource, user)

    category = request.args.get("category")
    if category is not None:
        if category not in RESOURCE_CATEGORIES:
            raise ApiError(
                "INVALID_REQUEST",
                "category 取值不合法",
                {"allowed": list(RESOURCE_CATEGORIES)},
            )
        stmt = stmt.where(Resource.category == category)

    knowledge_id = request.args.get("knowledge_id")
    if knowledge_id is not None:
        try:
            value = int(knowledge_id)
        except ValueError:
            raise ApiError("INVALID_REQUEST", "knowledge_id 必须是整数")
        if value < 1:
            raise ApiError("INVALID_REQUEST", "knowledge_id 必须是正整数")
        stmt = stmt.where(Resource.knowledge_id == value)

    published = _bool_arg("published")
    if published is not None:
        stmt = stmt.where(Resource.published == (1 if published else 0))

    q = _query_text()
    if q:
        stmt = stmt.where(Resource.title.contains(q, autoescape=True))

    stmt = stmt.order_by(Resource.created_at.desc(), Resource.id.desc())
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [resource_public(r, _resource_versions(session, r.id)) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@bp.post("/resources")
@roles_required(*STAFF_ROLES)
def create_resource():
    user = _require_staff()
    body = json_object(["title", "category", "knowledge_id", "published"])
    knowledge_id = None
    if body.get("knowledge_id") is not None:
        knowledge_id = _int_field(body, "knowledge_id", minimum=1)
        _require_knowledge_ref(knowledge_id)

    resource = Resource(knowledge_id=knowledge_id, owner_id=user.id, **_resource_write_fields(body))
    session = db_session()
    session.add(resource)
    session.commit()
    return success(resource_public(resource, []), 201)


# ---- E019 /resources/{id} ----

@bp.patch("/resources/<int:resource_id>")
@roles_required(*STAFF_ROLES)
def patch_resource(resource_id: int):
    user = _require_staff()
    body = json_object(["version", "title", "category", "knowledge_id", "published"])
    session = db_session()
    resource = _require_own(session.get(Resource, resource_id), user, "资源")

    version = body.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ApiError("VALIDATION_ERROR", "version 必须是整数", {"fields": {"version": "必填"}})
    if version != resource.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "资源已被修改，请刷新后重试",
            {"expected_version": version, "current_version": resource.version},
        )

    if "title" in body:
        resource.title = _title(body)
    if "category" in body:
        category = body.get("category")
        if category not in RESOURCE_CATEGORIES:
            raise ApiError(
                "VALIDATION_ERROR",
                "请求字段不合法",
                {"fields": {"category": "/".join(RESOURCE_CATEGORIES)}},
            )
        resource.category = category
    if "knowledge_id" in body:
        if body["knowledge_id"] is None:
            resource.knowledge_id = None
        else:
            knowledge_id = _int_field(body, "knowledge_id", minimum=1)
            _require_knowledge_ref(knowledge_id)
            resource.knowledge_id = knowledge_id
    if "published" in body:
        resource.published = 1 if _bool_field(body, "published") else 0

    if not {"title", "category", "knowledge_id", "published"} & set(body):
        raise ApiError("VALIDATION_ERROR", "没有可更新的字段")

    resource.version += 1
    session.commit()
    return success(resource_public(resource, _resource_versions(session, resource.id)))


# ---- E020 /resources/{id}/versions ----

def _note_value(raw: object) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str) or len(raw) > NOTE_MAX:
        raise ApiError(
            "VALIDATION_ERROR", "请求字段不合法", {"fields": {"note": f"不超过 {NOTE_MAX} 个字符"}}
        )
    return raw


def _uploaded_version() -> ResourceVersion:
    """multipart 分支：校验类型与大小后用随机名落盘，返回待入库的文件版本。"""
    if request.content_length is not None and request.content_length > MAX_UPLOAD_BYTES + MULTIPART_SLACK:
        raise ApiError("FILE_TOO_LARGE", f"上传文件过大，{FILE_SIZE_RULE}")

    unknown = sorted(set(request.form) - {"note"})
    if unknown:
        raise ApiError("VALIDATION_ERROR", "请求包含未支持的字段", {"unknown_fields": unknown})

    storage = request.files.get("file")
    if storage is None or not storage.filename:
        raise ApiError(
            "VALIDATION_ERROR",
            "请提供文件或外链之一",
            {"fields": {"file": "multipart 需包含 file 字段"}},
        )

    payload = storage.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ApiError("FILE_TOO_LARGE", f"上传文件过大，{FILE_SIZE_RULE}")

    try:
        validate_upload(storage.filename, payload)
    except ValueError as exc:
        reason = str(exc)
        if reason == "size":
            raise ApiError("FILE_TOO_LARGE", f"上传文件过大，{FILE_SIZE_RULE}") from exc
        if reason == "empty":
            raise ApiError(
                "VALIDATION_ERROR", "上传文件为空", {"fields": {"file": "不能为空文件"}}
            ) from exc
        raise ApiError(
            "FILE_TYPE_UNSUPPORTED", FILE_TYPE_RULE, {"allowed": ["pdf", "pptx", "png", "jpeg"]}
        ) from exc

    note = _note_value(request.form.get("note"))
    stored = store_file(current_app.config["UPLOAD_DIR"], storage.filename, payload)
    return ResourceVersion(
        kind="file",
        storage_key=stored.storage_key,
        original_name=stored.original_name,
        mime=stored.mime,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        note=note,
    )


def _linked_version() -> ResourceVersion:
    """JSON 分支：只接受 http/https 外链，服务器不抓取远端内容。"""
    body = json_object(["external_url", "note"])
    url = _optional_http_url(body, "external_url", required=True)
    return ResourceVersion(
        kind="link",
        external_url=url,
        note=_note_value(body.get("note")),
    )


@bp.post("/resources/<int:resource_id>/versions")
@roles_required(*STAFF_ROLES)
def create_resource_version(resource_id: int):
    user = _require_staff()
    session = db_session()
    resource = _require_own(session.get(Resource, resource_id), user, "资源")

    is_multipart = (request.content_type or "").startswith("multipart/form-data")
    if is_multipart:
        version = _uploaded_version()
        written_path = upload_root(current_app.config["UPLOAD_DIR"]) / version.storage_key
    else:
        version = _linked_version()
        written_path = None
    version.resource_id = resource.id

    # version_no 追加式生成：历史版本只读，新版本另起一行
    current_max = session.scalar(
        select(func.max(ResourceVersion.version_no)).where(
            ResourceVersion.resource_id == resource.id
        )
    )
    version.version_no = (current_max or 0) + 1

    session.add(version)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        # 落库失败不保留半成品文件（APIC 第 8 节）
        if written_path is not None:
            written_path.unlink(missing_ok=True)
        raise ApiError("DUPLICATE", "资源版本已被占用，请重试") from exc
    except Exception:
        session.rollback()
        if written_path is not None:
            written_path.unlink(missing_ok=True)
        raise

    return success(resource_version_public(version), 201)


# ---- E021 /resource-versions/{id}/download ----

@bp.get("/resource-versions/<int:version_id>/download")
@login_required
def download_resource_version(version_id: int):
    user = _require_reader()
    version = _visible_resource_version(version_id, user)
    if version.kind != "file":
        raise ApiError("VALIDATION_ERROR", "链接类资源不提供文件下载")

    try:
        path = resolve_storage_path(current_app.config["UPLOAD_DIR"], version.storage_key)
    except FileNotFoundError as exc:
        raise ApiError("NOT_FOUND", "资源文件已不可用") from exc

    return send_file(
        path,
        mimetype=version.mime or "application/octet-stream",
        as_attachment=True,
        # 原始文件名只用于响应显示，不参与磁盘路径拼接
        download_name=display_name(version.original_name or "download"),
    )


# ---- E022 /resource-versions/{id}/events ----

@bp.post("/resource-versions/<int:version_id>/events")
@login_required
def record_resource_event(version_id: int):
    user = _require_student()
    body = json_object(["event_kind"])
    event_kind = body.get("event_kind")
    if event_kind not in RESOURCE_EVENT_KINDS:
        raise ApiError(
            "VALIDATION_ERROR",
            "请求字段不合法",
            {"fields": {"event_kind": "/".join(RESOURCE_EVENT_KINDS)}},
        )
    _visible_resource_version(version_id, user)

    day = utc_day()
    session = db_session()
    key = (user.id, version_id, event_kind, day)
    recorded = session.get(ResourceEvent, key) is None
    if recorded:
        session.add(
            ResourceEvent(
                student_id=user.id,
                resource_version_id=version_id,
                event_kind=event_kind,
                event_day=day,
            )
        )
        try:
            session.commit()
        except IntegrityError:
            # 并发重复提交：同日同人同版本同种类只保留一条
            session.rollback()
            recorded = False
    return success({"recorded": recorded})
