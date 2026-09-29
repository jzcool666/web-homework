"""SPEC-005 课程种子：六单元 12 知识点、先修关系与一份外链资料。

- 只写课程内容，不创建账号、不重置成绩或入班关系。
- 可重复执行：按 (owner, 标题) 与 (章节, 标题) 逐条查找，已存在则跳过。
- 先修关系写入前用 Kahn 拓扑排序检查无环（SPEC-005 第 4 节第 5 条），有环则整批回滚。
- 引用来源沿用调研报告 R10（Computation Structures 时序逻辑讲义）与 R05（Nand2Tetris
  Project 03）；正文按「内容发布前核对引用来源」逐条给出可追溯出处。
"""

from __future__ import annotations

import click
from sqlalchemy import select

from .models import User
from .models_content import Chapter, KnowledgeEdge, KnowledgePoint, Resource, ResourceVersion

R10 = "https://computationstructures.org/notes/sequential_logic/notes.html"
R05 = "https://www.nand2tetris.org/project03"

# (章节标题, 排序, [(知识点键, 标题, 正文 Markdown, 来源 URL, 排序), ...])
SEED_CHAPTERS: tuple[tuple[str, int, tuple[tuple[str, str, str, str | None, int], ...]], ...] = (
    (
        "第一单元 时序基础",
        1,
        (
            (
                "k01",
                "组合逻辑与时序逻辑的区别",
                "组合逻辑的输出只由**当前输入**决定；时序逻辑还依赖电路**已保存的状态**。\n"
                "\n"
                "判断一个电路是否属于时序逻辑，看两点：\n"
                "\n"
                "1. 输出表达式里是否出现状态变量 Q；\n"
                "2. 状态是否只在**有效时钟沿**更新。\n"
                "\n"
                "> 本课程的正式内容限定为时序逻辑。组合逻辑只作为必要前置出现，"
                "不单独展开运算器、存储器等主题。\n"
                "\n"
                "来源见调研 R10：该讲义区分当前输入、保存状态与下一状态。",
                R10,
                1,
            ),
            (
                "k02",
                "时钟信号与有效时钟沿",
                "时钟是周期性的方波，状态只在**有效沿**更新。本课程约定**上升沿有效**。\n"
                "\n"
                "- 上升沿：时钟由 0 变到 1 的瞬间；\n"
                "- 下降沿：时钟由 1 变到 0；本课程不触发状态更新；\n"
                "- 时钟高电平期间改变输入 D 不会立刻改变 Q，要等到下一个上升沿。\n"
                "\n"
                "课时注意：一次「切换时钟」等于**半个周期**，不等于一次状态更新。\n"
                "\n"
                "来源见调研 R10：锁存与时钟行为、术语校对。",
                R10,
                2,
            ),
        ),
    ),
    (
        "第二单元 触发器",
        2,
        (
            (
                "k03",
                "D 触发器与有效沿",
                "D 触发器在上升沿把输入 D 送入输出 Q：`Q(t+1) = D`。\n"
                "\n"
                "课堂案例的固定约定：\n"
                "\n"
                "- 初态 Q = 0；\n"
                "- 复位为**同步高有效**，只在上升沿生效；\n"
                "- 上升沿之前改变 D，Q 保持不变。\n"
                "\n"
                "例：Q(0)=0，时钟为 0 时令 D=1，此时 Q 仍为 0；出现上升沿后 Q 变为 1。\n"
                "\n"
                "来源见调研 R05：从 DFF 到寄存器与存储器。",
                R05,
                1,
            ),
            (
                "k04",
                "JK 触发器的四种组合",
                "JK 触发器在上升沿按下表更新，J、K 同时为 0 时保持、同时为 1 时翻转：\n"
                "\n"
                "| J | K | Q(t+1) |\n"
                "| --- | --- | --- |\n"
                "| 0 | 0 | 保持 Q(t) |\n"
                "| 0 | 1 | 清零 0 |\n"
                "| 1 | 0 | 置位 1 |\n"
                "| 1 | 1 | 翻转 |\n"
                "\n"
                "同步复位与 JK 同为上升沿生效；复位优先。\n"
                "\n"
                "来源见调研 R10：状态更新的术语与编码校对。",
                R10,
                2,
            ),
        ),
    ),
    (
        "第三单元 时序分析",
        3,
        (
            (
                "k05",
                "状态表与状态图",
                "状态表把**当前状态**与**输入**的每一种组合对应到**下一状态**；"
                "状态图用结点和带标注的箭头表达同一份信息。\n"
                "\n"
                "读表时先固定位序约定，再逐步查表，避免把 Q3Q2Q1Q0 与十进制值混淆。\n"
                "\n"
                "来源见调研 R10：当前输入、保存状态与下一状态的区分。",
                R10,
                1,
            ),
            (
                "k06",
                "次态推导与状态方程",
                "次态由状态方程从当前状态推导：先写出每个状态位的输入表达式，"
                "再在**有效沿**上代入当前值。\n"
                "\n"
                "推导步骤：\n"
                "\n"
                "1. 写出各触发器的激励表达式；\n"
                "2. 代入当前状态与输入，得到次态；\n"
                "3. 逐个时钟沿重复，得到状态序列。\n"
                "\n"
                "来源见调研 R10：下一状态的计算方式。",
                R10,
                2,
            ),
        ),
    ),
    (
        "第四单元 寄存器",
        4,
        (
            (
                "k07",
                "4 位移位寄存器与位序",
                "本课程的 4 位移位寄存器固定为 Q3Q2Q1Q0，其中 Q3 是最高位。\n"
                "\n"
                "- **串行输入从 Q3 进入**，数据向 Q0 方向移动；\n"
                "- 每来一个上升沿整体移动一位，Q0 原有数据被移出；\n"
                "- 初态为 0000。\n"
                "\n"
                "例：Q = 1010 时输入 1，上升沿后 Q = 1101。\n"
                "\n"
                "来源见调研 R05：移位与寄存器的测试向量思路。",
                R05,
                1,
            ),
            (
                "k08",
                "寄存器使能与保持",
                "带使能端 EN 的寄存器在 EN=0 时**保持**当前状态，即使时钟出现上升沿也不改变。\n"
                "\n"
                "课堂演示中 EN=0 与「时钟不动」是两件不同的事：前者说明保持由输入决定，"
                "后者只是没有触发沿。\n"
                "\n"
                "来源见调研 R05：寄存器组的控制信号。",
                R05,
                2,
            ),
        ),
    ),
    (
        "第五单元 计数器",
        5,
        (
            (
                "k09",
                "二进制计数器与模值",
                "n 位二进制计数器有 2ⁿ 个状态，默认的 4 位计数器为**模 16**，"
                "状态从 0000 计到 1111 后回到 0000。\n"
                "\n"
                "位序仍然约定为 Q3Q2Q1Q0，Q3 为最高位；十进制值等于二进制按位展开。\n"
                "\n"
                "来源见调研 R05：从触发器搭建计数结构。",
                R05,
                1,
            ),
            (
                "k10",
                "模 6 计数器与 5→0 回卷",
                "模 6 计数器只使用 0000—0101 六个状态，**复位到 0000**；"
                "当前状态为 0101（即 5）时，下一个有效沿回到 0000。\n"
                "\n"
                "课堂案例的固定约定：\n"
                "\n"
                "- 位序 Q3Q2Q1Q0；\n"
                "- 初态 0000，同步高有效复位；\n"
                "- 上升沿更新；Q=5 的下一有效沿为 0。\n"
                "\n"
                "来源见调研 R05：计数器测试向量与期望输出对照。",
                R05,
                2,
            ),
        ),
    ),
    (
        "第六单元 同步设计",
        6,
        (
            (
                "k11",
                "同步复位与异步复位",
                "**同步复位**只在有效时钟沿检查复位信号，复位与时钟同步；"
                "**异步复位**一旦有效立即清零，与时钟无关。\n"
                "\n"
                "本课程所有课堂案例统一使用同步高有效复位，因此讨论状态序列时"
                "只需在有效沿上判断。\n"
                "\n"
                "来源见调研 R10：时钟行为与复位术语校对。",
                R10,
                1,
            ),
            (
                "k12",
                "多触发器同步与初态约定",
                "多个触发器共享同一个时钟，各自按次态更新，因此同一拍内所有位**同时**变化。\n"
                "\n"
                "讨论任何状态序列前先固定三件事：**位序**、**初态**、**复位方式**；"
                "缺少任一项时状态序列无法唯一确定。\n"
                "\n"
                "来源见调研 R10：状态与时序的统一记法。",
                R10,
                2,
            ),
        ),
    ),
)

