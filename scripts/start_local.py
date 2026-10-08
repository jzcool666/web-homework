"""Windows 本机演示启动器。仅使用标准库准备环境，所有数据落在 .local-run。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from contextlib import contextmanager

REPO = Path(__file__).resolve().parent.parent
JAR_NAME = "logisim-evolution-5.0.0-all.jar"
JAR_URL = f"https://github.com/logisim-evolution/logisim-evolution/releases/download/v5.0.0/{JAR_NAME}"
JAR_SHA256 = "6b368e894742c04cc83aa9830f869bcab0190ede4df43ad6fecdb89b3a23a41c"
CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


class LaunchError(Exception):
    pass


class StopRequested(Exception):
    pass


def read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + secrets.token_hex(4) + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


@contextmanager
def launch_lock(root):
    """锁随进程退出释放；不依赖可能过期或被复用的 PID 文件。"""
    handle = (root / "launcher.lock").open("a+b")
    acquired = False
    try:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            pass
        yield acquired
    finally:
        handle.close()


def settings(root):
    path = root / "settings.json"
    if path.exists():
        value = read_json(path)
        if not isinstance(value.get("secret_key"), str) or not value["secret_key"] or not value.get("demo_password"):
            raise LaunchError(f"配置文件无法读取或缺少密钥/演示口令，请检查 {path}；数据库不会被重置。")
    else:
        value = dict(port=5336, secret_key=secrets.token_urlsafe(32),
                     demo_password="Demo-" + secrets.token_urlsafe(9), java_path="", jar_path="")
        write_json(path, value)
    port = value.get("port")
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise LaunchError("settings.json 的 port 必须为 1024—65535 的整数。")
    if not isinstance(value["demo_password"], str) or not 10 <= len(value["demo_password"]) <= 128:
        raise LaunchError("settings.json 的 demo_password 必须为 10—128 字符。")
    return value


def child_environment(root, config, java="", jar=""):
    """不继承 backend/.env 和其他终端的数据库地址，Web/worker 使用相同路径。"""
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "FLASK_APP", "SQL_ECHO", "RECOGNITION_TIMEOUT_SECONDS"):
        env.pop(key, None)
    env.update(APP_ENV="production", DATABASE_URL="sqlite:///" + (root / "demo.sqlite").as_posix(),
               UPLOAD_DIR=str(root / "uploads"), SECRET_KEY=config["secret_key"],
               DEMO_PASSWORD=config["demo_password"], COOKIE_SECURE="0", FLASK_SKIP_DOTENV="1",
               PYTHONUTF8="1", PYTHONUNBUFFERED="1", LAB_JAVA=str(java), LAB_JAR=str(jar))
    return env


def check_command(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=15, creationflags=CREATE_FLAGS)
        return result.returncode, result.stdout + result.stderr
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def find_node():
    node, npm = shutil.which("node"), shutil.which("npm.cmd" if os.name == "nt" else "npm")
    code, output = check_command([node, "--version"]) if node else (1, "")
    match = re.search(r"v(\d+)\.(\d+)\.(\d+)", output)
    version = tuple(map(int, match.groups())) if match else (0, 0, 0)
    if code or not npm or not ((20, 19, 0) <= version < (21, 0, 0) or version >= (22, 12, 0)):
        raise LaunchError("请先安装 Node.js 24 LTS（含 npm），重新打开启动器。下载：https://nodejs.org/en/download")
    return npm


def find_java(config):
    explicit = config.get("java_path") or os.environ.get("LAB_JAVA")
    if explicit:
        candidates = [Path(explicit)]
    else:
        candidates = [REPO / "runtime/java/bin/java.exe"]
        if os.environ.get("JAVA_HOME"):
            candidates.append(Path(os.environ["JAVA_HOME"]) / "bin/java.exe")
        if found := shutil.which("java"):
            candidates.append(Path(found))
        folders = [Path.home() / ".jdks"]
        for name in ("ProgramFiles", "ProgramW6432"):
            if os.environ.get(name):
                folders.extend(Path(os.environ[name]) / p for p in ("Eclipse Adoptium", "Microsoft", "Java"))
        for folder in folders:
            if folder.is_dir():
                candidates.extend(sorted(folder.glob("*/bin/java.exe"), reverse=True))
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        code, output = check_command([str(path), "-version"])
        match = re.search(r'version "(\d+)', output)
        if not code and match and int(match[1]) >= 21:
            return path.resolve()
    raise LaunchError("未找到 Java 21 或以上，Logisim 文件测评暂未启用。安装 Java 21 后重启："
                      "https://adoptium.net/temurin/releases/?version=21&os=windows&arch=x64")


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def ensure_jar(root, config):
    explicit = config.get("jar_path") or os.environ.get("LAB_JAR")
    bundled = REPO / "runtime/logisim" / JAR_NAME
    path = Path(explicit).resolve() if explicit else (bundled if bundled.is_file() else root / "tools" / JAR_NAME)
    if path.is_file():
        if sha256(path) != JAR_SHA256:
            raise LaunchError(f"Logisim 文件 SHA-256 不匹配，请重新下载官方 5.0.0 文件：{path}")
        return path
    if explicit:
        raise LaunchError(f"指定的 Logisim 文件不存在：{path}")
    print("首次下载官方 Logisim 5.0.0（约 52 MiB），下载后校验 SHA-256…", flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jar.part")
    request = urllib.request.Request(JAR_URL, headers={"User-Agent": "digital-logic-local-launcher/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response, temporary.open("wb") as out:
            total = 0
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > 64 * 1024 * 1024:
                    raise LaunchError("Logisim 下载文件超过预期大小，已停止。")
                out.write(block)
        if sha256(temporary) != JAR_SHA256:
            raise LaunchError("下载的 Logisim 文件校验失败，未启用该文件。")
        temporary.replace(path)
    except (OSError, urllib.error.URLError) as exc:
        raise LaunchError(f"Logisim 下载失败。可手动从 {JAR_URL} 下载到 {path} 后重启。") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return path


def stop_requested(root, token):
    return read_json(root / "stop-request.json").get("token") == token


def terminate(process):
    if process.poll() is not None:
        return
    # 仅处理本次启动、仍由 Popen 持有句柄的子进程；不读取 PID 文件杀进程。
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_FLAGS)
    else:
        process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=8)


def run_step(command, cwd, env, log, root, token):
    with log.open("ab") as output:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, creationflags=CREATE_FLAGS)
        try:
            while process.poll() is None:
                if stop_requested(root, token):
                    raise StopRequested()
                time.sleep(0.2)
            if process.returncode:
                raise LaunchError(f"准备步骤失败（退出码 {process.returncode}），详情见 {log}")
        finally:
            terminate(process)


def ensure_python(root, env, log, token):
    if (REPO / "portable.json").exists():
        python = REPO / "runtime/python/python.exe"
        if Path(sys.executable).resolve() != python.resolve():
            raise LaunchError("请使用离线包中的一键启动.cmd，运行所附 Python。")
        pairs = [line.split("==") for line in (REPO / "backend/requirements.txt").read_text(encoding="utf-8").splitlines()
                 if line and not line.startswith("#")]
        verify = "import importlib.metadata as m; pairs=" + repr(pairs) + "; assert all(m.version(n)==v for n,v in pairs)"
        if check_command([str(python), "-c", verify])[0]:
            raise LaunchError("离线 Python 依赖缺失或版本不符，请重新解压完整运行包。")
        print("[1/5] 使用包内 Python 及依赖。", flush=True)
        return python
    folder = root / "venv"
    python = folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    stamp = root / "python-ready.json"
    if folder.exists() and check_command([str(python), "-c", "import sys; assert sys.version_info >= (3,12)"])[0]:
        # 移动项目后旧 venv 的基础解释器可能失效；保留原目录再重建，不删除数据。
        destination = root / ("venv-old-" + secrets.token_hex(4))
        if folder.resolve().parent != root.resolve() or destination.resolve().parent != root.resolve():
            raise LaunchError("Python 环境路径不在当前运行目录内，请检查 venv 是否被替换为目录链接。")
        folder.rename(destination)
    if not python.is_file():
        stamp.unlink(missing_ok=True)
        print("[1/5] 创建项目专用 Python 环境…", flush=True)
        run_step([sys.executable, "-m", "venv", str(folder)], REPO, env, log, root, token)
    fingerprint = hashlib.sha256((REPO / "backend/requirements.txt").read_bytes() +
                                 str(sys.version_info[:2]).encode()).hexdigest()
    pairs = [line.split("==") for line in (REPO / "backend/requirements.txt").read_text(encoding="utf-8").splitlines()
             if line and not line.startswith("#")]
    verify = "import importlib.metadata as m; pairs=" + repr(pairs) + "; assert all(m.version(n)==v for n,v in pairs)"
    if (read_json(stamp).get("fingerprint") != fingerprint or
            check_command([str(python), "-c", verify])[0] or
            check_command([str(python), "-m", "pip", "check"])[0]):
        print("[1/5] 安装后端依赖，首次需要联网，请查看 setup.log 中的进度…", flush=True)
        run_step([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r",
                  str(REPO / "backend/requirements.txt")], REPO, env, log, root, token)
        write_json(stamp, dict(fingerprint=fingerprint))
    else:
        print("[1/5] Python 依赖已就绪。", flush=True)
    return python


def frontend_fingerprint():
    digest = hashlib.sha256()
    frontend = REPO / "frontend"
    files = [frontend / p for p in ("package.json", "package-lock.json", "index.html", "vite.config.js")]
    for folder in ("src", "public"):
        files.extend(p for p in (frontend / folder).rglob("*") if p.is_file())
    for path in sorted(files):
        digest.update(path.relative_to(frontend).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def ensure_frontend(npm, root, env, log, token):
    if (REPO / "portable.json").exists():
        manifest = read_json(REPO / "portable.json")
        files = manifest.get("frontend_files")
        if (manifest.get("schema") != 1 or not isinstance(files, dict) or
                "frontend/dist/index.html" not in files or
                manifest.get("frontend_fingerprint") != frontend_fingerprint()):
            raise LaunchError("离线包清单或前端源码校验失败，请重新解压完整运行包。")
        base = (REPO / "frontend/dist").resolve()
        for name, expected in files.items():
            path = (REPO / name).resolve()
            if not path.is_relative_to(base) or not path.is_file() or sha256(path) != expected:
                raise LaunchError(f"离线页面文件校验失败：{name}，请重新解压运行包。")
        print("[2/5] 离线页面校验通过，无需 Node.js 或网络。", flush=True)
        return
    frontend = REPO / "frontend"
    lock_hash = sha256(frontend / "package-lock.json")
    stamp = root / "frontend-ready.json"
    old = read_json(stamp)
    if old.get("lock_hash") != lock_hash or not (frontend / "node_modules/.package-lock.json").is_file():
        print("[2/5] 安装前端依赖…", flush=True)
        run_step([npm, "ci", "--no-audit", "--no-fund"], frontend, env, log, root, token)
    fingerprint = frontend_fingerprint()
    if old.get("fingerprint") != fingerprint or not (frontend / "dist/index.html").is_file():
        print("[2/5] 构建前端页面…", flush=True)
        run_step([npm, "run", "build"], frontend, env, log, root, token)
    else:
        print("[2/5] 前端页面已就绪。", flush=True)
    write_json(stamp, dict(lock_hash=lock_hash, fingerprint=fingerprint))


def owner_watch(root, token, parent_pid, on_stop):
    """关闭启动窗口时，子进程持有的父进程句柄也会通知服务退出。"""
    handle = None
    kernel = None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, parent_pid)
    try:
        while True:
            if stop_requested(root, token):
                break
            if kernel:
                if not handle or kernel.WaitForSingleObject(handle, 500) != 258:
                    break
            else:
                try:
                    os.kill(parent_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.5)
        on_stop()
    finally:
        if handle:
            kernel.CloseHandle(handle)


def service_mode(kind, port):
    sys.path.insert(0, str(REPO / "backend"))
    os.chdir(REPO / "backend")
    root = Path(os.environ["LOCAL_RUN_DATA_DIR"])
    token = os.environ["LOCAL_RUN_TOKEN"]
    parent_pid = int(os.environ["LOCAL_RUN_OWNER_PID"])
    if kind == "_serve":
        from waitress import create_server
        from app import create_app
        server = create_server(create_app(), host="127.0.0.1", port=port, threads=4)
        threading.Thread(target=owner_watch, args=(root, token, parent_pid, server.close), daemon=True).start()
        print(f"网站已监听 http://127.0.0.1:{port}", flush=True)
        server.run()
    else:
        import _thread
        from flask.cli import main as flask_main
        threading.Thread(target=owner_watch, args=(root, token, parent_pid, _thread.interrupt_main), daemon=True).start()
        sys.argv = ["flask", "--app", "app:create_app", "lab-worker"]
        flask_main()


def wait_ready(process, predicate, root, token, log, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if stop_requested(root, token):
            raise StopRequested()
        if process.poll() is not None:
            raise LaunchError(f"服务启动失败，详情见 {log}")
        if predicate():
            return
        time.sleep(0.3)
    raise LaunchError(f"服务未在 {timeout} 秒内就绪，详情见 {log}")


def health_ok(url):
    try:
        # localhost 不经过使用者的 HTTP_PROXY，避免健康检测请求走代理。
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url + "/api/v1/health", timeout=2) as response:
            return json.load(response).get("data", {}).get("status") == "ok"
    except (OSError, ValueError):
        return False


def launch(root, args):
    root.mkdir(parents=True, exist_ok=True)
    with launch_lock(root) as acquired:
        if not acquired:
            state = read_json(root / "running.json")
            print("项目已在运行或正在准备，无需再次启动。", flush=True)
            if state.get("ready") and state.get("url") and health_ok(state["url"]):
                print(state["url"], flush=True)
                if not args.no_browser:
                    webbrowser.open(state["url"])
            return 0
        config = settings(root)
        port = args.port or config["port"]
        token = secrets.token_hex(24)
        reservation = socket.socket()
        processes = []
        handles = []
        state = dict(token=token, owner_pid=os.getpid(), ready=False, url=f"http://127.0.0.1:{port}")
        try:
            try:
                if os.name == "nt":
                    reservation.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                reservation.bind(("127.0.0.1", port))
            except OSError as exc:
                raise LaunchError(f"端口 {port} 已被其他程序占用。请关闭对应服务，或修改 .local-run/settings.json 的 port。") from exc
            write_json(root / "running.json", state)
            log_dir = root / "logs"
            log_dir.mkdir(exist_ok=True)
            setup_log = log_dir / "setup.log"
            npm = None if (REPO / "portable.json").exists() else find_node()
            env = child_environment(root, config)
            python = ensure_python(root, env, setup_log, token)
            ensure_frontend(npm, root, env, setup_log, token)
            print("[3/5] 升级专用演示库、准备模拟示例（已有数据不会重置）…", flush=True)
            run_step([str(python), "-m", "flask", "--app", "app:create_app", "db", "upgrade"],
                     REPO / "backend", env, setup_log, root, token)
            run_step([str(python), "-m", "flask", "--app", "app:create_app", "seed-demo", "--confirm-demo-database"],
                     REPO / "backend", env, setup_log, root, token)
            java = jar = ""
            if not args.without_grader:
                print("[4/5] 检查 Java 和 Logisim…", flush=True)
                try:
                    java = find_java(config)
                    jar = ensure_jar(root, config)
                except LaunchError as exc:
                    print(f"提示：{exc}\n网站仍会启动；其他功能可正常使用。", flush=True)
                    java = jar = ""
            env = child_environment(root, config, java, jar)
            env.update(LOCAL_RUN_DATA_DIR=str(root), LOCAL_RUN_TOKEN=token, LOCAL_RUN_OWNER_PID=str(os.getpid()))
            print("[5/5] 启动网站和测评服务…", flush=True)
            reservation.close()
            for kind, name in [("_serve", "web")] + ([("_worker", "worker")] if java and jar else []):
                log = log_dir / (name + ".log")
                heartbeat = root / "uploads/lab-runtime/heartbeat.json"
                old_token = read_json(heartbeat).get("token")
                database_hash = hashlib.sha256(env["DATABASE_URL"].encode()).hexdigest()
                output = log.open("wb")
                handles.append(output)
                process = subprocess.Popen([str(python), "-u", str(Path(__file__).resolve()), kind, "--port", str(port)],
                                           cwd=REPO, env=env, stdin=subprocess.DEVNULL, stdout=output,
                                           stderr=subprocess.STDOUT, creationflags=CREATE_FLAGS)
                processes.append(process)
                if name == "web":
                    predicate = lambda: health_ok(state["url"])
                else:
                    def predicate():
                        row = read_json(heartbeat)
                        return (bool(row.get("token")) and row.get("token") != old_token and
                                row.get("database") == database_hash and row.get("jar_sha256") == JAR_SHA256 and
                                0 <= time.time() - row.get("timestamp", 0) <= 15)
                wait_ready(process, predicate, root, token, log)
            state.update(ready=True, grader_ready=bool(java and jar))
            write_json(root / "running.json", state)
            print(f"\n启动完成：{state['url']}\n教师：demo_teacher_a\n学生：demo_student_01\n管理员：demo_admin\n"
                  f"演示口令：{config['demo_password']}\n电路文件测评：{'已就绪' if state['grader_ready'] else '未启用'}\n"
                  f"数据与日志：{root}\n保留此窗口。按 Ctrl+C 或双击“停止运行.cmd”退出。\n", flush=True)
            if not args.no_browser:
                webbrowser.open(state["url"])
            while not stop_requested(root, token):
                for process in processes:
                    if process.poll() is not None:
                        raise LaunchError(f"服务意外停止，详情见 {log_dir}；请重新启动。")
                time.sleep(0.3)
        except (KeyboardInterrupt, StopRequested):
            print("\n正在停止本次启动的服务…", flush=True)
        finally:
            reservation.close()
            # 服务先读取停止请求正常退出，超时才终止本次持有的子进程。
            write_json(root / "stop-request.json", dict(token=token))
            deadline = time.monotonic() + 10
            for process in processes:
                try:
                    process.wait(timeout=max(0.1, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    terminate(process)
            for handle in handles:
                handle.close()
            if read_json(root / "running.json").get("token") == token:
                (root / "running.json").unlink(missing_ok=True)
            print("本次服务已停止，演示数据已保留。", flush=True)
    return 0


def stop(root):
    if not root.is_dir():
        print("当前没有通过一键入口运行的服务。")
        return 0
    with launch_lock(root) as acquired:
        if acquired:
            print("当前没有通过一键入口运行的服务。")
            return 0
    state = read_json(root / "running.json")
    if not state.get("token"):
        raise LaunchError("启动器正在准备，请稍后再停止，或在启动窗口按 Ctrl+C。")
    write_json(root / "stop-request.json", dict(token=state["token"]))
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        with launch_lock(root) as acquired:
            if acquired:
                print("服务已停止，已有演示数据已保留。")
                return 0
        time.sleep(0.3)
    raise LaunchError("已发送停止请求；若仍在下载，请在启动窗口按 Ctrl+C，并查看 .local-run/logs。")


def main():
    parser = argparse.ArgumentParser(description="数字逻辑课程学习系统本机一键启动")
    parser.add_argument("action", nargs="?", default="start", choices=["start", "stop", "_serve", "_worker"])
    parser.add_argument("--port", type=int, help="本次使用的端口，默认 5336")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--without-grader", action="store_true", help="仅启动网站和接线模拟")
    args = parser.parse_args()
    if args.port is not None and not 1024 <= args.port <= 65535:
        parser.error("端口必须为 1024—65535")
    if args.action.startswith("_"):
        service_mode(args.action, args.port or 5336)
        return 0
    root = REPO / ".local-run"
    try:
        if args.action == "stop":
            return stop(root)
        if not (3, 12) <= sys.version_info[:2] <= (3, 14) or sys.maxsize <= 2**32:
            raise LaunchError("请使用 64 位 Python 3.12—3.14，推荐 Python 3.14。")
        return launch(root, args)
    except (LaunchError, OSError) as exc:
        print(f"\n启动器提示：{exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
