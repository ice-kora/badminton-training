const { request, ensureLogin } = require('../../utils/request')

const STATUS_LABEL = {
  pending: '等待中',
  rejected_precheck: '预检未通过',
  queued: '关键点排队中',
  extracting: '关键点提取中',
  pose_extracted: '关键点已提取',
  pose_failed: '关键点提取失败',
  failed: '关键点提取失败',
  not_implemented: '分析未开放',
}

function formatTime(iso) {
  if (!iso) return ''
  const s = String(iso).replace('T', ' ')
  return s.length > 19 ? s.slice(0, 19) : s
}

function formatDuration(ms) {
  if (ms == null) return '-'
  return `${Math.round(ms / 1000)} 秒`
}

function checkClass(status) {
  if (status === 'pass') return 'check-pass'
  if (status === 'fail') return 'check-fail'
  return 'check-other'
}

Page({
  data: {
    loading: true,
    error: '',
    video: null,
    videoId: null,
    checks: [],
    jobs: [],
    precheckPassed: false,
    durationText: '',
    createdText: '',
    poseExtracted: false,
    poseFrameCount: null,
    scoringBlocked: true,
    previewFrame: 0,
    previewMax: 0,
    previewLoading: false,
    previewError: '',
    canvasCssW: 360,
    canvasCssH: 480,
  },
  _canvas: null,
  _ctx: null,
  _previewSeq: 0,
  onLoad(q) {
    const id = q.id
    if (!id) {
      this.setData({ loading: false, error: '缺少视频 id' })
      return
    }
    this.setData({ videoId: id })
    ensureLogin()
      .then(() => request({ url: `/videos/${id}`, auth: true }))
      .then((video) => {
        const checks = ((video.precheck && video.precheck.checks) || []).map((c) => ({
          ...c,
          cls: checkClass(c.status),
        }))
        const jobs = (video.jobs || []).map((j) => ({
          ...j,
          statusLabel: STATUS_LABEL[j.status] || j.status,
        }))
        const poseExtracted = !!video.pose_extracted
        const frameCount = video.pose_frame_count || 0
        this.setData({
          loading: false,
          video,
          checks,
          jobs,
          precheckPassed: !!(video.precheck && video.precheck.passed),
          durationText: formatDuration(video.duration_ms),
          createdText: formatTime(video.created_at),
          poseExtracted,
          poseFrameCount: frameCount || null,
          scoringBlocked: true,
          previewFrame: 0,
          previewMax: Math.max(0, frameCount - 1),
        })
        if (poseExtracted) {
          wx.nextTick(() => this.initCanvasAndLoad(0))
        }
      })
      .catch((e) => {
        this.setData({
          loading: false,
          error: (e && (e.message || e.detail)) || '加载失败',
        })
      })
  },
  initCanvasAndLoad(frame) {
    const query = wx.createSelectorQuery()
    query
      .select('#skeletonCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res || !res[0] || !res[0].node) {
          this.setData({ previewError: '画布不可用' })
          return
        }
        const canvas = res[0].node
        const ctx = canvas.getContext('2d')
        const dpr = wx.getSystemInfoSync().pixelRatio || 1
        const cssW = res[0].width || 360
        const cssH = res[0].height || 480
        canvas.width = cssW * dpr
        canvas.height = cssH * dpr
        ctx.scale(dpr, dpr)
        this._canvas = canvas
        this._ctx = ctx
        this._cssW = cssW
        this._cssH = cssH
        this.setData({ canvasCssW: cssW, canvasCssH: cssH })
        this.loadPreviewFrame(frame)
      })
  },
  onPreviewScrub(e) {
    const frame = Number(e.detail.value) || 0
    this.setData({ previewFrame: frame })
    this.loadPreviewFrame(frame)
  },
  loadPreviewFrame(frame) {
    const videoId = this.data.videoId
    if (!videoId) return
    const seq = ++this._previewSeq
    this.setData({ previewLoading: true, previewError: '' })
    request({
      url: `/videos/${videoId}/pose/preview`,
      auth: true,
      data: { frame, format: 'json' },
    })
      .then((body) => {
        if (seq !== this._previewSeq) return
        this.setData({
          previewLoading: false,
          previewMax: Math.max(0, (body.frame_count || 1) - 1),
          previewFrame: body.frame != null ? body.frame : frame,
        })
        this.drawSkeleton(body)
      })
      .catch((e) => {
        if (seq !== this._previewSeq) return
        this.setData({
          previewLoading: false,
          previewError: (e && (e.message || e.detail)) || '预览加载失败',
        })
      })
  },
  drawSkeleton(body) {
    const ctx = this._ctx
    if (!ctx) return
    const w = this._cssW || 360
    const h = this._cssH || 480
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = '#181820'
    ctx.fillRect(0, 0, w, h)

    const landmarks = body.landmarks || []
    const bones = body.bones || []
    const pts = landmarks.map((lm) => {
      if (!lm || lm.x == null || lm.y == null) return null
      if (lm.visibility != null && lm.visibility < 0.1) return null
      return { x: lm.x * w, y: lm.y * h }
    })

    ctx.strokeStyle = '#50c878'
    ctx.lineWidth = 2
    bones.forEach((b) => {
      const a = pts[b.from]
      const c = pts[b.to]
      if (!a || !c) return
      ctx.beginPath()
      ctx.moveTo(a.x, a.y)
      ctx.lineTo(c.x, c.y)
      ctx.stroke()
    })

    ctx.fillStyle = '#dcdc50'
    pts.forEach((p) => {
      if (!p) return
      ctx.beginPath()
      ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2)
      ctx.fill()
    })

    ctx.fillStyle = '#b4b4c8'
    ctx.font = '12px sans-serif'
    ctx.fillText('仅关键点可视化，非评分', 8, 18)
  },
})
