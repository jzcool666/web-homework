"""从干净 Git 提交与已验证的 Windows 运行时生成源码包和离线运行包。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import zipfile

REPO = Path(__file__).resolve().parents[1]


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args]).decode("utf-8").strip()


def copy_runtime(source, target, *, exclude=()):
    source = Path(source).resolve()
    for path in source.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"运行时包含目录链接，不能生成独立运行包：{path}")
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", *exclude))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--python-runtime", required=True, type=Path)
    parser.add_argument("--java-home", required=True, type=Path)
    parser.add_argument("--jar", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.is_relative_to(REPO):
        raise RuntimeError("发布输出必须在仓库外。")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("请先提交全部受跟踪文件变更，再生成发布包。")
    commit = git("rev-parse", "HEAD")
    out.mkdir(parents=True, exist_ok=True)
    name = "digital-logic-v" + args.version
    source = out / (name + "-source.zip")
    subprocess.run(["git", "-C", str(REPO), "archive", "--format=zip", "--prefix=" + name + "/",
                    "--output=" + str(source), commit], check=True)
    stage = out / "stage"
    stage.mkdir()  # 不覆盖已经存在的产物或测试数据。
    with zipfile.ZipFile(source) as archive:
        archive.extractall(stage)
    package = stage / name
    copy_runtime(REPO / "frontend/dist", package / "frontend/dist")
    runtime = package / "runtime"
    runtime.mkdir()
    copy_runtime(args.python_runtime, runtime / "python", exclude=("site-packages", "Scripts", "include", "libs", "test", "tests"))
    copy_runtime(sysconfig.get_path("purelib"), runtime / "python/Lib/site-packages")
    copy_runtime(args.java_home, runtime / "java", exclude=("jmods", "include"))
    (runtime / "logisim").mkdir()
    shutil.copy2(args.jar, runtime / "logisim" / args.jar.name)
    spec = importlib.util.spec_from_file_location("release_launcher", REPO / "scripts/start_local.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    if sha256(args.jar) != launcher.JAR_SHA256 or args.jar.name != launcher.JAR_NAME:
        raise RuntimeError("Logisim 发布文件或 SHA-256 不匹配。")
    portable = {"schema": 1, "version": args.version, "source_commit": commit,
                "frontend_fingerprint": launcher.frontend_fingerprint(),
                "frontend_files": {p.relative_to(package).as_posix(): sha256(p)
                                   for p in sorted((package / "frontend/dist").rglob("*")) if p.is_file()}}
    (package / "portable.json").write_text(json.dumps(portable, ensure_ascii=False, indent=2), encoding="utf-8")
    notices = """# 随包第三方组件

Python 与依赖的版权、许可证及版本信息保存在 runtime/python/LICENSE.txt 和 Lib/site-packages/*dist-info 中；NumPy、SciPy 等附带的第三方许可证随库保留。

Microsoft Build of OpenJDK 的许可证保存在 runtime/java/legal/，版本见 runtime/java/release，Java 源码归档见 lib/src.zip。完整对应上游源码和构建资料：https://github.com/microsoft/openjdk 。本包使用 Microsoft OpenJDK 21.0.7，下载与源码入口：https://learn.microsoft.com/java/openjdk/download 。

Logisim-evolution 5.0.0 使用 GPL-3.0；许可及对应源码：https://github.com/logisim-evolution/logisim-evolution/tree/v5.0.0 ，源码下载：https://github.com/logisim-evolution/logisim-evolution/archive/refs/tags/v5.0.0.zip 。未修改其 JAR。本项目源码随运行包提供。
"""
    (package / "THIRD_PARTY.md").write_text(notices, encoding="utf-8")
    (package / "先读我.txt").write_text(
        "数字逻辑课程学习系统 v" + args.version + "（Windows 10/11 64 位）\n\n"
        "完整解压到可写目录，双击 一键启动.cmd；首次启动不需要联网或安装 Python/Node/Java。\n"
        "窗口显示网址、演示账号和本机随机生成的口令；保留窗口。结束时双击 停止运行.cmd。\n"
        "运行数据保存在 .local-run。不要删除该目录，分享原始 ZIP 即可，不要把使用后的目录重新打包。\n"
        "完整操作见 docs/一键运行说明.md 和 docs/用户手册.md。仅监听本机；另一台电脑的兼容性须现场确认。\n"
        "组件版权、许可证与源码入口见 THIRD_PARTY.md。课程手续见 docs/发布与交付说明.md。\n", encoding="utf-8")
    portable_zip = out / (name + "-windows-x64.zip")
    count = 0
    with zipfile.ZipFile(portable_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                relative = path.relative_to(package)
                if any(part in {".local-run", ".git", "node_modules", "__pycache__"} for part in relative.parts):
                    raise RuntimeError(f"不允许发布运行数据或开发环境：{relative}")
                archive.write(path, path.relative_to(stage).as_posix())
                count += 1
    artifacts = [{"name": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)} for p in (source, portable_zip)]
    (out / "SHA256SUMS.txt").write_text("".join(a["sha256"] + "  " + a["name"] + "\n" for a in artifacts), encoding="utf-8")
    (out / "release-manifest.json").write_text(json.dumps(
        {"version": args.version, "source_commit": commit, "portable_files": count, "artifacts": artifacts},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"source_commit": commit, "artifacts": artifacts}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
