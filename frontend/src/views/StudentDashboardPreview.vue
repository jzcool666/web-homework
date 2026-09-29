<script setup>
const navItems = [
  { icon: '⌂', label: '学习首页', active: true },
  { icon: '▤', label: '课程学习' },
  { icon: '⌁', label: '电路仿真' },
  { icon: '☷', label: '习题训练' },
  { icon: '♙', label: '实验中心' },
  { icon: '▥', label: '学习分析' },
  { icon: '✦', label: 'AI辅导' },
  { icon: '☆', label: '我的收藏' },
]

const stats = [
  { icon: '▤', label: '已学习知识点', value: '3', unit: '个', delta: '+1', tone: 'up' },
  { icon: '✎', label: '完成习题', value: '12', unit: '道', delta: '+4', tone: 'up' },
  { icon: '◔', label: '正确率', value: '82%', unit: '', delta: '-3%', tone: 'down' },
  { icon: '♙', label: '实验进度', value: '2/5', unit: '', delta: '+1', tone: 'up' },
]

const topics = [
  { key: 'd', title: 'D 触发器', status: '已完成', state: 'done' },
  { key: 'jk', title: 'JK 触发器', status: '学习中', state: 'learning' },
  { key: 'counter', title: '计数器', status: '待学习', state: 'pending' },
  { key: 'fsm', title: '状态机', status: '待学习', state: 'pending' },
]

const mastery = [
  { label: '触发器基础', value: 90, className: 'blue' },
  { label: 'JK 触发器', value: 68, className: 'purple' },
  { label: '计数器', value: 32, className: 'orange' },
  { label: '状态机', value: 25, className: 'gray' },
]
</script>

