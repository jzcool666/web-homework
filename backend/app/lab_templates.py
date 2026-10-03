"""Port-only desktop templates; never contain a reference solution."""

from xml.etree.ElementTree import Element, SubElement, tostring


def template(task):
    project = Element("project", source="5.0.0", version="1.0")
    for name, desc in [
        ("0", "#Wiring"),
        ("1", "#Gates"),
        ("4", "#Memory"),
        ("7", "#TTL"),
    ]:
        SubElement(project, "lib", name=name, desc=desc)
    SubElement(project, "main", name="main")
    circuit = SubElement(project, "circuit", name="main")
    inputs = [p for p in task["ports"] if p["direction"] == "input"]
    outputs = [p for p in task["ports"] if p["direction"] == "output"]
    for direction, ports, x in [("input", inputs, 100), ("output", outputs, 600)]:
        for index, p in enumerate(ports):
            component = SubElement(
                circuit, "comp", lib="0", name="Pin", loc=f"({x},{100 + index * 80})"
            )
            attrs = {
                "label": p["label"],
                "width": str(p["width"]),
                "facing": "east" if direction == "input" else "west",
                "output": "false" if direction == "input" else "true",
            }
            for name, value in attrs.items():
                SubElement(component, "a", name=name, val=value)
    return tostring(project, encoding="utf-8", xml_declaration=True)
