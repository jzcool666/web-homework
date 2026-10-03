<script setup>
import { computed } from 'vue'
import { boardLayout, wirePath } from '@/utils/lab'
const props = defineProps({ task: { type: Object, required: true }, board: { type: Object, required: true }, state: { type: Object, required: true }, selected: { type: String, default: '' }, readonly: Boolean })
const emit = defineEmits(['endpoint', 'wire'])
const layout = computed(() => boardLayout(props.task))
const invalid = computed(() => new Set(props.state.diagnostics?.flatMap(item => item.endpoints) ?? []))
const signal = endpoint => String(props.state.pins?.[endpoint] ?? 'Z')
</script>

<template>
  <div class="lab-board-scroll" tabindex="0" aria-label="实验箱，可横向滚动查看引脚">
    <svg class="lab-board" :viewBox="`0 0 ${layout.width} ${layout.height}`" role="group" aria-label="实验箱芯片顶视图与连线">
      <rect width="1060" :height="layout.height" rx="16" class="board-background" />
      <g class="wires">
        <path v-for="wire in board.wires" :key="wire.id" :d="wirePath(wire, layout.endpoints)" class="wire" :class="`signal-${signal(wire.from)}`" @click.stop="!readonly && emit('wire', wire.id)">
          <title>{{ wire.from }} → {{ wire.to }}；关电后点击删除</title>
        </path>
      </g>
      <g v-for="chip in layout.chips" :key="chip.id">
        <rect :x="chip.x" :y="chip.y" :width="chip.width" :height="chip.height" rx="8" class="chip" />
        <path :d="`M${chip.x + 107} ${chip.y} a18 18 0 0 0 36 0`" class="notch" />
        <text :x="chip.x + 125" :y="chip.y + 135" text-anchor="middle" class="chip-title">{{ chip.id }}</text>
        <text :x="chip.x + 125" :y="chip.y + 165" text-anchor="middle" class="chip-model">{{ chip.model }}</text>
      </g>
      <g v-for="point in layout.endpoints" :key="point.id" :data-endpoint="point.id" :role="readonly ? undefined : 'button'" :tabindex="readonly ? undefined : 0" :aria-label="point.label" :aria-pressed="selected === point.id" class="endpoint" @click="!readonly && emit('endpoint', point.id)" @keydown.enter.prevent="!readonly && emit('endpoint', point.id)" @keydown.space.prevent="!readonly && emit('endpoint', point.id)">
        <circle :cx="point.x" :cy="point.y" r="13" class="pin" :class="[{ selected: selected === point.id, invalid: invalid.has(point.id) }, `signal-${signal(point.id)}`]" />
        <text :x="point.x" :y="point.y + 5" text-anchor="middle" class="pin-number">{{ point.number ?? signal(point.id) }}</text>
        <text v-if="point.chip" :x="point.x + (point.left ? 34 : -34)" :y="point.y + 5" :text-anchor="point.left ? 'start' : 'end'" class="pin-label chip-pin">{{ point.name }}</text>
        <text v-else :x="point.x" :y="point.y + 32" text-anchor="middle" class="pin-label">{{ point.label }}</text>
        <title>{{ point.label }} · {{ signal(point.id) }}</title>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.lab-board-scroll { overflow: auto; border-radius: 12px; border: 1px solid var(--border); }
.lab-board { display: block; width: 100%; min-width: 840px; }
.board-background { fill: #f3f5f9; } .chip { fill: #243247; stroke: #172235; } .notch { fill: #f3f5f9; stroke: #172235; }
.chip-title { fill: #fff; font-size: 22px; font-weight: 700; } .chip-model { fill: #dce5f4; font-size: 19px; }
.pin-label { fill: #172235; font-size: 13px; font-family: monospace; } .pin-number { fill: #fff; font: bold 12px monospace; pointer-events: none; }
.chip-pin { fill: #fff; } .pin { fill: #78869a; stroke: #fff; stroke-width: 2; } .endpoint { cursor: pointer; }
.endpoint:focus .pin, .pin.selected { stroke: #285ae6; stroke-width: 5; } .pin.invalid { stroke: #b42318; stroke-width: 5; }
.wire { fill: none; stroke: #78869a; stroke-width: 3; cursor: pointer; } .wire:hover { stroke-width: 7; }
.pin.signal-1 { fill: #b42318; } .pin.signal-0 { fill: #2364aa; } .pin.signal-X { fill: #a66a05; }
.wire.signal-1 { stroke: #b42318; } .wire.signal-0 { stroke: #2364aa; } .wire.signal-X { stroke: #a66a05; }
</style>