<template>
  <div class="dashboard-preview">
    <header class="topbar">
      <div class="brand">
        <div class="brand-logo" aria-hidden="true">
          <svg viewBox="0 0 48 48" role="img">
            <path d="M6 8c8 0 14 2 18 7v25c-4-5-10-7-18-7z" />
            <path d="M42 8c-8 0-14 2-18 7v25c4-5 10-7 18-7z" />
            <path d="M24 15v25" />
          </svg>
        </div>
        <strong>学海通</strong>
        <span class="brand-divider">·</span>
        <span>数字逻辑课程学习系统</span>
      </div>

      <div class="top-actions">
        <label class="search-box">
          <span>⌕</span>
          <input aria-label="搜索" placeholder="搜索知识点、习题或实验…" />
        </label>
        <button class="icon-button notification-button" type="button" aria-label="通知">
          ♢
          <span class="notification-dot"></span>
        </button>
        <div class="user-card">
          <div class="avatar">李</div>
          <div class="user-copy">
            <strong>李明</strong>
            <span>电子信息工程</span>
          </div>
          <span class="chevron">⌄</span>
        </div>
      </div>
    </header>

    <aside class="sidebar">
      <nav class="nav-list" aria-label="学生导航">
        <a
          v-for="item in navItems"
          :key="item.label"
          href="#"
          class="nav-item"
          :class="{ active: item.active }"
          @click.prevent
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </a>
      </nav>

      <div class="sidebar-footer">
        <div class="campus-art" aria-hidden="true">
          <span class="campus-tower"></span>
          <span class="campus-building left"></span>
          <span class="campus-building right"></span>
        </div>
        <p>在逻辑的世界里<br />看见更大的可能</p>
      </div>
    </aside>

    <main class="dashboard-main">
      <div class="preview-note">界面预览 · 页面中的统计数值为示例数据</div>

      <section class="hero-section">
        <div class="hero-copy">
          <div>
            <p class="eyebrow">DIGITAL LOGIC · SEQUENTIAL CIRCUITS</p>
            <h1>上午好，欢迎继续学习时序逻辑</h1>
            <p class="hero-subtitle">循序渐进，掌握时序逻辑的核心概念与电路设计方法。</p>
          </div>

          <svg class="hero-circuit" viewBox="0 0 300 160" aria-hidden="true">
            <g fill="none" stroke="currentColor" stroke-width="2">
              <path d="M8 35h80l35 28h44" />
              <path d="M8 92h105l28-22h26" />
              <path d="M26 130h77l25-20h39" />
              <rect x="167" y="20" width="92" height="120" rx="5" />
              <path d="M167 77l-14 8 14 8" />
              <path d="M259 54h30M259 106h30" />
            </g>
            <g fill="currentColor" font-size="18" font-family="ui-monospace, monospace">
              <text x="103" y="59">D</text>
              <text x="95" y="103">CLK</text>
              <text x="215" y="60">Q</text>
              <text x="214" y="112">Q̅</text>
            </g>
          </svg>
        </div>

        <div class="continue-card">
          <div class="course-badge">◇</div>
          <div class="continue-copy">
            <span>当前学习内容</span>
            <strong>时序逻辑</strong>
            <p>上次学习：<b>JK 触发器</b><i></i>继续完成本章学习，掌握典型时序电路的分析与设计方法。</p>
          </div>
          <div class="progress-block">
            <div class="progress-title"><span>学习进度</span><b>68%</b></div>
            <div class="progress-track"><span style="width: 68%"></span></div>
          </div>
          <button class="continue-button" type="button">继续学习 <span>→</span></button>
        </div>
      </section>

      <section class="stats-grid" aria-label="学习概况">
        <article v-for="stat in stats" :key="stat.label" class="stat-card">
          <div class="stat-icon">{{ stat.icon }}</div>
          <div class="stat-content">
            <span>{{ stat.label }}</span>
            <div><strong>{{ stat.value }}</strong><small>{{ stat.unit }}</small></div>
            <p :class="stat.tone">
              <b>{{ stat.tone === 'up' ? '▲' : '▼' }} {{ stat.delta }}</b>
              <span>较昨日</span>
            </p>
          </div>
        </article>
      </section>

      <section class="left-card topics-panel">
        <div class="section-title">
          <span class="title-accent"></span>
          <h2>当前知识点</h2>
        </div>

        <div class="topic-grid">
          <article
            v-for="topic in topics"
            :key="topic.key"
            class="topic-card"
            :class="{ selected: topic.state === 'learning' }"
          >
            <h3>{{ topic.title }}</h3>

            <div v-if="topic.key === 'd'" class="mini-circuit d-circuit">
              <span class="wire left top"></span>
              <span class="wire left bottom"></span>
              <span class="circuit-box"><b>D</b><i>Q</i><em>Q̅</em></span>
              <span class="wire right top"></span>
              <span class="wire right bottom"></span>
              <small>CLK</small>
            </div>

            <div v-else-if="topic.key === 'jk'" class="mini-circuit d-circuit">
              <span class="wire left top"></span>
              <span class="wire left mid"></span>
              <span class="wire left bottom"></span>
              <span class="circuit-box"><b>J</b><u>K</u><i>Q</i><em>Q̅</em></span>
              <span class="wire right top"></span>
              <span class="wire right bottom"></span>
              <small>CLK</small>
            </div>

            <div v-else-if="topic.key === 'counter'" class="counter-graphic">
              <div class="counter-inputs"><i></i><i></i><i></i></div>
              <div class="counter-box">CT</div>
              <div class="counter-outputs"><i></i><i></i></div>
            </div>

            <div v-else class="fsm-graphic">
              <span class="node n1">S0</span>
              <span class="node n2">S1</span>
              <span class="node n3">S2</span>
              <i class="fsm-line l1"></i>
              <i class="fsm-line l2"></i>
              <i class="fsm-line l3"></i>
            </div>

            <div class="topic-footer">
              <span class="topic-status" :class="topic.state">
                <i>{{ topic.state === 'done' ? '✓' : topic.state === 'learning' ? '▶' : '•' }}</i>
                {{ topic.status }}
              </span>
              <span class="topic-arrow">›</span>
            </div>
          </article>
        </div>
      </section>

      <section class="lab-panel">
        <div class="panel-heading">
          <div class="heading-left"><span>♙</span><h2>时序逻辑实验室预览</h2></div>
          <button type="button">进入实验中心 →</button>
        </div>

        <div class="lab-tabs">
          <button class="active" type="button">JK 触发器实验</button>
          <button type="button">D 触发器</button>
          <button type="button">计数器</button>
          <button type="button">状态机</button>
        </div>

        <div class="lab-workspace">
          <div class="jk-canvas">
            <div class="canvas-grid"></div>
            <div class="jk-line input j"><span>J</span><i></i></div>
            <div class="jk-line input clk"><span>CLK</span><i></i></div>
            <div class="jk-line input k"><span>K</span><i></i></div>
            <div class="jk-block">JK<small>触发器</small></div>
            <div class="jk-line output q"><i></i><span>Q</span></div>
            <div class="jk-line output qb"><i></i><span>Q̅</span></div>
          </div>

          <div class="control-panel">
            <div class="control-title">
              <strong>实验控制</strong>
              <button type="button">↻ 重置</button>
            </div>

            <div class="switch-row">
              <span>J</span><button class="switch on" type="button"><i></i></button><b>1</b>
            </div>
            <div class="switch-row">
              <span>K</span><button class="switch" type="button"><i></i></button><b>0</b>
            </div>
            <div class="switch-row">
              <span>CLK</span><button class="switch on" type="button"><i></i></button><b>1</b>
            </div>

            <div class="frequency">
              <div><span>时钟频率</span><b>1 Hz</b></div>
              <div class="range"><span></span><i></i></div>
            </div>
          </div>
        </div>

        <div class="wave-panel">
          <div class="wave-heading">
            <strong>▶ 仿真波形</strong>
            <div class="wave-actions">
              <button class="run" type="button">▶ 运行</button>
              <button type="button">Ⅱ 暂停</button>
              <button type="button">▸| 单步</button>
            </div>
          </div>

          <svg viewBox="0 0 760 235" class="wave-chart" aria-label="JK触发器仿真波形示意">
            <defs>
              <pattern id="smallGrid" width="38" height="24" patternUnits="userSpaceOnUse">
                <path d="M 38 0 L 0 0 0 24" fill="none" stroke="#edf1f8" stroke-width="1" />
              </pattern>
            </defs>
            <rect x="60" y="10" width="680" height="190" fill="url(#smallGrid)" />
            <g fill="#53627a" font-size="16" font-family="system-ui, sans-serif">
              <text x="10" y="39">CLK</text>
              <text x="24" y="82">J</text>
              <text x="24" y="126">K</text>
              <text x="24" y="170">Q</text>
            </g>
            <polyline class="wave clk-wave" points="60,42 100,42 100,18 140,18 140,42 180,42 180,18 220,18 220,42 260,42 260,18 300,18 300,42 340,42 340,18 380,18 380,42 420,42 420,18 460,18 460,42 500,42 500,18 540,18 540,42 580,42 580,18 620,18 620,42 660,42 660,18 700,18 700,42 740,42" />
            <polyline class="wave j-wave" points="60,92 125,92 125,68 270,68 270,92 380,92 380,68 560,68 560,92 700,92 700,68 740,68" />
            <polyline class="wave k-wave" points="60,136 105,136 105,112 285,112 285,136 360,136 360,112 535,112 535,136 630,136 630,112 740,112" />
            <polyline class="wave q-wave" points="60,180 170,180 170,156 310,156 310,180 480,180 480,156 560,156 560,180 660,180 660,156 740,156" />
            <g fill="#8390a5" font-size="13" font-family="system-ui, sans-serif">
              <text x="58" y="222">0</text><text x="155" y="222">20</text><text x="250" y="222">40</text>
              <text x="345" y="222">60</text><text x="440" y="222">80</text><text x="532" y="222">100</text>
              <text x="630" y="222">120</text><text x="705" y="222">t (ns)</text>
            </g>
          </svg>
        </div>
      </section>

      <section class="bottom-grid">
        <article class="assistant-card">
          <div class="bottom-heading">
            <h2><span>✦</span> AI辅导建议</h2>
            <button type="button">↻ 换一换</button>
          </div>
          <div class="suggestion">
            <div class="bulb">●</div>
            <div>
              <strong>建议先复习 JK 触发器，再完成 5 道专项练习</strong>
              <p>你在触发器的理解上已经取得不错的进展，接下来可以通过专项练习巩固状态转换与时序分析方法。</p>
            </div>
            <span>›</span>
          </div>
        </article>

        <article class="mastery-card">
          <div class="bottom-heading">
            <h2><span>▣</span> 近期掌握度</h2>
            <button type="button">查看详情 →</button>
          </div>
          <div class="mastery-list">
            <div v-for="item in mastery" :key="item.label" class="mastery-row">
              <span>{{ item.label }}</span>
              <div class="mastery-track"><i :class="item.className" :style="{ width: item.value + '%' }"></i></div>
              <b>{{ item.value }}%</b>
            </div>
          </div>
        </article>

        <article class="quote-card">
          <div class="bottom-heading">
            <h2><span>◆</span> 每日一言</h2>
            <button type="button">↻ 换一换</button>
          </div>
          <blockquote>“复杂系统，始于简单的逻辑。”</blockquote>
          <p>—— 冯·诺依曼</p>
          <div class="quote-book" aria-hidden="true">⌁</div>
        </article>
      </section>
    </main>
  </div>
