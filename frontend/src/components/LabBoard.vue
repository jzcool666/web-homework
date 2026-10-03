<script setup>
import { computed, useId } from "vue";
import { boardLayout, wirePath } from "@/utils/lab";
const props = defineProps({
  task: { type: Object, required: true },
  board: { type: Object, required: true },
  state: { type: Object, required: true },
  selected: { type: String, default: "" },
  readonly: Boolean,
});
const emit = defineEmits(["endpoint", "wire"]);
const layout = computed(() => boardLayout(props.task));
const invalid = computed(
  () =>
    new Set(props.state.diagnostics?.flatMap((item) => item.endpoints) ?? []),
);
const signal = (endpoint) => String(props.state.pins?.[endpoint] ?? "Z");
// Each replay/preview gets its own SVG paint servers when mounted together.
const id = `lab-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
const paint = (name) => `url(#${id}-${name})`;
const cableColors = [
  "#d55a48",
  "#367fa4",
  "#ba8a32",
  "#698d60",
  "#8b70ad",
  "#d08346",
  "#4b7f83",
];
const cableColor = (wire) =>
  cableColors[
    [...wire.id].reduce(
      (hash, char) => (hash * 31 + char.charCodeAt(0)) >>> 0,
      0,
    ) % cableColors.length
  ];
const banks = [
  { x: 44, width: 202, title: "电源 / 时钟", caption: "POWER · CLK" },
  { x: 264, width: 516, title: "逻辑输入", caption: "INPUT" },
  { x: 798, width: 278, title: "输出探针", caption: "OUTPUT" },
];
const levels = [
  { value: "1", label: "高" },
  { value: "0", label: "低" },
  { value: "X", label: "未知" },
  { value: "Z", label: "悬空" },
];
</script>

<template>
  <div
    class="lab-board-scroll"
    tabindex="0"
    aria-label="实验箱，可横向滚动查看引脚"
  >
    <svg
      class="lab-board"
      :viewBox="`0 0 ${layout.width} ${layout.height}`"
      role="group"
      aria-label="实验箱芯片顶视图与连线"
      :class="{ 'board-readonly': readonly }"
    >
      <defs>
        <linearGradient :id="`${id}-chassis`" x1="0" y1="0" x2="0.8" y2="1">
          <stop offset="0" stop-color="#e1e5e6" />
          <stop offset=".35" stop-color="#aeb9bb" />
          <stop offset=".65" stop-color="#edf0ef" />
          <stop offset="1" stop-color="#939fa4" />
        </linearGradient>
        <linearGradient :id="`${id}-panel`" x1="0" y1="0" x2="0" y2="1">
          <stop stop-color="#f5f5f0" />
          <stop offset="1" stop-color="#e4e7e3" />
        </linearGradient>
        <linearGradient :id="`${id}-header`" x1="0" y1="0" x2="1" y2="1">
          <stop stop-color="#263e4d" />
          <stop offset="1" stop-color="#152a36" />
        </linearGradient>
        <linearGradient :id="`${id}-metal`" x1="0" y1="0" x2="0" y2="1">
          <stop stop-color="#f4f0e5" />
          <stop offset=".35" stop-color="#bdbbb1" />
          <stop offset=".55" stop-color="#e5e2d6" />
          <stop offset="1" stop-color="#8e968e" />
        </linearGradient>
        <linearGradient :id="`${id}-plastic`" x1="0" y1="0" x2="1" y2=".5">
          <stop stop-color="#43464a" />
          <stop offset=".15" stop-color="#282c30" />
          <stop offset=".85" stop-color="#1c2227" />
          <stop offset="1" stop-color="#41474c" />
        </linearGradient>
        <pattern
          :id="`${id}-grain`"
          width="5"
          height="5"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M0 .5 H5 M0 3 H2"
            stroke="#748279"
            stroke-opacity=".09"
            stroke-width=".5"
          />
        </pattern>
        <pattern
          :id="`${id}-chip-grain`"
          width="4"
          height="4"
          patternUnits="userSpaceOnUse"
        >
          <path d="M1 1 h1 M3 3 h1" stroke="#a6aeb5" stroke-opacity=".13" />
        </pattern>
        <filter
          :id="`${id}-chip-shadow`"
          x="-.3"
          y="-.1"
          width="1.6"
          height="1.3"
        >
          <feDropShadow
            dx="0"
            dy="5"
            stdDeviation="4"
            flood-color="#293b40"
            flood-opacity=".26"
          />
        </filter>
      </defs>

      <!-- Instrument enclosure and silk-screened input banks. -->
      <rect
        x="1"
        y="1"
        :width="layout.width - 2"
        :height="layout.height - 2"
        rx="26"
        :fill="paint('chassis')"
        stroke="#929fa5"
      />
      <rect
        x="14"
        y="14"
        :width="layout.width - 28"
        :height="layout.height - 28"
        rx="18"
        :fill="paint('panel')"
        stroke="#fff"
        stroke-opacity=".8"
      />
      <rect
        x="14"
        y="14"
        :width="layout.width - 28"
        :height="layout.height - 28"
        rx="18"
        :fill="paint('grain')"
      />
      <g
        v-for="corner in [
          [22, 22],
          [layout.width - 22, 22],
          [22, layout.height - 22],
          [layout.width - 22, layout.height - 22],
        ]"
        :key="corner.join('-')"
        :transform="`translate(${corner.join(' ')})`"
        class="screw"
      >
        <circle r="6" :fill="paint('metal')" stroke="#8c9698" />
        <path d="M-3 -3 L3 3 M-3 3 L3 -3" />
      </g>
      <rect
        x="34"
        y="34"
        width="1052"
        height="76"
        rx="12"
        :fill="paint('header')"
      />
      <path
        d="M57 78 h12 V57 h17 v21 h17 V57 h10"
        fill="none"
        stroke="#80c9c7"
        stroke-width="3"
        stroke-linejoin="round"
      />
      <text x="132" y="65" class="instrument-title">数字逻辑实验箱</text>
      <text x="133" y="87" class="instrument-caption">
        TTL SERIES / SEQUENTIAL LOGIC
      </text>
      <g transform="translate(923 55)">
        <rect
          width="138"
          height="33"
          rx="16.5"
          fill="#071921"
          fill-opacity=".5"
          stroke="#78928f"
          stroke-opacity=".4"
        />
        <circle
          cx="20"
          cy="16.5"
          r="4.5"
          :fill="board.power ? '#83d9aa' : '#7b8b91'"
        />
        <text x="37" y="21" class="power-label">
          {{ board.power ? "POWER ON" : "POWER OFF" }}
        </text>
      </g>
      <g v-for="bank in banks" :key="bank.title">
        <rect
          :x="bank.x"
          y="130"
          :width="bank.width"
          height="190"
          rx="9"
          fill="#fafaf6"
          stroke="#c8d0ca"
        />
        <path
          :d="`M${bank.x + 15} 166 H${bank.x + bank.width - 15}`"
          stroke="#dfe3dc"
        />
        <text :x="bank.x + 16" y="153" class="bank-title">
          {{ bank.title }}
        </text>
        <text
          :x="bank.x + bank.width - 16"
          y="153"
          text-anchor="end"
          class="bank-caption"
        >
          {{ bank.caption }}
        </text>
      </g>
      <g v-for="chip in layout.chips" :key="`socket-${chip.id}`">
        <rect
          :x="chip.slotX"
          :y="chip.slotY"
          :width="chip.slotWidth"
          height="326"
          rx="10"
          fill="#e2e9e3"
          stroke="#becbc2"
        />
        <rect
          :x="chip.slotX + 2"
          :y="chip.slotY + 2"
          :width="chip.slotWidth - 4"
          height="322"
          rx="9"
          :fill="paint('grain')"
        />
        <text :x="chip.slotX + 18" :y="chip.slotY + 24" class="module-label">
          {{ chip.id }} / DIP-{{ chip.pinCount }}
        </text>
        <text
          :x="chip.slotX + chip.slotWidth - 18"
          :y="chip.slotY + 24"
          text-anchor="end"
          class="module-caption"
        >
          芯片插座 · 顶视图
        </text>
        <rect
          :x="chip.x - 9"
          :y="chip.y - 9"
          :width="chip.width + 18"
          :height="chip.height + 18"
          rx="8"
          fill="#bcc7bd"
          stroke="#8e9c92"
        />
      </g>

      <!-- Jumper jackets, soft shadows and highlights share the same hit path. -->
      <g class="wires">
        <g
          v-for="wire in board.wires"
          :key="wire.id"
          :data-wire="wire.id"
          class="wire"
          :style="{ '--cable-color': cableColor(wire) }"
          @click.stop="!readonly && emit('wire', wire.id)"
        >
          <path
            :d="wirePath(wire, layout.endpoints)"
            class="wire-shadow"
            transform="translate(0 2)"
          />
          <path :d="wirePath(wire, layout.endpoints)" class="wire-jacket" />
          <path
            :d="wirePath(wire, layout.endpoints)"
            class="wire-shine"
            transform="translate(0 -1)"
          />
          <path :d="wirePath(wire, layout.endpoints)" class="wire-hit" />
          <title>{{ wire.from }} → {{ wire.to }}；关电后点击删除</title>
        </g>
      </g>

      <g v-for="chip in layout.chips" :key="chip.id" class="chip-package">
        <rect
          :x="chip.x"
          :y="chip.y"
          :width="chip.width"
          :height="chip.height"
          rx="8"
          :fill="paint('plastic')"
          stroke="#161e24"
          :filter="paint('chip-shadow')"
        />
        <rect
          :x="chip.x + 4"
          :y="chip.y + 4"
          :width="chip.width - 8"
          :height="chip.height - 8"
          rx="5"
          :fill="paint('chip-grain')"
          stroke="#98a2a7"
          stroke-opacity=".2"
        />
        <path
          :d="`M${chip.x + chip.width / 2 - 13} ${chip.y} a13 13 0 0 0 26 0`"
          fill="#10191e"
          stroke="#555f65"
          stroke-width="1.5"
        />
        <circle
          :cx="chip.x + 16"
          :cy="chip.y + 17"
          r="3"
          fill="#8c9699"
          opacity=".5"
        />
        <text
          :x="chip.x + chip.width / 2"
          :y="chip.y + chip.height / 2 - 17"
          text-anchor="middle"
          class="chip-reference"
        >
          {{ chip.id }}
        </text>
        <text
          :x="chip.x + chip.width / 2"
          :y="chip.y + chip.height / 2 + 14"
          text-anchor="middle"
          class="chip-model"
        >
          {{ chip.model }}
        </text>
        <text
          :x="chip.x + chip.width / 2"
          :y="chip.y + chip.height / 2 + 36"
          text-anchor="middle"
          class="chip-caption"
        >
          TTL · DIP {{ chip.pinCount }}
        </text>
      </g>

      <g
        v-for="point in layout.endpoints"
        :key="point.id"
        :data-endpoint="point.id"
        :role="readonly ? undefined : 'button'"
        :tabindex="readonly ? undefined : 0"
        :aria-label="`${point.label}，电平 ${signal(point.id)}`"
        :aria-pressed="selected === point.id"
        class="endpoint"
        :class="[
          {
            'endpoint-selected': selected === point.id,
            'endpoint-invalid': invalid.has(point.id),
          },
          `signal-${signal(point.id)}`,
        ]"
        @click="!readonly && emit('endpoint', point.id)"
        @keydown.enter.prevent="!readonly && emit('endpoint', point.id)"
        @keydown.space.prevent="!readonly && emit('endpoint', point.id)"
      >
        <rect
          v-if="point.chip"
          :x="point.left ? point.x + 4 : point.x - 25"
          :y="point.y - 5"
          width="21"
          height="10"
          rx="2"
          :fill="paint('metal')"
          stroke="#929a91"
          stroke-width=".5"
        />
        <path
          :d="`M${point.x - (point.chip ? 14 : 20)} ${point.y} a${point.chip ? 14 : 20} ${point.chip ? 14 : 20} 0 1 0 ${point.chip ? 28 : 40} 0 a${point.chip ? 14 : 20} ${point.chip ? 14 : 20} 0 1 0 ${point.chip ? -28 : -40} 0`"
          class="socket-rim"
          :fill="paint('metal')"
        />
        <circle
          :cx="point.x"
          :cy="point.y"
          :r="point.chip ? 10 : 15"
          class="pin"
        />
        <text
          :x="point.x"
          :y="point.y + 4"
          text-anchor="middle"
          class="pin-number"
        >
          {{ point.number ?? signal(point.id) }}
        </text>
        <text
          v-if="point.chip"
          :x="point.x + (point.left ? -24 : 24)"
          :y="point.y + 4"
          :text-anchor="point.left ? 'end' : 'start'"
          class="pin-label chip-pin"
        >
          {{ point.name }}
        </text>
        <text
          v-else
          :x="point.x"
          :y="point.y + 35"
          text-anchor="middle"
          class="pin-label"
        >
          {{ point.label }}
        </text>
        <title>{{ point.label }} · {{ signal(point.id) }}</title>
      </g>

      <path :d="`M44 ${layout.height - 75} H1076`" stroke="#c4cec6" />
      <text x="48" :y="layout.height - 45" class="footer-note">
        先关电接线，再通电清零
      </text>
      <text x="540" :y="layout.height - 45" class="footer-note">端点电平</text>
      <g
        v-for="(level, index) in levels"
        :key="level.value"
        :transform="`translate(${634 + index * 110} ${layout.height - 50})`"
        class="level"
        :class="`signal-${level.value}`"
      >
        <rect x="0" y="-7" width="10" height="10" rx="3" class="pin" />
        <text x="18" y="2" class="legend-label">
          {{ level.value }} {{ level.label }}
        </text>
      </g>
    </svg>
  </div>
  <p class="board-key">
    导线颜色用于区分接线，端点颜色表示电平。{{
      selected
        ? "已选择起点，点击另一端完成接线。"
        : "芯片缺口朝上；导线交叉不代表连接。"
    }}
  </p>
