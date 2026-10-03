"""Reference wiring for tests only, never included in public task JSON."""

from app.lab_catalog import profile, MODELS
from app.lab_engine import empty_board, apply_board_action


def reference_board(code):
    task = profile(code)
    board = empty_board()

    def connect(a, b):
        nonlocal board
        board = apply_board_action(task, board, "connect", {"from": a, "to": b})

    def pin(c, p):
        return f"chip:U{c}:{p}"

    def term(t):
        return f"terminal:{t}"

    for c in task["board"]["chips"]:
        for p in MODELS[c["model"]]["pins"]:
            if p["direction"] in ("power", "ground"):
                connect(
                    f"chip:{c['id']}:{p['number']}",
                    term("VCC" if p["direction"] == "power" else "GND"),
                )
    pairs = []
    if code == "LAB-D":
        pairs = [
            (pin(1, p), term(t))
            for p, t in [(1, "CLR_N"), (2, "D"), (3, "CLK"), (4, "PRE_N"), (5, "Q")]
        ]
    elif code == "LAB-S4":
        pairs = [
            (pin(1, p), term(t))
            for p, t in [
                (1, "CLR_N"),
                (2, "SR"),
                (3, "P3"),
                (4, "P2"),
                (5, "P1"),
                (6, "P0"),
                (7, "SL"),
                (9, "S0"),
                (10, "S1"),
                (11, "CLK"),
                (12, "Q0"),
                (13, "Q1"),
                (14, "Q2"),
                (15, "Q3"),
            ]
        ]
    elif code == "LAB-FSM":
        pairs = [
            (pin(1, p), term(t))
            for p, t in [
                (1, "CLR_N"),
                (13, "CLR_N"),
                (3, "CLK"),
                (11, "CLK"),
                (4, "VCC"),
                (10, "VCC"),
                (5, "Q0"),
                (9, "Q1"),
            ]
        ]
        pairs += [
            (pin(1, 5), pin(1, 12)),
            (pin(1, 9), pin(2, 1)),
            (pin(2, 2), pin(1, 2)),
        ]
    else:
        pairs = [
            (pin(1, p), term(t))
            for p, t in [
                (1, "CLR_N"),
                (2, "CLK"),
                (7, "EN"),
                (10, "EN"),
                (3, "GND"),
                (4, "GND"),
                (5, "GND"),
                (6, "GND"),
                (14, "Q0"),
                (13, "Q1"),
                (12, "Q2"),
                (11, "Q3"),
            ]
        ]
        pairs += [
            (pin(1, 13), pin(2, 1)),
            (pin(1, 11), pin(2, 3)),
            (pin(1, 14), pin(3, 1)),
            (pin(2, 2), pin(3, 2)),
            (pin(1, 12), pin(3, 4)),
            (pin(2, 4), pin(3, 5)),
            (pin(3, 3), pin(3, 9)),
            (pin(3, 6), pin(3, 10)),
            (pin(3, 8), pin(3, 12)),
            (term("EN"), pin(3, 13)),
            (pin(3, 11), pin(4, 1)),
            (pin(3, 11), pin(4, 2)),
            (pin(4, 3), pin(1, 9)),
        ]
    for a, b in pairs:
        connect(a, b)
    return board
