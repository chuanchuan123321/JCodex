<script setup>
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import { createGame } from './game/engine.js'

const canvasRef = ref(null)
const hud = ref({ score: 0, best: 0, coins: 0, distance: 0, phase: 'menu' })
let game = null

// RAF tick 用于刷新 HUD（轻量）
let rafId = null
function tick() {
  if (game) {
    const s = game.state
    hud.value = {
      score: Math.floor(s.score),
      best: s.best,
      coins: s.coins,
      distance: Math.floor(s.distance),
      phase: s.phase
    }
  }
  rafId = requestAnimationFrame(tick)
}

onMounted(() => {
  game = createGame(canvasRef.value)
  rafId = requestAnimationFrame(tick)
})
onBeforeUnmount(() => {
  cancelAnimationFrame(rafId)
  if (game) game = null
})

const phase = computed(() => hud.value.phase)
function startGame() { game && game.start() }
function togglePause() { game && game.togglePause() }
function moveLeft() { game && game.setLane(-1) }
function moveRight() { game && game.setLane(1) }
function jump() { game && game.tryJump() }
</script>

<template>
  <div class="stage">
    <canvas ref="canvasRef" class="game-canvas"></canvas>

    <!-- HUD -->
    <div class="hud" v-show="phase === 'playing' || phase === 'paused'">
      <div class="hud-left">
        <div class="hud-row">
          <span class="hud-icon">★</span>
          <span class="hud-val">{{ hud.score }}</span>
        </div>
        <div class="hud-row sub">
          <span class="hud-icon coin">●</span>
          <span class="hud-val">{{ hud.coins }}</span>
        </div>
      </div>
      <div class="hud-right">
        <div class="hud-row small">
          <span class="lbl">距离</span>
          <span class="hud-val">{{ hud.distance }} m</span>
        </div>
        <div class="hud-row small">
          <span class="lbl">最佳</span>
          <span class="hud-val">{{ hud.best }}</span>
        </div>
      </div>
      <button class="pause-btn" @click="togglePause" :title="phase === 'paused' ? '继续' : '暂停'">
        <span v-if="phase === 'paused'">▶</span>
        <span v-else>❚❚</span>
      </button>
    </div>

    <!-- 开始菜单 -->
    <div class="overlay menu" v-show="phase === 'menu'">
      <div class="title-wrap">
        <div class="lantern l"></div>
        <div class="lantern r"></div>
        <h1 class="title">圣庙逃亡</h1>
        <div class="subtitle">TEMPLE · ESCAPE</div>
        <p class="desc">夜色压城，寺庙坍塌。你在古庙残垣间飞奔，<br/>躲开石柱、跳过低台、穿越火墙，拾取金币！</p>

        <button class="big-btn" @click="startGame">开 始 逃 亡</button>

        <div class="control-grid">
          <div class="ctrl-card">
            <div class="key-row"><kbd>A</kbd><kbd>D</kbd> / <kbd>←</kbd><kbd>→</kbd></div>
            <div class="ctrl-label">切换跑道</div>
          </div>
          <div class="ctrl-card">
            <div class="key-row"><kbd>Space</kbd> / <kbd>↑</kbd></div>
            <div class="ctrl-label">跳跃</div>
          </div>
          <div class="ctrl-card">
            <div class="key-row"><kbd>Esc</kbd></div>
            <div class="ctrl-label">暂停</div>
          </div>
          <div class="ctrl-card mobile">
            <div class="key-row"><span>滑动</span><span>点击</span></div>
            <div class="ctrl-label">移动端操作</div>
          </div>
        </div>

        <div class="best" v-if="hud.best">历史最佳：{{ hud.best }}</div>
      </div>
    </div>

    <!-- 暂停 -->
    <div class="overlay pause" v-show="phase === 'paused'">
      <div class="panel">
        <h2>暂 停</h2>
        <button class="big-btn" @click="togglePause">继 续</button>
        <button class="ghost-btn" @click="startGame">重新开始</button>
      </div>
    </div>

    <!-- 结束 -->
    <div class="overlay over" v-show="phase === 'over'">
      <div class="panel">
        <h2 class="over-title">失 足 坠 落</h2>
        <div class="stats">
          <div class="stat">
            <div class="stat-label">本次得分</div>
            <div class="stat-val">{{ hud.score }}</div>
          </div>
          <div class="stat">
            <div class="stat-label">历史最佳</div>
            <div class="stat-val best">{{ hud.best }}</div>
          </div>
          <div class="stat">
            <div class="stat-label">金币</div>
            <div class="stat-val coin-c">{{ hud.coins }}</div>
          </div>
          <div class="stat">
            <div class="stat-label">距离</div>
            <div class="stat-val">{{ hud.distance }} m</div>
          </div>
        </div>
        <button class="big-btn" @click="startGame">再 来 一 次</button>
      </div>
    </div>

    <!-- 移动端操作 -->
    <div class="touch-controls" v-show="phase === 'playing'">
      <button class="tbtn left" @touchstart.prevent="moveLeft" @mousedown.prevent="moveLeft">◀</button>
      <button class="tbtn jump" @touchstart.prevent="jump" @mousedown.prevent="jump">跳</button>
      <button class="tbtn right" @touchstart.prevent="moveRight" @mousedown.prevent="moveRight">▶</button>
    </div>
  </div>
