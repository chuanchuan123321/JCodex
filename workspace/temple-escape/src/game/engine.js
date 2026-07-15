// 圣庙逃亡游戏核心引擎 —— 伪3D无尽跑酷
// 渲染策略：Canvas 2D + 透视投影（路面条纹与远景缩放）
// 操控：A/D 或 ←/→ 切换跑道；空格跳跃；点击屏幕在跑道间切换（移动端）

const LANE_COUNT = 3
const LANE_X = [-0.55, 0, 0.55] // 三条跑道的归一化x偏移（相对画面中线）

// 难度梯度：随时间加速
function difficulty(t) {
  // t: 已运行秒数
  const base = 1.0
  const ramp = Math.min(2.6, 1 + t / 35) // 35s 接近上限 3.6x
  return base * ramp
}

// 工具
const rand = (a, b) => a + Math.random() * (b - a)
const choice = arr => arr[Math.floor(Math.random() * arr.length)]
const clamp = (v, a, b) => Math.max(a, Math.min(b, v))

// 颜色：圣庙主题——金色 / 朱砂红 / 深石青 / 暮光紫
const PALETTE = {
  sky1: '#2a0a1a',
  sky2: '#0a0410',
  floor: '#1a1018',
  floorEdge: '#3a1f2a',
  laneLine: '#a87333',
  laneLineGlow: '#ffd27a',
  obstacle: '#3a1a1f',
  obstacleEdge: '#a8324a',
  obstacleHi: '#ffce6e',
  coin: '#ffd062',
  coinGlow: '#fff2b3',
  player: '#f0c674',
  playerTrim: '#8a1d2f',
  barrier: '#2a1218',
  wallGlow: '#ffb15a'
}

// 障碍物类型
const OB_TYPES = ['pillar', 'low', 'barrier', 'lantern']

