// Display and editing helpers only. All chip states are computed by the server.
export const labStatus = {
  queued: "等待测评",
  running: "正在测评",
  done: "测评完成",
  error: "测评失败",
};
export const newLabKey = () => crypto.randomUUID().replaceAll("-", "");
export const modeLabel = (mode) =>
  mode === "wiring" ? "实验箱接线" : "Logisim 文件";
export const outputText = (outputs) =>
  Object.entries(outputs ?? {})
    .map(([name, value]) => `${name}=${value}`)
    .join(" · ");

export function boardLayout(task) {
  const endpoints = [];
  const chips = [];
  for (const [index, terminal] of task.board.terminals.entries()) {
    endpoints.push({
      ...terminal,
      id: `terminal:${terminal.id}`,
      x: 45 + (index % 10) * 105,
      y: 48 + Math.floor(index / 10) * 72,
      label: terminal.label,
    });
  }
  for (const [index, chip] of task.board.chips.entries()) {
    const model = task.catalog.models.find((item) => item.model === chip.model);
    const x = 155 + (index % 2) * 510;
    const y = 235 + Math.floor(index / 2) * 400;
    chips.push({ ...chip, x, y, height: 310, width: 250 });
    for (const pin of model.pins) {
      const left = pin.number <= model.pin_count / 2;
      const order = left ? pin.number - 1 : model.pin_count - pin.number;
      endpoints.push({
        ...pin,
        id: `chip:${chip.id}:${pin.number}`,
        label: `${chip.id} ${pin.number} ${pin.name}`,
        name: pin.name,
        chip: chip.id,
        x: left ? x - 22 : x + 272,
        y: y + 28 + order * 36,
        left,
      });
    }
  }
  return {
    chips,
    endpoints,
    height: 235 + Math.ceil(chips.length / 2) * 400,
    width: 1060,
  };
}

export function wirePath(wire, endpoints) {
  const a = endpoints.find((p) => p.id === wire.from);
  const b = endpoints.find((p) => p.id === wire.to);
  if (!a || !b) return "";
  const middle = (a.y + b.y) / 2;
  return `M${a.x} ${a.y} V${middle} H${b.x} V${b.y}`;
}

export function inverseWireAction(op, payload, board) {
  if (op === "connect")
    return {
      op: "disconnect",
      payload: { wire_id: [payload.from, payload.to].sort().join("--") },
    };
  if (op === "disconnect") {
    const wire = board.wires.find((item) => item.id === payload.wire_id);
    return wire
      ? { op: "connect", payload: { from: wire.from, to: wire.to } }
      : null;
  }
  return null;
}