</template>

<style scoped>
.stage {
  position: relative;
  width: 100%;
  height: 100%;
  display: block;
  overflow: hidden;
  border-radius: 12px;
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 200, 130, 0.08) inset;
}
.game-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}

.hud {
  position: absolute;
  inset: 0 0 auto 0;
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  pointer-events: none;
  font-family: 'Cinzel', 'Songti SC', 'Noto Serif SC', serif;
}
.hud > * { pointer-events: auto; }
.hud-left, .hud-right { display: flex; flex-direction: column; gap: 6px; }
.hud-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  color: #f5e7c4;
  background: rgba(20, 8, 12, 0.45);
  border: 1px solid rgba(255, 200, 130, 0.18);
  padding: 6px 12px;
  border-radius: 22px;
  backdrop-filter: blur(6px);
}
.hud-row.small { font-size: 13px; opacity: 0.85; padding: 4px 10px; }
.hud-row.sub { background: rgba(40, 16, 6, 0.5); }
.hud-icon { color: #ffd27a; font-size: 16px; }
.hud-icon.coin { color: #ffd062; font-size: 11px; }
.hud-val { font-size: 22px; font-weight: 700; letter-spacing: 1px; }
.hud-row.small .hud-val { font-size: 14px; }
.lbl { font-size: 11px; opacity: 0.7; letter-spacing: 2px; }

.pause-btn {
  pointer-events: auto;
  width: 44px; height: 44px;
  border-radius: 50%;
  background: rgba(20, 8, 12, 0.55);
  border: 1px solid rgba(255, 200, 130, 0.25);
  color: #ffd27a;
  font-size: 14px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: transform .15s ease, background .2s ease;
}
.pause-btn:hover { transform: scale(1.05); background: rgba(40, 14, 20, 0.7); }

/* Overlay */
.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(ellipse at center, rgba(20, 8, 12, 0.55) 0%, rgba(8, 4, 6, 0.85) 80%);
  backdrop-filter: blur(2px);
  z-index: 10;
}
.panel {
  background: linear-gradient(180deg, rgba(35, 14, 20, 0.85), rgba(20, 8, 12, 0.92));
  border: 1px solid rgba(255, 200, 130, 0.25);
  padding: 36px 40px;
  border-radius: 16px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 30px rgba(255, 150, 80, 0.1) inset;
  min-width: 320px;
}
.panel h2 { font-size: 28px; letter-spacing: 8px; color: #ffd27a; margin-bottom: 20px; }
.over-title { color: #ff8a5a; }

/* 菜单 */
.title-wrap {
  position: relative;
  text-align: center;
  padding: 40px 30px;
  max-width: 560px;
}
.title {
  font-size: 64px;
  letter-spacing: 24px;
  margin: 0;
  font-weight: 900;
  background: linear-gradient(180deg, #ffe7b3 0%, #ffae5a 60%, #c66a2a 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: 0 0 30px rgba(255, 174, 90, 0.3);
  filter: drop-shadow(0 4px 10px rgba(0, 0, 0, 0.5));
}
.subtitle {
  font-size: 13px;
  letter-spacing: 8px;
  opacity: 0.7;
  margin-top: 8px;
  color: #ffd27a;
}
.desc {
  margin: 24px auto 30px;
  font-size: 15px;
  line-height: 1.9;
  color: #f5e7c4;
  opacity: 0.9;
  max-width: 420px;
}
.big-btn {
  margin-top: 4px;
  padding: 14px 38px;
  font-size: 18px;
  letter-spacing: 6px;
  color: #2a0f14;
  background: linear-gradient(180deg, #ffe7b3, #ffae5a 60%, #c66a2a);
  border: none;
  border-radius: 30px;
  cursor: pointer;
  font-weight: 800;
  font-family: inherit;
  box-shadow: 0 8px 24px rgba(255, 150, 80, 0.35), 0 0 0 1px rgba(255, 220, 160, 0.5) inset;
  transition: transform .15s ease, box-shadow .2s ease;
}
.big-btn:hover { transform: translateY(-2px); box-shadow: 0 12px 30px rgba(255, 150, 80, 0.5); }
.big-btn:active { transform: translateY(0); }

.ghost-btn {
  margin-top: 12px;
  background: transparent;
  border: 1px solid rgba(255, 200, 130, 0.4);
  color: #ffd27a;
  padding: 10px 24px;
  border-radius: 30px;
  cursor: pointer;
  font-family: inherit;
  letter-spacing: 4px;
  transition: all .2s;
}
.ghost-btn:hover { background: rgba(255, 200, 130, 0.08); }

.control-grid {
  margin-top: 36px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  max-width: 520px;
  margin-left: auto;
  margin-right: auto;
}
.ctrl-card {
  background: rgba(255, 200, 130, 0.06);
  border: 1px solid rgba(255, 200, 130, 0.15);
  padding: 12px 8px;
  border-radius: 10px;
}
.ctrl-card.mobile { display: none; }
.key-row { display: flex; gap: 4px; justify-content: center; align-items: center; min-height: 28px; flex-wrap: wrap; }
.key-row span { font-size: 12px; color: #ffd27a; padding: 2px 6px; border: 1px solid rgba(255, 200, 130, 0.3); border-radius: 4px; }
kbd {
  display: inline-block;
  background: rgba(255, 200, 130, 0.1);
  border: 1px solid rgba(255, 200, 130, 0.35);
  border-bottom-width: 2px;
  color: #ffd27a;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 13px;
  font-family: 'Courier New', monospace;
  min-width: 18px;
  text-align: center;
}
.ctrl-label { font-size: 12px; opacity: 0.7; margin-top: 6px; letter-spacing: 1px; }

.best {
  margin-top: 24px;
  font-size: 13px;
  color: #ffd27a;
  letter-spacing: 2px;
  opacity: 0.85;
}

.lantern {
  position: absolute;
  top: -10px;
  width: 24px;
  height: 36px;
  background: radial-gradient(circle at 50% 40%, #ffd062 0%, #c66a2a 60%, #5a1a0a 100%);
  border-radius: 12px 12px 6px 6px;
  box-shadow: 0 0 30px rgba(255, 174, 90, 0.5);
  animation: swing 2.4s ease-in-out infinite;
  transform-origin: top center;
}
.lantern::before {
  content: '';
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%);
  width: 12px;
  height: 2px;
  background: #5a3a1a;
}
.lantern::after {
  content: '';
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  width: 2px;
  height: 8px;
  background: #5a3a1a;
}
.lantern.l { left: -40px; }
.lantern.r { right: -40px; animation-delay: -1.2s; }
@keyframes swing {
  0%, 100% { transform: rotate(-4deg); }
  50% { transform: rotate(4deg); }
}

/* 结算 */
.stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin: 20px 0 28px;
}
.stat {
  padding: 14px 8px;
  background: rgba(255, 200, 130, 0.06);
  border: 1px solid rgba(255, 200, 130, 0.18);
  border-radius: 10px;
}
.stat-label { font-size: 12px; opacity: 0.7; letter-spacing: 2px; }
.stat-val { font-size: 26px; font-weight: 700; color: #ffd27a; margin-top: 6px; }
.stat-val.best { color: #ffe7b3; text-shadow: 0 0 16px rgba(255, 200, 130, 0.5); }
.stat-val.coin-c { color: #ffd062; }

/* 移动端控制 */
.touch-controls {
  position: absolute;
  bottom: 16px;
  left: 0;
  right: 0;
  display: none;
  justify-content: space-between;
  padding: 0 18px;
  z-index: 5;
  pointer-events: none;
}
.tbtn {
  pointer-events: auto;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: rgba(255, 200, 130, 0.12);
  border: 2px solid rgba(255, 200, 130, 0.35);
  color: #ffd27a;
  font-size: 24px;
  font-weight: 800;
  cursor: pointer;
  backdrop-filter: blur(6px);
  -webkit-user-select: none;
  user-select: none;
}
.tbtn.jump { background: rgba(255, 150, 80, 0.18); border-color: rgba(255, 150, 80, 0.5); }

@media (max-width: 720px) {
  .title { font-size: 44px; letter-spacing: 16px; }
  .subtitle { font-size: 11px; letter-spacing: 6px; }
  .desc { font-size: 13px; }
  .control-grid { grid-template-columns: repeat(2, 1fr); max-width: 320px; }
  .ctrl-card.mobile { display: block; }
  .panel { padding: 28px 24px; min-width: 280px; }
  .hud { padding: 12px 14px; }
  .hud-val { font-size: 18px; }
  .touch-controls { display: flex; }
  .lantern { display: none; }
}
@media (max-height: 560px) {
  .title { font-size: 36px; }
  .control-grid { margin-top: 20px; }
  .desc { margin: 14px auto 18px; }
}
</style>