</template>

<style scoped>
.lab-board-scroll {
  overflow: auto;
  border-radius: 18px;
  background: #e7ebe7;
  box-shadow:
    0 3px 8px rgb(31 50 59 / 10%),
    0 15px 30px rgb(31 50 59 / 5%);
}
.lab-board {
  display: block;
  width: 100%;
  min-width: 900px;
  font-family: "Microsoft YaHei", sans-serif;
}
.screw path {
  stroke: #647273;
  stroke-width: 1;
}
.instrument-title {
  fill: #f6faf8;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: 2px;
}
.instrument-caption {
  fill: #a8c2c6;
  font: 10px var(--font-mono, monospace);
  letter-spacing: 1.9px;
}
.power-label {
  fill: #c9dedb;
  font: 10px var(--font-mono, monospace);
  letter-spacing: 1px;
}
.bank-title {
  fill: #314743;
  font-size: 12px;
  font-weight: 650;
}
.bank-caption {
  fill: #83918a;
  font: 9px var(--font-mono, monospace);
  letter-spacing: 1px;
}
.module-label {
  fill: #5b6e62;
  font: 10px var(--font-mono, monospace);
  letter-spacing: 1.2px;
}
.module-caption {
  fill: #75837b;
  font-size: 10px;
}
.chip-reference {
  fill: #9aa9ad;
  font: 11px var(--font-mono, monospace);
  letter-spacing: 2px;
}
.chip-model {
  fill: #eef2ed;
  font: 700 20px var(--font-mono, monospace);
  letter-spacing: 1px;
}
.chip-caption {
  fill: #8d9b9e;
  font: 9px var(--font-mono, monospace);
  letter-spacing: 1.5px;
}
.pin-label {
  fill: #3f504b;
  font: 600 12px var(--font-mono, monospace);
}
.chip-pin {
  font-size: 11px;
  paint-order: stroke;
  stroke: #e2e9e3;
  stroke-width: 3;
  stroke-linejoin: round;
}
.pin-number {
  fill: #f9fcf9;
  font: 600 11px var(--font-mono, monospace);
  pointer-events: none;
}
.endpoint {
  cursor: pointer;
  outline: none;
  --signal-color: #5b6d6a;
}
.socket-rim {
  stroke: #97a399;
  stroke-width: 1;
}
.pin {
  fill: var(--signal-color, #5b6d6a);
  stroke: #344640;
  stroke-width: 1.2;
}
.endpoint:hover .socket-rim,
.endpoint:focus-visible .socket-rim,
.endpoint-selected .socket-rim {
  stroke: #345ff1;
  stroke-width: 3;
}
.endpoint-selected .pin {
  stroke: white;
  stroke-width: 2;
}
.endpoint-invalid .socket-rim {
  stroke: #bb372f;
  stroke-width: 3;
  stroke-dasharray: 3 2;
}
.signal-1 {
  --signal-color: #c34d3b;
}
.signal-0 {
  --signal-color: #3977a2;
}
.signal-X {
  --signal-color: #bc8634;
}
.signal-Z {
  --signal-color: #5b6d6a;
}
.wire path {
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.wire {
  cursor: pointer;
}
.wire-shadow {
  stroke: #172d27;
  stroke-width: 7;
  opacity: 0.14;
  pointer-events: none;
}
.wire-jacket {
  stroke: var(--cable-color);
  stroke-width: 5;
}
.wire-shine {
  stroke: #fff;
  stroke-width: 1;
  opacity: 0.4;
  pointer-events: none;
}
.wire-hit {
  stroke: transparent;
  stroke-width: 14;
}
.wire:hover .wire-jacket {
  stroke-width: 7;
}
.board-readonly .wire,
.board-readonly .endpoint {
  cursor: default;
}
.board-readonly .wire:hover .wire-jacket {
  stroke-width: 5;
}
.board-readonly .endpoint:hover .socket-rim {
  stroke: #97a399;
  stroke-width: 1;
}
.footer-note,
.legend-label {
  fill: #5a6d62;
  font-size: 11px;
}
.legend-label {
  font-family: var(--font-mono, monospace);
}
.board-key {
  color: var(--color-text-secondary);
  font-size: 0.75rem;
  line-height: 1.6;
  margin: 12px 0 0;
}
</style>
