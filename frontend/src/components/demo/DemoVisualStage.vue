<script setup>
import { computed, useId } from 'vue'
import { bitLabels, bitsOf, formatBits, inputLabel, inputsFor, INPUT_HINTS } from '@/utils/demo'
import { MODEL_LESSONS, describeCommittedEvent, committedShiftTokens } from '@/utils/demoPresentation'

const props = defineProps({
  state: { type: Object, required: true }, history: { type: Array, default: () => [] },
  simulatorType: { type: String, required: true }, config: { type: Object, default: () => ({}) },
  nextQ: { type: Number, default: null }, revealNext: Boolean, interactive: Boolean, disabled: Boolean, large: Boolean,
})
const emit = defineEmits(['input', 'clock', 'step'])
const id = `scene-${useId().replace(/[^\w-]/g, '')}`
const paint = (name) => `url(#${id}-${name})`
const lesson = computed(() => MODEL_LESSONS[props.simulatorType] ?? MODEL_LESSONS.d)
const pins = computed(() => inputsFor(props.simulatorType))
const labels = computed(() => bitLabels(props.simulatorType))
const bits = computed(() => bitsOf(props.state.q ?? 0, props.simulatorType))
const row = computed(() => props.history.at(-1))
const story = computed(() => describeCommittedEvent(row.value, props.simulatorType))
const transitionKey = computed(() => `${props.history.length}:${row.value?.seq ?? 0}:${row.value?.step_no ?? 0}`)
const shiftTokens = computed(() => committedShiftTokens(row.value))
const modulus = computed(() => Math.min(16, Math.max(2, Number(props.config.modulus) || 16)))
const counterNodes = computed(() => Array.from({ length: modulus.value }, (_, n) => ({
  n, x: 80 + (Math.floor(n / 4) % 2 ? 3 - n % 4 : n % 4) * 139, y: 112 + Math.floor(n / 4) * 90,
})))
const counterHeight = computed(() => 155 + Math.ceil(modulus.value / 4) * 90)
const counterLinks = computed(() => counterNodes.value.slice(0, -1).map((node, index) => {
  const next = counterNodes.value[index + 1]
  if (node.y === next.y) {
    const direction = next.x > node.x ? 1 : -1
    return `M${node.x + direction * 32} ${node.y} H${next.x - direction * 38}`
  }
  const bend = node.x + (Math.floor(node.n / 4) % 2 ? -48 : 48)
  return `M${node.x} ${node.y + 31} H${bend} V${next.y} H${next.x + (bend > next.x ? 38 : -38)}`
}))
const returnPath = computed(() => {
  const last = counterNodes.value.at(-1)
  return `M${last.x} ${last.y + 31} V${footerY.value - 7} H23 V112 H42`
})
const nextVisible = computed(() => props.revealNext && props.nextQ !== null && props.nextQ !== undefined)
const pinValue = (pin) => props.state.inputs?.[pin] ?? 0
const footerY = computed(() => props.simulatorType === 'counter' ? counterHeight.value - 25 : 297)
</script>

