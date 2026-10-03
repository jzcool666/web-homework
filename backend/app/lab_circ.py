"""Parse a bounded, self-contained subset of Logisim-evolution 5.0.0 XML.

The library identifier is resolved before checking a component. Presentation
defaults are removed from the execution copy; no supplied library is loaded.
"""

import re
import xml.etree.ElementTree as ET
from .lab_engine import LabError

MAX_BYTES = 2 * 1024 * 1024
LIBRARIES = {
    "#Wiring",
    "#Gates",
    "#Plexers",
    "#Arithmetic",
    "#Memory",
    "#TTL",
    "#Base",
    "#Input/Output",
}
COMMON = {
    "facing",
    "width",
    "label",
    "labelfont",
    "labelcolor",
    "labelvisible",
    "label_loc",
    "appearance",
}
ATTRS = {
    "#Wiring": {
        "Pin": COMMON | {"output", "tristate", "pull", "radix"},
        "Constant": COMMON | {"value"},
        "Probe": COMMON | {"radix"},
        "Tunnel": COMMON,
        "Splitter": COMMON | {"fanout", "incoming", "appear", "spacing"},
        "Bit Extender": COMMON | {"in_width", "out_width", "type"},
    },
    "#Gates": {
        name: COMMON | {"size", "inputs", "out", "xor", "negate"}
        for name in (
            "NOT Gate",
            "Buffer",
            "AND Gate",
            "OR Gate",
            "NAND Gate",
            "NOR Gate",
            "XOR Gate",
            "XNOR Gate",
        )
    },
    "#Plexers": {
        name: COMMON | {"select", "enable", "disabled", "size", "threeState", "selloc"}
        for name in ("Multiplexer", "Demultiplexer", "Decoder")
    },
    "#Arithmetic": {
        name: COMMON | {"mode", "dataa", "datab"}
        for name in ("Adder", "Subtractor", "Comparator")
    },
    "#Memory": {
        name: COMMON
        | {
            "trigger",
            "enable",
            "max",
            "ongoal",
            "length",
            "parallel",
            "showstate",
            "showInTab",
        }
        for name in (
            "D Flip-Flop",
            "JK Flip-Flop",
            "T Flip-Flop",
            "S-R Flip-Flop",
            "Register",
            "Counter",
            "Shift Register",
        )
    },
    "#TTL": {
        name: COMMON | {"VccGndPorts", "showInternalStructure"}
        for name in ("7400", "7404", "7408", "7432", "7474", "74161", "74194")
    },
}
COORD = re.compile(r"\((-?\d{1,6}),(-?\d{1,6})\)")


def invalid(message):
    raise LabError(message, "CIRCUIT_UNSUPPORTED")


def attrs(element, allowed):
    result = {}
    for child in element:
        if child.tag != "a" or set(child.attrib) != {"name", "val"} or list(child):
            invalid("不支持的器件属性结构")
        name, value = child.attrib["name"], child.attrib["val"]
        if name in result:
            invalid("器件属性重复")
        extra_bit = (
            name.startswith("bit")
            and name[3:].isdigit()
            and int(name[3:]) < 32
            and "fanout" in allowed
        )
        extra_negation = (
            name.startswith("negate")
            and name[6:].isdigit()
            and int(name[6:]) < 32
            and "negate" in allowed
        )
        if name not in allowed and not extra_bit and not extra_negation:
            invalid(f"不支持的器件属性：{name[:40]}")
        if len(value) > 128 or any(c in value for c in ("\x00", "\n", "\r")):
            invalid("器件属性过长或含控制字符")
        if name in {
            "width",
            "incoming",
            "in_width",
            "out_width",
            "inputs",
            "fanout",
            "select",
            "length",
            "spacing",
        }:
            if not value.isdigit() or not 1 <= int(value) <= 32:
                invalid("位宽或器件规模必须为1—32")
        if name.startswith("bit"):
            if not (value == "none" or value.isdigit() and int(value) < 32):
                invalid("分线器位映射不合法")
        if name == "facing" and value not in {"east", "west", "north", "south"}:
            invalid("方向属性不合法")
        if extra_negation and value not in {"true", "false"}:
            invalid("门输入取反属性必须是布尔值")
        if name == "appearance" and value not in {
            "classic",
            "evolution",
            "logisim_evolution",
            "logisim",
            "default",
        }:
            invalid("仅支持内置器件外观")
        result[name] = value
    return result


def coordinate(value):
    match = COORD.fullmatch(value or "")
    if not match or any(abs(int(n)) > 100000 for n in match.groups()):
        invalid("坐标超出支持范围")
    return tuple(map(int, match.groups()))


