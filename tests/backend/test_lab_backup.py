import importlib.util
from pathlib import Path
from app.lab_worker import worker_lock


def test_backup_with_live_worker_lock_preserves_artifacts_only(tmp_path):
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "backup.py"
    spec = importlib.util.spec_from_file_location("backup_lab_test", module_path)
    backup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backup)
    uploads = tmp_path / "uploads"
    artifacts = uploads / "lab-circuits"
    artifacts.mkdir(parents=True)
    (artifacts / "sample.circ").write_bytes(b"original circuit")
    (uploads / "ordinary.pdf").write_bytes(b"other module resource")
    with worker_lock({"UPLOAD_DIR": str(uploads)}):
        backup.copy_uploads(uploads, tmp_path / "backup")
    assert not (tmp_path / "backup" / "lab-runtime").exists()
    assert (
        tmp_path / "backup" / "lab-circuits" / "sample.circ"
    ).read_bytes() == b"original circuit"
    assert (
        tmp_path / "backup" / "ordinary.pdf"
    ).read_bytes() == b"other module resource"
