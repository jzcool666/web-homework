"""E066/E067/E068 时序逻辑知识图谱（SPEC-016 第 4 节）。

只读投影：图由 SPEC-005 的 knowledge_points 与 knowledge_edges 实时计算，
不另建缓存表，也不提供任何写入口——先修关系的增删改仍走课程内容管理接口。

三条不变式：
- 只包含**已发布**知识点；任一端点未发布的边不进入任何响应。
- 边方向恒为 prerequisite_id → target_id，响应里不翻转。
- 无路径返回 matched=false 且节点为空；有环返回环上各边且不输出拓扑序，
  不把「算不出来」伪装成「没有内容」。
"""

from __future__ import annotations

from flask import Blueprint, request
from sqlalchemy import select

from .auth import require_course_access
from .errors import ApiError, success
from .graph_service import (
    MAX_DEPTH,
    MIN_DEPTH,
    cycle_edges,
    distances_from_root,
    root_ids,
    scoped_edges,
    shortest_path,
    topological_order,
    truncate,
)
from .models_content import Chapter, KnowledgeEdge, KnowledgePoint
from .store import db_session

bp = Blueprint("graph", __name__)


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


def _depth_arg() -> int:
    """depth 默认 1；非整数是格式错误（400），超出 1—3 是字段错误（422）。"""
    raw = request.args.get("depth")
    if raw is None or raw == "":
        return MIN_DEPTH
    try:
        value = int(raw)
    except ValueError:
        raise ApiError("INVALID_REQUEST", "depth 必须是整数") from None
    if not (MIN_DEPTH <= value <= MAX_DEPTH):
        raise ApiError(
            "VALIDATION_ERROR",
            "请求字段不合法",
            {"fields": {"depth": f"必须是 {MIN_DEPTH}—{MAX_DEPTH} 的整数"}},
        )
    return value


def _load_scope(session, chapter_id: int | None):
    """已发布知识点（可按章节收窄）与其间两端都已发布的边。"""
    if chapter_id is not None and session.get(Chapter, chapter_id) is None:
        raise ApiError("NOT_FOUND", "章节不存在")

    stmt = select(KnowledgePoint).where(KnowledgePoint.published == 1)
    if chapter_id is not None:
        stmt = stmt.where(KnowledgePoint.chapter_id == chapter_id)
    points = list(
        session.scalars(
            stmt.order_by(KnowledgePoint.chapter_id, KnowledgePoint.sort_order, KnowledgePoint.id)
        )
    )
    by_id = {point.id: point for point in points}
    rows = session.execute(
        select(KnowledgeEdge.prerequisite_id, KnowledgeEdge.target_id)
    ).all()
    edges = scoped_edges(by_id.keys(), rows)
    return by_id, edges


def _node_public(point: KnowledgePoint, depth: int, dimension: int) -> dict:
    return {
        "knowledge_id": point.id,
        "title": point.title,
        "chapter_id": point.chapter_id,
        "depth": depth,
        "dimension": dimension,
    }


def _edge_public(edge: tuple[int, int]) -> dict:
    return {"prerequisite_id": edge[0], "target_id": edge[1]}


# ---- E066 /knowledge-graph ----

@bp.get("/knowledge-graph")
def knowledge_graph():
    require_course_access()
    session = db_session()
    chapter_id = _int_arg("chapter_id", required=False)
    root_id = _int_arg("root_id", required=False)
    depth = _depth_arg()
    by_id, edges = _load_scope(session, chapter_id)

    if root_id is not None:
        if root_id not in by_id:
            raise ApiError("NOT_FOUND", "知识点不存在")
        # 距离忽略方向；depth 层之外不进入子图
        distances = distances_from_root(list(by_id), edges, root_id, depth)
        ranked = sorted(
            distances, key=lambda node: (distances[node], by_id[node].sort_order, node)
        )
        kept, truncated = truncate(ranked, None)
        depth_of = {node: distances[node] for node in kept}
        dimension_of = {node: 1 if node == root_id else 0 for node in kept}
    else:
        ids = list(by_id)
        roots = set(root_ids(ids, edges))
        # 未指定 root 时不做深度裁剪，按 (章节, sort_order, id) 稳定排序后取前 200
        ranked = sorted(ids, key=lambda node: (by_id[node].chapter_id, by_id[node].sort_order, node))
        kept, truncated = truncate(ranked, None)
        depth_of = {node: 0 for node in kept}
        dimension_of = {node: 1 if node in roots else 0 for node in kept}

    kept_edges = scoped_edges(kept, edges)
    return success(
        {
            "nodes": [
                _node_public(by_id[node], depth_of[node], dimension_of[node]) for node in kept
            ],
            "edges": [_edge_public(edge) for edge in kept_edges],
            "has_cycle": bool(cycle_edges(kept, kept_edges)),
            "truncated": truncated,
        }
    )


# ---- E067 /knowledge-graph/path ----

@bp.get("/knowledge-graph/path")
def knowledge_graph_path():
    require_course_access()
    session = db_session()
    source = _int_arg("from", required=True)
    target = _int_arg("to", required=True)
    by_id, edges = _load_scope(session, None)
    for value in (source, target):
        if value not in by_id:
            raise ApiError("NOT_FOUND", "知识点不存在")

    path = shortest_path(list(by_id), edges, source, target)
    if path is None:
        return success({"matched": False, "nodes": [], "edges": []})
    return success(
        {
            "matched": True,
            "nodes": [
                _node_public(by_id[node], position, 1 if node == source else 0)
                for position, node in enumerate(path)
            ],
            "edges": [_edge_public(edge) for edge in zip(path, path[1:])],
        }
    )


# ---- E068 /knowledge-graph/topological ----

@bp.get("/knowledge-graph/topological")
def knowledge_graph_topological():
    require_course_access()
    session = db_session()
    chapter_id = _int_arg("chapter_id", required=False)
    by_id, edges = _load_scope(session, chapter_id)
    ids = list(by_id)

    order = topological_order(ids, edges, lambda node: (by_id[node].sort_order, node))
    if order is None:
        # 有环：只报告环上的边，不给一个看似可用的顺序
        return success(
            {
                "has_cycle": True,
                "cycle_edges": [_edge_public(edge) for edge in cycle_edges(ids, edges)],
            }
        )
    return success({"order": order, "has_cycle": False, "cycle_edges": []})
