"""SPEC-016 图查询的纯计算部分（E066/E067/E068）。

不依赖 Flask 与 SQLAlchemy：入参是从库里取出的普通结构，出参是图的节点、边与
状态。口径来自 SPEC-016 第 4 节与 ADR-007 第 5 条：

- 边方向恒为 prerequisite_id → target_id（先修指向后继）。
- 只处理调用方已过滤好的**已发布**知识点；本模块不判断发布状态。
- 遍历忽略方向的只有「到 root 的距离」；响应里的边始终保持先修→后继方向。
- 图算法用标准库实现（BFS、分层 Kahn 拓扑排序、Tarjan 强连通分量），不引入
  图数据库或第三方图库。
"""

from __future__ import annotations

MAX_NODES = 200
MIN_DEPTH = 1
MAX_DEPTH = 3
MAX_EDGES = 1000


def scoped_edges(node_ids, edges) -> list[tuple[int, int]]:
    """只保留两端都在 node_ids 中的边，按 (先修, 后继) 排序保证确定性。"""
    known = set(node_ids)
    kept = [(p, t) for p, t in edges if p in known and t in known]
    return sorted(set(kept))


def adjacency(node_ids, edges):
    outgoing: dict[int, list[int]] = {node: [] for node in node_ids}
    incoming: dict[int, list[int]] = {node: [] for node in node_ids}
    for prerequisite, target in scoped_edges(node_ids, edges):
        outgoing[prerequisite].append(target)
        incoming[target].append(prerequisite)
    for bucket in (outgoing, incoming):
        for node in bucket:
            bucket[node].sort()
    return outgoing, incoming


def root_ids(node_ids, edges) -> list[int]:
    """根节点集合 = 作用域内没有先修的节点（入度为 0），按 ID 升序。"""
    _outgoing, incoming = adjacency(node_ids, edges)
    return sorted(node for node in node_ids if not incoming.get(node))


def distances_from_root(node_ids, edges, root: int, max_depth: int) -> dict[int, int]:
    """以 root 为中心、忽略边方向的最短边数，最多 max_depth 层。

    与 root 不连通的节点不进入结果（子图按深度裁剪）。
    """
    neighbors: dict[int, list[int]] = {node: [] for node in node_ids}
    for prerequisite, target in scoped_edges(node_ids, edges):
        neighbors[prerequisite].append(target)
        neighbors[target].append(prerequisite)
    for node in neighbors:
        neighbors[node].sort()

    seen = {root: 0}
    frontier = [root]
    for depth in range(1, max_depth + 1):
        following: list[int] = []
        for node in frontier:
            for neighbor in neighbors[node]:
                if neighbor not in seen:
                    seen[neighbor] = depth
                    following.append(neighbor)
        if not following:
            break
        frontier = following
    return seen


def truncate(node_order, distances, limit: int = MAX_NODES):
    """按到 root 的距离裁剪到上限；distances 为 None 时按调用方给定顺序取前 limit 个。"""
    ranked = list(node_order)
    if distances is not None:
        ranked.sort(key=lambda node: (distances[node], node))
    kept = ranked[:limit]
    return kept, len(ranked) > limit


def shortest_path(node_ids, edges, source: int, target: int) -> list[int] | None:
    """沿先修→后继方向的 BFS 最短路；无路径返回 None（不编造中间节点）。"""
    if source == target:
        return [source]
    outgoing, _incoming = adjacency(node_ids, edges)
    previous: dict[int, int] = {source: source}
    frontier = [source]
    while frontier:
        following: list[int] = []
        for node in frontier:
            for neighbor in outgoing.get(node, ()):
                if neighbor in previous:
                    continue
                previous[neighbor] = node
                if neighbor == target:
                    path = [target]
                    while path[-1] != source:
                        path.append(previous[path[-1]])
                    return list(reversed(path))
                following.append(neighbor)
        frontier = following
    return None


def topological_order(node_ids, edges, order_key) -> list[int] | None:
    """分层 Kahn 拓扑排序；同层按 order_key（sort_order, id）排序。

    有环时返回 None —— 调用方改用 cycle_edges 说明环的位置。
    """
    outgoing, indegree = adjacency(node_ids, edges)
    degrees = {node: len(indegree[node]) for node in node_ids}
    ready = sorted((node for node in node_ids if degrees[node] == 0), key=order_key)
    order: list[int] = []
    while ready:
        layer = ready
        ready = []
        for node in layer:
            order.append(node)
            for neighbor in outgoing[node]:
                degrees[neighbor] -= 1
                if degrees[neighbor] == 0:
                    ready.append(neighbor)
        ready.sort(key=order_key)
    return order if len(order) == len(node_ids) else None


def cycle_edges(node_ids, edges) -> list[tuple[int, int]]:
    """位于某个环上的边：两端属于同一个大小 >1 的强连通分量（迭代 Tarjan）。

    只返回真正在环上的边，不含「指向环但从不在环上」的边。
    """
    kept = scoped_edges(node_ids, edges)
    if not kept:
        return []
    outgoing, _incoming = adjacency(node_ids, kept)
    index_of: dict[int, int] = {}
    low: dict[int, int] = {}
    on_stack: dict[int, bool] = {}
    component_stack: list[int] = []
    component_of: dict[int, int] = {}
    counter = 0
    component_count = 0

    for start in sorted(node_ids):
        if start in index_of:
            continue
        index_of[start] = low[start] = counter
        counter += 1
        component_stack.append(start)
        on_stack[start] = True
        frames: list[tuple[int, object]] = [(start, iter(outgoing[start]))]
        while frames:
            node, iterator = frames[-1]
            descended = False
            for neighbor in iterator:  # type: ignore[union-attr]
                if neighbor not in index_of:
                    index_of[neighbor] = low[neighbor] = counter
                    counter += 1
                    component_stack.append(neighbor)
                    on_stack[neighbor] = True
                    frames.append((neighbor, iter(outgoing[neighbor])))
                    descended = True
                    break
                if on_stack.get(neighbor):
                    low[node] = min(low[node], index_of[neighbor])
            if descended:
                continue
            frames.pop()
            if frames:
                parent = frames[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index_of[node]:
                while True:
                    member = component_stack.pop()
                    on_stack[member] = False
                    component_of[member] = component_count
                    if member == node:
                        break
                component_count += 1

    sizes: dict[int, int] = {}
    for component in component_of.values():
        sizes[component] = sizes.get(component, 0) + 1
    return [
        (prerequisite, target)
        for prerequisite, target in kept
        if component_of[prerequisite] == component_of[target]
        and sizes[component_of[prerequisite]] > 1
    ]
