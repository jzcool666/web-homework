#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OPS-02 恢复脚本（CHG-RB 第 4、6 节）。

从 `scripts/backup.py` 生成的备份目录恢复数据库与上传文件，并在恢复前核对
哈希清单、恢复后核对迁移号与关键数据量。

用法::

    python scripts/restore.py --backup backups/backup-20261003-000000-v1.0 --backend backend [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

KEY_TABLES = (
    "users", "classes", "enrollments", "chapters", "knowledge_points",
    "questions", "assessments", "assessment_items", "assessment_roster",
    "submissions", "submission_answers", "attendance_tasks", "attendance_records",
    "experiments", "experiment_attempts", "qa_entries", "recognition_tasks",
    "warning_snapshots", "learning_progress",
    "lab_tasks", "lab_sessions", "lab_attempts",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_counts(db: Path) -> dict:
    connection = sqlite3.connect(db)
    try:
        existing = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {}
        for name in KEY_TABLES:
            if name in existing:
                counts[name] = connection.execute(
                    f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        return counts
    finally:
        connection.close()


def revision_of(db: Path) -> str | None:
    connection = sqlite3.connect(db)
    try:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", required=True, help="备份目录")
    parser.add_argument("--backend", default="backend")
    parser.add_argument("--dry-run", action="store_true", help="只校验，不写入")
    parser.add_argument("--report", help="把恢复核对结果写入 JSON")
    args = parser.parse_args()

    backup = Path(args.backup).resolve()
    backend = Path(args.backend).resolve()
    repo_root = backend.parent
    meta_path = backup / "meta.json"
    if not meta_path.exists():
        raise SystemExit(f"备份目录缺少 meta.json：{backup}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # 1) 校验数据库副本与上传文件哈希
    backup_db = backup / "app.sqlite"
    if not backup_db.exists():
        raise SystemExit("备份缺少 app.sqlite")
    problems = []
    backup_uploads = backup / "uploads"
    for entry in meta.get("uploads", []):
        path = backup_uploads / entry["path"]
        if not path.exists():
            problems.append(f"缺失 {entry['path']}")
        elif sha256_file(path) != entry["sha256"]:
            problems.append(f"哈希不符 {entry['path']}")
    if problems:
        raise SystemExit("备份校验失败：\n  " + "\n  ".join(problems))
    print(f"[校验] 备份可读，上传文件 {len(meta.get('uploads', []))} 个哈希一致")

    backup_revision = revision_of(backup_db)
    counts = table_counts(backup_db)

    sys.path.insert(0, str(backend))
    from app import create_app  # noqa: E402

    app = create_app()
    database_url = app.config["DATABASE_URL"]
    if not database_url.startswith("sqlite:///"):
        raise SystemExit("本脚本仅支持 SQLite 部署")
    target_db = Path(database_url[len("sqlite:///"):])
    upload_dir = Path(app.config["UPLOAD_DIR"])
    if not upload_dir.is_absolute():
        upload_dir = backend / upload_dir

    report = {
        "restored_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "backup_dir": str(backup),
        "backup_created_at": meta.get("created_at"),
        "git_commit": meta.get("git_commit"),
        "migration_head": meta.get("migration_head"),
        "backup_revision": backup_revision,
        "target_db": str(target_db),
        "target_uploads": str(upload_dir),
        "table_counts": counts,
        "dry_run": args.dry_run,
    }

    if args.dry_run:
        print("[dry-run] 未写入任何文件")
        if args.report:
            Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
        return 0

    # 2) 恢复数据库（先备份当前，便于回退）
    if target_db.exists():
        shutil.copy2(target_db, target_db.with_suffix(target_db.suffix + ".pre-restore"))
    target_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_db, target_db)

    # 3) 恢复上传目录
    if backup_uploads.exists():
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
        shutil.copytree(backup_uploads, upload_dir)

    restored_revision = revision_of(target_db)
    restored_counts = table_counts(target_db)
    restored_uploads = sum(1 for p in upload_dir.rglob("*") if p.is_file()) \
        if upload_dir.exists() else 0

    report["restored_revision"] = restored_revision
    report["restored_table_counts"] = restored_counts
    report["restored_uploads_count"] = restored_uploads
    report["revision_matches"] = restored_revision == backup_revision
    report["counts_match"] = restored_counts == counts
    report["uploads_match"] = restored_uploads == len(meta.get("uploads", []))

    print(f"[恢复] 迁移号 {restored_revision}（备份 {backup_revision}）"
          f" 一致={report['revision_matches']}")
    print(f"[恢复] 关键表行数一致={report['counts_match']}")
    print(f"[恢复] 上传文件 {restored_uploads} 个，清单一致={report['uploads_match']}")
    for name, value in restored_counts.items():
        print(f"    {name}={value}")
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    ok = (report["revision_matches"] and report["counts_match"]
          and report["uploads_match"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
