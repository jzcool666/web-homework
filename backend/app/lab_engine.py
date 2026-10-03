"""Single authoritative, bounded, discrete TTL netlist engine.

No Flask/DB and no changes to the old synchronous teaching simulator.
All flip-flops sample the same pre-edge network, then outputs settle together.
"""

from copy import deepcopy
import time

from .lab_catalog import MODELS


class LabError(ValueError):
    def __init__(self, message, code="CIRCUIT_INVALID"):
        super().__init__(message)
        self.code = code


def _not(value):
    return 1 - value if value in (0, 1) else "X"


def _gate(kind, values):
    if kind == "not":
        return _not(values[0])
    if kind in ("and", "nand"):
        value = 0 if 0 in values else 1 if all(v == 1 for v in values) else "X"
        return _not(value) if kind == "nand" else value
    return 1 if 1 in values else 0 if all(v == 0 for v in values) else "X"


class Circuit:
    def __init__(self, task, board, timeout=1.0):
        self.task, self.board = task, deepcopy(board)
        self.deadline = time.monotonic() + timeout
        self.chips = {c["id"]: MODELS[c["model"]] for c in task["board"]["chips"]}
        self.terminals = {t["id"]: t for t in task["board"]["terminals"]}
        self.parent = {
            f"chip:{c}:{p['number']}": f"chip:{c}:{p['number']}"
            for c, m in self.chips.items()
            for p in m["pins"]
        }
        self.parent.update({f"terminal:{t}": f"terminal:{t}" for t in self.terminals})
        if len(board["wires"]) > 256:
            raise LabError("导线超过256条", "LAB_LIMIT_EXCEEDED")
        for w in board["wires"]:
            if w["from"] not in self.parent or w["to"] not in self.parent:
                raise LabError("导线端点不存在")
            self.parent[self.root(w["from"])] = self.root(w["to"])
        self.linked = {w[k] for w in board["wires"] for k in ("from", "to")}
        self.units = [
            (c, u)
            for c, m in self.chips.items()
            for u in m["units"]
            if any(f"chip:{c}:{p}" in self.linked for p in u["output_pins"])
        ]
        self.active_chips = {c for c, u in self.units}
        self.q = {
            (c, u["id"]): ["X"] * (1 if u["kind"] == "dff" else 4)
            for c, u in self.units
            if u["kind"] in ("dff", "counter", "shift")
        }
        self.diagnostics, self.values = [], {}
        self.previous_clock = 0
        gates = [
            (c, u) for c, u in self.units if u["kind"] in ("and", "nand", "or", "not")
        ]
        self.combination_cycle = []
        producers = {
            self.root(f"chip:{c}:{p}"): i
            for i, (c, u) in enumerate(gates)
            for p in u["output_pins"]
        }
        dependencies = {
            i: {
                producers[self.root(f"chip:{c}:{p}")]
                for p in u["input_pins"]
                if self.root(f"chip:{c}:{p}") in producers
            }
            for i, (c, u) in enumerate(gates)
        }
        while dependencies:
            ready = {i for i, deps in dependencies.items() if not deps}
            if not ready:
                self.combination_cycle = [
                    f"chip:{gates[i][0]}:{p}"
                    for i in dependencies
                    for p in gates[i][1]["output_pins"]
                ]
                break
            dependencies = {
                i: deps - ready for i, deps in dependencies.items() if i not in ready
            }

    def root(self, endpoint):
        while self.parent[endpoint] != endpoint:
            self.parent[endpoint] = self.parent[self.parent[endpoint]]
            endpoint = self.parent[endpoint]
        return endpoint

    def check_time(self):
        if time.monotonic() > self.deadline:
            raise LabError("实验重放超时", "LAB_SIMULATION_TIMEOUT")

    def pin(self, c, p):
        return self.values.get(self.root(f"chip:{c}:{p}"), "Z")

    def _diagnose(self, code, message, endpoints):
        item = dict(code=code, message=message, endpoints=endpoints)
        if item not in self.diagnostics:
            self.diagnostics.append(item)

    def _sources(self, outputs):
        drivers = {}

        def drive(endpoint, value):
            drivers.setdefault(self.root(endpoint), []).append((endpoint, value))

        for id, t in self.terminals.items():
            if t["kind"] == "probe":
                continue
            v = (
                (1 if id == "VCC" else 0)
                if t["kind"] == "rail"
                else self.board["clock"]
                if t["kind"] == "clock"
                else self.board["switches"].get(id, 0)
            )
            drive(f"terminal:{id}", v)
        for endpoint, v in outputs.items():
            drive(endpoint, v)
        values = {}
        for node, items in drivers.items():
            if len(items) > 1:
                values[node] = "X"
                self._diagnose(
                    "MULTIPLE_DRIVERS",
                    "多个主动输出或电源连接在同一节点",
                    [p for p, v in items],
                )
            else:
                values[node] = items[0][1]
        return values

    def _powered(self, c):
        m = self.chips[c]
        power = next(p["number"] for p in m["pins"] if p["direction"] == "power")
        ground = next(p["number"] for p in m["pins"] if p["direction"] == "ground")
        ok = self.pin(c, power) == 1 and self.pin(c, ground) == 0
        if not ok:
            self._diagnose(
                "POWER_MISSING",
                "芯片VCC/GND未正确连接",
                [f"chip:{c}:{power}", f"chip:{c}:{ground}"],
            )
        return ok

    def _outputs(self):
        outputs = {}
        for c, u in self.units:
            kind = u["kind"]
            q = self.q.get((c, u["id"]))
            if not self._powered(c):
                bits = ["X"] * len(u["output_pins"])
            elif kind in ("and", "nand", "or", "not"):
                bits = [_gate(kind, [self.pin(c, p) for p in u["input_pins"]])]
            elif kind == "dff":
                bits = [q[0], _not(q[0])]
            elif kind == "counter":
                bits = [q[3], q[2], q[1], q[0], _gate("and", [self.pin(c, 10), *q])]
            else:
                bits = list(reversed(q))  # q is QA,QB,QC,QD; DIP output order QD..QA
            outputs.update({f"chip:{c}:{p}": v for p, v in zip(u["output_pins"], bits)})
        return outputs

    def _async(self):
        for c, u in self.units:
            kind = u["kind"]
            key = (c, u["id"])
            if kind not in ("dff", "counter", "shift") or not self._powered(c):
                continue
            clr = self.pin(c, u["input_pins"][0])
            if kind == "dff":
                pre = self.pin(c, u["input_pins"][3])
                if clr == 0 and pre == 0:
                    self.q[key] = ["X"]
                    self._diagnose(
                        "CONTROL_CONFLICT",
                        "PRE_N和CLR_N不能同时为低",
                        [
                            f"chip:{c}:{p}"
                            for p in (u["input_pins"][0], u["input_pins"][3])
                        ],
                    )
                elif clr == 0:
                    self.q[key] = [0]
                elif pre == 0:
                    self.q[key] = [1]
                elif clr not in (0, 1) or pre not in (0, 1):
                    self.q[key] = ["X"]
            elif clr == 0:
                self.q[key] = [0] * 4
            elif clr not in (0, 1):
                self.q[key] = ["X"] * 4

    def settle(self):
        self.values = self._sources({})
        # Power validity is checked after known rails are present, before outputs.
        for _ in range(64):
            self.check_time()
            old = dict(self.values)
            oldq = deepcopy(self.q)
            self.values = self._sources(self._outputs())
            self._async()
            if old == self.values and oldq == self.q:
                return
        self._diagnose(
            "OSCILLATION",
            "组合反馈在64轮内未稳定",
            [f"chip:{c}:{p}" for c, u in self.units for p in u["output_pins"]],
        )
        for c, u in self.units:
            for p in u["output_pins"]:
                self.values[self.root(f"chip:{c}:{p}")] = "X"

    def evaluate(self, clock=None, switches=None):
        self.check_time()
        self.diagnostics = []
        if clock is not None:
            self.board["clock"] = clock
        if switches is not None:
            self.board["switches"].update(switches)
        if not self.board["power"]:
            return dict(
                status="off",
                pins={p: "Z" for p in self.parent},
                outputs={
                    p["label"]: "Z" * p["width"]
                    for p in self.task["ports"]
                    if p["direction"] == "output"
                },
                diagnostics=[],
            )
        self.settle()
        if self.combination_cycle:
            self._diagnose(
                "COMBINATIONAL_LOOP",
                "本实验不支持纯组合反馈，请检查门输出回接",
                self.combination_cycle,
            )
        snapshot = dict(self.values)
        nextq = deepcopy(self.q)
        for c, u in self.units:
            kind = u["kind"]
            key = (c, u["id"])
            if kind not in ("dff", "counter", "shift") or not self._powered(c):
                continue
            cp = u["input_pins"][2] if kind == "dff" else 2 if kind == "counter" else 11
            if self.root(f"chip:{c}:{cp}") != self.root("terminal:CLK"):
                self._diagnose(
                    "CLOCK_UNSUPPORTED",
                    "活动时序单元CLK必须直接接箱CLK",
                    [f"chip:{c}:{cp}"],
                )
                continue
            if self.previous_clock != 0 or self.board["clock"] != 1:
                continue
            get = lambda p: snapshot.get(self.root(f"chip:{c}:{p}"), "Z")
            if get(u["input_pins"][0]) != 1:
                continue
            if kind == "dff":
                if get(u["input_pins"][3]) == 1:
                    nextq[key] = [
                        get(u["input_pins"][1])
                        if get(u["input_pins"][1]) in (0, 1)
                        else "X"
                    ]
            elif kind == "counter":
                if get(9) == 0:
                    nextq[key] = [
                        get(p) if get(p) in (0, 1) else "X" for p in (3, 4, 5, 6)
                    ]
                elif get(9) == 1 and get(7) == 1 and get(10) == 1:
                    value = (
                        sum(b << i for i, b in enumerate(self.q[key]))
                        if all(b in (0, 1) for b in self.q[key])
                        else None
                    )
                    nextq[key] = (
                        [((value + 1) & 15) >> i & 1 for i in range(4)]
                        if value is not None
                        else ["X"] * 4
                    )
                elif (
                    get(9) not in (0, 1)
                    or get(7) not in (0, 1)
                    or get(10) not in (0, 1)
                ):
                    nextq[key] = ["X"] * 4
            else:
                s = (get(10), get(9))
                q = self.q[key]
                if s == (1, 1):
                    nextq[key] = [
                        get(p) if get(p) in (0, 1) else "X" for p in (3, 4, 5, 6)
                    ]
                elif s == (0, 1):
                    nextq[key] = [get(2), *q[:3]]
                elif s == (1, 0):
                    nextq[key] = [*q[1:], get(7)]
                elif s != (0, 0):
                    nextq[key] = ["X"] * 4
        self.q = nextq
        self.settle()
        self.previous_clock = self.board["clock"]
        for c, u in self.units:
            for p in u["input_pins"]:
                if self.pin(c, p) == "Z":
                    self._diagnose(
                        "INPUT_FLOATING", "活动单元输入未连接", [f"chip:{c}:{p}"]
                    )
        pins = {p: self.values.get(self.root(p), "Z") for p in self.parent}
        outputs = {}
        for p in self.task["ports"]:
            if p["direction"] == "output":
                bits = {
                    t["bit"]: pins[f"terminal:{id}"]
                    for id, t in self.terminals.items()
                    if t["kind"] == "probe" and t["port"] == p["label"]
                }
                outputs[p["label"]] = "".join(
                    str(bits[b]) for b in reversed(range(p["width"]))
                )
                if "Z" in outputs[p["label"]]:
                    self._diagnose(
                        "OUTPUT_FLOATING",
                        "输出探针未连接",
                        [
                            f"terminal:{id}"
                            for id, t in self.terminals.items()
                            if t["kind"] == "probe" and t["port"] == p["label"]
                        ],
                    )
        return dict(
            status="blocked" if self.diagnostics else "ready",
            pins=pins,
            outputs=outputs,
            diagnostics=deepcopy(self.diagnostics),
        )