</template>

<style scoped>
.dashboard-preview {
  --blue-950: #11245a;
  --blue-900: #172f73;
  --blue-800: #214aa8;
  --blue-700: #315ee8;
  --blue-600: #3f72ff;
  --blue-500: #5d86ff;
  --purple-600: #6b58ed;
  --ink: #101a34;
  --muted: #6d7891;
  --line: #e4e9f3;
  --panel: #ffffff;
  --page: #f5f7fb;
  min-height: 100vh;
  display: grid;
  grid-template-columns: 212px minmax(0, 1fr);
  grid-template-rows: 72px 1fr;
  color: var(--ink);
  background: var(--page);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
}

* {
  box-sizing: border-box;
}

button,
input {
  font: inherit;
}

button {
  cursor: pointer;
}

.topbar {
  grid-column: 1 / -1;
  position: sticky;
  top: 0;
  z-index: 20;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px 0 24px;
  border-bottom: 1px solid #edf0f6;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
  color: #172554;
  font-size: 18px;
  font-weight: 650;
}

.brand strong {
  font-size: 22px;
  font-weight: 800;
}

.brand-divider {
  color: #a2abc0;
}

.brand-logo {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  color: #3971ff;
}

.brand-logo svg {
  width: 38px;
  height: 38px;
  fill: none;
  stroke: currentColor;
  stroke-width: 3;
  stroke-linejoin: round;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.search-box {
  width: 280px;
  height: 42px;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 14px;
  border: 1px solid #edf0f7;
  border-radius: 22px;
  color: #7c879d;
  background: #f6f8fc;
}

.search-box input {
  min-width: 0;
  width: 100%;
  border: 0;
  outline: 0;
  color: #27344f;
  background: transparent;
}

.search-box input::placeholder {
  color: #a7b0c1;
}

.icon-button {
  position: relative;
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 10px;
  color: #42516f;
  background: transparent;
  font-size: 20px;
}

.notification-dot {
  position: absolute;
  top: 5px;
  right: 6px;
  width: 7px;
  height: 7px;
  border: 2px solid white;
  border-radius: 50%;
  background: #ef4444;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 150px;
}

.avatar {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #17417e;
  background: linear-gradient(145deg, #d7efff, #b9dbff);
  font-weight: 800;
}

.user-copy {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.user-copy strong {
  font-size: 14px;
}

.user-copy span {
  margin-top: 4px;
  color: #94a0b6;
  font-size: 11px;
}

.chevron {
  margin-left: auto;
  color: #8e99ad;
}

.sidebar {
  grid-column: 1;
  grid-row: 2;
  position: sticky;
  top: 72px;
  height: calc(100vh - 72px);
  display: flex;
  flex-direction: column;
  padding: 14px 12px 18px;
  border-right: 1px solid #edf0f6;
  background: white;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.nav-item {
  position: relative;
  height: 48px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 16px;
  border-radius: 10px;
  color: #485675;
  text-decoration: none;
  font-size: 15px;
  font-weight: 600;
}

.nav-item:hover {
  background: #f6f8fd;
}

.nav-item.active {
  color: #2f6bf4;
  background: #edf4ff;
}

.nav-item.active::before {
  content: "";
  position: absolute;
  left: -12px;
  top: 9px;
  width: 4px;
  height: 30px;
  border-radius: 0 4px 4px 0;
  background: #3e78ff;
}

.nav-icon {
  width: 24px;
  display: inline-grid;
  place-items: center;
  color: currentColor;
  font-size: 20px;
}

.sidebar-footer {
  margin-top: auto;
  padding: 18px 8px 0;
  color: #b1b9c9;
  text-align: center;
  font-size: 12px;
  line-height: 1.8;
}

.campus-art {
  position: relative;
  height: 72px;
  opacity: 0.55;
}

.campus-tower,
.campus-building {
  position: absolute;
  bottom: 8px;
  border: 2px solid #b9d5ff;
  border-bottom: 0;
}

.campus-tower {
  left: calc(50% - 16px);
  width: 32px;
  height: 52px;
  border-radius: 8px 8px 0 0;
}

.campus-tower::before {
  content: "";
  position: absolute;
  top: -14px;
  left: 7px;
  width: 14px;
  height: 14px;
  border: 2px solid #b9d5ff;
  border-bottom: 0;
  transform: rotate(45deg);
}

.campus-building {
  width: 52px;
  height: 28px;
}

.campus-building.left { left: 18px; }
.campus-building.right { right: 18px; }

.dashboard-main {
  grid-column: 2;
  grid-row: 2;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.58fr) minmax(390px, 1fr);
  grid-template-areas:
    "note note"
    "hero lab"
    "stats lab"
    "topics lab"
    "bottom bottom";
  gap: 14px 18px;
  padding: 14px 18px 28px;
}

.preview-note {
  grid-area: note;
  justify-self: end;
  padding: 4px 9px;
  border: 1px solid #dce6ff;
  border-radius: 999px;
  color: #6b7a99;
  background: #f7f9ff;
  font-size: 11px;
}

.hero-section {
  grid-area: hero;
  min-width: 0;
  overflow: hidden;
  border-radius: 15px;
  color: white;
  background:
    radial-gradient(circle at 70% 30%, rgba(108, 140, 255, 0.3), transparent 38%),
    linear-gradient(135deg, #17377e 0%, #294dba 58%, #3244b0 100%);
  box-shadow: 0 10px 30px rgba(35, 69, 150, 0.14);
}

.hero-copy {
  position: relative;
  min-height: 128px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 25px 26px 18px;
  overflow: hidden;
}

.hero-copy::after {
  content: "";
  position: absolute;
  inset: 0;
  opacity: 0.16;
  background-image:
    linear-gradient(90deg, transparent 49%, rgba(255,255,255,.18) 50%, transparent 51%),
    linear-gradient(0deg, transparent 49%, rgba(255,255,255,.13) 50%, transparent 51%);
  background-size: 90px 90px;
}

.eyebrow {
  position: relative;
  z-index: 2;
  margin: 0 0 6px;
  color: #aabfff;
  font-size: 10px;
  letter-spacing: 0.08em;
}

.hero-copy h1 {
  position: relative;
  z-index: 2;
  margin: 0;
  font-size: clamp(22px, 2vw, 31px);
  line-height: 1.24;
}

.hero-subtitle {
  position: relative;
  z-index: 2;
  margin: 9px 0 0;
  color: #cdd9ff;
  font-size: 13px;
}

.hero-circuit {
  position: absolute;
  top: -1px;
  right: 3px;
  width: 290px;
  height: 155px;
  color: rgba(202, 216, 255, 0.7);
  opacity: 0.72;
}

.continue-card {
  position: relative;
  z-index: 3;
  margin: 0 22px 22px;
  min-height: 108px;
  display: grid;
  grid-template-columns: 60px minmax(230px, 1.35fr) minmax(170px, 0.82fr) auto;
  align-items: center;
  gap: 18px;
  padding: 18px 20px;
  border-radius: 13px;
  color: var(--ink);
  background: rgba(255,255,255,.98);
  box-shadow: 0 8px 25px rgba(13, 38, 90, .12);
}

.course-badge {
  width: 56px;
  height: 56px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  color: #5c6df6;
  background: #eef0ff;
  font-size: 30px;
}

.continue-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.continue-copy > span {
  color: #78849a;
  font-size: 12px;
}

.continue-copy > strong {
  margin-top: 3px;
  font-size: 22px;
}

.continue-copy p {
  margin: 10px 0 0;
  color: #738098;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.continue-copy p b {
  color: #33415f;
}

.continue-copy p i {
  display: inline-block;
  height: 11px;
  margin: 0 10px;
  border-left: 1px solid #d8deea;
}

.progress-block {
  min-width: 0;
}

.progress-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  color: #6f7c96;
  font-size: 12px;
}

.progress-title b {
  color: #5364ee;
  font-size: 26px;
}

.progress-track {
  height: 10px;
  margin-top: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #e8ecf3;
}

.progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #5f6ef4, #3f8fff);
}

.continue-button {
  height: 46px;
  padding: 0 19px;
  border: 0;
  border-radius: 10px;
  color: white;
  background: linear-gradient(135deg, #5667f1, #584be7);
  box-shadow: 0 6px 18px rgba(84, 86, 233, 0.25);
  font-weight: 700;
}

.continue-button span {
  margin-left: 7px;
}

.stats-grid {
  grid-area: stats;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border: 1px solid #edf0f6;
  border-radius: 13px;
  background: white;
  box-shadow: 0 5px 16px rgba(35, 48, 78, 0.04);
}

.stat-icon {
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: #3572ff;
  background: #edf4ff;
  font-size: 21px;
}

.stat-content {
  min-width: 0;
}

.stat-content > span {
  display: block;
  margin-bottom: 5px;
  color: #77849a;
  font-size: 11px;
}

.stat-content > div {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.stat-content strong {
  color: #111d39;
  font-size: 26px;
}

.stat-content small {
  color: #5f6e88;
  font-size: 11px;
}

.stat-content p {
  display: flex;
  gap: 8px;
  margin: 5px 0 0;
  font-size: 10px;
}

.stat-content p span {
  color: #adb5c4;
}

.stat-content p.up b { color: #23ad68; }
.stat-content p.down b { color: #ef5050; }

.left-card {
  border: 1px solid #edf0f6;
  border-radius: 13px;
  background: white;
  box-shadow: 0 5px 16px rgba(35, 48, 78, 0.04);
}

.topics-panel {
  grid-area: topics;
  padding: 14px 14px 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 2px 10px;
}

.title-accent {
  width: 4px;
  height: 22px;
  border-radius: 4px;
  background: #3975ff;
}

.section-title h2 {
  margin: 0;
  font-size: 16px;
}

.topic-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 11px;
}

.topic-card {
  min-width: 0;
  height: 177px;
  display: flex;
  flex-direction: column;
  padding: 14px 14px 12px;
  border: 1px solid #dde4ef;
  border-radius: 11px;
  background: #fff;
  transition: .18s ease;
}

.topic-card.selected {
  border-color: #4f84ff;
  background: linear-gradient(180deg, #fbfdff, #f6f9ff);
  box-shadow: 0 0 0 2px rgba(79, 132, 255, .07);
}

.topic-card h3 {
  margin: 0;
  font-size: 14px;
}

.mini-circuit,
.counter-graphic,
.fsm-graphic {
  position: relative;
  height: 88px;
  margin-top: 7px;
}

.circuit-box {
  position: absolute;
  top: 16px;
  left: 50%;
  width: 64px;
  height: 62px;
  transform: translateX(-50%);
  border: 1.7px solid #303d58;
  font-style: normal;
}

.circuit-box b,
.circuit-box u,
.circuit-box i,
.circuit-box em {
  position: absolute;
  color: #2c3953;
  font-size: 11px;
  font-style: normal;
  text-decoration: none;
}

.circuit-box b { top: 9px; left: 9px; }
.circuit-box u { bottom: 8px; left: 9px; }
.circuit-box i { top: 9px; right: 7px; }
.circuit-box em { bottom: 8px; right: 7px; }

.wire {
  position: absolute;
  height: 1.5px;
  background: #303d58;
}

.wire.left { left: 19px; width: calc(50% - 51px); }
.wire.right { right: 17px; width: calc(50% - 49px); }
.wire.top { top: 34px; }
.wire.mid { top: 47px; }
.wire.bottom { top: 63px; }

.d-circuit small {
  position: absolute;
  left: 8px;
  top: 43px;
  color: #33415f;
  font-size: 9px;
}

.counter-box {
  position: absolute;
  top: 20px;
  left: 50%;
  width: 64px;
  height: 57px;
  display: grid;
  place-items: center;
  transform: translateX(-50%);
  border: 1.6px solid #303d58;
  color: #31415e;
  font-size: 11px;
  font-weight: 700;
}

.counter-inputs,
.counter-outputs {
  position: absolute;
  top: 25px;
  width: calc(50% - 32px);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.counter-inputs { left: 5px; }
.counter-outputs { right: 7px; padding-top: 6px; }

.counter-inputs i,
.counter-outputs i {
  display: block;
  height: 1.5px;
  background: #303d58;
}

.fsm-graphic .node {
  position: absolute;
  z-index: 2;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1.5px solid #33415c;
  border-radius: 50%;
  color: #2f3d56;
  background: white;
  font-size: 9px;
}

.fsm-graphic .n1 { left: calc(50% - 17px); top: 5px; }
.fsm-graphic .n2 { left: 20%; bottom: 5px; }
.fsm-graphic .n3 { right: 20%; bottom: 5px; }

.fsm-line {
  position: absolute;
  z-index: 1;
  height: 1.5px;
  background: #66738a;
  transform-origin: left center;
}

.fsm-line.l1 { left: 38%; top: 40px; width: 43px; transform: rotate(42deg); }
.fsm-line.l2 { left: 31%; bottom: 21px; width: 40%; }
.fsm-line.l3 { right: 38%; top: 40px; width: 43px; transform: rotate(-42deg); transform-origin: right center; }

.topic-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
}

.topic-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #8b95a9;
  font-size: 10px;
  font-weight: 600;
}

.topic-status i {
  width: 17px;
  height: 17px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: white;
  background: #b7bfcc;
  font-style: normal;
  font-size: 9px;
}

.topic-status.done { color: #32a966; }
.topic-status.done i { background: #30b46b; }
.topic-status.learning { color: #3474ff; }
.topic-status.learning i { background: #3f7dff; }

.topic-arrow {
  color: #51617e;
  font-size: 20px;
}

.lab-panel {
  grid-area: lab;
  min-width: 0;
  padding: 14px;
  border: 1px solid #edf0f6;
  border-radius: 13px;
  background: white;
  box-shadow: 0 5px 16px rgba(35, 48, 78, 0.04);
}

.panel-heading,
.bottom-heading,
.wave-heading,
.control-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.heading-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.heading-left > span {
  color: #3975ff;
  font-size: 20px;
}

.panel-heading h2,
.bottom-heading h2 {
  margin: 0;
  font-size: 14px;
}

.panel-heading button,
.bottom-heading button,
.control-title button {
  border: 0;
  color: #3975ff;
  background: transparent;
  font-size: 11px;
}

.lab-tabs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin-top: 14px;
  border-radius: 9px;
  background: #f7f9fc;
}

.lab-tabs button {
  position: relative;
  height: 42px;
  border: 0;
  color: #7c879d;
  background: transparent;
  font-size: 11px;
}

.lab-tabs button.active {
  color: #2f6cf4;
  font-weight: 700;
}

.lab-tabs button.active::after {
  content: "";
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 0;
  height: 2px;
  border-radius: 2px;
  background: #3e78ff;
}

.lab-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 172px;
  gap: 12px;
  margin-top: 13px;
}

.jk-canvas {
  position: relative;
  height: 255px;
  overflow: hidden;
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  background-color: white;
}

.canvas-grid {
  position: absolute;
  inset: 0;
  opacity: .8;
  background-image:
    linear-gradient(#eef2f8 1px, transparent 1px),
    linear-gradient(90deg, #eef2f8 1px, transparent 1px);
  background-size: 16px 16px;
}

.jk-block {
  position: absolute;
  top: 78px;
  left: 50%;
  width: 96px;
  height: 118px;
  display: grid;
  place-content: center;
  transform: translateX(-50%);
  border: 2px solid #28364d;
  color: #1e2a43;
  background: rgba(255,255,255,.95);
  font-size: 15px;
  font-weight: 800;
  text-align: center;
}

.jk-block small {
  display: block;
  margin-top: 4px;
  font-size: 10px;
}

.jk-line {
  position: absolute;
  z-index: 3;
  display: flex;
  align-items: center;
  color: #1e2b44;
  font-size: 12px;
}

.jk-line i {
  display: block;
  height: 2px;
  background: #26364e;
}

.jk-line.input { left: 12%; width: 39%; }
.jk-line.input span { width: 38px; text-align: right; margin-right: 8px; }
.jk-line.input i { flex: 1; }
.jk-line.j { top: 100px; }
.jk-line.clk { top: 137px; }
.jk-line.k { top: 174px; }

.jk-line.output { left: 62%; width: 31%; }
.jk-line.output i { flex: 1; margin-right: 8px; }
.jk-line.q { top: 105px; }
.jk-line.qb { top: 171px; }

.control-panel {
  padding: 14px 13px;
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  background: #fff;
}

.control-title {
  margin-bottom: 17px;
}

.control-title strong {
  font-size: 12px;
}

.switch-row {
  display: grid;
  grid-template-columns: 42px 1fr 18px;
  align-items: center;
  gap: 8px;
  margin: 13px 0;
  color: #34435f;
  font-size: 11px;
}

.switch {
  position: relative;
  width: 46px;
  height: 26px;
  border: 0;
  border-radius: 20px;
  background: #d8dee8;
}

.switch i {
  position: absolute;
  top: 4px;
  left: 4px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  box-shadow: 0 1px 4px rgba(31, 42, 67, .2);
}

.switch.on {
  background: #4290ff;
}

.switch.on i {
  left: 24px;
}

.switch-row b {
  color: #61708a;
  font-size: 11px;
}

.frequency {
  margin-top: 23px;
  color: #77839a;
  font-size: 10px;
}

.frequency > div:first-child {
  display: flex;
  justify-content: space-between;
}

.range {
  position: relative;
  height: 5px;
  margin-top: 12px;
  border-radius: 99px;
  background: #e7ebf2;
}

.range span {
  display: block;
  width: 45%;
  height: 100%;
  border-radius: inherit;
  background: #3f82ff;
}

.range i {
  position: absolute;
  top: 50%;
  left: 45%;
  width: 17px;
  height: 17px;
  transform: translate(-50%, -50%);
  border: 1px solid #dfe5f0;
  border-radius: 50%;
  background: white;
  box-shadow: 0 2px 5px rgba(30, 40, 60, .15);
}

.wave-panel {
  margin-top: 12px;
  overflow: hidden;
  border: 1px solid #e5eaf3;
  border-radius: 8px;
  background: white;
}

.wave-heading {
  height: 42px;
  padding: 0 10px 0 13px;
  border-bottom: 1px solid #edf0f6;
  color: #34415c;
  font-size: 11px;
}

.wave-actions {
  display: flex;
  gap: 5px;
}

.wave-actions button {
  height: 27px;
  padding: 0 9px;
  border: 0;
  border-radius: 6px;
  color: #65728b;
  background: #f4f6fa;
  font-size: 10px;
}

.wave-actions button.run {
  color: white;
  background: #3e7cff;
}

.wave-chart {
  width: 100%;
  display: block;
  padding: 6px 8px 4px;
}

.wave {
  fill: none;
  stroke-width: 2.4;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.clk-wave { stroke: #3c80f6; }
.j-wave { stroke: #23aa63; }
.k-wave { stroke: #ff8b31; }
.q-wave { stroke: #6d51ef; }

.bottom-grid {
  grid-area: bottom;
  display: grid;
  grid-template-columns: 1.1fr 1fr 0.92fr;
  gap: 14px;
}

.assistant-card,
.mastery-card,
.quote-card {
  min-width: 0;
  min-height: 145px;
  padding: 15px;
  border: 1px solid #edf0f6;
  border-radius: 13px;
  background: white;
  box-shadow: 0 5px 16px rgba(35, 48, 78, 0.04);
}

.bottom-heading h2 span {
  margin-right: 7px;
  color: #3475ff;
}

.suggestion {
  min-height: 89px;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) 14px;
  align-items: center;
  gap: 9px;
  margin-top: 12px;
  padding: 12px;
  border-radius: 9px;
  background: linear-gradient(135deg, #f7f3ff, #f2f6ff);
}

.bulb {
  color: #ffbc38;
  text-align: center;
  font-size: 20px;
}

.suggestion strong {
  color: #4040ad;
  font-size: 11px;
}

.suggestion p {
  margin: 6px 0 0;
  color: #78839a;
  font-size: 10px;
  line-height: 1.55;
}

.suggestion > span {
  color: #4f5d79;
  font-size: 21px;
}

.mastery-list {
  margin-top: 12px;
}

.mastery-row {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr) 36px;
  align-items: center;
  gap: 8px;
  margin: 9px 0;
  color: #63708a;
  font-size: 10px;
}

.mastery-track {
  height: 8px;
  overflow: hidden;
  border-radius: 99px;
  background: #e9edf4;
}

.mastery-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.mastery-track i.blue { background: #4586f4; }
.mastery-track i.purple { background: #7964e9; }
.mastery-track i.orange { background: #f29a49; }
.mastery-track i.gray { background: #9ca7b9; }

.mastery-row b {
  color: #68758d;
  font-size: 10px;
  text-align: right;
}

.quote-card {
  position: relative;
  overflow: hidden;
  background: linear-gradient(145deg, #fbfdff, #f4f9ff);
}

.quote-card blockquote {
  position: relative;
  z-index: 2;
  margin: 28px 0 0;
  color: #1d2943;
  font-size: 15px;
  font-weight: 700;
}

.quote-card > p {
  position: relative;
  z-index: 2;
  margin: 11px 0 0;
  color: #7f8ba1;
  font-size: 10px;
  text-align: center;
}

.quote-book {
  position: absolute;
  right: 9px;
  bottom: -24px;
  color: #d9e8ff;
  font-size: 100px;
  opacity: .5;
  transform: rotate(-10deg);
}

@media (max-width: 1320px) {
  .dashboard-preview {
    grid-template-columns: 184px minmax(0, 1fr);
  }

  .brand {
    font-size: 16px;
  }

  .search-box {
    width: 220px;
  }

  .dashboard-main {
    grid-template-columns: minmax(0, 1.45fr) minmax(360px, 1fr);
  }

  .continue-card {
    grid-template-columns: 54px minmax(190px, 1.2fr) minmax(145px, .8fr);
  }

  .continue-button {
    grid-column: 3;
    justify-self: end;
  }

  .progress-block {
    grid-column: 2;
  }
}

@media (max-width: 1080px) {
  .dashboard-main {
    grid-template-columns: 1fr;
    grid-template-areas:
      "note"
      "hero"
      "stats"
      "topics"
      "lab"
      "bottom";
  }

  .lab-workspace {
    grid-template-columns: minmax(0, 1fr) 190px;
  }

  .bottom-grid {
    grid-template-columns: 1fr 1fr;
  }

  .quote-card {
    grid-column: 1 / -1;
  }

  .user-copy {
    display: none;
  }

  .user-card {
    min-width: auto;
  }
}

@media (max-width: 760px) {
  .dashboard-preview {
    display: block;
    min-height: 100vh;
  }

  .topbar {
    height: 62px;
    padding: 0 14px;
  }

  .brand-divider,
  .brand > span:last-child,
  .search-box,
  .notification-button,
  .chevron {
    display: none;
  }

  .brand strong {
    font-size: 18px;
  }

  .brand-logo {
    width: 34px;
    height: 34px;
  }

  .brand-logo svg {
    width: 31px;
    height: 31px;
  }

  .sidebar {
    display: none;
  }

  .dashboard-main {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
  }

  .preview-note {
    align-self: flex-end;
  }

  .hero-copy {
    min-height: 140px;
    padding: 20px 18px;
  }

  .hero-circuit {
    width: 190px;
    right: -45px;
    opacity: .35;
  }

  .continue-card {
    margin: 0 12px 12px;
    grid-template-columns: 46px minmax(0, 1fr);
    gap: 10px;
    padding: 14px;
  }

  .course-badge {
    width: 44px;
    height: 44px;
    font-size: 23px;
  }

  .continue-copy > strong {
    font-size: 18px;
  }

  .continue-copy p {
    white-space: normal;
    line-height: 1.5;
  }

  .progress-block {
    grid-column: 1 / -1;
  }

  .continue-button {
    grid-column: 1 / -1;
    justify-self: stretch;
  }

  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }

  .topic-grid {
    grid-template-columns: 1fr 1fr;
  }

  .lab-workspace {
    grid-template-columns: 1fr;
  }

  .control-panel {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px 12px;
  }

  .control-title,
  .frequency {
    grid-column: 1 / -1;
  }

  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .quote-card {
    grid-column: auto;
  }
}

@media (max-width: 430px) {
  .stats-grid,
  .topic-grid {
    grid-template-columns: 1fr;
  }

  .stat-card {
    align-items: center;
  }

  .topic-card {
    height: 160px;
  }

  .lab-tabs {
    overflow-x: auto;
    grid-template-columns: repeat(4, minmax(100px, 1fr));
  }

  .jk-canvas {
    height: 220px;
  }

  .wave-panel {
    overflow-x: auto;
  }

  .wave-panel > svg {
    min-width: 690px;
  }
}
</style>
