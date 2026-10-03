"""Real CLI adapter. A zero exit status alone never means a correct circuit."""

import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
from .lab_engine import LabError

ENGINE_VERSION = "logisim-evolution-5.0.0"
JAR_SHA256 = "6b368e894742c04cc83aa9830f869bcab0190ede4df43ad6fecdb89b3a23a41c"


def run_bounded(command, cwd, timeout=15, limit=256 * 1024):
    """Drain both pipes concurrently, kill on deadline/output overflow."""
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as exc:
        raise LabError(
            "Java测评进程不能启动，请检查部署配置", "LAB_ENGINE_UNAVAILABLE"
        ) from exc
    chunks = [bytearray(), bytearray()]
    lock = threading.Lock()
    overflow = threading.Event()
    size = 0

    def reader(index, pipe):
        nonlocal size
        try:
            while data := pipe.read(1024):
                with lock:
                    size += len(data)
                    if size > limit:
                        overflow.set()
                    else:
                        chunks[index].extend(data)
                if overflow.is_set():
                    break
        finally:
            pipe.close()

    threads = [
        threading.Thread(target=reader, args=(i, p), daemon=True)
        for i, p in enumerate((process.stdout, process.stderr))
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    error = None
    try:
        while process.poll() is None:
            if overflow.is_set():
                error = ("测评输出超过限制", "GRADING_OUTPUT_LIMIT")
                break
            if time.monotonic() > deadline:
                error = ("测评超过15秒，请检查电路是否振荡", "GRADING_TIMEOUT")
                break
            time.sleep(0.02)
        if error:
            process.kill()
        process.wait(timeout=3)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        for thread in threads:
            thread.join(timeout=3)
    if overflow.is_set():
        error = ("测评输出超过限制", "GRADING_OUTPUT_LIMIT")
    if error:
        raise LabError(*error)
    return process.returncode, *(
        bytes(chunk).decode("utf-8", errors="replace").replace("\r", "\n")
        for chunk in chunks
    )


def runtime(config):
    java = Path(config.get("LAB_JAVA", ""))
    jar = Path(config.get("LAB_JAR", ""))
    if (
        not java.is_absolute()
        or not java.is_file()
        or not jar.is_absolute()
        or not jar.is_file()
    ):
        raise LabError("未配置Java21和固定Logisim JAR", "LAB_ENGINE_UNAVAILABLE")
    with jar.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != JAR_SHA256:
            raise LabError("Logisim JAR校验失败", "LAB_ENGINE_UNAVAILABLE")
    code, out, err = run_bounded([str(java), "-version"], str(java.parent), timeout=5)
    match = re.search(r'version "(\d+)', out + err)
    if code or not match or int(match[1]) < 21:
        raise LabError("Logisim测评需要Java21或以上", "LAB_ENGINE_UNAVAILABLE")
    return str(java), str(jar)


def vectors(task, suite):
    ports = task["ports"]
    header = (
        " ".join(
            p["label"] + (f"[{p['width']}]" if p["width"] > 1 else "") for p in ports
        )
        + " <set> <seq>"
    )
    rows = []
    lines = [header]
    for case in suite["cases"]:
        for seq, row in enumerate(case["steps"], 1):
            fields = [
                row["inputs"][p["label"]]
                if p["direction"] == "input"
                else row["expected"].get(p["label"], "<DC>")
                for p in ports
            ]
            lines.append(" ".join(fields) + f" {case['set_id']} {seq}")
            rows.append(row)
    if not rows or len(rows) > 256:
        raise LabError("测试集超出支持范围", "GRADING_OUTPUT_INVALID")
    return "\n".join(lines) + "\n", rows


def parse_result(code, stdout, stderr, rows):
    summaries = re.findall(r"Passed:\s*(\d+),\s*Failed:\s*(\d+)", stdout)
    indices = [int(n) for n in re.findall(r"^\s*(\d+)\s*$", stdout, re.M)]
    failures = [int(n) for n in re.findall(r"Error on test vector (\d+):", stderr)]
    if code or len(summaries) != 1 or list(range(1, len(rows) + 1)) != indices:
        raise LabError("测评引擎未返回完整测试结果", "GRADING_OUTPUT_INVALID")
    good, bad = map(int, summaries[0])
    if (
        good + bad != len(rows)
        or len(set(failures)) != bad
        or len(failures) != bad
        or any(n < 1 or n > len(rows) for n in failures)
    ):
        raise LabError("测评结果计数不一致", "GRADING_OUTPUT_INVALID")
    blocks = {}
    current = None
    for line in stdout.splitlines():
        if re.fullmatch(r"\s*\d+\s*", line):
            current = int(line.strip())
        elif "=" in line and "(expected " in line:
            match = re.fullmatch(
                r"\s*([A-Za-z0-9_]+) = ([01xXzZEe]+) \(expected ([01xXzZEe]+)\)(?:\s+.*)?",
                line,
            )
            if not match or current is None:
                raise LabError("无法解析首错输出", "GRADING_OUTPUT_INVALID")
            blocks.setdefault(current, {})[match[1]] = (
                match[2].upper().replace("E", "X")
            )
    total = passed = 0
    first = None
    for index, row in enumerate(rows, 1):
        if index in failures:
            if not row["scored"] or not blocks.get(index):
                raise LabError("初始化向量或错误详情不一致", "GRADING_OUTPUT_INVALID")
            if set(blocks[index]) - set(row["expected"]):
                raise LabError("错误输出端口不一致", "GRADING_OUTPUT_INVALID")
        if row["scored"]:
            total += 1
            passed += index not in failures
            if index in failures and first is None:
                actual = dict(row["expected"])
                actual.update(blocks[index])
                if any(
                    len(actual[name]) != len(value)
                    for name, value in row["expected"].items()
                ):
                    raise LabError("错误输出位宽不一致", "GRADING_OUTPUT_INVALID")
                first = dict(
                    checkpoint=total,
                    inputs=row["inputs"],
                    expected=row["expected"],
                    actual=actual,
                    reason="电路输出与任务要求不符",
                )
    if not total:
        raise LabError("测试集没有计分点", "GRADING_OUTPUT_INVALID")
    return dict(
        total_checkpoints=total,
        passed_checkpoints=passed,
        score=round(100 * passed / total, 2),
        passed=passed == total,
        first_failure=first,
    )


def grade_circ(task, suite, content, config, checked_runtime=None):
    java, jar = checked_runtime or runtime(config)
    text, rows = vectors(task, suite)
    with tempfile.TemporaryDirectory(prefix="logic-lab-") as directory:
        path = Path(directory)
        (path / "project.circ").write_bytes(content)
        (path / "vectors.txt").write_text(text, encoding="utf-8")
        command = [
            java,
            "-Xmx256m",
            f"-Djava.util.prefs.userRoot={path / 'prefs'}",
            "-jar",
            jar,
            "--no-splash",
            "--locale",
            "en",
            "--test-vector",
            "main",
            str(path / "vectors.txt"),
            str(path / "project.circ"),
        ]
        code, out, err = run_bounded(
            command, directory, float(config.get("LAB_PROCESS_TIMEOUT", 15))
        )
        return parse_result(code, out, err, rows)
