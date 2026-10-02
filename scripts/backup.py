#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OPS-02 备份脚本（CHG-RB 第 3 节）。

备份集合：应用提交号、依赖锁文件摘要、前端构建版本、数据库迁移号、数据库
一致性备份、上传文件目录及哈希清单、脱敏配置说明。真实密钥不进入备份包。

SQLite 使用官方 backup API 生成一致性副本，**不是**在写入期间直接复制主文件。

用法::

    python scripts/backup.py --backend backend [--out backups] [--label v1.0]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_consistent_copy(source_url_path: Path, dest: Path) -> None:
    """用 SQLite backup API 做一致性副本（写入期间也安全）。"""
    source = sqlite3.connect(f"file:{source_url_path.as_posix()}?mode=ro", uri=True)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
    finally:
        source.close()


def git_commit(repo_root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def index_uploads(upload_dir: Path) -> list[dict]:
    entries = []
    if not upload_dir.exists():
        return entries
    for path in sorted(upload_dir.rglob("*")):
        if path.is_file():
            entries.append({
                "path": path.relative_to(upload_dir).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="backend", help="backend 目录")
    parser.add_argument("--out", default="backups", help="备份根目录")
    parser.add_argument("--label", default="", help="版本标签")
    parser.add_argument("--skip-uploads", action="store_true")
    args = parser.parse_args()

    backend = Path(args.backend).resolve()
    repo_root = backend.parent
    sys.path.insert(0, str(backend))

    from app import create_app, __version__          # noqa: E402
    from app.cli import build_alembic_config         # noqa: E402
    from alembic.config import Config as AlembicConf  # noqa: E402
    from alembic.script import ScriptDirectory       # noqa: E402

    app = create_app()
    database_url = app.config["DATABASE_URL"]
    if not database_url.startswith("sqlite:///"):
        raise SystemExit("本脚本仅支持 SQLite 部署（README 约定）")
    db_path = Path(database_url[len("sqlite:///"):])
    upload_dir = Path(app.config["UPLOAD_DIR"])
    if not upload_dir.is_absolute():
        upload_dir = backend / upload_dir

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"backup-{stamp}-{args.label or __version__}".rstrip("-")
    target = (Path(args.out) if Path(args.out).is_absolute() else repo_root / args.out) / name
    if target.exists():
        raise SystemExit(f"备份目录已存在：{target}")

    # 空间预检
    need = db_path.stat().st_size if db_path.exists() else 0
    if upload_dir.exists():
        need += sum(p.stat().st_size for p in upload_dir.rglob("*") if p.is_file())
    free = shutil.disk_usage(target.parent if target.parent.exists() else repo_root).free
    if free < need * 2 + (16 << 20):
        raise SystemExit(f"剩余空间不足：需要约 {need} 字节，可用 {free} 字节")

    target.mkdir(parents=True)

    # 1) 数据库一致性副本
    sqlite_consistent_copy(db_path, target / "app.sqlite")

    # 2) 上传文件 + 哈希清单
    copied_uploads = target / "uploads"
    if not args.skip_uploads and upload_dir.exists():
        shutil.copytree(upload_dir, copied_uploads)
    manifest = index_uploads(copied_uploads)

    # 3) 版本与迁移号
    script = ScriptDirectory.from_config(build_alembic_config(app))
    revision = script.get_current_head()
    connection = sqlite3.connect(target / "app.sqlite")
    try:
        row = connection.execute(
            "SELECT version_num FROM alembic_version").fetchone()
        db_revision = row[0] if row else None
    except sqlite3.Error:
        db_revision = None
    finally:
        connection.close()

    files = {}
    for relative in ("backend/requirements.txt", "frontend/package-lock.json"):
        path = repo_root / relative
        if path.exists():
            files[relative] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    dist = repo_root / "frontend" / "dist"
    if dist.is_dir():
        files["frontend/dist"] = {
            "files": sorted(p.relative_to(dist).as_posix() for p in dist.rglob("*")
                            if p.is_file()),
        }

    meta = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "app_version": __version__,
        "app_env": app.config["APP_ENV"],
        "git_commit": git_commit(repo_root),
        "migration_head": revision,
        "database_revision": db_revision,
        "database_bytes": (target / "app.sqlite").stat().st_size,
        "uploads": manifest,
        "uploads_count": len(manifest),
        "lock_files": files,
        "note": "SECRET_KEY 等真实密钥不进入备份包，恢复时由部署环境单独提供。",
    }
    (target / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    print(f"备份完成：{target}")
    print(f"  提交号={meta['git_commit']} 迁移号={db_revision} "
          f"上传文件={len(manifest)} 数据库={meta['database_bytes']} 字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
