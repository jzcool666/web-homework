#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D7 PERF-01 课堂负载脚本（模拟数据，明确标记为模拟）。

模拟一个班 60 名学生在一个课堂活动中的混合负载：以约 3 秒周期轮询演示状态，
穿插读取测评、保存答案，最后集中提交；另有一个教师客户端周期性查询统计与
组卷，用于单独记录统计与组卷接口的延迟。

只使用标准库（urllib + http.cookiejar + threading），不引入新依赖。
产出的全部客户端与作答都是**模拟数据**，不代表真实课堂参与。

用法::

    python tests/perf/load_test.py --base http://127.0.0.1:5090 \\
        --clients 60 --duration 600 --poll 3 --out <结果.json> \\
        --pid <被测量的服务进程 PID>

结果包含按接口类别的 p50/p95/最大值、错误计数、服务进程 CPU/内存采样与数据一致性核对。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path

API = "/api/v1"
PASSWORD = "Passw0rd!23"
LOAD_CLASS_NAME = "负载测试模拟班"
LOAD_TEACHER = "t_load"
LOAD_TEACHER_PASSWORD = "LoadPass!2345"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def rfc3339(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class HttpError(Exception):
    def __init__(self, status, payload):
        super().__init__(f"HTTP {status}: {payload}")
        self.status = status
        self.payload = payload


class Client:
    def __init__(self, base, name):
        self.base = base.rstrip("/")
        self.name = name
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = None

    def _request(self, method, path, *, body=None, raw=None, ctype="application/json"):
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = ctype
        elif raw is not None:
            data = raw
            headers["Content-Type"] = ctype
        if method != "GET" and self.csrf and path != f"{API}/auth/csrf":
            headers["X-CSRF-Token"] = self.csrf
        request = urllib.request.Request(
            self.base + urllib.parse.quote(path, safe="/?&=:%"),
            data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                return response.status, self._decode(response)
        except urllib.error.HTTPError as exc:
            return exc.code, self._decode(exc)

    @staticmethod
    def _decode(response):
        payload = response.read()
        if "application/json" in response.headers.get("Content-Type", ""):
            return json.loads(payload.decode("utf-8")) if payload else None
        return payload

    def login(self, login_name, password):
        status, data = self._request("GET", f"{API}/auth/csrf")
        self.csrf = data["data"]["csrf_token"]
        status, data = self._request("POST", f"{API}/auth/login",
                                     body={"login_name": login_name, "password": password})
        if status != 200:
            raise HttpError(status, data)
        self.csrf = data["data"]["csrf_token"]
        return data["data"]["user"]

    def call(self, method, path, *, body=None, expect=None):
        status, data = self._request(method, path, body=body)
        if expect is not None and status != expect:
            raise HttpError(status, data)
        return status, data

    def data(self, method, path, *, body=None, expect=200):
        status, payload = self.call(method, path, body=body, expect=expect)
        return payload["data"]


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.samples: dict[str, list[float]] = {}
        self.errors: list[dict] = []
        self.counts: dict[str, int] = {}

    def record(self, bucket, elapsed, ok, detail=None):
        with self.lock:
            self.samples.setdefault(bucket, []).append(elapsed)
            self.counts[bucket] = self.counts.get(bucket, 0) + 1
            if not ok:
                self.errors.append({"bucket": bucket, "detail": str(detail)[:200]})

    def summary(self):
        out = {}
        for bucket, values in self.samples.items():
            ordered = sorted(values)
            out[bucket] = {
                "count": len(values),
                "p50_ms": round(statistics.median(ordered) * 1000, 1),
                "p95_ms": round(ordered[min(len(ordered) - 1,
                                            int(round(0.95 * (len(ordered) - 1))))] * 1000, 1),
                "max_ms": round(max(ordered) * 1000, 1),
                "mean_ms": round(statistics.fmean(ordered) * 1000, 1),
            }
        return out


def ensure_load_dataset(base, clients):
    """建立（幂等的）负载测试班级、教师与 60 名学生，返回可用学生名单。"""
    admin = Client(base, "admin")
    admin.login("admin_root", "Adm1nPass!23")

    # 教师
    status, payload = admin.call("POST", f"{API}/users", body={
        "login_name": LOAD_TEACHER, "display_name": "负载模拟教师",
        "password": LOAD_TEACHER_PASSWORD, "role": "teacher"})
    if status == 409:
        teacher = next(u for u in admin.data("GET", f"{API}/users?role=teacher&page_size=100")
                       if u["login_name"] == LOAD_TEACHER)
    else:
        teacher = payload["data"]

    # 班级
    classes = admin.data("GET", f"{API}/classes?page_size=100")
    school_class = next((c for c in classes if c["name"] == LOAD_CLASS_NAME), None)
    if school_class is None:
        school_class = admin.data("POST", f"{API}/classes",
                                  body={"name": LOAD_CLASS_NAME,
                                        "teacher_id": teacher["id"]}, expect=201)

    students = []
    for index in range(1, clients + 1):
        login_name = f"load_stu{index:02d}"
        status, payload = admin.call("POST", f"{API}/users", body={
            "login_name": login_name, "display_name": f"负载模拟学生{index:02d}",
            "password": PASSWORD, "role": "student", "student_no": f"2027{index:04d}"})
        if status == 409:
            student = next(u for u in admin.data("GET", f"{API}/users?role=student&page_size=100")
                           if u["login_name"] == login_name)
        else:
            student = payload["data"]
        admin.call("PUT", f"{API}/classes/{school_class['id']}/enrollments",
                   body={"student_id": student["id"], "active": True})
        students.append(student)
    return teacher, school_class, students


def prepare_activity(base, school_class, students):
    """教师准备一场随堂测并发布，返回测评与题目信息（幂等：每次新建一场）。"""
    teacher = Client(base, "load_teacher")
    teacher.login(LOAD_TEACHER, LOAD_TEACHER_PASSWORD)

    points = teacher.data("GET", f"{API}/knowledge-points?page_size=100")
    point_id = points[0]["id"]
    question = teacher.data("POST", f"{API}/questions", body={
        "type": "single", "stem_md": f"负载测试题 {uuid.uuid4()}：模6计数器次态？",
        "options": [{"key": "A", "label": "0000"}, {"key": "B", "label": "0110"}],
        "answer": ["A"], "explanation_md": "负载测试用固定题。", "difficulty": 1,
        "knowledge_ids": [point_id], "published": True}, expect=201)
    quiz = teacher.data("POST", f"{API}/assessments", body={
        "class_id": school_class["id"], "kind": "quiz", "title": "负载模拟随堂测",
        "items": [{"question_id": question["id"], "points": 10}]}, expect=201)
    quiz = teacher.data("POST", f"{API}/assessments/{quiz['id']}/publication", body={
        "version": quiz["version"],
        "starts_at": rfc3339(now_utc() - timedelta(seconds=5)),
        "ends_at": rfc3339(now_utc() + timedelta(hours=2))})
    quiz["knowledge_id"] = point_id
    return teacher, quiz, question


def student_worker(base, login_name, quiz_id, demo_id, duration, poll, metrics, barrier, state):
    client = Client(base, login_name)
    try:
        client.login(login_name, PASSWORD)
        logged_in = True
    except HttpError as exc:
        metrics.record("login", 0.0, False, exc)
        logged_in = False
    if not logged_in:
        state[login_name] = {"submission_id": None, "saved": 0}
        try:
            barrier.wait(timeout=30)
        except threading.BrokenBarrierError:
            pass
        return
    submission = None
    item_id = None
    deadline = time.monotonic() + duration
    try:
        barrier.wait(timeout=30)
    except threading.BrokenBarrierError:
        pass
    while time.monotonic() < deadline:
        start = time.perf_counter()
        try:
            if demo_id is not None:
                client.data("GET", f"{API}/demo-sessions/{demo_id}")
                metrics.record("poll_demo", time.perf_counter() - start, True)
            else:
                client.data("GET", f"{API}/me/recommendations?limit=3")
                metrics.record("poll_recommendation", time.perf_counter() - start, True)
        except Exception as exc:  # noqa: BLE001
            metrics.record("poll_demo", time.perf_counter() - start, False, exc)
        time.sleep(poll)

    # 集中保存与提交
    try:
        start = time.perf_counter()
        submission = client.data("POST", f"{API}/assessments/{quiz_id}/submissions",
                                 body={}, expect=201)
        metrics.record("start_submission", time.perf_counter() - start, True)
        item_id = client.data("GET", f"{API}/assessments/{quiz_id}")["items"][0]["id"]
        start = time.perf_counter()
        saved = client.data("PUT", f"{API}/submissions/{submission['id']}/answers",
                            body={"version": submission["version"],
                                  "answers": [{"item_id": item_id, "selected": ["A"]}]})
        metrics.record("save_answer", time.perf_counter() - start, True)
        start = time.perf_counter()
        client.data("POST", f"{API}/submissions/{submission['id']}/finalization",
                    body={"version": saved["version"]})
        metrics.record("finalize", time.perf_counter() - start, True)
    except Exception as exc:  # noqa: BLE001
        metrics.record("submit_burst", time.perf_counter() - start, False, exc)
    state[login_name] = {"submission_id": submission["id"] if submission else None,
                         "saved": 1 if submission else 0}


def teacher_worker(base, school_class_id, metrics, duration, poll, knowledge_id, state):
    client = Client(base, "load_teacher_poll")
    client.login(LOAD_TEACHER, LOAD_TEACHER_PASSWORD)
    deadline = time.monotonic() + duration
    round_no = 0
    while time.monotonic() < deadline:
        round_no += 1
        for bucket, path in (
            ("analytics_assessment",
             f"{API}/analytics/assessment?class_id={school_class_id}"),
            ("analytics_learning", f"{API}/analytics/learning?class_id={school_class_id}"),
            ("knowledge_graph", f"{API}/knowledge-graph?depth=2"),
        ):
            start = time.perf_counter()
            try:
                client.data("GET", path)
                metrics.record(bucket, time.perf_counter() - start, True)
            except Exception as exc:  # noqa: BLE001
                metrics.record(bucket, time.perf_counter() - start, False, exc)
        if round_no <= 3:
            start = time.perf_counter()
            try:
                client.data("POST", f"{API}/paper-generations", body={
                    "class_id": school_class_id, "title": f"负载组卷 {round_no}",
                    "kind": "quiz", "count": 1,
                    "difficulty_counts": {"easy": 1, "medium": 0, "hard": 0},
                    "knowledge_minimums": [{"knowledge_id": knowledge_id, "min_count": 1}],
                    "seed": 100 + round_no}, expect=201)
                metrics.record("paper_generation", time.perf_counter() - start, True)
            except Exception as exc:  # noqa: BLE001
                metrics.record("paper_generation", time.perf_counter() - start, False, exc)
        time.sleep(poll * 4)
    state["rounds"] = round_no


def sample_process(pid, stop_event, samples):
    """采样服务进程的 CPU 时间与工作集（Windows：tasklist / powershell）。"""
    import subprocess
    while not stop_event.is_set():
        try:
            if os.name == "nt":
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | "
                     f"Select-Object -Property CPU,WorkingSet64 | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=15).stdout.strip()
                if out:
                    record = json.loads(out)
                    if isinstance(record, list):
                        record = record[0]
                    samples.append({"t": time.time(), "cpu_s": record.get("CPU"),
                                    "ws_bytes": record.get("WorkingSet64")})
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--clients", type=int, default=60)
    parser.add_argument("--duration", type=int, default=600, help="轮询阶段秒数（默认600=10分钟）")
    parser.add_argument("--poll", type=float, default=3.0)
    parser.add_argument("--pid", type=int, help="被测量服务进程 PID（可选）")
    parser.add_argument("--out")
    args = parser.parse_args()

    print("[setup] 建立模拟班级与 60 名学生…", flush=True)
    teacher, school_class, students = ensure_load_dataset(args.base, args.clients)
    teacher_client, quiz, question = prepare_activity(args.base, school_class, students)
    # 开一场演示，供学生轮询（已有进行中的演示则复用）
    experiment_id = teacher_client.data(
        "GET", f"{API}/experiments?page_size=100")[0]["id"]
    status, payload = teacher_client.call(
        "POST", f"{API}/demo-sessions",
        body={"class_id": school_class["id"], "experiment_id": experiment_id})
    if status == 201:
        demo_id = payload["data"]["id"]
    else:
        active = teacher_client.data(
            "GET", f"{API}/demo-sessions?class_id={school_class['id']}&active=true")
        demo_id = active[0]["id"]
    print(f"[setup] 班级 id={school_class['id']} 测评 id={quiz['id']} "
          f"演示 id={demo_id} 学生 {len(students)}", flush=True)

    metrics = Metrics()
    state: dict = {}
    barrier = threading.Barrier(args.clients, timeout=60)
    threads = [
        threading.Thread(target=student_worker, daemon=True,
                         args=(args.base, s["login_name"], quiz["id"], demo_id,
                               args.duration, args.poll, metrics, barrier, state))
        for s in students
    ]
    tstate: dict = {}
    teacher_thread = threading.Thread(
        target=teacher_worker, daemon=True,
        args=(args.base, school_class["id"], metrics, args.duration, args.poll,
              quiz.get("knowledge_id") or 1, tstate))

    stop_event = threading.Event()
    samples: list[dict] = []
    sampler = None
    if args.pid:
        sampler = threading.Thread(target=sample_process,
                                   args=(args.pid, stop_event, samples), daemon=True)
        sampler.start()

    started_at = now_utc()
    print(f"[run] 启动 {args.clients} 模拟客户端，轮询 {args.duration}s，周期 {args.poll}s…",
          flush=True)
    for thread in threads:
        thread.start()
    teacher_thread.start()
    t0 = time.monotonic()
    for thread in threads:
        thread.join()
    teacher_thread.join()
    elapsed = time.monotonic() - t0
    stop_event.set()

    summary = metrics.summary()
    ok_scenarios = {
        "普通API p95 ≤ 1s": all(
            summary[b]["p95_ms"] <= 1000 for b in
            ("poll_demo", "save_answer", "finalize", "start_submission")
            if b in summary),
        "统计 p95 ≤ 2s": all(
            summary[b]["p95_ms"] <= 2000 for b in
            ("analytics_assessment", "analytics_learning") if b in summary),
        "组卷 p95 ≤ 5s": summary.get("paper_generation", {}).get("p95_ms", 0) <= 5000,
    }
    submitted = sum(1 for v in state.values() if v.get("submission_id"))
    result = {
        "marker": "SIMULATED_DATA",
        "note": "全部客户端与作答为模拟数据，不代表真实课堂参与",
        "environment": {
            "os": platform.platform(),
            "python": sys.version.split()[0],
            "base": args.base,
            "started_at": rfc3339(started_at),
            "duration_s": round(elapsed, 1),
            "clients": args.clients,
            "poll_interval_s": args.poll,
        },
        "latency": summary,
        "errors": metrics.errors[:100],
        "error_count": len(metrics.errors),
        "consistency": {"students_with_submission": submitted,
                        "expected": len(students),
                        "teacher_rounds": tstate.get("rounds")},
        "process_samples": samples[:120],
        "targets_met": ok_scenarios,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    print(json.dumps({k: result[k] for k in
                      ("latency", "error_count", "consistency", "targets_met")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