<template>
  <section class="visual-stage" :class="{ 'visual-stage--large': large }" :style="{ '--model-color': lesson.color }" aria-label="动态课堂演示台">
    <header class="stage-heading">
      <div><span class="stage-kicker">观察 · 操作 · 理解</span><h2>{{ lesson.title }}</h2><p>{{ lesson.focus }}</p></div>
      <span class="stage-step"><strong>{{ state.step_no ?? 0 }}</strong> 已执行拍数</span>
    </header>

    <div class="stage-workspace">
      <aside class="input-dock">
        <h3><span class="section-number">01</span> 设置输入</h3>
        <div class="input-switches">
          <component :is="interactive ? 'button' : 'div'" v-for="pin in pins" :key="pin" class="input-toggle" :class="{ 'input-toggle--on': pinValue(pin) }"
            :type="interactive ? 'button' : undefined" :disabled="interactive ? disabled : undefined"
            :aria-pressed="interactive ? Boolean(pinValue(pin)) : undefined" :aria-label="`${inputLabel(pin)} 输入 ${pinValue(pin)}${interactive ? '，点击切换' : ''}`"
            @click="interactive && !disabled && emit('input', pin)">
            <span class="input-name">{{ inputLabel(pin) }}<small>{{ INPUT_HINTS[pin] || '逻辑输入' }}</small></span>
            <span class="switch-track"><span class="switch-knob">{{ pinValue(pin) }}</span></span>
          </component>
        </div>
        <div class="clock-dock">
          <div class="clock-level"><span>时钟 CLK</span><strong>{{ state.clock ? '1 · 高电平' : '0 · 低电平' }}</strong></div>
          <svg viewBox="0 0 180 40" aria-hidden="true"><path class="clock-trace" d="M4 30 H40 V10 H85 V30 H130 V10 H176"/><circle :cx="state.clock ? 152 : 106" :cy="state.clock ? 10 : 30" r="5"/></svg>
          <template v-if="interactive">
            <button class="step-button" type="button" :disabled="disabled" @click="emit('step')"><span>↑</span> 前进一步 <small>产生一个有效上升沿</small></button>
            <button class="half-button" type="button" :disabled="disabled" @click="emit('clock')">切换时钟半周期 · {{ state.clock ? '下降沿 ↓' : '上升沿 ↑' }}</button>
          </template>
          <p v-else class="watch-hint">跟随教师操作同步更新</p>
        </div>
      </aside>

      <div class="scene-dock">
        <div class="scene-top"><h3><span class="section-number">02</span> {{ lesson.caption }}</h3><span class="edge-pill" :class="{ 'edge-pill--rise': row?.rising }">{{ row ? row.rising ? '最近：有效上升沿 ↑' : '最近：输出保持' : '等待时钟 ↑' }}</span></div>
        <svg class="teaching-scene" :class="{ 'teaching-scene--shifting': simulatorType === 'shift' && shiftTokens.length }" :viewBox="`0 0 600 ${simulatorType === 'counter' ? counterHeight : 328}`" role="img" :aria-label="`${lesson.caption}动态图，当前 Q=${formatBits(state.q ?? 0, simulatorType)}`">
          <defs>
            <linearGradient :id="`${id}-card`" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff"/><stop offset="1" stop-color="#ecf2ff"/></linearGradient>
            <linearGradient :id="`${id}-memory`" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#426ce1"/><stop offset="1" stop-color="#284cab"/></linearGradient>
            <pattern :id="`${id}-dots`" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#cad8eb"/></pattern>
            <marker :id="`${id}-arrow`" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto"><path d="M0 0 L6 3.5 L0 7" fill="#8099c6"/></marker>
          </defs>
          <rect x="0" y="0" width="600" height="100%" rx="16" fill="#f7faff"/>
          <rect x="0" y="0" width="600" height="100%" rx="16" :fill="paint('dots')" opacity=".5"/>

          <template v-if="simulatorType === 'd' || simulatorType === 'jk'">
            <path class="signal-line" :class="{ 'signal-line--high': pinValue(simulatorType === 'd' ? 'd' : 'j') }" d="M98 100 H218"/>
            <path v-if="simulatorType === 'jk'" class="signal-line" :class="{ 'signal-line--high': pinValue('k') }" d="M98 158 H218"/>
            <path class="signal-line signal-line--output" :class="{ 'signal-line--high': state.q }" d="M382 124 H484"/>
            <path class="signal-line signal-line--clock" :class="{ 'signal-line--high': state.clock }" d="M98 230 H185 Q195 230 195 220 V204 H218"/>
            <rect x="218" y="63" width="164" height="174" rx="20" :fill="paint('memory')"/>
            <path d="M218 192 L233 204 L218 216" fill="none" stroke="#bfd3ff" stroke-width="2"/>
            <text class="chip-label" x="243" y="108">{{ simulatorType === 'd' ? 'D' : 'J' }}</text>
            <text v-if="simulatorType === 'jk'" class="chip-label" x="243" y="165">K</text>
            <text class="chip-label" x="353" y="132">Q</text>
            <text class="chip-caption" x="300" y="174">记忆单元</text>
            <text class="chip-small" x="300" y="195">仅在 ↑ 时更新</text>
            <circle cx="74" cy="100" r="24" class="signal-node" :class="{ 'signal-node--on': pinValue(simulatorType === 'd' ? 'd' : 'j') }"/>
            <text class="node-value" x="74" y="107">{{ pinValue(simulatorType === 'd' ? 'd' : 'j') }}</text>
            <text class="scene-label" x="74" y="64">{{ simulatorType === 'd' ? 'D' : 'J' }}</text>
            <template v-if="simulatorType === 'jk'"><circle cx="74" cy="158" r="24" class="signal-node" :class="{ 'signal-node--on': pinValue('k') }"/><text class="node-value" x="74" y="165">{{ pinValue('k') }}</text><text class="scene-label" x="30" y="165">K</text></template>
            <circle cx="74" cy="230" r="24" class="clock-node"/><text class="node-value" x="74" y="237">{{ state.clock ? '1' : '0' }}</text><text class="scene-label" x="74" y="269">CLK</text>
            <circle cx="515" cy="124" r="34" class="output-glow" :class="{ 'output-glow--on': state.q }"/>
            <text class="output-value" x="515" y="133">{{ state.q ?? 0 }}</text><text class="scene-label" x="515" y="182">输出 Q</text>
            <g :key="transitionKey" v-if="row?.rising" class="committed-pulse" aria-hidden="true"><path d="M98 230 H185 Q195 230 195 220 V204 H218"/><path d="M382 124 H484"/></g>
          </template>

          <template v-else-if="simulatorType === 'counter'">
            <text class="scene-title" x="300" y="35">模 {{ modulus }} 计数 · 当前状态 {{ state.q }}</text>
            <text class="scene-subtitle" x="300" y="58">按编号循环；亮起的位置就是当前 Q</text>
            <path v-for="(link, index) in counterLinks" :key="`link-${index}`" :d="link" class="state-arrow" :marker-end="paint('arrow')"/>
            <g v-for="node in counterNodes" :key="node.n">
              <circle :cx="node.x" :cy="node.y" r="30" class="count-node" :class="{ 'count-node--current': node.n === state.q }"/>
              <text :x="node.x" :y="node.y + 8" class="count-value" :class="{ 'count-value--current': node.n === state.q }">{{ node.n }}</text>
              <text :x="node.x" :y="node.y + 48" class="count-bits">{{ formatBits(node.n, 'counter') }}</text>
            </g>
            <g :key="transitionKey" v-if="row?.rising" class="count-flash" aria-hidden="true"><circle v-for="node in counterNodes.filter(n => n.n === state.q)" :key="node.n" :cx="node.x" :cy="node.y" r="37"/></g>
            <path :d="returnPath" class="state-arrow" stroke-dasharray="4 5" :marker-end="paint('arrow')"/>
            <text class="scene-subtitle" x="300" :y="footerY + 15">循环回到 0</text>
          </template>

          <template v-else-if="simulatorType === 'shift'">
            <text class="scene-title" x="300" y="36">四位记忆 · 从左向右移动</text>
            <text class="scene-subtitle" x="300" y="59">SI → Q3 → Q2 → Q1 → Q0 → 移出</text>
            <path d="M55 142 H550" class="state-arrow" :marker-end="paint('arrow')"/>
            <circle cx="39" cy="142" r="22" class="signal-node" :class="{ 'signal-node--on': pinValue('serial_in') }"/><text x="39" y="150" class="node-value">{{ pinValue('serial_in') }}</text><text x="39" y="99" class="scene-label">SI</text>
            <g v-for="(bit, index) in bits" :key="`${transitionKey}:${labels[index]}`" :transform="`translate(${95 + index * 110} 104)`">
              <rect width="84" height="82" rx="15" class="register-cell" :class="{ 'register-cell--on': bit }"/>
              <text class="register-value" x="42" y="52">{{ bit }}</text><text class="scene-label" x="42" y="-13">{{ labels[index] }}</text>
              <text class="scene-subtitle" x="42" y="111">存储 1 位</text>
            </g>
            <text class="scene-label" x="558" y="195">移出</text>
            <g v-if="shiftTokens.length" :key="transitionKey" class="shift-motion" aria-hidden="true">
              <g v-for="(bit, index) in shiftTokens" :key="index" :style="{ '--travel': `${index === 0 ? 98 : index === 4 ? 90 : 110}px` }" class="shift-token">
                <circle :cx="index === 0 ? 39 : 137 + (index - 1) * 110" cy="142" r="19"/><text :x="index === 0 ? 39 : 137 + (index - 1) * 110" y="149">{{ bit }}</text>
              </g>
            </g>
            <path d="M136 235 H467" class="signal-line signal-line--clock" :class="{ 'signal-line--high': state.clock }"/>
            <path v-for="n in 4" :key="n" :d="`M${137 + (n - 1) * 110} 235 V216`" class="signal-line signal-line--clock"/>
            <text x="300" y="267" class="scene-label">共享同一个时钟 CLK · {{ state.clock ? '高电平 1' : '低电平 0' }}</text>
          </template>

          <template v-if="simulatorType !== 'counter'">
            <rect x="171" :y="footerY - 10" width="258" height="26" rx="13" :fill="pinValue('reset') ? '#fff0df' : '#eaf0fa'"/>
            <text x="300" :y="footerY + 8" class="reset-label">RESET={{ pinValue('reset') }} · 同步复位，仅 ↑ 生效</text>
          </template>
        </svg>
      </div>

      <aside class="output-dock">
        <h3><span class="section-number">03</span> 读取输出</h3>
        <div class="output-lamps"><div v-for="(bit, index) in bits" :key="labels[index]" class="output-lamp" :class="{ 'output-lamp--on': bit }"><span>{{ labels[index] }}</span><strong>{{ bit }}</strong><small>{{ bit ? '高电平' : '低电平' }}</small></div></div>
        <div class="decimal-display"><span>当前状态 Q</span><strong>{{ state.q ?? 0 }}</strong><small>{{ formatBits(state.q ?? 0, simulatorType) }}<span v-if="bits.length > 1"> · 二进制</span></small></div>
        <div class="prediction-display"><span>下一状态 Q(t+1)</span><strong v-if="nextVisible" data-testid="next-state">{{ formatBits(nextQ, simulatorType) }}</strong><strong v-else class="prediction-hidden">? <small>待揭示</small></strong><p>{{ nextVisible ? '下一个有效上升沿的状态' : '先想一想：下一拍会发生什么？' }}</p></div>
      </aside>
    </div>

    <div class="event-story" :class="`event-story--${story.tone}`" aria-live="polite"><span class="story-icon">{{ story.tone === 'rise' ? '↑' : story.tone === 'hold' ? '＝' : '◷' }}</span><div><strong>{{ story.title }}</strong><p>{{ story.text }}</p></div><span class="story-label">最近一次操作</span></div>
  </section>
