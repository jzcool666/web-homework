import copy
import pytest
from app.lab_catalog import CODES, profile, MODELS
from app.lab_engine import Circuit, LabError, empty_board, apply_board_action, replay
from app.lab_suites import suite, grade_wiring
from lab_fixtures import reference_board


@pytest.mark.parametrize("code", CODES)
def test_four_truth_table_suites(code):
    result = grade_wiring(profile(code), reference_board(code), suite(code))
    assert result["passed"] and result["score"] == 100
    assert result["total_checkpoints"] > 12


def test_counter_stops_at_five_and_returns_zero():
    task = profile("LAB-C6")
    board = reference_board("LAB-C6")
    board["power"] = True
    c = Circuit(task, board)
    c.evaluate(switches={"CLR_N": 0, "EN": 1})
    c.evaluate(switches={"CLR_N": 1})
    for i in range(1, 6):
        c.evaluate(clock=0)
        assert c.evaluate(clock=1)["outputs"]["Q"] == format(i, "04b")
    c.evaluate(clock=0, switches={"EN": 0})
    assert c.evaluate(clock=1)["outputs"]["Q"] == "0101"
    c.evaluate(clock=0, switches={"EN": 1})
    assert c.evaluate(clock=1)["outputs"]["Q"] == "0000"


def test_same_edge_samples_before_any_q_changes():
    task = profile("LAB-FSM")
    board = reference_board("LAB-FSM")
    board["power"] = True
    c = Circuit(task, board)
    c.units.reverse()
    c.evaluate(switches={"CLR_N": 0})
    c.evaluate(switches={"CLR_N": 1})
    for bits in ["01", "11", "10", "00"]:
        c.evaluate(clock=0)
        assert c.evaluate(clock=1)["outputs"]["Q"] == bits


def test_asynchronous_controls_and_high_clock_hold():
    board = reference_board("LAB-D")
    board["power"] = True
    c = Circuit(profile("LAB-D"), board)
    assert c.evaluate(switches={"CLR_N": 0, "PRE_N": 1})["outputs"]["Q"] == "0"
    c.evaluate(switches={"CLR_N": 1, "D": 1})
    assert c.evaluate(clock=1)["outputs"]["Q"] == "1"
    assert c.evaluate(switches={"D": 0})["outputs"]["Q"] == "1"
    assert c.evaluate(switches={"CLR_N": 0})["outputs"]["Q"] == "0"
    state = c.evaluate(switches={"PRE_N": 0})
    assert state["status"] == "blocked" and state["outputs"]["Q"] == "X"


@pytest.mark.parametrize("kind", ["power", "floating", "multiple", "wrongclock"])
def test_invalid_wiring_never_passes(kind):
    task = profile("LAB-D")
    board = reference_board("LAB-D")
    if kind in ("power", "floating"):
        pin = "chip:U1:14" if kind == "power" else "chip:U1:2"
        board["wires"] = [w for w in board["wires"] if pin not in (w["from"], w["to"])]
    elif kind == "multiple":
        board = apply_board_action(
            task, board, "connect", {"from": "terminal:VCC", "to": "terminal:GND"}
        )
    else:
        board["wires"] = [
            w for w in board["wires"] if "chip:U1:3" not in (w["from"], w["to"])
        ]
        board = apply_board_action(
            task, board, "connect", {"from": "terminal:D", "to": "chip:U1:3"}
        )
    with pytest.raises(LabError):
        grade_wiring(task, board, suite("LAB-D"))


def test_wrong_function_gets_score_and_first_failure():
    task = profile("LAB-D")
    board = reference_board("LAB-D")
    board["wires"] = [
        w for w in board["wires"] if "terminal:Q" not in (w["from"], w["to"])
    ]
    board = apply_board_action(
        task, board, "connect", {"from": "chip:U1:6", "to": "terminal:Q"}
    )
    result = grade_wiring(task, board, suite("LAB-D"))
    assert (
        not result["passed"]
        and result["score"] < 100
        and result["first_failure"]["checkpoint"] == 1
    )


def test_process_replay_power_cycle_and_strict_actions():
    task = profile("LAB-D")
    b = reference_board("LAB-D")
    events = [
        dict(op="connect", payload={"from": w["from"], "to": w["to"]})
        for w in b["wires"]
    ]
    events += [
        dict(op="set_switch", payload=dict(terminal_id="PRE_N", value=1)),
        dict(op="power", payload=dict(on=True)),
        dict(op="set_switch", payload=dict(terminal_id="CLR_N", value=1)),
        dict(op="set_switch", payload=dict(terminal_id="D", value=1)),
        dict(op="set_clock", payload=dict(value=1)),
    ]
    board, state = replay(task, events)
    assert state["outputs"]["Q"] == "1" and len(state["trace"]) == len(events)
    with pytest.raises(LabError):
        apply_board_action(
            task, board, "connect", {"from": "terminal:D", "to": "terminal:Q"}
        )
    with pytest.raises(LabError):
        apply_board_action(task, board, "set_clock", {"value": True})
    with pytest.raises(LabError):
        replay(task, events * 100)
    board, state = replay(
        task,
        events
        + [
            dict(op="power", payload=dict(on=False)),
            dict(op="power", payload=dict(on=True)),
        ],
    )
    assert state["outputs"]["Q"] == "X"


def test_pin_numbers_and_bit_mapping_are_independent_facts():
    assert MODELS["74LS74"]["pins"][11]["name"] == "2D"
    assert MODELS["74LS161"]["pins"][13]["name"] == "QA"
    assert MODELS["74LS194"]["pins"][14]["name"] == "QA"
    assert MODELS["74LS00"]["pins"][8]["name"] == "3B"
    assert MODELS["74LS08"]["pins"][8]["name"] == "3A"
    assert profile("LAB-S4")["board"]["terminals"][-1]["id"] == "Q3"


def test_unknown_feedback_is_not_mistaken_for_stable_function():
    task = profile("LAB-FSM")
    board = reference_board("LAB-FSM")
    # Extra unused NOT section becomes active in a self-inverting ring. X->X
    # is a numerical fixed point, but must not hide an unsupported circuit.
    board = apply_board_action(
        task, board, "connect", {"from": "chip:U2:3", "to": "chip:U2:4"}
    )
    board["power"] = True
    state = Circuit(task, board).evaluate(switches={"CLR_N": 0})
    assert state["status"] == "blocked"
    assert "COMBINATIONAL_LOOP" in {d["code"] for d in state["diagnostics"]}
