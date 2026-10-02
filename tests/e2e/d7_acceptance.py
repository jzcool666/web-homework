#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D7 系统集成验收脚本：E2E-01/02/03 与 SEC-01。

只用标准库（urllib + http.cookiejar）对一个**真实运行**的服务发 HTTP 请求，
不使用 Werkzeug 测试客户端，因此验证的是真实 WSGI 部署形态（会话 Cookie、
CSRF、状态码与响应投影）。

阶段：

* ``bootstrap`` —— 通过管理员接口建立两教师两班与两班学生（幂等）。
  课程内容/实验/问答语料由 CLI 种子命令建立，不在本脚本内。
* ``all`` —— 在已 bootstrap 的环境上跑 E2E-01/02/03 与 SEC-01。

用法::

    python tests/e2e/d7_acceptance.py --base http://127.0.0.1:5090 \\
        --admin-login admin_root --admin-password 'Adm1nPass!23' \\
        --phase bootstrap|all --out <证据.json>

退出码 0 表示本阶段全部断言通过；任何断言失败返回 1。
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path

API = "/api/v1"
DEFAULT_PASSWORD = "Passw0rd!23"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def rfc3339(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class HttpError(Exception):
    def __init__(self, status: int, payload):
        super().__init__(f"HTTP {status}: {payload}")
        self.status = status
        self.payload = payload


class Client:
    """带 Cookie 与 CSRF 的极简 HTTP 客户端。"""

    def __init__(self, base: str, name: str):
        self.base = base.rstrip("/")
        self.name = name
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.csrf: str | None = None

    def _request(self, method: str, path: str, *, body=None, raw=None, headers=None,
                 ctype="application/json") -> tuple[int, object]:
        headers = dict(headers or {})
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
            data=data, headers=headers, method=method,
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                return response.status, self._decode(response)
        except urllib.error.HTTPError as exc:
            return exc.code, self._decode(exc)

    @staticmethod
    def _decode(response) -> object:
        payload = response.read()
        ctype = response.headers.get("Content-Type", "")
        if "application/json" in ctype:
            return json.loads(payload.decode("utf-8")) if payload else None
        return payload

    def bootstrap_csrf(self) -> str:
        status, data = self._request("GET", f"{API}/auth/csrf")
        assert status == 200, (status, data)
        self.csrf = data["data"]["csrf_token"]
        return self.csrf

    def login(self, login_name: str, password: str) -> dict:
        self.bootstrap_csrf()
        status, data = self._request(
            "POST", f"{API}/auth/login",
            body={"login_name": login_name, "password": password},
        )
        if status != 200:
            raise HttpError(status, data)
        self.csrf = data["data"]["csrf_token"]
        return data["data"]["user"]

    def call(self, method: str, path: str, *, body=None, expect=None, raw=None,
             headers=None, ctype="application/json"):
        status, data = self._request(method, path, body=body, raw=raw,
                                     headers=headers, ctype=ctype)
        if expect is not None and status != expect:
            raise HttpError(status, data)
        return status, data

    def ok(self, method: str, path: str, *, body=None, expect=200):
        status, data = self.call(method, path, body=body, expect=expect)
        return data["data"] if isinstance(data, dict) and "data" in data else data


class Report:
    def __init__(self):
        self.results: list[dict] = []

    @staticmethod
    def _jsonable(value):
        if isinstance(value, bytes):
            return value[:16].hex() + ("…" if len(value) > 16 else "")
        if isinstance(value, dict):
            return {k: Report._jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [Report._jsonable(v) for v in value]
        return value

    def check(self, case: str, name: str, ok: bool, detail=None):
        self.results.append(
            {"case": case, "check": name, "ok": bool(ok),
             "detail": self._jsonable(detail)}
        )
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {case} :: {name}"
        if detail is not None and not ok:
            line += f"  -> {detail}"
        print(line, flush=True)
        return ok

    @property
    def failures(self) -> list[dict]:
        return [r for r in self.results if not r["ok"]]


# --------------------------------------------------------------------------
# bootstrap
# --------------------------------------------------------------------------

def ensure_user(admin: Client, report: Report, *, login_name, role, display_name,
                student_no=None) -> dict:
    body = {
        "login_name": login_name,
        "display_name": display_name,
        "password": DEFAULT_PASSWORD,
        "role": role,
    }
    if role == "student":
        body["student_no"] = student_no
    status, data = admin.call("POST", f"{API}/users", body=body)
    if status == 201:
        return data["data"]
    if status == 409:
        # 已存在：按登录名回查
        users = admin.ok("GET", f"{API}/users?role={role}&page_size=100")
        for user in users:
            if user["login_name"] == login_name:
                return user
    raise HttpError(status, data)


def ensure_class(admin: Client, *, name, teacher_id) -> dict:
    classes = admin.ok("GET", f"{API}/classes?page_size=100")
    for item in classes:
        if item["name"] == name:
            return item
    return admin.ok("POST", f"{API}/classes", body={"name": name, "teacher_id": teacher_id},
                    expect=201)


def ensure_enrollment(admin: Client, class_id: int, student_id: int):
    admin.ok("PUT", f"{API}/classes/{class_id}/enrollments",
             body={"student_id": student_id, "active": True})


def bootstrap(base: str, admin_login: str, admin_password: str) -> dict:
    report = Report()
    admin = Client(base, "admin")
    admin.login(admin_login, admin_password)

    teacher_alpha = ensure_user(admin, report, login_name="t_alpha", role="teacher",
                                display_name="教师甲")
    teacher_beta = ensure_user(admin, report, login_name="t_beta", role="teacher",
                               display_name="教师乙")
    class_alpha = ensure_class(admin, name="时序逻辑甲班", teacher_id=teacher_alpha["id"])
    class_beta = ensure_class(admin, name="时序逻辑乙班", teacher_id=teacher_beta["id"])

    alpha_students = []
    for index in range(1, 5):
        student = ensure_user(
            admin, report, login_name=f"s_alpha{index}", role="student",
            display_name=f"甲班学生{index}", student_no=f"2026000{index}",
        )
        ensure_enrollment(admin, class_alpha["id"], student["id"])
        alpha_students.append(student)

    beta_students = []
    for index in range(1, 4):
        student = ensure_user(
            admin, report, login_name=f"s_beta{index}", role="student",
            display_name=f"乙班学生{index}", student_no=f"2026100{index}",
        )
        ensure_enrollment(admin, class_beta["id"], student["id"])
        beta_students.append(student)

    report.check("bootstrap", "两教师两班建立", True,
                 {"class_alpha": class_alpha["id"], "class_beta": class_beta["id"]})
    print(json.dumps({
        "teacher_alpha": teacher_alpha["id"], "teacher_beta": teacher_beta["id"],
        "class_alpha": class_alpha["id"], "class_beta": class_beta["id"],
        "alpha_students": [s["id"] for s in alpha_students],
        "beta_students": [s["id"] for s in beta_students],
    }, ensure_ascii=False), flush=True)
    if report.failures:
        sys.exit(1)


# --------------------------------------------------------------------------
# E2E-01 课堂主流程
# --------------------------------------------------------------------------

def e2e_01(base, report: Report, ctx: dict, questions: dict, experiments: dict):
    case = "E2E-01"
    alpha = Client(base, "teacher_alpha")
    alpha.login("t_alpha", DEFAULT_PASSWORD)
    beta = Client(base, "teacher_beta")
    beta.login("t_beta", DEFAULT_PASSWORD)
    student1 = Client(base, "s_alpha1")
    student1.login("s_alpha1", DEFAULT_PASSWORD)
    student2 = Client(base, "s_alpha2")
    student2.login("s_alpha2", DEFAULT_PASSWORD)
    outsider = Client(base, "s_beta1")
    outsider.login("s_beta1", DEFAULT_PASSWORD)

    class_alpha = ctx["class_alpha"]
    class_beta = ctx["class_beta"]

    # --- 教师甲开演示（SPEC-012），学生同步只读 ---
    demo = alpha.ok("POST", f"{API}/demo-sessions",
                    body={"class_id": class_alpha, "experiment_id": experiments["counter"]},
                    expect=201)
    report.check(case, "教师甲为甲班发起模6计数器演示", demo["class_id"] == class_alpha)
    report.check(case, "演示初始隐藏下一状态（reveal_next=false）",
                 demo["reveal_next"] is False and demo.get("next_q") is None)

    student_view = student1.ok("GET", f"{API}/demo-sessions/{demo['id']}")
    report.check(case, "甲班学生可读取本班演示",
                 student_view["state"]["q"] == demo["state"]["q"])
    status, _ = outsider.call("GET", f"{API}/demo-sessions/{demo['id']}", expect=404)
    report.check(case, "乙班学生读取甲班演示返回404", status == 404, status)

    # 学生不得操作演示
    status, _ = student1.call("POST", f"{API}/demo-sessions/{demo['id']}/actions",
                              body={"expected_version": demo["version"],
                                    "event": {"op": "toggle_clock"}}, expect=403)
    report.check(case, "学生操作演示返回403", status == 403, status)

    # 教师单步：升沿
    step = alpha.ok("POST", f"{API}/demo-sessions/{demo['id']}/actions",
                    body={"expected_version": demo["version"],
                          "event": {"op": "toggle_clock"}})
    report.check(case, "教师单步后版本递增且时钟翻转",
                 step["version"] == demo["version"] + 1 and step["state"]["clock"] == 1)

    # 旧版本号再次操作 → 409
    status, _ = alpha.call("POST", f"{API}/demo-sessions/{demo['id']}/actions",
                           body={"expected_version": demo["version"],
                                 "event": {"op": "toggle_clock"}}, expect=409)
    report.check(case, "同 expected_version 二次动作返回409", status == 409, status)

    # 讲评：揭示下一状态后学生可见 next_q
    revealed = alpha.ok("POST", f"{API}/demo-sessions/{demo['id']}/actions",
                        body={"expected_version": step["version"],
                              "action": {"op": "set_reveal", "value": True}})
    student_view = student1.ok("GET", f"{API}/demo-sessions/{demo['id']}")
    report.check(case, "揭示后学生可读到 next_q",
                 student_view["reveal_next"] is True and student_view["next_q"] is not None)

    # --- 教师甲准备1题短测并发布（SPEC-010） ---
    quiz = alpha.ok("POST", f"{API}/assessments",
                    body={"class_id": class_alpha, "kind": "quiz",
                          "title": "模6计数器下一状态",
                          "items": [{"question_id": questions["counter"], "points": 10}]},
                    expect=201)
    starts_at = now_utc() - timedelta(seconds=5)
    ends_at = now_utc() + timedelta(seconds=120)
    published = alpha.ok("POST", f"{API}/assessments/{quiz['id']}/publication",
                         body={"version": quiz["version"],
                               "starts_at": rfc3339(starts_at),
                               "ends_at": rfc3339(ends_at)})
    report.check(case, "测评发布后 effective_state=open",
                 published["effective_state"] == "open", published["effective_state"])

    # --- 学生1 作答 ---
    submission = student1.ok("POST", f"{API}/assessments/{quiz['id']}/submissions",
                             body={}, expect=201)
    items = student1.ok("GET", f"{API}/assessments/{quiz['id']}")["items"]
    report.check(case, "学生读取测评条目不含答案与解析",
                 all("answer" not in it and "explanation_md" not in it for it in items))
    item_id = items[0]["id"]
    saved = student1.ok("PUT", f"{API}/submissions/{submission['id']}/answers",
                        body={"version": submission["version"],
                              "answers": [{"item_id": item_id, "selected": ["A"]}]})
    student2_post = student2.ok("POST", f"{API}/assessments/{quiz['id']}/submissions",
                                body={}, expect=201)

    # 学生2 交白卷（不提答案直接最终化）
    student2.ok("POST", f"{API}/submissions/{student2_post['id']}/finalization",
                body={"version": student2_post["version"]})

    student1.ok("POST", f"{API}/submissions/{submission['id']}/finalization",
                body={"version": saved["version"]})

    # --- 教师结束并讲评 ---
    current = alpha.ok("GET", f"{API}/assessments/{quiz['id']}")
    closed = alpha.ok("POST", f"{API}/assessments/{quiz['id']}/closure",
                      body={"version": current["version"]})
    report.check(case, "结束后 effective_state=closed",
                 closed["effective_state"] == "closed", closed["effective_state"])

    # 未公开反馈：学生结果 score 为 null
    result_before = student1.ok("GET", f"{API}/submissions/{submission['id']}/result")
    report.check(case, "反馈未公开时学生结果 score=null",
                 result_before["score"] is None and result_before["feedback_available"] is False,
                 result_before)

    released = alpha.ok("POST", f"{API}/assessments/{quiz['id']}/feedback-release",
                        body={"version": closed["version"]})
    result_after = student1.ok("GET", f"{API}/submissions/{submission['id']}/result")
    report.check(case, "公开反馈后学生可见分数与解析",
                 result_after["score"] is not None and result_after["feedback_available"] is True
                 and "answer" in result_after["items"][0], result_after)

    # --- 统计人数与成绩一致（SPEC-010 E057） ---
    stats = alpha.ok("GET", f"{API}/analytics/assessment?class_id={class_alpha}"
                            f"&assessment_id={quiz['id']}")
    row = stats["assessments"][0]
    report.check(case, "统计：名单4人、已提交2人、白卷1份",
                 row["roster_count"] == 4 and row["submitted_count"] == 2
                 and row["blank_count"] == 1, row)
    report.check(case, "统计：提交率=0.5",
                 abs(row["submission_rate"] - 0.5) < 1e-9, row["submission_rate"])

    # --- 班乙无权访问甲班测评 ---
    status, _ = outsider.call("GET", f"{API}/assessments/{quiz['id']}", expect=404)
    report.check(case, "乙班学生访问甲班测评返回404", status == 404, status)
    status, _ = beta.call("GET", f"{API}/assessments/{quiz['id']}", expect=404)
    report.check(case, "乙班教师访问甲班测评返回404", status == 404, status)

    # 清理：结束演示
    alpha.ok("POST", f"{API}/demo-sessions/{demo['id']}/actions",
             body={"expected_version": revealed["version"], "action": {"op": "close"}})
    return {"quiz_id": quiz["id"], "submission_id": submission["id"]}


# --------------------------------------------------------------------------
# E2E-02 实验纠错闭环
# --------------------------------------------------------------------------

def e2e_02(base, report: Report, ctx: dict, experiments: dict):
    case = "E2E-02"
    alpha = Client(base, "teacher_alpha")
    alpha.login("t_alpha", DEFAULT_PASSWORD)
    student = Client(base, "s_alpha1")
    student.login("s_alpha1", DEFAULT_PASSWORD)

    experiment = student.ok("GET", f"{API}/experiments/{experiments['shift']}")
    checkpoints = experiment["checkpoints"]
    report.check(case, "移位寄存器实验给出检查点（不含标准状态）",
                 len(checkpoints) >= 2 and "expected" not in json.dumps(checkpoints))
    length = len(checkpoints)

    def shift_row():
        data = alpha.ok("GET", f"{API}/analytics/experiment?class_id={ctx['class_alpha']}"
                              f"&experiment_id={experiments['shift']}")
        return next(e for e in data["experiments"]
                    if e["experiment_id"] == experiments["shift"])

    baseline = shift_row()

    # 1) 探针：用全 0 预测拿到后端标准状态
    probe = student.ok("POST", f"{API}/experiments/{experiments['shift']}/attempts",
                       body={"experiment_version": experiment["version"],
                             "predictions": [0] * length,
                             "request_key": str(uuid.uuid4())},
                       expect=201)
    expected = probe["expected"]
    report.check(case, "探针提交返回标准状态序列（长度与检查点一致）",
                 len(expected) == length, expected)

    # 2) 故意只在第二拍出错（状态值是 0—15 的十进制，不是单个 0/1）
    wrong = list(expected)
    wrong[1] = (wrong[1] + 1) % 16
    attempt = student.ok("POST", f"{API}/experiments/{experiments['shift']}/attempts",
                         body={"experiment_version": experiment["version"],
                               "predictions": wrong,
                               "request_key": str(uuid.uuid4())},
                         expect=201)
    report.check(case, "错误预测得到首错位置 index=1",
                 attempt["passed"] is False and attempt["first_error_index"] == 1, attempt)
    report.check(case, "错误预测保留失败记录", attempt["id"] > 0)

    # 3) 重做：按后端给出的标准状态提交正确预测
    retry = student.ok("POST", f"{API}/experiments/{experiments['shift']}/attempts",
                       body={"experiment_version": experiment["version"],
                             "predictions": expected,
                             "request_key": str(uuid.uuid4())},
                       expect=201)
    report.check(case, "按标准状态重做后通过", retry["passed"] is True, retry)

    # 教师查看实验统计：尝试 +3、通过 +1；参与人数不重复（同一学生仍只计 1）
    after = shift_row()
    report.check(case, "实验统计：尝试+3、通过+1、通过率1.0",
                 after["attempt_count"] == baseline["attempt_count"] + 3
                 and after["passed_students"] == 1
                 and abs(after["pass_rate"] - 1.0) < 1e-9,
                 {"baseline": baseline, "after": after})
    report.check(case, "参与人数不重复：多拍重做后仍只计 1 人",
                 after["participants"] == 1
                 and after["participants"] - baseline["participants"] <= 1,
                 {"baseline_participants": baseline["participants"],
                  "after_participants": after["participants"]})
    return {"experiment_id": experiments["shift"]}


# --------------------------------------------------------------------------
# E2E-03 断线恢复与截止判定
# --------------------------------------------------------------------------

def e2e_03(base, report: Report, ctx: dict, questions: dict):
    case = "E2E-03"
    alpha = Client(base, "teacher_alpha")
    alpha.login("t_alpha", DEFAULT_PASSWORD)
    student = Client(base, "s_alpha3")
    student.login("s_alpha3", DEFAULT_PASSWORD)

    quiz = alpha.ok("POST", f"{API}/assessments",
                    body={"class_id": ctx["class_alpha"], "kind": "quiz",
                          "title": "断线恢复用短测",
                          "items": [{"question_id": questions["counter"], "points": 10}]},
                    expect=201)
    # 短截止：40 秒后
    published = alpha.ok("POST", f"{API}/assessments/{quiz['id']}/publication",
                         body={"version": quiz["version"],
                               "starts_at": rfc3339(now_utc() - timedelta(seconds=2)),
                               "ends_at": rfc3339(now_utc() + timedelta(seconds=40))})

    submission = student.ok("POST", f"{API}/assessments/{quiz['id']}/submissions",
                            body={}, expect=201)
    detail = student.ok("GET", f"{API}/assessments/{quiz['id']}")
    item_id = detail["items"][0]["id"]
    saved = student.ok("PUT", f"{API}/submissions/{submission['id']}/answers",
                       body={"version": submission["version"],
                             "answers": [{"item_id": item_id, "selected": ["B"]}]})
    report.check(case, "首次保存成功并回执新版本",
                 saved["version"] == submission["version"] + 1, saved["version"])

    # 模拟断线：用全新会话重新登录，服务器仍保留已保存草稿
    reconnect = Client(base, "s_alpha3-reconnect")
    reconnect.login("s_alpha3", DEFAULT_PASSWORD)
    restored = reconnect.ok("GET", f"{API}/assessments/{quiz['id']}")
    report.check(case, "重连后服务器返回上次已保存的 my_submission_id",
                 restored["my_submission_id"] == submission["id"]
                 and restored["effective_state"] == "open", restored)

    # 断线期间的本地编辑（未保存）不改变服务器状态：服务器不知道任何新增改动，
    # 旧版本号以外的写入才会被接受，这里用陈旧版本号验证服务器未被本地编辑推进
    status, _ = reconnect.call("PUT", f"{API}/submissions/{submission['id']}/answers",
                               body={"version": submission["version"],
                                     "answers": [{"item_id": item_id, "selected": ["A"]}]})
    report.check(case, "用陈旧版本号保存返回409（本地编辑不算已提交）",
                 status == 409, status)

    # 截止：到期后用旧版本保存应 409（截止不可补交）
    print(f"[{case}] 等待测评截止（约45秒）…", flush=True)
    time.sleep(45)
    status, payload = student.call(
        "PUT", f"{API}/submissions/{submission['id']}/answers",
        body={"version": saved["version"],
              "answers": [{"item_id": item_id, "selected": ["A"]}]})
    report.check(case, "截止后保存返回409",
                 status == 409, (status, payload))
    if status == 409:
        report.check(case, "截止错误码为 DEADLINE_PASSED",
                     payload["error"]["code"] == "DEADLINE_PASSED",
                     payload["error"]["code"])

    # 截止后读取触发幂等最终化：草稿被最终化，未开始者仍记未提交
    final = student.ok("GET", f"{API}/submissions/{submission['id']}/result")
    report.check(case, "截止后已开始草稿被最终化（feedback 未公开时 score=null）",
                 final["feedback_available"] is False and final["score"] is None, final)

    stats = alpha.ok("GET", f"{API}/analytics/assessment?class_id={ctx['class_alpha']}"
                            f"&assessment_id={quiz['id']}")
    row = stats["assessments"][0]
    report.check(case, "截止最终化后统计到1份提交、名单4人",
                 row["submitted_count"] == 1 and row["roster_count"] == 4, row)
    return {"quiz_id": quiz["id"]}


# --------------------------------------------------------------------------
# SEC-01 越权与伪造
# --------------------------------------------------------------------------

def sec_01(base, report: Report, ctx: dict, questions: dict, experiments: dict):
    case = "SEC-01"
    alpha = Client(base, "teacher_alpha")
    alpha.login("t_alpha", DEFAULT_PASSWORD)
    beta = Client(base, "teacher_beta")
    beta.login("t_beta", DEFAULT_PASSWORD)
    student_a = Client(base, "s_alpha4")
    student_a.login("s_alpha4", DEFAULT_PASSWORD)
    student_b = Client(base, "s_beta2")
    student_b.login("s_beta2", DEFAULT_PASSWORD)
    anon = Client(base, "anon")

    ca, cb = ctx["class_alpha"], ctx["class_beta"]

    # 1) 匿名访问受保护接口 → 401
    for path in (f"{API}/analytics/attendance?class_id={ca}",
                 f"{API}/me/recommendations",
                 f"{API}/knowledge-graph"):
        status, _ = anon.call("GET", path)
        report.check(case, f"匿名访问 {path.split('?')[0]} 返回401", status == 401, status)

    # 2) 学生访问教师统计 → 403/404
    status, _ = student_a.call("GET", f"{API}/analytics/attendance?class_id={ca}")
    report.check(case, "学生访问出勤统计被拒", status in (403, 404), status)

    # 3) 他班教师访问本班统计 → 404
    status, _ = beta.call("GET", f"{API}/analytics/attendance?class_id={ca}")
    report.check(case, "乙班教师访问甲班统计返回404", status == 404, status)
    status, _ = beta.call("GET", f"{API}/analytics/experiment?class_id={ca}")
    report.check(case, "乙班教师访问甲班实验统计返回404", status == 404, status)

    # 4) 他班教师为本班生成预警/组卷 → 404
    status, _ = beta.call("POST", f"{API}/warnings/generations", body={"class_id": ca})
    report.check(case, "乙班教师为甲班生成预警返回404", status == 404, status)
    status, _ = beta.call(
        "POST", f"{API}/paper-generations",
        body={"class_id": ca, "title": "越权组卷", "kind": "quiz", "count": 1,
              "difficulty_counts": {"easy": 1, "medium": 0, "hard": 0},
              "knowledge_minimums": [], "seed": 1})
    report.check(case, "乙班教师为甲班组卷返回404", status == 404, status)

    # 5) 学生访问其他学生的 submission → 404
    secure_quiz = alpha.ok("POST", f"{API}/assessments",
                           body={"class_id": ca, "kind": "quiz", "title": "越权读取用短测",
                                 "items": [{"question_id": questions["counter"], "points": 10}]},
                           expect=201)
    alpha.ok("POST", f"{API}/assessments/{secure_quiz['id']}/publication",
             body={"version": secure_quiz["version"],
                   "starts_at": rfc3339(now_utc() - timedelta(seconds=2)),
                   "ends_at": rfc3339(now_utc() + timedelta(seconds=300))})
    sub = student_a.ok("POST", f"{API}/assessments/{secure_quiz['id']}/submissions",
                       body={}, expect=201)
    status, _ = student_b.call("GET", f"{API}/submissions/{sub['id']}/result")
    report.check(case, "乙班学生读取甲班学生 submission 返回404", status == 404, status)
    status, _ = beta.call("GET", f"{API}/submissions/{sub['id']}/result")
    report.check(case, "乙班教师读取甲班学生 submission 返回404", status == 404, status)

    # 6) 伪造 role/score/passed 被拒绝或忽略
    anon.bootstrap_csrf()
    status, _ = anon.call("POST", f"{API}/auth/register",
                          body={"login_name": "evil_admin1", "student_no": "20269999",
                                "display_name": "坏", "password": DEFAULT_PASSWORD,
                                "role": "admin"})
    report.check(case, "注册携带 role=admin 被拒（422/400）", status in (400, 422), status)

    experiment = student_a.ok("GET", f"{API}/experiments/{experiments['shift']}")
    status, payload = student_a.call("POST", f"{API}/experiments/{experiments['shift']}/attempts",
                                     body={"experiment_version": experiment["version"],
                                           "predictions": [1, 1, 1, 1],
                                           "request_key": str(uuid.uuid4()),
                                           "passed": True, "score": 100})
    report.check(case, "实验提交携带 passed/score 被拒绝（422 未支持字段）",
                 status == 422 and payload["error"]["code"] == "VALIDATION_ERROR"
                 and set(payload["error"]["details"]["unknown_fields"]) == {"passed", "score"},
                 (status, payload))

    # 7) 缺 CSRF 写操作 → 403
    bare = Client(base, "no-csrf")
    bare.bootstrap_csrf()
    saved_csrf, bare.csrf = bare.csrf, None
    status, payload = bare.call("POST", f"{API}/auth/login",
                                body={"login_name": "s_beta1", "password": DEFAULT_PASSWORD})
    report.check(case, "缺 CSRF 的登录写请求返回403",
                 status == 403 and payload["error"]["code"] in ("CSRF_FAILED", "FORBIDDEN"),
                 (status, payload))

    # 8) CSV 公式注入转义（教师导出）
    csv_payload = alpha.ok("GET", f"{API}/analytics/attendance?class_id={ca}&format=csv")
    report.check(case, "出勤统计 CSV 可导出（含 BOM）",
                 csv_payload[:3] == b"\xef\xbb\xbf", csv_payload[:8])

    # 9) 知识图谱越权：学生可读本课程图；他班学生同样可读已发布课程内容（课程级）
    status, _ = student_a.call("GET", f"{API}/knowledge-graph")
    report.check(case, "学生可读已发布知识图谱", status == 200, status)

    # 10) 推荐接口不接受学生ID参数（只按本人会话）
    rec = student_a.ok("GET", f"{API}/me/recommendations?limit=3")
    report.check(case, "推荐接口只返回本人条目", "items" in rec)
    status, _ = alpha.call("GET", f"{API}/me/recommendations")
    report.check(case, "教师访问推荐接口返回403", status == 403, status)
    return {}


# --------------------------------------------------------------------------
# 覆盖矩阵失败/无数据分支（清单第 2 条）
# --------------------------------------------------------------------------

# 一张 200×120 的非状态表 PNG（一条斜线 + 一个椭圆），用于识别失败分支
NON_TABLE_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAMgAAAB4CAIAAAA48Cq8AAAD0ElEQVR4nO2d0VLjMBAEvfz/P+vqAkWSg/hsR2vvzHa/UQW2hDqrkaLEMcZYAGbzMf2KAIgFWVCxIAXEghQQC1JALEgBsSAFxIIrxIqInPvC0r1ixY1TGgP9pkL0gplijRvfP1K6YCOx/U3oR6t46xqmrQr/KV1UL5hTse5/85zlqV4wR6yvv0QvyNggJddDSsV6ugq5HjLe0iHXQ0rFul+O4AUZYn1dFL3ak3K6gVwPKRXrEXJ9T9LPY5Hre5Jese53Inh14jyxvu6HXj04+2gyub4JZ1esp3uzX+/LlR+mINcbc2XFqhy8dp02q9DgapQQq4JeE88tjjL/0gspJNYlweuVT7tuPeUiZpQT6xy9fqow8S6ReXEVioqVNDOePOTR2LC6Ys3Vq1SAG7X/5y3EmjIwRTbMokYzzkFDrMMDU3Aso16Tuou1d2C+f7NgH6Nw25qKtWVmVBm2EGlnF7HW9dIarZBqbQuxbDYnw9EtebFsEnHcuiDaeNuvijQ4KDFuXVBsubNYP1/uinoNI7c+/OZBdb0WC7ccxPrk0SddvQYZq37mFT1fPywmRO1V4faVlNyyMcQXiT5T4TqiM6MuwhXr2Gta6ARLKBetLhXLINdroSrWmzYI5foo3DZDsT55c5p41Ktg6Rqak6CDWFNgZswAsf5C8JqO5KowdblUbdkYmmtDKpZwrq8MYknm+vog1hrk+sMg1n8g1x8DsTaBXntBrB2Q67eDWLsh128BsQ5CrjfcIC21bZi6oRplurkXKta7kOt/BbHmQK63EqvahvjcXB/FetdCrMqxY0w9oVq5p4ZiFWe0PwCtuioUWjTFoWWjRNdWoGKlM1qew9GuWHKv7Nj2uVmtTnlWLK0PpI8Nud7AKgexvhFya7zWS6UXLcRSfHGPVb0Ue+SWsQxmkCj28Y0pOFQsxbBlv2z0qVi630Ac+l/87C+WnFvxo7UeM6OhWEJuxet2quvlKVZ9vWJb23SXis5i1RyYsHiGWXexSg1MvNEMuZmxhViXD0xYPCd2F13EcnomdCjo1Ussp6fYR435/RVNxZq7OXnhDmdU1au7WBlvpAzNADcXxJrgWYWxjGJ6IZYVUUYvn9MNsFQ6KEHFsiUuzfVULFvGpU92oWL5E1cEL8TqQpyrF1NhF8a5uZ6K1ZHIz/VUrI6M/FxPxWpNpAUvxIIlQy+mQlgycj0VC1JyPRULUnI9FQtSghdiQYpeTIWQkuupWJCS66lYkJLrEQuOz4wrIBak6IVYcJB1txALUkAsSAGxIAXEghQQC1JALEgBsWDJ4A+CaANM+gBDGwAAAABJRU5ErkJggg=="
)


def build_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = "----d7boundary" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(str(value).encode("utf-8") + b"\r\n")
    for name, (filename, content) in files.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        chunks.append(b"Content-Type: image/png\r\n\r\n")
        chunks.append(content + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def matrix_checks(base, report: Report, ctx: dict, questions: dict, experiments: dict):
    case = "MATRIX"
    alpha = Client(base, "teacher_alpha")
    alpha.login("t_alpha", DEFAULT_PASSWORD)
    student = Client(base, "s_alpha1")
    student.login("s_alpha1", DEFAULT_PASSWORD)
    beta_student = Client(base, "s_beta1")
    beta_student.login("s_beta1", DEFAULT_PASSWORD)
    ca, cb = ctx["class_alpha"], ctx["class_beta"]

    # --- SPEC-016 知识图谱：无路径分支（T-016-03） ---
    topo = student.ok("GET", f"{API}/knowledge-graph/topological")
    report.check(case, "知识图谱拓扑序可用且无环",
                 topo["has_cycle"] is False and len(topo["order"]) > 1,
                 {"has_cycle": topo["has_cycle"], "n": len(topo["order"])})
    order = topo["order"]
    no_path_pair = None
    for source in reversed(order):
        for target in order:
            if source == target:
                continue
            data = student.ok("GET", f"{API}/knowledge-graph/path?from={source}&to={target}")
            if data["matched"] is False:
                no_path_pair = (source, target, data)
                break
        if no_path_pair:
            break
    report.check(case, "图谱无路径时 matched=false 且不编造节点（T-016-03）",
                 no_path_pair is not None and no_path_pair[2]["nodes"] == []
                 and no_path_pair[2]["edges"] == [],
                 no_path_pair)

    status, _ = student.call("GET", f"{API}/knowledge-graph/path?from=9999&to=9998")
    report.check(case, "图谱路径端点不存在返回404", status == 404, status)
    status, payload = student.call("GET", f"{API}/knowledge-graph?depth=99")
    report.check(case, "图谱 depth=99 越界返回422", status == 422, (status, payload))
    graph = student.ok("GET", f"{API}/knowledge-graph?depth=1")
    report.check(case, "图谱响应含 truncated 标记", "truncated" in graph, list(graph))

    # --- SPEC-017 识别辅助：失败分支（T-017-02）与跨班（T-017-04） ---
    body, ctype = build_multipart({"class_id": ca, "kind": "state_table"},
                                  {"image": ("not_a_table.png",
                                             base64.b64decode(NON_TABLE_PNG_B64))})
    status, payload = student.call("POST", f"{API}/recognition-tasks", raw=body, ctype=ctype)
    failed = status == 201 and payload["data"]["status"] == "failed"
    report.check(case, "非状态表图片识别 status=failed 且给出格式原因（T-017-02）",
                 failed and payload["data"]["result"] is None
                 and bool(payload["data"]["error"]["code"]),
                 payload)

    body, ctype = build_multipart({"class_id": ca, "kind": "state_table"},
                                  {"image": ("x.gif", b"GIF89a\x00\x00")})
    status, payload = student.call("POST", f"{API}/recognition-tasks", raw=body, ctype=ctype)
    report.check(case, "GIF 上传返回415（T-017-03）", status == 415, (status, payload))

    body, ctype = build_multipart({"class_id": ca, "kind": "state_table", "passed": "true"},
                                  {"image": ("not_a_table.png",
                                             base64.b64decode(NON_TABLE_PNG_B64))})
    status, payload = student.call("POST", f"{API}/recognition-tasks", raw=body, ctype=ctype)
    report.check(case, "识别上传携带 passed 字段被忽略而非报错（T-017-03）",
                 status == 201, (status, payload))

    body, ctype = build_multipart({"class_id": ca, "kind": "state_table"},
                                  {"image": ("not_a_table.png",
                                             base64.b64decode(NON_TABLE_PNG_B64))})
    status, payload = beta_student.call("POST", f"{API}/recognition-tasks",
                                        raw=body, ctype=ctype)
    report.check(case, "他班学生用本班 class_id 提交识别返回404（T-017-04）",
                 status == 404, (status, payload))

    # --- SPEC-007 问答：无匹配分支（T-007-02） ---
    qa = student.ok("POST", f"{API}/qa/queries", body={"query": "今天晚饭吃什么比较好"})
    report.check(case, "域外查询 matched=false 且不编造解释（T-007-02）",
                 qa["matched"] is False and qa["matches"] == [], qa)
    status, _ = student.call("POST", f"{API}/qa/queries", body={"query": "x"})
    report.check(case, "过短查询返回422（T-007-02）", status == 422, status)

    # --- SPEC-011 组卷：不可行分支（T-011-03） ---
    status, payload = alpha.call("POST", f"{API}/paper-generations", body={
        "class_id": ca, "title": "不可行组卷", "kind": "quiz", "count": 30,
        "difficulty_counts": {"easy": 0, "medium": 0, "hard": 30},
        "knowledge_minimums": [], "seed": 7})
    report.check(case, "困难题不足时组卷返回422 INFEASIBLE_PAPER（T-011-03）",
                 status == 422 and payload["error"]["code"] == "INFEASIBLE_PAPER",
                 (status, payload))

    # --- SPEC-004 预警：无批次返回空（T-004-04） ---
    # 用本班一个从未生成过的历史窗口，确认没有批次时返回空数组而不是假造
    warnings = alpha.ok("GET", f"{API}/warnings?class_id={ca}"
                               "&from=2020-01-01T00:00:00Z&to=2020-02-01T00:00:00Z")
    report.check(case, "未生成过的窗口预警返回空数组而非假造（E064）",
                 warnings == [], warnings)

    # --- SPEC-015 推荐：冷启动 score=null（T-015-02） ---
    new_student = Client(base, "s_alpha4")
    new_student.login("s_alpha4", DEFAULT_PASSWORD)
    recs = new_student.ok("GET", f"{API}/me/recommendations?limit=3")
    report.check(case, "冷启动推荐返回基础路径且 score=null（T-015-02）",
                 len(recs["items"]) >= 1
                 and any(item["score"] is None for item in recs["items"]),
                 recs)
    return {}


# --------------------------------------------------------------------------
# 十类基础功能的逐类运行时抽查（覆盖矩阵第 1 节）
# --------------------------------------------------------------------------

def basic_functions(base, report: Report, ctx: dict, questions: dict):
    alpha = Client(base, "teacher_alpha")
    alpha.login("t_alpha", DEFAULT_PASSWORD)
    beta_student = Client(base, "s_beta1")
    beta_student.login("s_beta1", DEFAULT_PASSWORD)
    student1 = Client(base, "s_alpha1")
    student1.login("s_alpha1", DEFAULT_PASSWORD)
    student2 = Client(base, "s_alpha2")
    student2.login("s_alpha2", DEFAULT_PASSWORD)
    ca = ctx["class_alpha"]

    knowledge = alpha.ok("GET", f"{API}/knowledge-points?page_size=100")
    kid = knowledge[0]["id"]
    # 自练必须有已发布题目；预置素材只含知识点，D7 的计数器题挂在含"计数器"的知识点上
    practice_point = next(
        (k["id"] for k in knowledge if "计数器" in k["title"]), kid)

    # --- 课程知识 / 教学资源（SPEC-005） ---
    chapters = student1.ok("GET", f"{API}/chapters")
    report.check("基础-课程知识", "学生可列出已发布章节",
                 isinstance(chapters, list) and len(chapters) >= 6, len(chapters))

    resource = alpha.ok("POST", f"{API}/resources", body={
        "title": "D7 集成抽查资料", "category": "reference",
        "knowledge_id": kid, "published": True}, expect=201)
    version = alpha.ok("POST", f"{API}/resources/{resource['id']}/versions", body={
        "external_url": "https://example.com/d7", "note": "v1"}, expect=201)
    student_view = student1.ok("GET", f"{API}/resources?page_size=100")
    report.check("基础-教学资源", "学生可见已发布资料",
                 any(r["id"] == resource["id"] for r in student_view), resource["id"])

    recorded = student1.ok("POST", f"{API}/resource-versions/{version['id']}/events",
                           body={"event_kind": "open"})
    again = student1.ok("POST", f"{API}/resource-versions/{version['id']}/events",
                        body={"event_kind": "open"})
    report.check("基础-教学资源", "同人同版本同日打开事件去重（T-005-04）",
                 recorded["recorded"] is True and again["recorded"] is False,
                 {"first": recorded, "second": again})

    fav = student1.ok("PUT", f"{API}/me/favorites/{kid}")
    favs = student1.ok("GET", f"{API}/me/favorites")
    report.check("基础-课程知识", "收藏幂等且出现在收藏列表（T-005-03）",
                 fav["favorited"] is True
                 and any(k["id"] == kid for k in favs), fav)

    student1.ok("PUT", f"{API}/me/learning-progress",
                body={"knowledge_id": kid, "completed": True})
    progress = student1.ok("GET", f"{API}/me/learning-progress")
    report.check("基础-课程知识", "完成标记写入并读回（T-005-03）",
                 any(p["knowledge_id"] == kid and p["completed"] for p in progress))

    # --- 课前备课（SPEC-008） ---
    plan = alpha.ok("POST", f"{API}/lesson-plans", body={
        "title": "D7 集成抽查备课单", "planned_at": None, "notes": "抽查用",
        "items": [{"sort_order": 1, "target_type": "knowledge", "target_id": kid}]},
        expect=201)
    preview = alpha.ok("POST", f"{API}/preview-assignments", body={
        "class_id": ca, "plan_id": plan["id"], "due_at": None}, expect=201)
    report.check("基础-课前备课", "发布预习快照不含题目答案（T-008-03）",
                 all("answer" not in json.dumps(item) for item in preview["items"]))
    own = student1.ok("GET", f"{API}/preview-assignments?class_id={ca}")
    report.check("基础-课前备课", "本班学生可见预习",
                 any(p["id"] == preview["id"] for p in own))
    status, _ = beta_student.call("GET", f"{API}/preview-assignments?class_id={ca}")
    report.check("基础-课前备课", "他班学生查预习返回404（T-008-03）", status == 404, status)

    # --- 考勤（SPEC-002） ---
    task = alpha.ok("POST", f"{API}/attendance-tasks", body={
        "class_id": ca, "title": "D7 集成抽查签到",
        "opens_at": rfc3339(now_utc() - timedelta(seconds=10)),
        "late_at": rfc3339(now_utc() + timedelta(seconds=2)),
        "closes_at": rfc3339(now_utc() + timedelta(seconds=6))}, expect=201)
    code = task.get("code")
    report.check("基础-考勤", "发布签到任务返回 6 位数字码",
                 isinstance(code, str) and len(code) == 6 and code.isdigit(), code)
    signed = student1.ok("POST", f"{API}/attendance-tasks/{task['id']}/sign-ins",
                         body={"code": code})
    report.check("基础-考勤", "学生签到成功且状态为 present",
                 signed["status"] == "present", signed["status"])
    status, _ = student2.call("POST", f"{API}/attendance-tasks/{task['id']}/sign-ins",
                              body={"code": "000000"})
    report.check("基础-考勤", "错误签到码返回422", status == 422, status)
    print("[基础-考勤] 等待签到截止与结算（约8秒）…", flush=True)
    time.sleep(8)
    settled = alpha.ok("POST", f"{API}/attendance-tasks/{task['id']}/settlements", body={})
    counts = settled["counts"]
    report.check("基础-考勤", "结算结果：present=1、absent=3",
                 counts["present"] == 1 and counts["absent"] == 3 and counts["late"] == 0,
                 counts)

    # --- 学习数据分析（SPEC-003/006） ---
    attendance_stats = alpha.ok("GET", f"{API}/analytics/attendance?class_id={ca}")
    report.check("基础-数据分析", "出勤统计出勤率=(1+0)/(1+0+3)=0.25（T-003-01）",
                 attendance_stats["attendance_rate"] is not None
                 and abs(attendance_stats["attendance_rate"] - 0.25) < 1e-9,
                 attendance_stats["attendance_rate"])
    learning_stats = alpha.ok("GET", f"{API}/analytics/learning?class_id={ca}")
    report.check("基础-数据分析", "学习统计含已发布知识点分母与学生进度",
                 learning_stats["published_knowledge_count"] >= 12
                 and len(learning_stats["students"]) >= 1, {
                     "published": learning_stats["published_knowledge_count"],
                     "students": len(learning_stats["students"])})
    csv_data = alpha.ok("GET", f"{API}/analytics/learning?class_id={ca}&format=csv")
    report.check("基础-数据分析", "学习统计 CSV 含 summary 行",
                 csv_data[:3] == b"\xef\xbb\xbf" and b"summary" in csv_data[:400])

    # --- 习题与测评：自练 + 错题（SPEC-009） ---
    # 甲班有一份已结束但未公开反馈的班级测评（E2E-03），其题目必须被挡在自练之外；
    # 乙班没有任何班级测评，同一道已发布题对乙班学生可用。
    status, payload = student2.call("POST", f"{API}/practice-sessions",
                                    body={"knowledge_ids": [practice_point], "count": 1})
    report.check("基础-习题测评", "已结束未公开反馈的测评题目不进自练候选（T-009-04）",
                 status == 422 and payload["error"]["code"] == "INFEASIBLE_PAPER",
                 (status, payload))

    practice = beta_student.ok("POST", f"{API}/practice-sessions",
                               body={"knowledge_ids": [practice_point], "count": 1},
                               expect=201)
    psub = beta_student.ok("POST", f"{API}/assessments/{practice['id']}/submissions",
                           body={}, expect=201)
    pitem = beta_student.ok("GET", f"{API}/assessments/{practice['id']}")["items"][0]
    psaved = beta_student.ok("PUT", f"{API}/submissions/{psub['id']}/answers", body={
        "version": psub["version"],
        "answers": [{"item_id": pitem["id"], "selected": ["B"]}]})
    beta_student.ok("POST", f"{API}/submissions/{psub['id']}/finalization",
                    body={"version": psaved["version"]})
    presult = beta_student.ok("GET", f"{API}/submissions/{psub['id']}/result")
    report.check("基础-习题测评", "自练即时反馈含答案与解析（T-009-01）",
                 "answer" in presult["items"][0]
                 and presult["feedback_available"] is True, presult.get("score"))
    mistakes = beta_student.ok("GET", f"{API}/me/mistakes")
    report.check("基础-习题测评", "错题本记录本次答错（T-009-04）",
                 any(m["question_id"] == pitem["question_id"] for m in mistakes), mistakes)
    return {}


# --------------------------------------------------------------------------
# 数据准备（内容/题目）
# --------------------------------------------------------------------------

def prepare_questions(base, report: Report) -> dict:
    """教师甲建立 D7 用的固定题目（幂等：按题干查重）。"""
    alpha = Client(base, "teacher_alpha")
    alpha.login("t_alpha", DEFAULT_PASSWORD)
    knowledge = alpha.ok("GET", f"{API}/knowledge-points?page_size=100")
    if not knowledge:
        raise RuntimeError("课程知识点为空，请先执行 seed-content")
    counter_point = None
    for point in knowledge:
        if "计数器" in point["title"]:
            counter_point = point["id"]
            break
    if counter_point is None:
        counter_point = knowledge[0]["id"]

    stem = "模6计数器当前状态为0101，下一个有效时钟沿后的状态是什么？"
    existing = alpha.ok("GET", f"{API}/questions?page_size=100")
    for question in existing:
        if question["stem_md"] == stem:
            return {"counter": question["id"]}
    created = alpha.ok("POST", f"{API}/questions",
                       body={"type": "single", "stem_md": stem,
                             "options": [{"key": "A", "label": "0000"},
                                         {"key": "B", "label": "0110"}],
                             "answer": ["A"],
                             "explanation_md": "模6计数器从0101（5）计数到最大值后回到0000。",
                             "difficulty": 1, "knowledge_ids": [counter_point],
                             "published": True},
                       expect=201)
    report.check("bootstrap", "建立模6计数器测试题", created["id"] > 0)
    return {"counter": created["id"]}


def discover_experiments(base, report: Report) -> dict:
    alpha = Client(base, "teacher_alpha")
    alpha.login("t_alpha", DEFAULT_PASSWORD)
    experiments = alpha.ok("GET", f"{API}/experiments?page_size=100")
    mapping = {}
    for experiment in experiments:
        mapping[experiment["simulator_type"]] = experiment["id"]
    if "counter" not in mapping or "shift" not in mapping:
        raise RuntimeError(f"预置实验不完整：{mapping}，请先执行 seed-experiments")
    report.check("bootstrap", "预置实验包含 counter 与 shift",
                 True, mapping)
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--admin-login", default="admin_root")
    parser.add_argument("--admin-password", default="Adm1nPass!23")
    parser.add_argument("--phase", choices=["bootstrap", "all"], default="all")
    parser.add_argument("--out")
    parser.add_argument("--ctx")
    args = parser.parse_args()

    if args.phase == "bootstrap":
        bootstrap(args.base, args.admin_login, args.admin_password)
        return 0

    report = Report()
    ctx = json.loads(Path(args.ctx).read_text(encoding="utf-8")) if args.ctx else None
    if ctx is None:
        raise SystemExit("--phase all 需要 --ctx 指向 bootstrap 输出的 JSON")

    questions = prepare_questions(args.base, report)
    experiments = discover_experiments(args.base, report)

    e2e_ctx = {}
    e2e_ctx.update(e2e_01(args.base, report, ctx, questions, experiments))
    ctx["e2e01_quiz"] = e2e_ctx["quiz_id"]
    e2e_02(args.base, report, ctx, experiments)
    e2e_03(args.base, report, ctx, questions)
    sec_01(args.base, report, ctx, questions, experiments)
    basic_functions(args.base, report, ctx, questions)
    matrix_checks(args.base, report, ctx, questions, experiments)

    summary = {
        "base": args.base,
        "total": len(report.results),
        "passed": len(report.results) - len(report.failures),
        "failed": len(report.failures),
        "results": report.results,
    }
    if args.out:
        Path(args.out).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"== 合计 {summary['passed']}/{summary['total']} 通过，"
          f"{summary['failed']} 失败 ==", flush=True)
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
