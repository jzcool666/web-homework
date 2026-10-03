import { roundedWirePath } from "./lab";

// Visual routing only. Display coordinates never change electrical connectivity.
export function routeLabWires(wires, base) {
  const points = new Map(base.endpoints.map((point) => [point.id, point]));
  const groups = new Map();
  const links = wires
    .filter((wire) => points.has(wire.from) && points.has(wire.to))
    .map((wire) => ({
      ...wire,
      row: Math.max(
        points.get(wire.from).row ?? 0,
        points.get(wire.to).row ?? 0,
      ),
    }));
  for (const link of links) {
    for (const endpoint of [link.from, link.to]) {
      const point = points.get(endpoint);
      const group = point.chip ? `${point.column}:${point.left}` : point.id;
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push({ endpoint, wireId: link.id, point });
    }
  }
  const escapes = new Map();
  for (const members of groups.values()) {
    members.sort(
      (a, b) =>
        a.wireId.localeCompare(b.wireId) ||
        a.endpoint.localeCompare(b.endpoint),
    );
    for (const [rank, member] of members.entries()) {
      const point = member.point;
      const spacing = Math.min(
        point.chip ? 7 : 8,
        (point.chip ? 116 : 64) / Math.max(1, members.length - 1),
      );
      const direction = point.chip
        ? point.left
          ? -1
          : 1
        : point.id === "terminal:GND"
          ? -1
          : 1;
      escapes.set(
        `${member.wireId}|${member.endpoint}`,
        point.x + direction * ((point.chip ? 20 : 0) + rank * spacing),
      );
    }
  }
  const rows = Array.from(
    { length: Math.ceil(base.chips.length / 2) },
    () => [],
  );
  for (const link of links) {
    link.ax = escapes.get(`${link.id}|${link.from}`);
    link.bx = escapes.get(`${link.id}|${link.to}`);
    link.range = [Math.min(link.ax, link.bx), Math.max(link.ax, link.bx)];
    rows[link.row].push(link);
  }
  const rowPositions = [];
  let cursor = 330;
  for (const [row, runs] of rows.entries()) {
    const lanes = [];
    runs.sort(
      (a, b) =>
        a.range[0] - b.range[0] ||
        a.range[1] - b.range[1] ||
        a.id.localeCompare(b.id),
    );
    for (const run of runs) {
      let lane = lanes.findIndex((end) => end + 14 < run.range[0]);
      if (lane < 0) lane = lanes.length;
      lanes[lane] = run.range[1];
      run.channelY = cursor + lane * 10;
    }
    const slotY = cursor + Math.max(8, lanes.length) * 10 + 24;
    rowPositions[row] = slotY;
    cursor = slotY + 326 + 24;
  }
  const endpoints = base.endpoints.map((point) =>
    point.chip
      ? {
          ...point,
          y: point.y + rowPositions[point.row] - (354 + point.row * 344),
        }
      : point,
  );
  const routedPoints = new Map(endpoints.map((point) => [point.id, point]));
  const routes = links.map((link) => {
    const a = routedPoints.get(link.from);
    const b = routedPoints.get(link.to);
    const startY = a.chip ? a.y : a.y + 26;
    const endY = b.chip ? b.y : b.y + 26;
    const vertices = [
      [a.x, a.y],
      [link.ax, startY],
      [link.ax, link.channelY],
      [link.bx, link.channelY],
      [link.bx, endY],
      [b.x, b.y],
    ];
    return { ...link, vertices, path: roundedWirePath(vertices) };
  });
  return {
    ...base,
    endpoints,
    chips: base.chips.map((chip) => ({
      ...chip,
      slotY: rowPositions[chip.row],
      y: chip.y + rowPositions[chip.row] - chip.slotY,
    })),
    height: cursor + 84,
    routes,
  };
}