def empty_board():
    return dict(wires=[], switches={}, power=False, clock=0)


def apply_board_action(task, board, op, payload):
    board = deepcopy(board)
    fields = {
        "connect": {"from", "to"},
        "disconnect": {"wire_id"},
        "set_switch": {"terminal_id", "value"},
        "set_clock": {"value"},
        "power": {"on"},
        "reset": set(),
    }
    if op not in fields or not isinstance(payload, dict) or set(payload) != fields[op]:
        raise LabError("动作或字段不合法", "VALIDATION_ERROR")
    if op in ("connect", "disconnect") and board["power"]:
        raise LabError("请先关电再改线", "STATE_CONFLICT")
    if op == "connect":
        endpoints = Circuit(task, board).parent
        a, b = payload["from"], payload["to"]
        if (
            not isinstance(a, str)
            or not isinstance(b, str)
            or a not in endpoints
            or b not in endpoints
            or a == b
        ):
            raise LabError("导线端点不合法", "VALIDATION_ERROR")
        id = "--".join(sorted((a, b)))
        if any(w["id"] == id for w in board["wires"]):
            raise LabError("导线已存在", "DUPLICATE")
        if len(board["wires"]) >= 256:
            raise LabError("导线超过256条", "LAB_LIMIT_EXCEEDED")
        board["wires"].append(dict(id=id, **payload))
    elif op == "disconnect":
        if not any(w["id"] == payload["wire_id"] for w in board["wires"]):
            raise LabError("导线不存在", "NOT_FOUND")
        board["wires"] = [w for w in board["wires"] if w["id"] != payload["wire_id"]]
    elif op in ("set_switch", "set_clock"):
        v = payload["value"]
        if type(v) is not int or v not in (0, 1):
            raise LabError("逻辑值只能为整数0或1", "VALIDATION_ERROR")
        if op == "set_clock":
            if not board["power"]:
                raise LabError("请先开电", "STATE_CONFLICT")
            board["clock"] = v
        else:
            if payload["terminal_id"] not in {
                t["id"] for t in task["board"]["terminals"] if t["kind"] == "switch"
            }:
                raise LabError("开关不存在", "VALIDATION_ERROR")
            board["switches"][payload["terminal_id"]] = v
    elif op == "power":
        if type(payload["on"]) is not bool:
            raise LabError("on必须为布尔值", "VALIDATION_ERROR")
        board["power"] = payload["on"]
        if not board["power"]:
            board["clock"] = 0
    elif op == "reset":
        return empty_board()
    return board


def replay(task, events, timeout=1.0):
    if len(events) > 512:
        raise LabError("过程事件超过512条", "LAB_LIMIT_EXCEEDED")
    start = time.monotonic()
    board = empty_board()
    circuit = None
    trace = []
    state = Circuit(task, board).evaluate()
    for event in events:
        board = apply_board_action(task, board, event["op"], event["payload"])
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0:
            raise LabError("实验重放超时", "LAB_SIMULATION_TIMEOUT")
        if circuit is None or not board["power"]:
            circuit = Circuit(task, board, remaining)
        else:
            circuit.board = deepcopy(board)
            circuit.deadline = start + timeout
        state = circuit.evaluate()
        trace.append(
            dict(
                seq=event.get("seq", len(trace) + 1),
                op=event["op"],
                clock=board["clock"],
                outputs=state["outputs"],
                status=state["status"],
            )
        )
    state["trace"] = trace
    return board, state
