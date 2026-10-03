"""SPEC-007 问答语料种子：16 条已发布问答（PRD 第 5 节的素材口径）。

- 每条挂在 SPEC-005 种子建立的知识点上，按标题定位；找不到时给出可读提示。
- 可重复执行：按 (owner, question) 查找，已存在则跳过。
- 回答按本课程的时序逻辑口径书写（有效上升沿、位序、复位方式），并且**不写**任何
  会随时间漂移的测评答案；来源沿用调研报告的 R05/R10。
"""

from __future__ import annotations

import click
from sqlalchemy import select

from .models import User
from .models_content import KnowledgePoint
from .models_qa import QAEntry

R10 = "https://computationstructures.org/notes/sequential_logic/notes.html"
R05 = "https://www.nand2tetris.org/project03"

# (知识点标题, 问题, 回答 Markdown, 来源 URL)
SEED_QA: tuple[tuple[str, str, str, str | None], ...] = (
    (
        "组合逻辑与时序逻辑的区别",
        "组合逻辑和时序逻辑有什么区别？",
        "组合逻辑的输出只由**当前输入**决定；时序逻辑还依赖电路**已保存的状态**。\n"
        "\n"
        "判断方法：输出表达式里是否出现状态变量 Q，以及状态是否只在**有效时钟沿**更新。",
        R10,
    ),
    (
        "时钟信号与有效时钟沿",
        "为什么时钟在高电平期间改变 D 不会立刻改变 Q？",
        "因为状态只在**有效上升沿**更新。时钟为 1 期间改变 D 只是改了输入，"
        "Q 要等到下一个上升沿才接收新值。",
        R10,
    ),
    (
        "时钟信号与有效时钟沿",
        "上升沿和下降沿哪个才算有效时钟沿？",
        "本课程统一约定**上升沿有效**：时钟由 0 变到 1 的瞬间更新状态。"
        "下降沿（1→0）不触发状态更新。",
        R10,
    ),
    (
        "D 触发器与有效沿",
        "D 触发器在有效上升沿做什么？",
        "在上升沿把输入 D 送入输出：`Q(t+1) = D`。上升沿之前改变 D，Q 保持不变。",
        R05,
    ),
    (
        "D 触发器与有效沿",
        "D 触发器为什么要有初态约定？",
        "只有给定位序、初态与复位方式，状态序列才唯一确定。本课程 D 触发器案例"
        "取初态 Q=0、同步高有效复位。",
        R05,
    ),
    (
        "JK 触发器的四种组合",
        "JK 触发器 J=1、K=1 时输出怎么变化？",
        "同时为 1 时**翻转**：有效上升沿后 Q 取反。",
        R10,
    ),
    (
        "JK 触发器的四种组合",
        "JK 触发器 J=0、K=0 时输出是什么？",
        "同时为 0 时**保持**：有效上升沿后 Q 不变。另外 J=1,K=0 置位，J=0,K=1 清零。",
        R10,
    ),
    (
        "状态表与状态图",
        "状态表和状态图有什么区别？",
        "两者表达同一份信息：状态表把**当前状态与输入**的每种组合对应到**下一状态**；"
        "状态图用结点和带标注的箭头表示同样的对应关系。读表前先固定位序约定。",
        R10,
    ),
    (
        "次态推导与状态方程",
        "怎么从当前状态推出下一个状态？",
        "先写出每个状态位的激励表达式，再在**有效上升沿**上代入当前状态与输入，"
        "得到次态；逐个时钟沿重复就得到状态序列。",
        R10,
    ),
    (
        "4 位移位寄存器与位序",
        "移位寄存器的位序是怎么约定的？",
        "本课程固定为 Q3Q2Q1Q0，**Q3 是最高位**。每一位在有效上升沿整体移动一位。",
        R05,
    ),
    (
        "4 位移位寄存器与位序",
        "移位寄存器右移时串行输入从哪里进入？",
        "串行输入**从 Q3 进入**，数据向 Q0 方向移动，Q0 原有数据被移出。"
        "例：Q=1010 时输入 1，上升沿后 Q=1101。",
        R05,
    ),
    (
        "寄存器使能与保持",
        "寄存器使能端为 0 时会发生什么？",
        "EN=0 时寄存器**保持**当前状态：即使出现有效上升沿也不改变 Q。"
        "这与「时钟不动」是两件事——前者由输入决定保持。",
        R05,
    ),
    (
        "二进制计数器与模值",
        "4 位计数器一共能表示多少个状态？",
        "4 位二进制计数器有 2⁴ = 16 个状态，即**模 16**：从 0000 计到 1111 后回到 0000。",
        R05,
    ),
    (
        "模 6 计数器与 5→0 回卷",
        "模 6 计数器数到 5 之后是什么状态？",
        "模 6 只使用 0000—0101 六个状态，当前状态为 0101（5）时，"
        "**下一个有效上升沿回到 0000**。",
        R05,
    ),
    (
        "同步复位与异步复位",
        "同步复位和异步复位有什么区别？",
        "**同步复位**只在有效时钟沿检查复位信号，复位与时钟同步；"
        "**异步复位**一旦有效立即清零，与时钟无关。本课程统一使用同步高有效复位。",
        R10,
    ),
    (
        "多触发器同步与初态约定",
        "多个触发器共用一个时钟时状态是怎么变的？",
        "它们共享同一个时钟、各自按次态更新，因此**同一拍内所有位同时变化**。"
        "讨论状态序列前必须先固定位序、初态与复位方式。",
        R10,
    ),
)


