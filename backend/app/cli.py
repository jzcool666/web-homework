"""`flask db` 命令组。

README 约定的命令是 `python -m flask --app app:create_app db upgrade`（工作目录 backend）。
这里直接调用 Alembic 的 API，迁移脚本本身仍是标准 Alembic，没有额外封装层。
"""

from __future__ import annotations

import click
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from flask import Flask

from .config import BACKEND_DIR

ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
MIGRATIONS_DIR = BACKEND_DIR / "migrations"


def build_alembic_config(app: Flask) -> AlembicConfig:
    """把应用解析出的 DATABASE_URL 交给 Alembic，避免两处配置漂移。"""
    config = AlembicConfig(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", app.config["DATABASE_URL"])
    return config


def register_cli(app: Flask) -> None:
    @app.cli.group("db")
    def db_group() -> None:
        """数据库迁移（Alembic）。"""

    @db_group.command("upgrade")
    @click.argument("revision", default="head")
    def upgrade(revision: str) -> None:
        """升级到指定版本，默认 head。"""
        alembic_command.upgrade(build_alembic_config(app), revision)

    @db_group.command("downgrade")
    @click.argument("revision", default="-1")
    def downgrade(revision: str) -> None:
        """回退到指定版本，默认回退一步。"""
        alembic_command.downgrade(build_alembic_config(app), revision)

    @db_group.command("current")
    def current() -> None:
        """显示当前数据库版本。"""
        alembic_command.current(build_alembic_config(app), verbose=True)

    @app.cli.command("init-admin")
    @click.option("--login-name", required=True, help="管理员登录名")
    @click.option("--password", required=True, help="管理员口令（10—128 字符）")
    @click.option("--display-name", default="系统管理员", show_default=True)
    def init_admin(login_name: str, password: str, display_name: str) -> None:
        """创建初始管理员账号（SPEC-001）。

        公开注册只允许学生，因此首个管理员必须由本命令在服务端建立。
        需先执行 `flask db upgrade`，否则业务表不存在。
        """
        # 延迟导入，避免 CLI 模块在应用工厂导入期就拉起模型
        from sqlalchemy import select

        from .models import User
        from .security import hash_password
        from .store import db_session
        from .validation import LOGIN_NAME_RE

        name = login_name.strip()
        if not LOGIN_NAME_RE.match(name):
            raise click.ClickException("登录名需为 4—32 位字母、数字或下划线")
        if not 10 <= len(password) <= 128:
            raise click.ClickException("口令长度需为 10—128 个字符")
        label = display_name.strip() or "系统管理员"
        if len(label) > 50:
            raise click.ClickException("显示名不超过 50 个字符")

        session = db_session()
        if session.scalar(select(User.id).where(User.login_name == name)):
            raise click.ClickException(f"登录名 {name} 已存在，未创建")

        user = User(
            login_name=name,
            student_no=None,
            display_name=label,
            password_hash=hash_password(password),
            role="admin",
            active=1,
        )
        session.add(user)
        session.commit()
        click.echo(f"已创建管理员：id={user.id} login_name={user.login_name}")