# (先修键, 后继键)；方向为先修 → 后继
SEED_EDGES: tuple[tuple[str, str], ...] = (
    ("k01", "k02"),
    ("k02", "k03"),
    ("k03", "k04"),
    ("k02", "k05"),
    ("k05", "k06"),
    ("k02", "k07"),
    ("k03", "k07"),
    ("k07", "k08"),
    ("k03", "k09"),
    ("k04", "k09"),
    ("k06", "k10"),
    ("k09", "k10"),
    ("k02", "k11"),
    ("k11", "k12"),
    ("k09", "k12"),
)

SEED_RESOURCE = {
    "title": "时序逻辑讲义（Computation Structures，调研 R10）",
    "category": "reference",
    "knowledge_key": "k01",
    "external_url": R10,
    "note": "外部讲义，仅作术语与结构对照；课堂核心内容不依赖外网。",
}


def find_cycle(edges: list[tuple[int, int]]) -> list[tuple[int, int]] | None:
    """Kahn 拓扑排序；有环时返回一条仍留在环上的边，无环返回 None。"""
    nodes = {node for edge in edges for node in edge}
    outgoing: dict[int, list[int]] = {node: [] for node in nodes}
    indegree: dict[int, int] = {node: 0 for node in nodes}
    for source, target in edges:
        outgoing[source].append(target)
        indegree[target] += 1

    ready = sorted(node for node, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        node = ready.pop(0)
        visited += 1
        for target in outgoing[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)

    if visited == len(nodes):
        return None
    # 环上任取一条边作为证据
    for source, target in edges:
        if indegree[source] > 0 and indegree[target] > 0:
            return (source, target)
    return edges[0]


def _seed_owner(session, owner_login: str | None) -> User:
    if owner_login:
        owner = session.scalar(select(User).where(User.login_name == owner_login))
        if owner is None or owner.role not in {"teacher", "admin"} or not owner.active:
            raise click.ClickException(f"账号 {owner_login} 不存在或不是有效的教师/管理员")
        return owner

    owner = session.scalar(
        select(User)
        .where(User.role == "teacher", User.active == 1)
        .order_by(User.id.asc())
        .limit(1)
    )
    if owner is None:
        raise click.ClickException(
            "没有可用的教师账号：请先创建教师，或用 --owner-login 指定归属账号"
        )
    return owner


def seed_course_content(session, owner: User, *, echo=click.echo) -> dict:
    """幂等写入课程种子，返回各表新增数量。"""
    created = {"chapters": 0, "knowledge_points": 0, "edges": 0, "resources": 0}
    points_by_key: dict[str, KnowledgePoint] = {}

    for chapter_title, chapter_order, points in SEED_CHAPTERS:
        chapter = session.scalar(
            select(Chapter).where(
                Chapter.owner_id == owner.id, Chapter.title == chapter_title
            )
        )
        if chapter is None:
            chapter = Chapter(
                title=chapter_title,
                sort_order=chapter_order,
                published=1,
                owner_id=owner.id,
            )
            session.add(chapter)
            session.flush()
            created["chapters"] += 1

        for key, title, body_md, source_url, order in points:
            point = session.scalar(
                select(KnowledgePoint).where(
                    KnowledgePoint.chapter_id == chapter.id, KnowledgePoint.title == title
                )
            )
            if point is None:
                point = KnowledgePoint(
                    chapter_id=chapter.id,
                    title=title,
                    body_md=body_md,
                    source_url=source_url,
                    sort_order=order,
                    published=1,
                    owner_id=owner.id,
                )
                session.add(point)
                session.flush()
                created["knowledge_points"] += 1
            points_by_key[key] = point

    # 先修关系：写入前检查无环，有环则整批回滚（SPEC-005 第 4 节第 5 条）
    pending: list[tuple[int, int]] = []
    for prerequisite_key, target_key in SEED_EDGES:
        pair = (points_by_key[prerequisite_key].id, points_by_key[target_key].id)
        if session.get(KnowledgeEdge, pair) is None:
            pending.append(pair)

    if pending:
        existing = [
            (edge.prerequisite_id, edge.target_id)
            for edge in session.scalars(select(KnowledgeEdge)).all()
        ]
        cycle = find_cycle(existing + pending)
        if cycle is not None:
            raise click.ClickException(
                f"先修关系存在环，已整批回滚：{cycle[0]} → {cycle[1]}"
            )
        for pair in pending:
            session.add(KnowledgeEdge(prerequisite_id=pair[0], target_id=pair[1]))
        created["edges"] = len(pending)

    resource = session.scalar(
        select(Resource).where(
            Resource.owner_id == owner.id, Resource.title == SEED_RESOURCE["title"]
        )
    )
    if resource is None:
        resource = Resource(
            title=SEED_RESOURCE["title"],
            category=SEED_RESOURCE["category"],
            knowledge_id=points_by_key[SEED_RESOURCE["knowledge_key"]].id,
            published=1,
            owner_id=owner.id,
        )
        session.add(resource)
        session.flush()
        session.add(
            ResourceVersion(
                resource_id=resource.id,
                version_no=1,
                kind="link",
                external_url=SEED_RESOURCE["external_url"],
                note=SEED_RESOURCE["note"],
            )
        )
        created["resources"] += 1

    echo(
        "课程种子：章节 +{chapters}，知识点 +{knowledge_points}，先修关系 +{edges}，"
        "资源 +{resources}（已存在的条目跳过）".format(**created)
    )
    return created


def register_content_cli(app) -> None:
    @app.cli.command("seed-content")
    @click.option("--owner-login", default=None, help="内容归属账号（教师/管理员登录名）")
    def seed_content(owner_login: str | None) -> None:
        """写入 SPEC-005 课程种子（六单元 12 知识点、先修关系、一份外链资料）。"""
        # 延迟导入，避免 CLI 模块在应用工厂导入期就拉起模型
        from .store import db_session

        session = db_session()
        owner = _seed_owner(session, owner_login)
        try:
            seed_course_content(session, owner)
        except click.ClickException:
            session.rollback()
            raise
        session.commit()
        click.echo(f"归属账号：{owner.login_name}（id={owner.id}）")
