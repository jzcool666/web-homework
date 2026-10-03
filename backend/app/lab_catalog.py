"""Versioned DIP pin facts and four bounded teaching boards (SPEC-018).

Pin numbers are TI top-view DIP numbers, not Logisim component coordinates.
Only public facts live here; reference wires and grading vectors are separate.
"""

from copy import deepcopy

CATALOG_VERSION = "ttl-dip-1"


def _model(model, names, units, power, ground):
    outputs = {pin for unit in units for pin in unit["output_pins"]}
    pins = []
    for number, name in enumerate(names, 1):
        unit = next(
            (u["id"] for u in units if number in u["input_pins"] + u["output_pins"]),
            None,
        )
        direction = (
            "power"
            if number == power
            else "ground"
            if number == ground
            else "output"
            if number in outputs
            else "input"
        )
        pins.append(dict(number=number, name=name, direction=direction, unit=unit))
    return dict(model=model, pin_count=len(names), pins=pins, units=units)


def _unit(id, kind, inputs, outputs):
    return dict(id=id, kind=kind, input_pins=inputs, output_pins=outputs)


MODELS = {}
for model, kind in [("74LS00", "nand"), ("74LS08", "and"), ("74LS32", "or")]:
    MODELS[model] = _model(
        model,
        [
            "1A",
            "1B",
            "1Y",
            "2A",
            "2B",
            "2Y",
            "GND",
            "3Y",
            "3A",
            "3B",
            "4Y",
            "4A",
            "4B",
            "VCC",
        ],
        [
            _unit(str(n), kind, ins, [out])
            for n, ins, out in [
                (1, [1, 2], 3),
                (2, [4, 5], 6),
                (3, [9, 10], 8),
                (4, [12, 13], 11),
            ]
        ],
        14,
        7,
    )
# TI SDLS025D's 7400 DIP drawing labels A/B in the reverse order for gates
# 3/4 versus the 7408/7432 drawings. Inputs commute, pin facts still matter.
for number, name in [(9, "3B"), (10, "3A"), (12, "4B"), (13, "4A")]:
    MODELS["74LS00"]["pins"][number - 1]["name"] = name
MODELS["74LS04"] = _model(
    "74LS04",
    [
        "1A",
        "1Y",
        "2A",
        "2Y",
        "3A",
        "3Y",
        "GND",
        "4Y",
        "4A",
        "5Y",
        "5A",
        "6Y",
        "6A",
        "VCC",
    ],
    [
        _unit(str(n), "not", [a], [y])
        for n, a, y in [
            (1, 1, 2),
            (2, 3, 4),
            (3, 5, 6),
            (4, 9, 8),
            (5, 11, 10),
            (6, 13, 12),
        ]
    ],
    14,
    7,
)
MODELS["74LS74"] = _model(
    "74LS74",
    [
        "1CLR_N",
        "1D",
        "1CLK",
        "1PRE_N",
        "1Q",
        "1Q_N",
        "GND",
        "2Q_N",
        "2Q",
        "2PRE_N",
        "2CLK",
        "2D",
        "2CLR_N",
        "VCC",
    ],
    [
        _unit("1", "dff", [1, 2, 3, 4], [5, 6]),
        _unit("2", "dff", [13, 12, 11, 10], [9, 8]),
    ],
    14,
    7,
)
MODELS["74LS161"] = _model(
    "74LS161",
    [
        "CLR_N",
        "CLK",
        "A",
        "B",
        "C",
        "D",
        "ENP",
        "GND",
        "LOAD_N",
        "ENT",
        "QD",
        "QC",
        "QB",
        "QA",
        "RCO",
        "VCC",
    ],
    [_unit("1", "counter", [1, 2, 3, 4, 5, 6, 7, 9, 10], [11, 12, 13, 14, 15])],
    16,
    8,
)
MODELS["74LS194"] = _model(
    "74LS194",
    [
        "CLR_N",
        "SR",
        "A",
        "B",
        "C",
        "D",
        "SL",
        "GND",
        "S0",
        "S1",
        "CLK",
        "QD",
        "QC",
        "QB",
        "QA",
        "VCC",
    ],
    [_unit("1", "shift", [1, 2, 3, 4, 5, 6, 7, 9, 10, 11], [12, 13, 14, 15])],
    16,
    8,
)


def profile(code):
    definitions = {
        "LAB-D": (
            "D触发器接线",
            [("CLK", 1), ("CLR_N", 1), ("PRE_N", 1), ("D", 1)],
            1,
            [("U1", "74LS74")],
        ),
        "LAB-C6": (
            "同步模6计数器接线",
            [("CLK", 1), ("CLR_N", 1), ("EN", 1)],
            4,
            [("U1", "74LS161"), ("U2", "74LS04"), ("U3", "74LS08"), ("U4", "74LS00")],
        ),
        "LAB-S4": (
            "四位双向寄存器接线",
            [
                ("CLK", 1),
                ("CLR_N", 1),
                ("S1", 1),
                ("S0", 1),
                ("SR", 1),
                ("SL", 1),
                ("P", 4),
            ],
            4,
            [("U1", "74LS194")],
        ),
        "LAB-FSM": (
            "两位Gray状态机接线",
            [("CLK", 1), ("CLR_N", 1)],
            2,
            [("U1", "74LS74"), ("U2", "74LS04")],
        ),
    }
    title, inputs, width, chips = definitions[code]
    ports = [dict(label=label, direction="input", width=w) for label, w in inputs] + [
        dict(label="Q", direction="output", width=width)
    ]
    terminals = [
        dict(id="VCC", label="+5V", kind="rail", port=None, bit=None),
        dict(id="GND", label="GND", kind="rail", port=None, bit=None),
    ]
    for port in ports:
        for bit in range(port["width"]):
            label = port["label"] if port["width"] == 1 else f"{port['label']}{bit}"
            terminals.append(
                dict(
                    id=label,
                    label=label,
                    kind="probe"
                    if port["direction"] == "output"
                    else "clock"
                    if label == "CLK"
                    else "switch",
                    port=port["label"],
                    bit=bit,
                )
            )
    instructions = {
        "LAB-D": "接好VCC/GND，1CLR_N和1PRE_N低有效，1D接输入，1CLK接时钟，1Q接Q。先异步清零，再观察D只在上升沿采样。PRE_N与CLR_N禁止同时低。",
        "LAB-C6": "161的QA为最低位。A/B/C/D接0，EN接ENP与ENT。用门电路译码0101并与EN相与，取反接LOAD_N；CLR_N接清零。验证0到5后同步回0，以及EN=0时保持。",
        "LAB-S4": "194显示位序QA QB QC QD。P3到P0接A到D。S1S0=00保持、01右移(SR进入QA)、10左移(SL进入QD)、11并行装载。CLR_N低时立即清零。",
        "LAB-FSM": "用74LS74两路实现Q1/Q0。两CLK直连箱CLK，PRE_N接高，CLR_N共同清零。由状态表推导D输入，验证00→01→11→10→00。",
    }
    return dict(
        code=code,
        title=title,
        instructions_md=instructions[code],
        catalog_version=CATALOG_VERSION,
        ports=ports,
        board=dict(
            chips=[dict(id=id, model=model) for id, model in chips], terminals=terminals
        ),
        catalog=dict(
            version=CATALOG_VERSION,
            models=[deepcopy(MODELS[m]) for m in dict(chips).values()],
        ),
    )


CODES = ("LAB-D", "LAB-C6", "LAB-S4", "LAB-FSM")