</template>

<style scoped>
.visual-stage { border: 1px solid #e0e8f5; border-radius: 22px; overflow: hidden; background: white; box-shadow: 0 8px 28px #2f56810a; }
.stage-heading { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 24px 26px; background: linear-gradient(115deg,#eff4ff,#fbfcff 70%); border-bottom: 1px solid #e6edf8; }
.stage-kicker { font-size: .7rem; font-weight: 800; letter-spacing: .18em; color: var(--model-color); }
.stage-heading h2 { font-size: 1.45rem; margin: 6px 0; color: #183661; }.stage-heading p { margin: 0; color: #7485a2; font-size: .82rem; line-height: 1.7; }
.stage-step { display: grid; text-align: center; white-space: nowrap; color: #7b8ea9; font-size: .7rem; }.stage-step strong { color: var(--model-color); font: 750 2.2rem var(--font-mono); }
.stage-workspace { display: grid; grid-template-columns: 190px minmax(0,1fr) 165px; padding: 22px; gap: 22px; }
h3 { display: flex; align-items: center; gap: 8px; font-size: .82rem; margin: 0 0 16px; color: #3b5376; }.section-number { color: #98a9c2; font: 600 .75rem var(--font-mono); }
.input-switches { display: grid; gap: 12px; }.input-toggle { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 12px; background: #f7f9fd; border: 1px solid #e7edf7; border-radius: 12px; text-align: left; color: #435778; }.input-toggle--on { border-color: #c8d5ff; background: #f0f4ff; }.input-toggle:disabled { opacity: .6; cursor: wait; }.input-toggle:focus-visible,.step-button:focus-visible,.half-button:focus-visible { outline: 3px solid #94b3ff; outline-offset: 3px; }
button.input-toggle { cursor: pointer; }.input-name { font: 750 .8rem var(--font-mono); }.input-name small { display: block; margin-top: 4px; font: 400 .65rem sans-serif; color: #8291aa; }.switch-track { width: 46px; height: 26px; border-radius: 16px; padding: 3px; background: #dbe3ef; flex-shrink: 0; transition: background .2s; }.switch-knob { display: grid; place-items: center; background: white; width: 20px; height: 20px; border-radius: 50%; font: 700 11px var(--font-mono); box-shadow: 0 2px 4px #23395b21; transition: transform .2s; }.input-toggle--on .switch-track { background: var(--model-color); }.input-toggle--on .switch-knob { transform: translateX(20px); color: var(--model-color); }
.clock-dock { padding-top: 21px; }.clock-level { display: grid; gap: 6px; font-size: .72rem; color: #8091ac; }.clock-level strong { font-size: .82rem; color: #5c7294; }.clock-dock svg { display: block; width: 100%; height: 42px; margin: 10px 0; fill: #efaa62; }.clock-trace { fill: none; stroke: #a9bcd7; stroke-width: 2.5; }
.step-button { background: var(--model-color); border: 0; border-radius: 11px; padding: 12px 8px; color: white; width: 100%; font-size: .85rem; font-weight: 700; cursor: pointer; box-shadow: 0 5px 12px color-mix(in srgb,var(--model-color) 20%,transparent); }.step-button span { font-size: 1.1rem; padding-right: 4px; }.step-button small { display: block; font-size: .61rem; font-weight: 400; opacity: .8; margin-top: 5px; }.half-button { width: 100%; background: none; border: 0; padding: 12px 0 0; color: #788ba8; font-size: .63rem; cursor: pointer; }.step-button:disabled,.half-button:disabled { opacity: .55; cursor: default; }
.watch-hint { font-size: .72rem; color: #8091ac; }.scene-dock { min-width: 0; }.scene-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }.scene-top h3 { margin: 0; }.edge-pill { font-size: .62rem; color: #8798b1; padding: 5px 8px; border-radius: 20px; background: #f1f5fc; }.edge-pill--rise { color: #269382; background: #eaf8f4; }
.teaching-scene { width: 100%; display: block; min-height: 230px; }.signal-line { fill: none; stroke: #bacbe2; stroke-width: 4; stroke-linecap: round; transition: stroke .2s; }.signal-line--high { stroke: #5a80e9; }.signal-line--output.signal-line--high { stroke: #dc9a4d; }.signal-line--clock { stroke: #b3a3da; }.signal-line--clock.signal-line--high { stroke: #926dd1; }
.signal-node { fill: #eef3fc; stroke: #c2d2ec; stroke-width: 2; }.signal-node--on { fill: #dfe9ff; stroke: #7195eb; }.node-value { text-anchor: middle; fill: #47628c; font: 700 22px var(--font-mono); }.clock-node { fill: #f0eafb; stroke: #c1ace0; stroke-width: 2; }.scene-label { text-anchor: middle; fill: #6c82a4; font: 600 13px var(--font-mono); }.chip-label { fill: #c9d9ff; font: 650 17px var(--font-mono); text-anchor: middle; }.chip-caption { fill: white; text-anchor: middle; font: 650 20px sans-serif; }.chip-small { fill: #b9ccf9; text-anchor: middle; font: 12px sans-serif; }.output-glow { fill: #ebedf1; stroke: #d0d8e4; stroke-width: 5; transition: fill .2s; }.output-glow--on { fill: #ffe3a7; stroke: #f2bd62; filter: drop-shadow(0 0 12px #ffd27c88); }.output-value { font: 750 29px var(--font-mono); fill: #7c715a; text-anchor: middle; }
.scene-title { text-anchor: middle; fill: #3d577f; font: 700 17px sans-serif; }.scene-subtitle { text-anchor: middle; fill: #8b9cb6; font: 12px sans-serif; }.state-arrow { fill: none; stroke: #c0cde1; stroke-width: 2; }.count-node { fill: white; stroke: #d7e2ee; stroke-width: 2; }.count-node--current { fill: var(--model-color); stroke: var(--model-color); filter: drop-shadow(0 4px 7px #31989930); }.count-value { font: 700 24px var(--font-mono); fill: #8595b0; text-anchor: middle; }.count-value--current { fill: white; }.count-bits { font: 11px var(--font-mono); fill: #8c9db4; text-anchor: middle; }
.register-cell { fill: white; stroke: #d6e2f1; stroke-width: 2; }.register-cell--on { fill: #fff0d8; stroke: #e5b26a; }.register-value { fill: #96734c; font: 750 32px var(--font-mono); text-anchor: middle; }.reset-label { fill: #8697b0; text-anchor: middle; font: 11px sans-serif; }
.committed-pulse path { fill: none; stroke: #9cc2ff; stroke-width: 5; stroke-dasharray: 18 180; animation: travel 1s ease-out both; }.count-flash circle { fill: none; stroke: #47bba2; stroke-width: 3; animation: ripple 1s ease-out both; transform-box: fill-box; transform-origin: center; }.shift-token { animation: shift 1.15s ease-in-out both; }.shift-token circle { fill: #edb05c; stroke: white; stroke-width: 2; }.shift-token text { text-anchor: middle; font: 750 21px var(--font-mono); fill: white; }
@keyframes travel { from { stroke-dashoffset: 200; opacity: 1; } to { stroke-dashoffset: 0; opacity: 0; } }@keyframes ripple { from { transform: scale(.85); opacity: 1; } to { transform: scale(1.3); opacity: 0; } }@keyframes shift { 0% { transform: translateX(0); opacity: 0; } 15% { opacity: 1; } 85% { opacity: 1; } 100% { transform: translateX(var(--travel)); opacity: 0; } }
.output-lamps { display: grid; grid-template-columns: repeat(2,1fr); gap: 10px; }.output-lamp { display: grid; justify-items: center; gap: 5px; }.output-lamp span { color: #91a0b7; font: 600 .67rem var(--font-mono); }.output-lamp strong { width: 36px; height: 36px; display: grid; place-items: center; border: 4px solid #e7ecf5; background: #d6dfec; border-radius: 50%; color: #7e8fac; font: 750 .88rem var(--font-mono); }.output-lamp--on strong { background: #ffd48e; border-color: #fff1d7; color: #885826; box-shadow: 0 0 14px #ffc36840; }.output-lamp small { font-size: .58rem; color: #a1adc0; }
.decimal-display { border-radius: 14px; background: #f5f8fc; padding: 15px; margin-top: 20px; display: grid; text-align: center; gap: 4px; }.decimal-display>span,.prediction-display>span { font-size: .67rem; color: #8091ad; }.decimal-display strong { font: 750 2.5rem var(--font-mono); color: #3d577f; }.decimal-display small { font: 600 .7rem var(--font-mono); color: #93a2b9; }.prediction-display { text-align: center; margin-top: 17px; border: 1px dashed #d7dfef; border-radius: 13px; padding: 13px 8px; }.prediction-display>strong { display: block; margin: 9px 0; font: 750 1.45rem var(--font-mono); color: var(--model-color); }.prediction-hidden small { font: 500 .7rem sans-serif; color: #8d9cb3; }.prediction-display p { margin: 0; color: #94a2b8; font-size: .62rem; line-height: 1.6; }
.event-story { display: flex; gap: 13px; padding: 18px 24px; align-items: center; border-top: 1px solid #e7edf7; background: #f8faff; }.story-icon { width: 36px; height: 36px; border-radius: 10px; background: #e9eef9; display: grid; place-items: center; flex-shrink: 0; color: #7d91b5; font: 700 22px sans-serif; }.event-story--rise .story-icon { background: #e5f4ef; color: #279878; }.event-story strong { font-size: .84rem; color: #456185; }.event-story p { font-size: .74rem; line-height: 1.8; color: #7f91ad; margin: 4px 0 0; }.story-label { margin-left: auto; flex-shrink: 0; font-size: .6rem; color: #a3b0c5; }
.teaching-scene--shifting .register-value { animation: cell-reveal 1.15s both; }@keyframes cell-reveal { 0%,90% { opacity: 0; }100% { opacity: 1; } }
.visual-stage--large .stage-workspace { grid-template-columns: 190px minmax(0,1fr) 180px; }.visual-stage--large .stage-heading { padding: 18px 24px; }.visual-stage--large .stage-heading h2 { font-size: 1.65rem; }.visual-stage--large .event-story strong { font-size: 1.05rem; }.visual-stage--large .event-story p { font-size: .9rem; }.visual-stage--large .teaching-scene { height: clamp(240px,38vh,350px); min-height: 0; }
@media(min-width:901px) { .visual-stage--large .stage-heading { padding-top: 12px; padding-bottom: 12px; }.visual-stage--large .output-lamps { grid-template-columns: repeat(4,minmax(0,1fr)); gap: 6px; }.visual-stage--large .input-name small { display: none; }.visual-stage--large .input-toggle { padding: 9px 12px; }.visual-stage--large .input-switches { gap: 9px; }.visual-stage--large .clock-dock { padding-top: 15px; }.visual-stage--large .clock-dock svg { height: 32px; margin: 8px 0; }.visual-stage--large .event-story { padding-top: 13px; padding-bottom: 13px; } }
@media(max-width:1200px) { .stage-workspace,.visual-stage--large .stage-workspace { grid-template-columns: 155px minmax(0,1fr) 130px; gap: 15px; padding: 18px; }.input-toggle { padding: 10px 8px; }.stage-heading { padding: 20px; }.story-label { display: none; }.teaching-scene { min-height: 190px; } }
@media(max-width:900px) { .stage-workspace,.visual-stage--large .stage-workspace { grid-template-columns: minmax(0,1fr) 145px; }.input-dock { grid-column: 1/-1; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.input-dock h3 { grid-column: 1/-1; margin: 0; }.input-switches { grid-template-columns: repeat(2,minmax(0,1fr)); align-content: start; }.clock-dock { padding: 0; }.clock-dock svg { display: none; }.clock-level { display: flex; justify-content: space-between; margin-bottom: 8px; }.half-button { padding-top: 8px; }.scene-dock { align-self: center; } }
@media(max-width:580px) { .stage-heading { padding: 18px 15px; align-items: flex-start; gap: 10px; }.stage-heading h2,.visual-stage--large .stage-heading h2 { font-size: 1.18rem; }.stage-heading p { font-size: .7rem; }.stage-step strong { font-size: 1.7rem; }.stage-workspace,.visual-stage--large .stage-workspace { display: flex; flex-direction: column; padding: 15px; gap: 18px; }.input-dock { display: flex; flex-direction: column; }.input-switches { grid-template-columns: repeat(2,minmax(0,1fr)); }.clock-dock { margin-top: 3px; }.step-button { padding: 11px; }.step-button small { display: inline; margin-left: 6px; }.scene-top { align-items: center; }.scene-top h3 { font-size: .74rem; }.edge-pill { font-size: .55rem; }.teaching-scene { min-height: 0; }.output-dock { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.output-dock h3 { grid-column: 1/-1; margin: 0; }.output-lamps { grid-template-columns: repeat(4,1fr); grid-column: 1/-1; justify-items: center; }.decimal-display,.prediction-display { margin: 0; }.decimal-display strong { font-size: 1.9rem; }.event-story { padding: 15px; align-items: flex-start; }.event-story p,.visual-stage--large .event-story p { font-size: .72rem; }.visual-stage--large .event-story strong { font-size: .86rem; }.visual-stage { border-radius: 17px; } }
@media(prefers-reduced-motion:reduce) { .committed-pulse,.count-flash,.shift-motion { display: none; }.switch-knob,.switch-track,.signal-line,.output-glow { transition: none; }.teaching-scene--shifting .register-value { animation: none; } }
</style>
