"""SPEC-012 预置实验：D、JK、模 6 计数器、4 位移位寄存器。

- 只写实验定义（配置 + 输入序列 + 步骤说明），**不写期望输出**：APIC 第 2 节
  明确 Experiment「无期望输出」，期望状态由 SPEC-013 用同一套仿真规则计算，
  避免期望值与实现两处定义漂移。
- 输入序列为每个模型提供不少于 4 个有效上升沿，供 SPEC-013 取检查点；
  本 Spec 不判定学生预测。
- 可重复执行：按 (owner, 标题) 查找，已存在则跳过。
- 需要先有课程知识点（knowledge_id 非空）：先执行 `seed-content`。
"""

from __future__ import annotations

import click
from sqlalchemy import select

from .models import User
from .models_content import KnowledgePoint
from .models_experiment import Experiment, dump_json


def _cycles(count: int) -> list[dict]:
    """count 个完整时钟周期：每个周期恰好一次有效上升沿。

    每个元素都是新对象，避免列表乘法带来的共享引用。
    """
    return [
        {"op": op} for _ in range(count) for op in ("toggle_clock", "toggle_clock")
    ]


def _set(**inputs) -> dict:
    return {"op": "set", "inputs": inputs}


SEED_EXPERIMENTS: tuple[dict, ...] = (
    {
        "key": "d",
        "knowledge_title": "D 触发器与有效沿",
        "title": "D 触发器：有效上升沿把 D 送入 Q",
        "simulator_type": "d",
        "config": {"initial_q": 0},
        "steps_md": (
            "初态 Q=0，时钟初始为 0，复位为同步高有效。\n"
            "\n"
            "1. 时钟为 0 时把 D 置 1，观察 Q 是否立刻变化；\n"
            "2. 切换时钟，观察有效上升沿之后 Q 的变化；\n"
            "3. 把 D 改回 0 并再走一个周期。\n"
            "\n"
            "观察要点：只有 0→1 的有效沿更新 Q；1→0 与单独改输入都不改变 Q。"
        ),
        "input_sequence": [
            _set(d=1),
            *_cycles(2),
            _set(d=0),
            *_cycles(2),
        ],
    },
    {
        "key": "jk",
        "knowledge_title": "JK 触发器的四种组合",
        "title": "JK 触发器：保持 / 清零 / 置位 / 翻转",
        "simulator_type": "jk",
        "config": {"initial_q": 0},
        "steps_md": (
            "初态 Q=0，时钟初始为 0，复位为同步高有效。\n"
            "\n"
            "依次给出四组输入并各走一个周期：J=1,K=1 翻转；J=1,K=0 置 1；"
            "J=0,K=1 清零；J=0,K=0 保持。\n"
            "\n"
            "观察要点：四种组合只在有效上升沿生效；同步复位也只在有效沿优先清零。"
        ),
        "input_sequence": [
            _set(j=1, k=1),
            *_cycles(2),
            _set(j=1, k=0),
            *_cycles(2),
            _set(j=0, k=1),
            *_cycles(2),
            _set(j=0, k=0),
            *_cycles(2),
        ],
    },
    {
        "key": "counter",
        "knowledge_title": "模 6 计数器与 5→0 回卷",
        "title": "模 6 计数器：0—5 循环",
        "simulator_type": "counter",
        "config": {"initial_q": 0, "modulus": 6},
        "steps_md": (
            "初态 Q=0000（模 6，取值 0—5），位序 Q3Q2Q1Q0，时钟初始为 0，"
            "复位为同步高有效。\n"
            "\n"
            "1. 保持 enable=1，连续切换时钟，逐拍观察 Q 的十进制与二进制；\n"
            "2. 观察 Q=0101（5）的下一个有效沿；\n"
            "3. 再把 enable 置 0 走一拍，确认状态保持。\n"
            "\n"
            "观察要点：只有有效上升沿计数；Q≥M 的无效状态在下个有效沿回到 0。"
        ),
        "input_sequence": [
            *_cycles(7),
            _set(enable=0),
            *_cycles(1),
        ],
    },
    {
        "key": "shift",
        "knowledge_title": "4 位移位寄存器与位序",
        "title": "4 位移位寄存器：串行输入右移",
        "simulator_type": "shift",
        "config": {"initial_q": 10},  # 1010
        "steps_md": (
            "初态 Q=1010，位序 Q3Q2Q1Q0（Q3 为最高位），时钟初始为 0，"
            "复位为同步高有效。\n"
            "\n"
            "1. 串行输入取自 Q3，数据向 Q0 方向移动；\n"
            "2. 令 serial_in=1 走两个周期，观察 Q 的变化；\n"
            "3. 令 serial_in=0 再走两个周期；\n"
            "4. 令 enable=0 走一拍，确认状态保持。\n"
            "\n"
            "观察要点：每一位在有效上升沿整体右移，移出的低位从 Q0 丢失。"
        ),
        "input_sequence": [
            _set(serial_in=1),
            *_cycles(2),
            _set(serial_in=0),
            *_cycles(2),
            _set(enable=0),
            *_cycles(1),
        ],
    },
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


def _resolve_knowledge(session, title: str) -> KnowledgePoint:
    point = session.scalar(
        select(KnowledgePoint)
        .where(KnowledgePoint.title == title)
        .order_by(KnowledgePoint.id.asc())
        .limit(1)
    )
    if point is not None:
        return point
    # 课程种子未按预期标题存在时退到任一知识点，保证预置实验仍可建立
    point = session.scalar(
        select(KnowledgePoint).where(KnowledgePoint.published == 1).order_by(KnowledgePoint.id.asc()).limit(1)
    )
    if point is None:
        raise click.ClickException(
            "库里还没有知识点：请先执行 `flask --app app:create_app seed-content` 建立课程内容"
        )
    return point


def seed_experiments(session, owner: User, *, echo=click.echo) -> dict:
    """幂等写入四个预置实验，返回新增数量。"""
    created = 0
    for spec in SEED_EXPERIMENTS:
        existing = session.scalar(
            select(Experiment).where(
                Experiment.owner_id == owner.id, Experiment.title == spec["title"]
            )
        )
        if existing is not None:
            continue
        session.add(
            Experiment(
                title=spec["title"],
                knowledge_id=_resolve_knowledge(session, spec["knowledge_title"]).id,
                simulator_type=spec["simulator_type"],
                config_json=dump_json(spec["config"]),
                steps_md=spec["steps_md"],
                input_sequence_json=dump_json(spec["input_sequence"]),
                published=1,
                owner_id=owner.id,
            )
        )
        session.flush()
        created += 1

    echo(f"预置实验：新增 {created} 个（共 {len(SEED_EXPERIMENTS)} 个，已存在的跳过）")
    return {"created": created, "total": len(SEED_EXPERIMENTS)}


def register_experiment_cli(app) -> None:
    @app.cli.command("seed-experiments")
    @click.option("--owner-login", default=None, help="实验归属账号（教师/管理员登录名）")
    def seed_experiments_command(owner_login: str | None) -> None:
        """写入 SPEC-012 预置实验（D、JK、模 6 计数器、4 位移位寄存器）。"""
        from .store import db_session

        session = db_session()
        owner = _seed_owner(session, owner_login)
        try:
            seed_experiments(session, owner)
        except click.ClickException:
            session.rollback()
            raise
        session.commit()
        click.echo(f"归属账号：{owner.login_name}（id={owner.id}）")