def validate_circ(content, task):
    if len(content) > MAX_BYTES:
        raise LabError("电路文件不能超过2MiB", "FILE_TOO_LARGE")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        invalid("请使用UTF-8的5.0.0电路文件")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I):
        invalid("不允许DOCTYPE或实体声明")
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, ValueError):
        invalid("电路XML格式不正确")
    if root.tag != "project" or root.get("source") != "5.0.0":
        invalid("请用Logisim-evolution 5.0.0打开并另存为.circ")
    count = 0

    def depth(node, level=0):
        nonlocal count
        count += 1
        if level > 24 or count > 12000:
            invalid("XML结构超过限制")
        for child in node:
            depth(child, level + 1)

    depth(root)
    libs = {}
    circuits = {}
    main = []
    for node in root:
        if node.tag == "lib":
            name, desc = node.get("name"), node.get("desc")
            if not name or name in libs or desc not in LIBRARIES:
                invalid("只允许内置库，不支持文件、JAR或外部库")
            libs[name] = desc
        elif node.tag == "circuit":
            name = node.get("name")
            if (
                not name
                or name in circuits
                or not re.fullmatch(r"[A-Za-z0-9_\-\u4e00-\u9fff]{1,64}", name)
            ):
                invalid("子电路名称不合法或重复")
            circuits[name] = node
        elif node.tag == "main":
            main.append(node.get("name"))
        elif node.tag not in {"options", "mappings", "toolbar", "message"}:
            invalid("不支持的项目结构")
    if main != ["main"] or "main" not in circuits:
        invalid("必须有且仅有一个main入口")
    if not 1 <= len(circuits) <= 16:
        invalid("最多16个电路")
    graph = {name: set() for name in circuits}
    components = wires = 0
    port_map = {}
    canonical = ET.Element("project", {"source": "5.0.0", "version": "1.0"})
    for name, desc in libs.items():
        ET.SubElement(canonical, "lib", {"name": name, "desc": desc})
    ET.SubElement(canonical, "main", {"name": "main"})
    for name, node in circuits.items():
        target = ET.SubElement(canonical, "circuit", {"name": name})
        for child in node:
            if child.tag == "a":
                # Circuit display/HDL defaults are not execution components.
                if child.get("name") not in {
                    "appearance",
                    "circuit",
                    "circuitnamedbox",
                    "circuitvhdlpath",
                    "clabel",
                    "clabelup",
                    "clabelfont",
                    "simulationFrequency",
                }:
                    invalid("不支持的电路属性")
                if child.get("name") == "circuitvhdlpath" and child.get("val"):
                    invalid("不支持HDL文件路径")
                if (
                    set(child.attrib) != {"name", "val"}
                    or list(child)
                    or len(child.get("val", "")) > 128
                ):
                    invalid("电路属性结构不合法")
                if child.get("name") == "appearance" and child.get("val") == "custom":
                    invalid("不支持自定义子电路外观")
                target.append(child)
            elif child.tag == "wire":
                if set(child.attrib) != {"from", "to"} or list(child):
                    invalid("连线结构不合法")
                a, b = coordinate(child.get("from")), coordinate(child.get("to"))
                if a == b or a[0] != b[0] and a[1] != b[1]:
                    invalid("连线必须为非零水平或竖直线段")
                wires += 1
                target.append(child)
            elif child.tag == "comp":
                if set(child.attrib) - {"lib", "loc", "name"}:
                    invalid("器件含未支持字段")
                coordinate(child.get("loc"))
                component = child.get("name")
                library = libs.get(child.get("lib"))
                if "lib" in child.attrib:
                    if component not in ATTRS.get(library, {}):
                        invalid(f"不支持的器件：{(component or '')[:40]}")
                    properties = attrs(child, ATTRS[library][component])
                else:
                    if component not in circuits:
                        invalid("引用了外部或不存在的子电路")
                    graph[name].add(component)
                    properties = attrs(
                        child, {"facing", "label", "labelfont", "labelvisible"}
                    )
                if name == "main" and library == "#Wiring" and component == "Pin":
                    label = properties.get("label", "")
                    if not label or label in port_map:
                        invalid("main引脚必须有唯一标签")
                    if properties.get("tristate", "false") != "false":
                        invalid("任务端口不能为三态输入")
                    if properties.get("output", "false") not in {"true", "false"}:
                        invalid("端口方向不合法")
                    port_map[label] = dict(
                        direction="output"
                        if properties.get("output") == "true"
                        else "input",
                        width=int(properties.get("width", "1")),
                    )
                components += 1
                target.append(child)
            else:
                invalid("不支持的电路结构或自定义外观")
    if components > 512 or wires > 2048:
        invalid("最多512个器件、2048条连线")
    expected = {
        p["label"]: dict(direction=p["direction"], width=p["width"])
        for p in task["ports"]
    }
    if port_map != expected:
        invalid("main端口的标签、输入输出方向与位宽必须完全符合任务")
    visited = set()
    active = set()

    def visit(name):
        if name in active:
            invalid("不支持递归子电路")
        if name in visited:
            return
        active.add(name)
        for child in graph[name]:
            visit(child)
        active.remove(name)
        visited.add(name)

    for name in graph:
        visit(name)
    return ET.tostring(canonical, encoding="utf-8", xml_declaration=True)
