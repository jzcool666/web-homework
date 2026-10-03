import { expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { boardLayout } from "../lab";
import { routeLabWires } from "../labRouting";
import LabBoard from "@/components/LabBoard.vue";

const task = {
  board: {
    terminals: [
      { id: "GND", label: "GND", kind: "rail" },
      { id: "VCC", label: "+5V", kind: "rail" },
    ],
    chips: ["U1", "U2", "U3", "U4"].map((id) => ({ id, model: "74LS74" })),
  },
  catalog: {
    models: [
      {
        model: "74LS74",
        pin_count: 14,
        pins: Array.from({ length: 14 }, (_, i) => ({
          number: i + 1,
          name: `P${i + 1}`,
        })),
      },
    ],
  },
};
const connect = (from, to) => ({ from, to, id: [from, to].sort().join("--") });
const wires = [
  ...[1, 2, 3, 4, 5, 7].map((pin) => connect(`chip:U1:${pin}`, "terminal:GND")),
  ...["U1", "U2", "U3", "U4"].map((id) =>
    connect(`chip:${id}:14`, "terminal:VCC"),
  ),
  connect("chip:U1:13", "chip:U2:1"),
  connect("chip:U1:11", "chip:U2:3"),
  connect("chip:U2:2", "chip:U3:2"),
  connect("chip:U2:4", "chip:U3:5"),
  connect("chip:U3:3", "chip:U3:9"),
  connect("chip:U3:11", "chip:U4:1"),
];

it("overlapping horizontal spans occupy different channels", () => {
  const layout = routeLabWires(wires, boardLayout(task));
  for (const [index, route] of layout.routes.entries()) {
    for (const other of layout.routes.slice(index + 1)) {
      if (route.channelY === other.channelY) {
        expect(
          route.range[1] + 14 < other.range[0] ||
            other.range[1] + 14 < route.range[0],
        ).toBe(true);
      }
    }
  }
});

it("shared sockets fan out while preserving both electrical endpoints", () => {
  const before = structuredClone(wires);
  const layout = routeLabWires(wires, boardLayout(task));
  const ground = layout.routes.filter((wire) => wire.to === "terminal:GND");
  expect(new Set(ground.map((wire) => wire.bx)).size).toBe(ground.length);
  for (const route of layout.routes) {
    const from = layout.endpoints.find((point) => point.id === route.from);
    const to = layout.endpoints.find((point) => point.id === route.to);
    expect(route.vertices[0]).toEqual([from.x, from.y]);
    expect(route.vertices.at(-1)).toEqual([to.x, to.y]);
    expect(route.path).not.toMatch(/NaN|Infinity/);
  }
  expect(wires).toEqual(before);
});

it("routing is independent of event-list ordering", () => {
  const paths = (list) =>
    Object.fromEntries(
      routeLabWires(list, boardLayout(task)).routes.map((wire) => [
        wire.id,
        wire.path,
      ]),
    );
  expect(paths(wires.toReversed())).toEqual(paths(wires));
});

it("readonly cable selection traces exactly its endpoints without deleting it", async () => {
  const wire = wires[0];
  const wrapper = mount(LabBoard, {
    props: {
      task,
      board: { wires, power: true },
      state: { pins: {}, diagnostics: [] },
      readonly: true,
    },
  });
  await wrapper.get(`[data-wire="${wire.id}"]`).trigger("click");
  expect(
    wrapper
      .findAll(".endpoint-traced")
      .map((node) => node.attributes("data-endpoint"))
      .sort(),
  ).toEqual([wire.from, wire.to].sort());
  expect(wrapper.emitted("wire")).toBeUndefined();
  await wrapper.get("button.wire-trace-clear").trigger("click");
  expect(wrapper.findAll(".endpoint-traced")).toHaveLength(0);
  wrapper.unmount();
});
