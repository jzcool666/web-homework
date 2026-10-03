"""Private behavioral checks, independently derived from TI truth tables.

Both grading adapters consume these vectors; never generate expected outputs
by running the submitted circuit or the TTL engine.
"""

from copy import deepcopy
from .lab_catalog import profile

SUITE_VERSION = "behavior-1"


def suite(code):
    task = profile(code)
    defaults = {
        p["label"]: "0" * p["width"] for p in task["ports"] if p["direction"] == "input"
    }
    defaults.update(CLR_N="1")
    if code == "LAB-D":
        defaults["PRE_N"] = "1"
    if code == "LAB-C6":
        defaults["EN"] = "1"
    cases = []

    def case():
        rows = []
        cases.append(dict(set_id=len(cases) + 1, steps=rows))
        return rows, deepcopy(defaults)

    def add(rows, inputs, value=None, **changes):
        inputs.update({k: str(v) for k, v in changes.items()})
        width = next(p["width"] for p in task["ports"] if p["label"] == "Q")
        rows.append(
            dict(
                inputs=deepcopy(inputs),
                expected={} if value is None else dict(Q=format(value, f"0{width}b")),
                scored=value is not None,
            )
        )

    def start():
        rows, i = case()
        add(rows, i, None, CLR_N=0, CLK=0)
        add(rows, i, 0)
        add(rows, i, 0, CLR_N=1)
        return rows, i

    if code == "LAB-D":
        rows, i = start()
        for changes, q in [
            (dict(D=1), 0),
            (dict(CLK=1), 1),
            (dict(D=0), 1),
            (dict(CLK=0), 1),
            (dict(CLK=1), 0),
            (dict(PRE_N=0), 1),
            (dict(PRE_N=1), 1),
            (dict(CLR_N=0), 0),
            (dict(CLR_N=1, CLK=0), 0),
        ]:
            add(rows, i, q, **changes)
        rows, i = start()
        old = 0
        for d in [1, 1, 0, 1, 0]:
            add(rows, i, old, CLK=0, D=d)
            add(rows, i, d, CLK=1)
            old = d
    elif code == "LAB-C6":
        rows, i = start()
        old = 0
        for q in [1, 2, 3, 4, 5]:
            add(rows, i, old, CLK=0)
            add(rows, i, q, CLK=1)
            old = q
        for _ in range(2):
            add(rows, i, 5, CLK=0, EN=0)
            add(rows, i, 5, CLK=1)
        for q in [0, 1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 5, 0]:
            add(rows, i, old, CLK=0, EN=1)
            add(rows, i, q, CLK=1)
            old = q
        add(rows, i, 0, CLR_N=0)
        rows, i = start()
        for _ in range(3):
            add(rows, i, 0, EN=0, CLK=0)
            add(rows, i, 0, CLK=1)
    elif code == "LAB-S4":
        rows, i = start()
        old = 0
        for controls, q in [
            (dict(S1=1, S0=1, P="1010"), 10),
            (dict(S1=0, S0=0, P="0101"), 10),
            (dict(S1=0, S0=1, SR=1), 13),
            (dict(S1=0, S0=1, SR=0), 6),
            (dict(S1=1, S0=0, SL=1), 13),
            (dict(S1=1, S0=1, P="0011"), 3),
            (dict(S1=1, S0=0, SL=0), 6),
            (dict(S1=0, S0=1, SR=1), 11),
        ]:
            add(rows, i, old, CLK=0, **controls)
            add(rows, i, q, CLK=1)
            old = q
        add(rows, i, 0, CLR_N=0)
        rows, i = start()
        add(rows, i, 0, CLK=0, S1=1, S0=1, P="1111")
        add(rows, i, 15, CLK=1)
        old = 15
        for q in [7, 3, 1, 0]:
            add(rows, i, old, CLK=0, S1=0, S0=1, SR=0)
            add(rows, i, q, CLK=1)
            old = q
    else:
        rows, i = start()
        old = 0
        for q in [1, 3, 2, 0] * 3:
            add(rows, i, old, CLK=0)
            add(rows, i, q, CLK=1)
            old = q
        rows, i = start()
        add(rows, i, 1, CLK=1)
        add(rows, i, 0, CLR_N=0)
        add(rows, i, 0, CLR_N=1, CLK=0)
        add(rows, i, 1, CLK=1)
    return dict(suite_version=SUITE_VERSION, task_code=code, cases=cases)


def switch_values(task, inputs):
    values = {}
    for t in task["board"]["terminals"]:
        if t["kind"] == "switch":
            values[t["id"]] = int(inputs[t["port"]][-1 - t["bit"]])
    return values


def grade_wiring(task, board, tests):
    from .lab_engine import Circuit, LabError

    total = passed = 0
    first = None
    for case in tests["cases"]:
        b = deepcopy(board)
        b.update(power=True, clock=0, switches={})
        circuit = Circuit(task, b)
        for row in case["steps"]:
            state = circuit.evaluate(
                clock=int(row["inputs"]["CLK"]),
                switches=switch_values(task, row["inputs"]),
            )
            if state["status"] == "blocked":
                raise LabError("接线结构无效", "CIRCUIT_INVALID")
            if row["scored"]:
                total += 1
                correct = state["outputs"] == row["expected"]
                passed += int(correct)
                if not correct and first is None:
                    first = dict(
                        checkpoint=total,
                        inputs=row["inputs"],
                        expected=row["expected"],
                        actual=state["outputs"],
                        reason="输出与任务要求不符",
                    )
    if not total:
        raise LabError("测试集没有计分点")
    return dict(
        passed_checkpoints=passed,
        total_checkpoints=total,
        score=round(100 * passed / total, 2),
        passed=passed == total,
        first_failure=first,
    )
