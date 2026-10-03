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
  const terminalCounts = { rail: 0, clock: 0, switch: 0, probe: 0 };
  for (const terminal of task.board.terminals) {
    const index = terminalCounts[terminal.kind]++;
    const positions = {
      rail: [96 + index * 98, 192],
      clock: [145, 262],
      switch: [326 + (index % 5) * 93, 192 + Math.floor(index / 5) * 70],
      probe: [876 + (index % 2) * 112, 192 + Math.floor(index / 2) * 70],
    };
    const [x, y] = positions[terminal.kind];
    endpoints.push({
      ...terminal,
      id: `terminal:${terminal.id}`,
      x,
      y,
      label: terminal.label,
    });
  }
  for (const [index, chip] of task.board.chips.entries()) {
    const model = task.catalog.models.find((item) => item.model === chip.model);
    const single = task.board.chips.length === 1;
    const slotX = 44 + (index % 2) * 536;
    const slotY = 354 + Math.floor(index / 2) * 344;
    const slotWidth = single ? 1032 : 496;
    const x = slotX + (slotWidth - 188) / 2;
    const y = slotY + 52;
    const height = 52 + (model.pin_count / 2 - 1) * 30;
    chips.push({
      ...chip,
      x,
      y,
      height,
      width: 188,
      slotX,
      slotY,
      slotWidth,
      pinCount: model.pin_count,
    });
    for (const pin of model.pins) {
      const left = pin.number <= model.pin_count / 2;
      const order = left ? pin.number - 1 : model.pin_count - pin.number;
      endpoints.push({
        ...pin,
        id: `chip:${chip.id}:${pin.number}`,
        label: `${chip.id} ${pin.number} ${pin.name}`,
        name: pin.name,
        chip: chip.id,
        x: left ? x - 22 : x + 210,
        y: y + 26 + order * 30,
        busY: slotY - 22,
        left,
      });
    }
  }
  return {
    chips,
    endpoints,
    height: 354 + Math.ceil(chips.length / 2) * 344 + 90,
    width: 1120,
  };
}

export function wirePath(wire, endpoints) {
  const a = endpoints.find((p) => p.id === wire.from);
  const b = endpoints.find((p) => p.id === wire.to);
  if (!a || !b) return "";
  const lane =
    [...wire.id].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 6;
  const middle = Math.min(a.busY ?? Infinity, b.busY ?? Infinity);
  const routeY = Number.isFinite(middle)
    ? middle - lane * 4
    : Math.max(a.y, b.y) + 40 + lane * 4;
  const ax = a.chip ? a.x + (a.left ? -18 : 18) : a.x;
  const bx = b.chip ? b.x + (b.left ? -18 : 18) : b.x;
  const points = [
    [a.x, a.y],
    [ax, a.y],
    [ax, routeY],
    [bx, routeY],
    [bx, b.y],
    [b.x, b.y],
  ].filter(
    (point, index, all) =>
      !index ||
      point[0] !== all[index - 1][0] ||
      point[1] !== all[index - 1][1],
  );
  let path = `M${points[0].join(" ")}`;
  for (let index = 1; index < points.length - 1; index++) {
    const [x, y] = points[index];
    const [px, py] = points[index - 1];
    const [nx, ny] = points[index + 1];
    const before = Math.hypot(x - px, y - py);
    const after = Math.hypot(nx - x, ny - y);
    const radius = Math.min(12, before / 2, after / 2);
    path += ` L${x - ((x - px) / before) * radius} ${y - ((y - py) / before) * radius} Q${x} ${y} ${x + ((nx - x) / after) * radius} ${y + ((ny - y) / after) * radius}`;
  }
  return path + ` L${points.at(-1).join(" ")}`;
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
