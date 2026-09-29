"""SPEC-005 / ADR-008 资源文件落盘规则。

- 只接受 PDF、PPTX、PNG、JPEG，单文件 ≤ 20 MiB。
- 磁盘名一律由服务端随机生成（storage_key），用户提供的文件名只用于显示。
- 扩展名白名单之外的内容一律拒绝；扩展名与文件头同时校验，避免改后缀绕过。
- 下载只按 storage_key 定位，并在解析后复核仍在 UPLOAD_DIR 之内。
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from pathlib import Path

from .config import BACKEND_DIR

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MiB

RESOURCE_SUBDIR = "resources"

# 扩展名 → (规范 MIME, 文件头判定函数)
_SIGNATURES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".pptx": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        (b"PK\x03\x04",),
    ),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
}

ALLOWED_EXTENSIONS = tuple(sorted(_SIGNATURES))
FILE_TYPE_RULE = "仅支持 PDF、PPTX、PNG、JPEG"
FILE_SIZE_RULE = "单文件不超过 20 MiB"


@dataclass(frozen=True)
class StoredFile:
    storage_key: str
    original_name: str
    mime: str
    size_bytes: int
    sha256: str


def upload_root(upload_dir: str) -> Path:
    """UPLOAD_DIR 为相对路径时按 backend/ 解析，避免工作目录变化写到别处。"""
    path = Path(upload_dir)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path


def file_extension(filename: str) -> str:
    """取小写扩展名；只按最后一个点切分，不解释路径。"""
    return Path(filename or "").suffix.lower()


def _matches_signature(head: bytes, extension: str) -> bool:
    expected = _SIGNATURES.get(extension)
    if expected is None:
        return False
    for prefix in expected[1]:
        # PDF 允许文件头前有少量填充字节
        index = head.find(prefix)
        if index == 0 or (extension == ".pdf" and 0 <= index <= 1024):
            return True
    return False


def validate_upload(filename: str, payload: bytes) -> tuple[str, str]:
    """校验扩展名、大小与文件头，返回 (扩展名, 规范 MIME)。失败抛 ValueError。"""
    extension = file_extension(filename)
    if extension not in _SIGNATURES:
        raise ValueError("extension")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError("size")
    if not payload:
        raise ValueError("empty")
    if not _matches_signature(payload[:1024], extension):
        raise ValueError("content")
    return extension, _SIGNATURES[extension][0]


def store_file(upload_dir: str, filename: str, payload: bytes) -> StoredFile:
    """把通过校验的内容写入随机命名的文件，返回可入库的元数据。"""
    extension, mime = validate_upload(filename, payload)
    root = upload_root(upload_dir) / RESOURCE_SUBDIR
    root.mkdir(parents=True, exist_ok=True)

    # 随机名 + 白名单扩展名；原始文件名不参与磁盘路径
    storage_key = f"{RESOURCE_SUBDIR}/{secrets.token_hex(16)}{extension}"
    target = root / Path(storage_key).name
    target.write_bytes(payload)

    return StoredFile(
        storage_key=storage_key,
        original_name=display_name(filename),
        mime=mime,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def resolve_storage_path(upload_dir: str, storage_key: str) -> Path:
    """按 storage_key 解析磁盘路径，并确认没有越出上传根目录。"""
    root = upload_root(upload_dir).resolve()
    candidate = (root / storage_key).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise FileNotFoundError(storage_key)
    return candidate


def display_name(filename: str) -> str:
    """只取最后一段并去掉控制字符，供界面显示与下载响应使用。"""
    raw = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(ch for ch in raw if ch.isprintable()).strip()
    return cleaned[:255] or "download"
