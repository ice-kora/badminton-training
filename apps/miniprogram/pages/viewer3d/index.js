const { SYNTHETIC_BANNER, LITERATURE_BANNER, bannerForKind, statusLabel } = require('../../utils/honesty')
const { request } = require('../../utils/request')

function project(j, yaw, pitch, dist, cx, cy, scale) {
  const cosY = Math.cos(yaw)
  const sinY = Math.sin(yaw)
  const cosP = Math.cos(pitch)
  const sinP = Math.sin(pitch)
  // rotate yaw around Y, then pitch around X
  let x = j.x
  let y = j.y
  let z = j.z
  const x1 = x * cosY + z * sinY
  const z1 = -x * sinY + z * cosY
  const y2 = y * cosP - z1 * sinP
  const z2 = y * sinP + z1 * cosP
  const zCam = z2 + dist
  const f = scale / Math.max(0.35, zCam)
  return {
    x: cx + x1 * f,
    y: cy - y2 * f,
    depth: zCam,
  }
}

Page({
  data: {
    skillCode: '',
    skillName: '',
    banner: '',
    benchmarkKind: '',
    stages: [],
    hudAngles: [],
    speeds: [0.25, 0.5, 1],
    speed: 1,
    playing: true,
    currentStage: '',
    metaLine: '加载中…',
  },

  manifest: null,
  frameIdx: 0,
  canvas: null,
  ctx: null,
  raf: null,
  lastTs: 0,
  accum: 0,
  yaw: 0.4,
  pitch: 0.12,
  dist: 2.6,
  touch: null,
  dpr: 1,
  cssW: 0,
  cssH: 0,

  onLoad(q) {
    const skillCode = q.skill_code || ''
    const skillId = q.skill_id || ''
    this.setData({ skillCode })
    if (skillCode) {
      this.loadManifest(skillCode)
    } else if (skillId) {
      request({ url: `/skills/${skillId}` })
        .then((skill) => {
          this.setData({ skillCode: skill.code, skillName: skill.name })
          return this.loadManifest(skill.code)
        })
        .catch((e) => {
          this.setData({ metaLine: e.message || '加载失败' })
        })
    } else {
      this.setData({ metaLine: '缺少 skill_code' })
    }
  },

  onReady() {
    this.initCanvas()
  },

  onUnload() {
    this.stopLoop()
  },

  onHide() {
    this.stopLoop()
  },

  onShow() {
    if (this.manifest && this.ctx && this.data.playing) {
      this.startLoop()
    }
  },

  loadManifest(skillCode) {
    return request({ url: `/benchmarks/${skillCode}/viewer3d` })
      .then((m) => {
        this.manifest = m
        this.frameIdx = 0
        this.setData({
          skillName: m.skill_name || skillCode,
          banner: bannerForKind(m.benchmark_kind || m.verification_status, m.banner) || SYNTHETIC_BANNER,
          benchmarkKind: m.benchmark_kind || '',
          stages: m.stages || [],
          hudAngles: (m.hud_angles || []).slice(0, 4),
          speeds: m.playback_speeds || [0.25, 0.5, 1],
          speed: m.default_speed || 1,
          metaLine: `f=1/${m.frame_count} · ${m.sequence_source}`,
        })
        wx.setNavigationBarTitle({ title: '3D 标准动作（演示）' })
        this.draw()
        this.startLoop()
      })
      .catch((e) => {
        this.setData({ metaLine: e.message || 'manifest 加载失败' })
        wx.showToast({ title: e.message || '加载失败', icon: 'none' })
      })
  },

  initCanvas() {
    const query = wx.createSelectorQuery()
    query
      .select('#viewer3d')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res || !res[0] || !res[0].node) {
          // Fallback: old canvas API not used; retry shortly
          setTimeout(() => this.initCanvas(), 80)
          return
        }
        const canvas = res[0].node
        const ctx = canvas.getContext('2d')
        const dpr = wx.getSystemInfoSync().pixelRatio || 1
        const w = res[0].width
        const h = res[0].height
        canvas.width = w * dpr
        canvas.height = h * dpr
        ctx.scale(dpr, dpr)
        this.canvas = canvas
        this.ctx = ctx
        this.dpr = dpr
        this.cssW = w
        this.cssH = h
        this.draw()
        if (this.manifest) this.startLoop()
      })
  },

  stopLoop() {
    if (this.raf && this.canvas) {
      this.canvas.cancelAnimationFrame(this.raf)
      this.raf = null
    }
  },

  startLoop() {
    this.stopLoop()
    if (!this.canvas) return
    this.lastTs = Date.now()
    this.accum = 0
    const tick = () => {
      this.raf = this.canvas.requestAnimationFrame(tick)
      const now = Date.now()
      const dt = now - this.lastTs
      this.lastTs = now
      const m = this.manifest
      if (this.data.playing && m && m.frames && m.frames.length > 1) {
        const step = Math.max(
          16,
          (m.duration_ms || 600) / Math.max(1, m.frame_count - 1)
        )
        this.accum += dt * (this.data.speed || 1)
        let changed = false
        while (this.accum >= step) {
          this.accum -= step
          this.frameIdx = (this.frameIdx + 1) % m.frames.length
          changed = true
        }
        if (changed) {
          const fr = m.frames[this.frameIdx]
          this.setData({
            metaLine: `t=${fr.timestamp_ms}ms · f=${this.frameIdx + 1}/${m.frame_count}`,
          })
        }
      }
      this.draw()
    }
    this.raf = this.canvas.requestAnimationFrame(tick)
  },

  draw() {
    const ctx = this.ctx
    const m = this.manifest
    if (!ctx || !this.cssW) return
    const w = this.cssW
    const h = this.cssH
    ctx.clearRect(0, 0, w, h)
    // floor grid
    ctx.strokeStyle = '#1e293b'
    ctx.lineWidth = 1
    for (let i = -3; i <= 3; i++) {
      const a = project({ x: i * 0.35, y: -1, z: -1.2 }, this.yaw, this.pitch, this.dist, w / 2, h * 0.55, 280)
      const b = project({ x: i * 0.35, y: -1, z: 1.2 }, this.yaw, this.pitch, this.dist, w / 2, h * 0.55, 280)
      ctx.beginPath()
      ctx.moveTo(a.x, a.y)
      ctx.lineTo(b.x, b.y)
      ctx.stroke()
    }

    if (!m || !m.frames || !m.frames.length) {
      ctx.fillStyle = '#64748b'
      ctx.font = '14px sans-serif'
      ctx.fillText('等待关键点序列…', 16, h / 2)
      return
    }

    const fr = m.frames[this.frameIdx] || m.frames[0]
    const joints = fr.joints || []
    const pairs = m.bone_index_pairs || []
    const cx = w / 2
    const cy = h * 0.55
    const scale = Math.min(w, h) * 0.55
    const pts = joints.map((j) =>
      project(j, this.yaw, this.pitch, this.dist, cx, cy, scale)
    )

    ctx.strokeStyle = '#50c878'
    ctx.lineWidth = 3
    ctx.lineCap = 'round'
    pairs.forEach(([a, b]) => {
      if (!pts[a] || !pts[b]) return
      ctx.beginPath()
      ctx.moveTo(pts[a].x, pts[a].y)
      ctx.lineTo(pts[b].x, pts[b].y)
      ctx.stroke()
    })

    pts.forEach((p) => {
      ctx.beginPath()
      ctx.fillStyle = '#4ade80'
      ctx.arc(p.x, p.y, 4, 0, Math.PI * 2)
      ctx.fill()
    })

    ctx.fillStyle = '#94a3b8'
    ctx.font = '11px sans-serif'
    ctx.fillText('拖动旋转 · 双指/按钮缩放见控件', 12, h - 12)
  },

  onTouchStart(e) {
    const t = e.touches
    if (t.length === 1) {
      this.touch = {
        mode: 'orbit',
        x: t[0].x,
        y: t[0].y,
        yaw: this.yaw,
        pitch: this.pitch,
      }
    } else if (t.length >= 2) {
      const dx = t[0].x - t[1].x
      const dy = t[0].y - t[1].y
      this.touch = {
        mode: 'zoom',
        dist0: Math.sqrt(dx * dx + dy * dy),
        dist: this.dist,
      }
    }
  },

  onTouchMove(e) {
    if (!this.touch) return
    const t = e.touches
    if (this.touch.mode === 'orbit' && t.length === 1) {
      const dx = t[0].x - this.touch.x
      const dy = t[0].y - this.touch.y
      this.yaw = this.touch.yaw + dx * 0.01
      this.pitch = Math.max(-1.1, Math.min(1.1, this.touch.pitch + dy * 0.01))
    } else if (t.length >= 2) {
      const dx = t[0].x - t[1].x
      const dy = t[0].y - t[1].y
      const d = Math.sqrt(dx * dx + dy * dy)
      const base = this.touch.mode === 'zoom' ? this.touch : { dist0: d, dist: this.dist }
      if (this.touch.mode !== 'zoom') {
        this.touch = { mode: 'zoom', dist0: d, dist: this.dist }
      }
      const ratio = base.dist0 / Math.max(1, d)
      this.dist = Math.max(1.0, Math.min(5.5, (this.touch.dist || base.dist) * ratio))
    }
  },

  onTouchEnd() {
    this.touch = null
  },

  togglePlay() {
    const playing = !this.data.playing
    this.setData({ playing })
    if (playing) this.startLoop()
  },

  setSpeed(e) {
    const speed = parseFloat(e.currentTarget.dataset.speed)
    this.setData({ speed })
  },

  jumpStage(e) {
    const t = parseInt(e.currentTarget.dataset.t, 10) || 0
    const code = e.currentTarget.dataset.code
    const m = this.manifest
    if (!m || !m.frames) return
    let best = 0
    let bestD = 1e18
    m.frames.forEach((f, i) => {
      const d = Math.abs((f.timestamp_ms || 0) - t)
      if (d < bestD) {
        bestD = d
        best = i
      }
    })
    this.frameIdx = best
    this.setData({
      currentStage: code,
      metaLine: `stage=${code} · t=${m.frames[best].timestamp_ms}ms`,
    })
    this.draw()
  },
})