export function createGame(canvas) {
  const ctx = canvas.getContext('2d')

  // 状态
  const state = {
    phase: 'menu', // menu | playing | paused | over
    t: 0,           // 累计时间 s
    speed: 0,       // 基础速度 px/s
    baseSpeed: 480,
    worldZ: 0,      // 玩家 z 推进（世界向后滚动量）
    distance: 0,    // 距离 m
    score: 0,
    coins: 0,
    best: Number(localStorage.getItem('temple_best') || 0),
    lane: 1,        // 0/1/2
    targetLaneX: 0,
    playerY: 0,     // 跳跃高度 (0 = 地面)
    vy: 0,
    isJumping: false,
    invincible: 0,  // 无敌时间（碰撞后短暂闪烁）
    flash: 0,
    shake: 0,
    obstacles: [],  // 障碍物 {z, lane, type, w, h, hit, passed}
    coins3d: [],    // 道具 {z, lane, type:'coin', taken}
    particles: [],  // 粒子
    bgStars: [],    // 背景火星/灯
    pillars: [],    // 两侧寺庙立柱（用于装饰透视）
    rngSeed: Date.now(),
    width: 0,
    height: 0,
    horizon: 0,
    groundTop: 0
  }

  // 背景火星
  function initBgStars() {
    state.bgStars = []
    for (let i = 0; i < 60; i++) {
      state.bgStars.push({
        x: Math.random(),
        y: Math.random() * 0.55,
        r: rand(0.4, 1.6),
        tw: rand(0, Math.PI * 2),
        sp: rand(0.6, 1.6),
        hue: choice(['#ffb060', '#ff7a3a', '#ffd27a', '#ff5a4a'])
      })
    }
  }
  initBgStars()

  // 立柱（用于两侧装饰，随 z 后移循环）
  function initPillars() {
    state.pillars = []
    for (let z = 0; z < 60; z += 6) {
      state.pillars.push({ z, side: -1, kind: Math.random() < 0.5 ? 'pillar' : 'lantern' })
      state.pillars.push({ z, side: 1, kind: Math.random() < 0.5 ? 'pillar' : 'lantern' })
    }
  }
  initPillars()

  // 尺寸
  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const rect = canvas.getBoundingClientRect()
    state.width = rect.width
    state.height = rect.height
    canvas.width = Math.floor(rect.width * dpr)
    canvas.height = Math.floor(rect.height * dpr)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    state.horizon = state.height * 0.42
    state.groundTop = state.horizon
  }
  window.addEventListener('resize', resize)

  // 投影：将世界 z (距离镜头) 投影到屏幕 y/scale
  function project(z) {
    // z 越小越远，z>=0 在镜头前
    const camZ = 6
    const zCam = camZ - z
    if (zCam <= 0.1) return { s: 50, y: state.horizon } // 接近镜头防爆
    const s = 1 / zCam
    const y = state.horizon + (state.height - state.horizon) * (1 - s * (camZ - 0.2))
    return { s, y }
  }

  function laneToX(laneX) {
    return state.width * 0.5 + laneX * state.width * 0.32
  }

  // 障碍物生成
  function spawnObstacle() {
    // 简化：随机跑道 + 类型
    const lane = Math.floor(Math.random() * LANE_COUNT)
    const type = choice(OB_TYPES)
    let w = 0.6, h = 0.9
    if (type === 'low') { w = 0.7; h = 0.5 }       // 低矮：可跳过
    if (type === 'barrier') { w = 0.9; h = 0.7 }   // 横档
    if (type === 'pillar') { w = 0.5; h = 1.6 }    // 高柱：必须换道
    if (type === 'lantern') { w = 0.55; h = 1.1 }  // 灯笼柱
    state.obstacles.push({
      z: state.worldZ + 120, // 远处生成
      lane,
      type,
      w, h,
      hit: false,
      passed: false
    })
  }

  function spawnCoins() {
    const lane = Math.floor(Math.random() * LANE_COUNT)
    const count = 3 + Math.floor(Math.random() * 4)
    const startZ = state.worldZ + 90 + rand(0, 20)
    for (let i = 0; i < count; i++) {
      state.coins3d.push({
        z: startZ + i * 2.2,
        lane,
        taken: false
      })
    }
  }

  // 粒子
  function emitParticles(x, y, color, n = 14) {
    for (let i = 0; i < n; i++) {
      const a = rand(0, Math.PI * 2)
      const sp = rand(60, 220)
      state.particles.push({
        x, y,
        vx: Math.cos(a) * sp,
        vy: Math.sin(a) * sp - 50,
        life: rand(0.5, 1.0),
        age: 0,
        color,
        size: rand(1.5, 3.5)
      })
    }
  }

  // 输入
  const input = { left: false, right: false, jump: false }
  function setLane(dir) {
    if (state.phase !== 'playing') return
    state.lane = clamp(state.lane + dir, 0, LANE_COUNT - 1)
  }
  function tryJump() {
    if (state.phase !== 'playing') return
    if (!state.isJumping) {
      state.isJumping = true
      state.vy = 720 // px/s
    }
  }
  window.addEventListener('keydown', (e) => {
    if (e.repeat) return
    if (e.code === 'ArrowLeft' || e.code === 'KeyA') setLane(-1)
    else if (e.code === 'ArrowRight' || e.code === 'KeyD') setLane(1)
    else if (e.code === 'Space' || e.code === 'ArrowUp' || e.code === 'KeyW') { tryJump(); e.preventDefault() }
    else if (e.code === 'Escape') togglePause()
  })

  // 触摸
  let touchStartX = 0, touchStartY = 0, touchStartT = 0
  canvas.addEventListener('touchstart', (e) => {
    const t = e.changedTouches[0]
    touchStartX = t.clientX
    touchStartY = t.clientY
    touchStartT = performance.now()
    e.preventDefault()
  }, { passive: false })
  canvas.addEventListener('touchend', (e) => {
    const t = e.changedTouches[0]
    const dx = t.clientX - touchStartX
    const dy = t.clientY - touchStartY
    const dt = performance.now() - touchStartT
    if (state.phase === 'menu') { start(); return }
    if (state.phase === 'over') { start(); return }
    if (Math.abs(dx) > 30 && Math.abs(dx) > Math.abs(dy)) {
      setLane(dx > 0 ? 1 : -1)
    } else if (dy < -30 && dt < 400) {
      tryJump()
    } else if (Math.abs(dx) < 12 && Math.abs(dy) < 12 && dt < 250) {
      // 点击：尝试跳跃
      tryJump()
    }
  })
  canvas.addEventListener('click', () => {
    if (state.phase === 'menu' || state.phase === 'over') start()
  })

  // 游戏控制
  function start() {
    state.phase = 'playing'
    state.t = 0
    state.speed = state.baseSpeed
    state.worldZ = 0
    state.distance = 0
    state.score = 0
    state.coins = 0
    state.lane = 1
    state.targetLaneX = LANE_X[1]
    state.playerY = 0
    state.vy = 0
    state.isJumping = false
    state.invincible = 0
    state.obstacles = []
    state.coins3d = []
    state.particles = []
    initPillars()
  }
  function togglePause() {
    if (state.phase === 'playing') state.phase = 'paused'
    else if (state.phase === 'paused') state.phase = 'playing'
  }
  function gameOver() {
    state.phase = 'over'
    state.best = Math.max(state.best, Math.floor(state.score))
    localStorage.setItem('temple_best', String(state.best))
    emitParticles(laneToX(state.targetLaneX), state.height * 0.72, '#ffae5a', 36)
    state.shake = 0.6
  }

  // 更新
  let last = performance.now()
  function loop(now) {
    const dt = Math.min(0.05, (now - last) / 1000)
    last = now
    update(dt)
    render()
    requestAnimationFrame(loop)
  }

  function update(dt) {
    // 即使在菜单也保持背景动画
    state.bgStars.forEach(s => { s.tw += dt * s.sp })

    if (state.phase !== 'playing') {
      // 让粒子淡出
      state.particles.forEach(p => { p.age += dt; p.vy += 200 * dt })
      state.particles = state.particles.filter(p => p.age < p.life)
      state.shake = Math.max(0, state.shake - dt)
      return
    }

    state.t += dt
    const diff = difficulty(state.t)
    state.speed = state.baseSpeed * diff
    state.worldZ += state.speed * dt
    state.distance = state.worldZ / 4 // 视觉化距离
    state.score += dt * 10 * diff

    // 立柱 z 循环
    state.pillars.forEach(p => {
      p.z -= state.speed * dt
      if (p.z < -4) p.z += 60
    })

    // 玩家横向平滑
    state.targetLaneX = LANE_X[state.lane] * state.width * 0.32
    // 用欧拉积分在屏幕坐标里
    const curX = state.width * 0.5 + (LANE_X[state.lane]) * state.width * 0.32 - 0 // 已在 laneToX
    // 上面的 targetLaneX 已是目标偏移
    // 平滑移动由渲染端做插值更稳：使用 lerp 缓存
    state._curLaneX = (state._curLaneX ?? curX) + (laneToX(state.lane) - (state._curLaneX ?? laneToX(state.lane))) * Math.min(1, dt * 12)

    // 跳跃物理
    if (state.isJumping) {
      state.vy -= 2200 * dt
      state.playerY += state.vy * dt
      if (state.playerY <= 0) {
        state.playerY = 0
        state.isJumping = false
        state.vy = 0
      }
    }

    state.invincible = Math.max(0, state.invincible - dt)
    state.flash = Math.max(0, state.flash - dt)
    state.shake = Math.max(0, state.shake - dt)

    // 障碍物前进（世界 z 推进相当于障碍变近）
    state.obstacles.forEach(o => {
      o.z -= state.speed * dt
      // 碰撞：玩家在 z≈0，命中判定
      const playerZ = 0
      const dz = Math.abs(o.z - playerZ)
      const px = state._curLaneX
      const ox = laneToX(o.lane)
      if (!o.hit && dz < 0.9 && state.invincible <= 0) {
        // 进一步：低矮障碍在跳跃时可躲过
        const isLow = o.type === 'low'
        const isJumping = state.playerY > 40
        if (Math.abs(px - ox) < state.width * 0.13) {
          if (isLow && isJumping) {
            // 跳过
            o.passed = true
            state.score += 8
          } else {
            o.hit = true
            emitParticles(px, state.height * 0.72 - state.playerY, '#ff7a3a', 28)
            state.flash = 0.25
            state.shake = 0.35
            gameOver()
          }
        }
      }
    })
    state.obstacles = state.obstacles.filter(o => o.z > -3)

    // 金币
    state.coins3d.forEach(c => {
      c.z -= state.speed * dt
      if (c.taken) return
      const dz = Math.abs(c.z)
      const px = state._curLaneX
      const cx = laneToX(c.lane)
      if (dz < 1.0 && Math.abs(px - cx) < state.width * 0.16) {
        c.taken = true
        state.coins += 1
        state.score += 5
        emitParticles(cx, state.height * 0.72 - state.playerY, '#ffd062', 10)
      }
    })
    state.coins3d = state.coins3d.filter(c => c.z > -3)

    // 粒子
    state.particles.forEach(p => {
      p.age += dt
      p.x += p.vx * dt
      p.y += p.vy * dt
      p.vy += 600 * dt
    })
    state.particles = state.particles.filter(p => p.age < p.life)

    // 道具/障碍生成节流
    if (!state._nextObsZ || state.worldZ + 120 > state._nextObsZ) {
      spawnObstacle()
      // 30% 概率在另一跑道补充一组金币
      if (Math.random() < 0.6) spawnCoins()
      state._nextObsZ = state.worldZ + 120 + rand(14, 24)
    }
  }

  // 渲染
  function render() {
    const w = state.width, h = state.height
    const horizon = state.horizon
    const shakeX = state.shake ? (Math.random() - 0.5) * state.shake * 18 : 0
    const shakeY = state.shake ? (Math.random() - 0.5) * state.shake * 18 : 0

    // 背景渐变
    const bg = ctx.createLinearGradient(0, 0, 0, h)
    bg.addColorStop(0, PALETTE.sky1)
    bg.addColorStop(0.6, '#150812')
    bg.addColorStop(1, PALETTE.sky2)
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, w, h)

    // 背景星辰/灯
    state.bgStars.forEach(s => {
      const x = s.x * w
      const y = s.y * (horizon - 10)
      const a = 0.5 + 0.5 * Math.sin(s.tw)
      ctx.globalAlpha = 0.5 + 0.5 * a
      ctx.fillStyle = s.hue
      ctx.beginPath()
      ctx.arc(x, y, s.r, 0, Math.PI * 2)
      ctx.fill()
      ctx.globalAlpha = 1
    })

    // 远景寺庙剪影
    drawTempleSilhouette(shakeX, shakeY)

    // 地面透视网格
    drawGround(shakeX, shakeY)

    // 绘制障碍物（按 z 排序，远→近）
    const sorted = [...state.obstacles].sort((a, b) => b.z - a.z)
    sorted.forEach(o => drawObstacle(o, shakeX, shakeY))

    // 绘制金币
    const sortedCoins = [...state.coins3d].sort((a, b) => b.z - a.z)
    sortedCoins.forEach(c => drawCoin(c, shakeX, shakeY, state.t))

    // 绘制玩家（最后画，最前）
    drawPlayer(shakeX, shakeY)

    // 粒子
    state.particles.forEach(p => {
      const a = 1 - p.age / p.life
      ctx.globalAlpha = a
      ctx.fillStyle = p.color
      ctx.beginPath()
      ctx.arc(p.x + shakeX, p.y + shakeY, p.size, 0, Math.PI * 2)
      ctx.fill()
    })
    ctx.globalAlpha = 1

    // 受击闪光
    if (state.flash > 0) {
      ctx.fillStyle = `rgba(255,80,80,${state.flash * 0.5})`
      ctx.fillRect(0, 0, w, h)
    }

    // UI 文字（HUD）由 Vue 层覆盖
  }

  function drawTempleSilhouette(shakeX, shakeY) {
    const w = state.width, h = state.height
    const horizon = state.horizon
    // 山形剪影
    ctx.fillStyle = '#1c0c14'
    ctx.beginPath()
    ctx.moveTo(0, horizon)
    const peaks = 7
    for (let i = 0; i <= peaks; i++) {
      const x = (i / peaks) * w
      const y = horizon - (i % 2 === 0 ? 22 : 10)
      ctx.lineTo(x, y)
    }
    ctx.lineTo(w, horizon)
    ctx.closePath()
    ctx.fill()

    // 庙宇塔尖
    const towers = 5
    for (let i = 0; i < towers; i++) {
      const x = ((i + 0.5) / towers) * w
      const baseY = horizon - 8
      const th = 18 + (i % 2) * 6
      ctx.fillStyle = '#241018'
      ctx.beginPath()
      ctx.moveTo(x - 12, baseY)
      ctx.lineTo(x - 8, baseY - th)
      ctx.lineTo(x, baseY - th - 8)
      ctx.lineTo(x + 8, baseY - th)
      ctx.lineTo(x + 12, baseY)
      ctx.closePath()
      ctx.fill()
      // 顶部微光
      ctx.fillStyle = 'rgba(255,180,90,0.35)'
      ctx.beginPath()
      ctx.arc(x, baseY - th - 10, 1.6, 0, Math.PI * 2)
      ctx.fill()
    }

    // 月
    const moonX = w * 0.78, moonY = horizon - 60
    const grad = ctx.createRadialGradient(moonX, moonY, 4, moonX, moonY, 50)
    grad.addColorStop(0, 'rgba(255,220,160,0.9)')
    grad.addColorStop(1, 'rgba(255,120,80,0)')
    ctx.fillStyle = grad
    ctx.beginPath(); ctx.arc(moonX, moonY, 50, 0, Math.PI * 2); ctx.fill()
    ctx.fillStyle = '#ffd9a0'
    ctx.beginPath(); ctx.arc(moonX, moonY, 18, 0, Math.PI * 2); ctx.fill()
  }

  function drawGround(shakeX, shakeY) {
    const w = state.width, h = state.height
    const horizon = state.horizon
    const groundBottom = h

    // 地面暗色填充
    ctx.fillStyle = PALETTE.floor
    ctx.fillRect(0, horizon, w, groundBottom - horizon)

    // 道路主体（梯形）
    const roadHalfTop = w * 0.05
    const roadHalfBot = w * 0.55
    const cx = w / 2 + shakeX
    ctx.fillStyle = '#2a1420'
    ctx.beginPath()
    ctx.moveTo(cx - roadHalfTop, horizon + shakeY)
    ctx.lineTo(cx + roadHalfTop, horizon + shakeY)
    ctx.lineTo(cx + roadHalfBot, groundBottom + shakeY)
    ctx.lineTo(cx - roadHalfBot, groundBottom + shakeY)
    ctx.closePath()
    ctx.fill()

    // 道路边缘亮线
    ctx.strokeStyle = '#8a3a3a'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(cx - roadHalfTop, horizon + shakeY); ctx.lineTo(cx - roadHalfBot, groundBottom + shakeY)
    ctx.moveTo(cx + roadHalfTop, horizon + shakeY); ctx.lineTo(cx + roadHalfBot, groundBottom + shakeY)
    ctx.stroke()

    // 跑道分隔虚线（远→近，按 y 比例均匀分布）
    const lines = 28
    const scrollIndex = Math.floor(state.worldZ * 0.6)
    for (let i = 0; i < lines; i++) {
      const t1 = i / lines
      const t2 = (i + 1) / lines
      const y1 = horizon + (groundBottom - horizon) * t1
      const y2 = horizon + (groundBottom - horizon) * t2
      // 滚动虚线
      if (((i + scrollIndex) % 2) === 0) continue
      // 当前 y 对应的路面半宽
      const halfT1 = roadHalfTop + (roadHalfBot - roadHalfTop) * t1
      const halfT2 = roadHalfTop + (roadHalfBot - roadHalfTop) * t2
      // 三条跑道：左 / 中 / 右 之间的分隔线 ≈ ±1/3, 0
      ;[-0.34, 0, 0.34].slice(0, 2).concat([-0.34, 0.34]).forEach(f => {
        // 跳过最外侧两条（已是边缘）
      })
      // 仅画两条内部分隔线（占路面 1/3 与 2/3 处）
      ;[-1/3, 1/3].forEach(f => {
        const alpha = 0.35 + 0.45 * t1
        ctx.strokeStyle = `rgba(255,210,120,${alpha})`
        ctx.lineWidth = 1.2
        ctx.beginPath()
        ctx.moveTo(cx + f * 2 * halfT2, y2)
        ctx.lineTo(cx + f * 2 * halfT1, y1)
        ctx.stroke()
      })

      // 路面水平线（强化透视感）
      ctx.strokeStyle = `rgba(255,200,130,${0.06 + 0.08 * t1})`
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(cx - (roadHalfTop + (roadHalfBot - roadHalfTop) * t1), y1)
      ctx.lineTo(cx + (roadHalfTop + (roadHalfBot - roadHalfTop) * t1), y1)
      ctx.stroke()
    }
  }

  function drawObstacle(o, shakeX, shakeY) {
    const p = project(o.z)
    if (p.s <= 0) return
    const cx = laneToX(o.lane)
    const groundY = state.height * 0.92 // 玩家所在"近地面"
    const baseY = state.horizon + (state.height - state.horizon) * (1 - p.s * 0.85)
    // 让 baseY 与透视吻合：用 (z 越小 baseY 越大)
    const tZ = clamp((6 - o.z) / 5.8, 0, 1.05)
    const yBase = state.horizon + (state.height - state.horizon) * tZ
    const x = cx + shakeX
    const y = yBase + shakeY
    const w = o.w * 90 * (0.4 + p.s * 0.8)
    const h = o.h * 110 * (0.4 + p.s * 0.8)

    ctx.save()
    ctx.translate(x, y)

    if (o.type === 'pillar') {
      // 圆角柱
      const r = w * 0.35
      ctx.fillStyle = '#3a1218'
      roundRect(ctx, -w / 2, -h, w, h, r); ctx.fill()
      ctx.strokeStyle = '#a8324a'; ctx.lineWidth = 2
      roundRect(ctx, -w / 2, -h, w, h, r); ctx.stroke()
      // 金边
      ctx.fillStyle = '#ffce6e'
      ctx.fillRect(-w / 2, -h, w, 4)
      ctx.fillRect(-w / 2, -h + h - 6, w, 4)
      // 雕刻纹
      ctx.fillStyle = 'rgba(255,206,110,0.45)'
      ctx.fillRect(-w / 2 + 4, -h + 14, 4, h - 28)
      ctx.fillRect(w / 2 - 8, -h + 14, 4, h - 28)
    } else if (o.type === 'low') {
      // 低矮石台（可跳）
      ctx.fillStyle = '#2a0f14'
      roundRect(ctx, -w / 2, -h, w, h, 6); ctx.fill()
      ctx.strokeStyle = '#a8324a'; ctx.lineWidth = 2
      roundRect(ctx, -w / 2, -h, w, h, 6); ctx.stroke()
      ctx.fillStyle = '#a8324a'
      ctx.fillRect(-w / 2, -h, w, 3)
    } else if (o.type === 'barrier') {
      // 横档（带支柱）
      ctx.fillStyle = '#2a1218'
      ctx.fillRect(-w / 2, -h * 0.7, w, h * 0.35)
      ctx.strokeStyle = PALETTE.wallGlow; ctx.lineWidth = 2
      ctx.strokeRect(-w / 2, -h * 0.7, w, h * 0.35)
      // 支柱
      ctx.fillStyle = '#1a0a10'
      ctx.fillRect(-w / 2 - 3, -h, 6, h)
      ctx.fillRect(w / 2 - 3, -h, 6, h)
      // 火焰
      const flick = 0.7 + 0.3 * Math.sin(state.t * 8 + o.z)
      ctx.fillStyle = `rgba(255,${160 + Math.floor(flick * 60)},60,0.95)`
      ctx.beginPath()
      ctx.moveTo(-w / 2, -h)
      ctx.quadraticCurveTo(-w / 2 - 4, -h - 12, -w / 2 + 2, -h - 8)
      ctx.quadraticCurveTo(0, -h - 22 - flick * 6, w / 2 - 2, -h - 8)
      ctx.quadraticCurveTo(w / 2 + 4, -h - 12, w / 2, -h)
      ctx.closePath()
      ctx.fill()
    } else if (o.type === 'lantern') {
      // 灯笼柱
      ctx.fillStyle = '#1a0a10'
      ctx.fillRect(-3, -h, 6, h * 0.7)
      // 灯笼
      ctx.fillStyle = '#7a1f2a'
      roundRect(ctx, -w / 2, -h, w, h * 0.55, w * 0.2); ctx.fill()
      ctx.strokeStyle = '#ffce6e'; ctx.lineWidth = 1.5
      roundRect(ctx, -w / 2, -h, w, h * 0.55, w * 0.2); ctx.stroke()
      // 灯光
      const flick = 0.6 + 0.4 * Math.sin(state.t * 6 + o.z * 0.7)
      ctx.fillStyle = `rgba(255,210,120,${0.4 + 0.5 * flick})`
      ctx.beginPath(); ctx.arc(0, -h + h * 0.275, w * 0.45 * (0.8 + 0.3 * flick), 0, Math.PI * 2); ctx.fill()
    }
    ctx.restore()
  }

  function drawCoin(c, shakeX, shakeY, time) {
    const p = project(c.z)
    if (p.s <= 0 || c.taken) return
    const cx = laneToX(c.lane) + shakeX
    const tZ = clamp((6 - c.z) / 5.8, 0, 1.05)
    const yBase = state.horizon + (state.height - state.horizon) * tZ - 40 * p.s
    const y = yBase + shakeY
    const r = 12 * (0.4 + p.s * 0.8)
    const wob = Math.sin(time * 4 + c.z) * 0.4 + 0.6

    // 光晕
    const grad = ctx.createRadialGradient(cx, y, 1, cx, y, r * 2.5)
    grad.addColorStop(0, 'rgba(255,242,179,0.6)')
    grad.addColorStop(1, 'rgba(255,210,120,0)')
    ctx.fillStyle = grad
    ctx.beginPath(); ctx.arc(cx, y, r * 2.5, 0, Math.PI * 2); ctx.fill()

    // 币
    ctx.save()
    ctx.translate(cx, y)
    ctx.scale(wob, 1)
    const grad2 = ctx.createRadialGradient(-r * 0.3, -r * 0.3, 1, 0, 0, r)
    grad2.addColorStop(0, '#fff2b3')
    grad2.addColorStop(0.6, PALETTE.coin)
    grad2.addColorStop(1, '#a86b1a')
    ctx.fillStyle = grad2
    ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fill()
    ctx.strokeStyle = '#a86b1a'; ctx.lineWidth = 1
    ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.stroke()
    // 文字/纹
    ctx.fillStyle = '#7a4a0a'
    ctx.font = `bold ${Math.floor(r * 1.1)}px serif`
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
    ctx.fillText('¥', 0, 1)
    ctx.restore()
  }

  function drawPlayer(shakeX, shakeY) {
    const cx = (state._curLaneX ?? laneToX(state.lane)) + shakeX
    const baseY = state.height * 0.86 + shakeY
    const y = baseY - state.playerY

    // 阴影
    const shR = 32 * Math.max(0.2, 1 - state.playerY / 400)
    ctx.fillStyle = `rgba(0,0,0,${0.4 * Math.max(0.3, 1 - state.playerY / 300)})`
    ctx.beginPath(); ctx.ellipse(cx, baseY + 6, shR, shR * 0.35, 0, 0, Math.PI * 2); ctx.fill()

    // 主角 —— 简化的"冒险者"造型（不依赖图片）
    const blink = (state.invincible > 0) ? (Math.floor(state.t * 20) % 2 === 0 ? 0.4 : 1) : 1
    ctx.save()
    ctx.globalAlpha = blink
    ctx.translate(cx, y)
    // 身体微微浮动
    const bob = Math.sin(state.t * 10) * 1.5
    ctx.translate(0, bob)

    // 腿（动态）
    const stride = state.isJumping ? 0 : Math.sin(state.t * 12) * 4
    ctx.fillStyle = PALETTE.playerTrim
    ctx.fillRect(-7, 4 - state.isJumping * 2, 5, 16 + stride)
    ctx.fillRect(2, 4 - state.isJumping * 2, 5, 16 - stride)

    // 身体（披风）
    ctx.fillStyle = PALETTE.playerTrim
    roundRect(ctx, -10, -8, 20, 18, 4); ctx.fill()
    ctx.fillStyle = '#5a0f1f'
    ctx.fillRect(-10, -8, 20, 4)

    // 头部
    ctx.fillStyle = '#f3d29b'
    ctx.beginPath(); ctx.arc(0, -16, 7, 0, Math.PI * 2); ctx.fill()
    // 头带
    ctx.fillStyle = '#d12c3f'
    ctx.fillRect(-7, -20, 14, 3)
    // 眼睛
    ctx.fillStyle = '#1a0a10'
    ctx.fillRect(-3, -17, 1.5, 2)
    ctx.fillRect(1.5, -17, 1.5, 2)

    // 手臂 / 武器
    ctx.fillStyle = PALETTE.playerTrim
    ctx.save(); ctx.translate(-10, -2); ctx.rotate(Math.sin(state.t * 8) * 0.3 - 0.2)
    ctx.fillRect(-2, 0, 4, 12); ctx.restore()
    ctx.save(); ctx.translate(10, -2); ctx.rotate(-Math.sin(state.t * 8) * 0.3 + 0.2)
    ctx.fillRect(-2, 0, 4, 12); ctx.restore()

    // 武器（金色短剑）
    ctx.save()
    ctx.translate(13, -6)
    ctx.rotate(-0.4 - Math.sin(state.t * 6) * 0.15)
    ctx.fillStyle = '#ffce6e'
    ctx.fillRect(-1.2, -16, 2.4, 18)
    ctx.fillStyle = '#a86b1a'
    ctx.fillRect(-3, 2, 6, 3)
    ctx.restore()

    // 头部光晕
    const grad = ctx.createRadialGradient(0, -16, 0, 0, -16, 22)
    grad.addColorStop(0, 'rgba(255,210,120,0.35)')
    grad.addColorStop(1, 'rgba(255,210,120,0)')
    ctx.fillStyle = grad
    ctx.beginPath(); ctx.arc(0, -16, 22, 0, Math.PI * 2); ctx.fill()

    ctx.restore()
  }

  function roundRect(ctx, x, y, w, h, r) {
    if (w < 2 * r) r = w / 2
    if (h < 2 * r) r = h / 2
    ctx.beginPath()
    ctx.moveTo(x + r, y)
    ctx.arcTo(x + w, y, x + w, y + h, r)
    ctx.arcTo(x + w, y + h, x, y + h, r)
    ctx.arcTo(x, y + h, x, y, r)
    ctx.arcTo(x, y, x + w, y, r)
    ctx.closePath()
  }

  resize()
  requestAnimationFrame(loop)

  return {
    state,
    start,
    togglePause,
    getScore: () => Math.floor(state.score),
    getBest: () => state.best,
    getCoins: () => state.coins,
    getDistance: () => Math.floor(state.distance),
    getPhase: () => state.phase,
    setLane,
    tryJump
  }
}