def _seed_owner(session, owner_login: str | None) -> User:
    if owner_login:
        owner = session.scalar(select(User).where(User.login_name == owner_login))
        if owner is None or owner.role not in {"teacher", "admin"} or not owner.active:
            raise click.ClickException(f"账号 {owner_login} 不存在或不是有效的教师/管理员")
        return owner
    owner = session.scalar(
        select(User).where(User.role == "teacher", User.active == 1).order_by(User.id.asc()).limit(1)
    )
    if owner is None:
        raise click.ClickException(
            "没有可用的教师账号：请先创建教师，或用 --owner-login 指定归属账号"
        )
    return owner


def _point_by_title(session, title: str) -> KnowledgePoint | None:
    return session.scalar(
        select(KnowledgePoint)
        .where(KnowledgePoint.title == title)
        .order_by(KnowledgePoint.id.asc())
        .limit(1)
    )


def seed_qa_entries(session, owner: User, *, echo=click.echo) -> dict:
    """幂等写入 16 条问答语料，返回新增数量。"""
    created = 0
    missing: list[str] = []
    for knowledge_title, question, answer_md, source_url in SEED_QA:
        existing = session.scalar(
            select(QAEntry).where(QAEntry.owner_id == owner.id, QAEntry.question == question)
        )
        if existing is not None:
            continue
        point = _point_by_title(session, knowledge_title)
        if point is None:
            missing.append(knowledge_title)
            continue
        session.add(
            QAEntry(
                knowledge_id=point.id,
                question=question,
                answer_md=answer_md,
                source_url=source_url,
                published=1,
                owner_id=owner.id,
            )
        )
        session.flush()
        created += 1

    if missing:
        raise click.ClickException(
            "缺少这些知识点，请先执行 seed-content："
            + "、".join(sorted(set(missing)))
        )
    echo(f"问答语料：新增 {created} 条（共 {len(SEED_QA)} 条，已存在的跳过）")
    return {"created": created, "total": len(SEED_QA)}


def register_qa_cli(app) -> None:
    @app.cli.command("seed-qa")
    @click.option("--owner-login", default=None, help="语料归属账号（教师/管理员登录名）")
    def seed_qa_command(owner_login: str | None) -> None:
        """写入 SPEC-007 问答语料（16 条，需先执行 seed-content）。"""
        from .store import db_session

        session = db_session()
        owner = _seed_owner(session, owner_login)
        try:
            seed_qa_entries(session, owner)
        except click.ClickException:
            session.rollback()
            raise
        session.commit()
        click.echo(f"归属账号：{owner.login_name}（id={owner.id}）")
