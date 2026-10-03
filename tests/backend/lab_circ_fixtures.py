"""Independently constructed native-component circuits used only by tests.

No reference circuit or expected wiring is served by the production API.
"""

import xml.etree.ElementTree as ET
from app.lab_catalog import profile


def reference_circ(code, wrong=False, equivalent=False):
    root = ET.Element("project", {"source": "5.0.0", "version": "1.0"})
    for lib, desc in [("0", "#Wiring"), ("1", "#Gates"), ("4", "#Memory")]:
        ET.SubElement(root, "lib", {"name": lib, "desc": desc})
    ET.SubElement(root, "main", {"name": "main"})
    c = ET.SubElement(root, "circuit", {"name": "main"})
    row = 0
    net = 0

    def pos(p):
        return f"({p[0]},{p[1]})"

    def comp(name, lib, p, **attrs):
        node = ET.SubElement(c, "comp", {"name": name, "lib": lib, "loc": pos(p)})
        for name, value in attrs.items():
            ET.SubElement(node, "a", {"name": name, "val": str(value)})

    def wire(a, b):
        ET.SubElement(c, "wire", {"from": pos(a), "to": pos(b)})

    def link(p, label, width=1, step=10):
        other = (p[0] + step, p[1])
        comp("Tunnel", "0", other, label=label, width=width)
        wire(p, other)

    def location():
        nonlocal row
        row += 1
        return (500, 100 * row)

    def gate(name, a, b=None):
        nonlocal net
        if b is None and equivalent:
            # Three inversions implement the same function with a different netlist.
            for _ in range(3):
                p = location()
                net += 1
                out = f"n{net}"
                comp("NOT Gate", "1", p, size=30)
                link((p[0] - 30, p[1]), a)
                link(p, out)
                a = out
            return out
        p = location()
        net += 1
        out = f"n{net}"
        if b is None:
            comp("NOT Gate", "1", p, size=30)
            link((p[0] - 30, p[1]), a)
        else:
            comp(name, "1", p, size=30, inputs=2)
            link((p[0] - 30, p[1] - 10), a)
            link((p[0] - 30, p[1] + 10), b)
        link(p, out)
        return out

    def dff(d, q, reset, preset="ZERO"):
        p = location()
        comp("D Flip-Flop", "4", p, appearance="classic", trigger="rising")
        link((p[0] - 40, p[1] + 20), d)
        link((p[0] - 40, p[1]), "CLK")
        link((p[0] - 10, p[1] + 30), reset)
        link((p[0] - 30, p[1] + 30), preset)
        link((p[0], p[1] + (20 if wrong else 0)), q)

    def bus(label, width, split):
        p = location()
        comp("Splitter", "0", p, incoming=width, fanout=width, appear="center")
        link(p, label, width)
        for bit in range(width):
            link((p[0] + 20, p[1] - 10 * (width // 2) + 10 * bit), f"{split}{bit}")

    for i, port in enumerate(profile(code)["ports"]):
        p = (100, 100 + 100 * i)
        comp(
            "Pin",
            "0",
            p,
            label=port["label"],
            width=port["width"],
            output="true" if port["direction"] == "output" else "false",
            facing="west" if port["direction"] == "output" else "east",
        )
        link(p, port["label"], port["width"])
    p = location()
    comp("Constant", "0", p, value="0x0")
    link(p, "ZERO")
    p = location()
    comp("Constant", "0", p, value="0x1")
    link(p, "ONE")
    reset = gate("NOT Gate", "CLR_N")
    if code == "LAB-D":
        dff("D", "Q", reset, gate("NOT Gate", "PRE_N"))
    elif code == "LAB-C6":
        p = location()
        comp(
            "Counter",
            "4",
            p,
            appearance="classic",
            width=4,
            max="0x6" if wrong else "0x5",
            ongoal="wrap",
        )
        for offset, label, width in [
            ((0, 0), "Q", 4),
            ((-20, 20), "CLK", 1),
            ((-10, 20), reset, 1),
            ((-30, 10), "EN", 1),
            ((-30, -10), "ZERO", 1),
            ((-20, -20), "ONE", 1),
        ]:
            link(
                (p[0] + offset[0], p[1] + offset[1]),
                label,
                width,
                step=-10 if label == "CLK" else 10,
            )
        z = location()
        comp("Constant", "0", z, width=4, value="0x0")
        link(z, "ZERO4", 4)
        link((p[0] - 30, p[1]), "ZERO4", 4)
    elif code == "LAB-S4":
        bus("P", 4, "p")
        bus("Q", 4, "q")
        ns1 = gate("NOT Gate", "S1")
        ns0 = gate("NOT Gate", "S0")
        modes = [
            gate("AND Gate", ns1, ns0),
            gate("AND Gate", ns1, "S0"),
            gate("AND Gate", "S1", ns0),
            gate("AND Gate", "S1", "S0"),
        ]
        for bit in range(4):
            sources = [
                f"q{bit}",
                f"q{bit + 1}" if bit < 3 else "SR",
                f"q{bit - 1}" if bit > 0 else "SL",
                f"p{bit}",
            ]
            terms = [gate("AND Gate", m, s) for m, s in zip(modes, sources)]
            d = gate(
                "OR Gate",
                gate("OR Gate", terms[0], terms[1]),
                gate("OR Gate", terms[2], terms[3]),
            )
            dff(d, f"q{bit}", reset)
    else:
        bus("Q", 2, "q")
        dff(gate("NOT Gate", "q1"), "q0", reset)
        dff("q0", "q1", reset)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
