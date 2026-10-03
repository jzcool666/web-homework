import json
import click
from sqlalchemy import select
from .lab_catalog import CODES, profile, CATALOG_VERSION
from .lab_suites import suite, SUITE_VERSION
from .models_lab import LabTask
from .models_content import KnowledgePoint


def seed_labs(session):
    points = session.scalars(
        select(KnowledgePoint)
        .where(KnowledgePoint.published == 1)
        .order_by(KnowledgePoint.id)
    ).all()
    if not points:
        raise click.ClickException("请先建立已发布知识点，再运行seed-labs")
    keywords = {
        "LAB-D": "D触发器",
        "LAB-C6": "计数器",
        "LAB-S4": "寄存器",
        "LAB-FSM": "状态",
    }
    created = 0
    for code in CODES:
        if session.scalar(select(LabTask).where(LabTask.code == code)):
            continue
        point = next((p for p in points if keywords[code] in p.title), points[0])
        p = profile(code)
        session.add(
            LabTask(
                code=code,
                title=p["title"],
                knowledge_id=point.id,
                published=1,
                catalog_version=CATALOG_VERSION,
                suite_version=SUITE_VERSION,
                engine_contract_version="ttl-engine-1",
                public_profile_json=json.dumps(p, ensure_ascii=False),
                private_suite_json=json.dumps(suite(code)),
                template_key=code + ".circ",
            )
        )
        created += 1
    session.flush()
    return created


def register_lab_cli(app):
    @app.cli.command("seed-labs")
    def command():
        from .store import db_session

        s = db_session()
        count = seed_labs(s)
        s.commit()
        click.echo(f"接线/电路任务新增{count}个，已有任务保持原版本")
