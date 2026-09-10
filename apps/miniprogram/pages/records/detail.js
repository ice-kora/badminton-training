const { request, ensureLogin, getToken, baseUrl } = require('../../utils/request')

const STATUS_LABEL = {
  pending: '等待中',
  rejected_precheck: '预检未通过',
  queued: '关键点排队中',
  extracting: '关键点提取中',
  pose_extracted: '关键点已提取',
  scored: '已评分',
  pose_failed: '关键点提取失败',
  failed: '关键点提取失败',
  not_implemented: '该动作标准标定中，暂时无法评分',
}

const {
  SYNTHETIC_BANNER,
  LITERATURE_BANNER,
  bannerForKind,
  humanizeJobMessage,
} = require('../../utils/honesty')

function formatTime(iso) {
  if (!iso) return ''
  const s = String(iso).replace('T', ' ')
  return s.length > 19 ? s.slice(0, 19) : s
}

function formatDuration(ms) {
  if (ms == null) return '-'
  return `${Math.round(ms / 1000)} 秒`
}


function humanizeStageSegment(s, index) {
  const name = s.name || s.code || ('阶段' + (index + 1))
  const pace = s.pace_label || ''
  let paceLabel = pace
  if (!paceLabel && s.delta_ms != null) {
    const d = Number(s.delta_ms)
    const thr = 80
    if (Math.abs(d) >= thr) {
      paceLabel = d > 0 ? (name + '偏慢') : (name + '偏快')
    }
  }
  return {
    ...s,
    stageOrderLabel: '第' + (index + 1) + '段 · ' + name,
    paceLabel,
    // keep deltaText empty for amateurs (no lab ms)
    deltaText: '',
  }
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
    hasBaseline: false,
    baselineSummary: null,
    canCompare: false,
    compareFrame: 0,
    compareMax: 0,
    compareLoading: false,
    compareError: '',
    compareCanvasCssW: 160,
    compareCanvasCssH: 240,
    score: null,
    problems: [],
    dimensionList: [],
    benchmarkKind: null,
    isSyntheticDemo: false,
    isLiteratureCited: false,
    scoringBanner: SYNTHETIC_BANNER,
    scoreDelta: null,
    scoreDeltaText: '',
    baselineOverall: null,
    currentOverall: null,
    stageSegments: [],
    stageNotice: '',
    overlayAvailable: false,
    overlaySynthetic: false,
    overlayFrame: 0,
    overlayMax: 0,
    overlayLoading: false,
    overlayError: '',
    overlayStageName: '',
    overlayCssW: 360,
    overlayCssH: 480,
    videoUrl: '',
    playbackRate: 1,
    playerTime: 0,
    showSkeleton: false,
    showOverlayPanel: false,
  },
  _canvas: null,
  _ctx: null,
  _previewSeq: 0,
  _compareSeq: 0,
  _overlaySeq: 0,
  _overlayCanvas: null,
  _overlayCtx: null,
  _baseCanvas: null,
  _baseCtx: null,
  _curCanvas: null,
  _curCtx: null,
  onLoad(q) {
    const id = q.id
    if (!id) {
      this.setData({ loading: false, error: '缺少视频 id' })
      return
    }
    this.setData({ videoId: id })
    ensureLogin()
      .then(() => {
        const token = getToken()
        this.setData({
          videoUrl: `${baseUrl}/videos/${id}/file?token=${encodeURIComponent(token || '')}`,
        })
        return request({ url: `/videos/${id}`, auth: true })
      })
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
        const baseline = video.baseline || null
        const hasBaseline = !!(video.baseline_video_id && baseline)
        const baselinePoseOk = !!(baseline && baseline.pose_extracted)
        const canCompare = hasBaseline && poseExtracted && baselinePoseOk
        const score = video.score || null
        const problems = (video.problems || (score && score.problems) || []).slice(0, 3)
        const dims = score && score.dimension_scores ? score.dimension_scores : {}
        const dimensionList = Object.keys(dims).map((id) => ({
          id,
          name: id,
          score: dims[id],
        }))
        const benchmarkKind = video.benchmark_kind || (score && score.benchmark_kind) || null
        const isSyntheticDemo = benchmarkKind === 'synthetic_demo'
        const isLiteratureCited = benchmarkKind === 'literature_cited'
        const scoringBanner =
          video.scoring_banner ||
          (score && score.banner) ||
          bannerForKind(isLiteratureCited ? 'literature_cited' : isSyntheticDemo ? 'synthetic_demo' : '', '')
        const stageTimeline = video.stage_timeline || null
        const stageSegments = ((stageTimeline && stageTimeline.segments) || []).map((s, i) =>
          humanizeStageSegment(s, i)
        )
        const overlayAvailable = !!(video.overlay_available || poseExtracted)
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
          scoringBlocked: !score,
          previewFrame: 0,
          previewMax: Math.max(0, frameCount - 1),
          hasBaseline,
          baselineSummary: baseline,
          canCompare,
          compareFrame: 0,
          compareMax: 0,
          score,
          problems,
          dimensionList,
          benchmarkKind,
          isSyntheticDemo,
          isLiteratureCited,
          scoringBanner,
          stageSegments,
          stageNotice: (stageTimeline && stageTimeline.notice) || '',
          overlayAvailable,
          overlaySynthetic: isSyntheticDemo,
          overlayFrame: 0,
          overlayMax: Math.max(0, frameCount - 1),
        })
        // Skeleton / overlay default OFF — load only when user opts in
        if (canCompare) {
          wx.nextTick(() => this.initCompareCanvasesAndLoad(0))
        }
      })
      .catch((e) => {
        this.setData({
          loading: false,
          error: (e && (e.message || e.detail)) || '加载失败',
        })
      })
  },
  goRetest() {
    const video = this.data.video
    if (!video) return
    wx.navigateTo({
      url: `/pages/filming/record?skill_id=${video.skill_id}&baseline_video_id=${video.id}`,
    })
  },
  goDrill(e) {
    const code = e.currentTarget.dataset.code
    if (code) {
      wx.navigateTo({ url: `/pages/drills/detail?code=${code}` })
      return
    }
    wx.switchTab({ url: '/pages/plan/index' })
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
        this.drawSkeleton(this._ctx, this._cssW || 360, this._cssH || 480, body, '仅关键点可视化，非评分')
      })
      .catch((e) => {
        if (seq !== this._previewSeq) return
        this.setData({
          previewLoading: false,
          previewError: (e && (e.message || e.detail)) || '预览加载失败',
        })
      })
  },
  initCompareCanvasesAndLoad(frame) {
    const query = wx.createSelectorQuery()
    query
      .select('#compareBaselineCanvas')
      .fields({ node: true, size: true })
      .select('#compareCurrentCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res || !res[0] || !res[0].node || !res[1] || !res[1].node) {
          this.setData({ compareError: '对比画布不可用' })
          return
        }
        const dpr = wx.getSystemInfoSync().pixelRatio || 1
        const setup = (nodeRes) => {
          const canvas = nodeRes.node
          const ctx = canvas.getContext('2d')
          const cssW = nodeRes.width || 160
          const cssH = nodeRes.height || 240
          canvas.width = cssW * dpr
          canvas.height = cssH * dpr
          ctx.scale(dpr, dpr)
          return { canvas, ctx, cssW, cssH }
        }
        const base = setup(res[0])
        const cur = setup(res[1])
        this._baseCanvas = base.canvas
        this._baseCtx = base.ctx
        this._baseCssW = base.cssW
        this._baseCssH = base.cssH
        this._curCanvas = cur.canvas
        this._curCtx = cur.ctx
        this._curCssW = cur.cssW
        this._curCssH = cur.cssH
        this.setData({
          compareCanvasCssW: base.cssW,
          compareCanvasCssH: base.cssH,
        })
        this.loadCompareFrame(frame)
      })
  },
  onCompareScrub(e) {
    const frame = Number(e.detail.value) || 0
    this.setData({ compareFrame: frame })
    this.loadCompareFrame(frame)
  },
  loadCompareFrame(frame) {
    const videoId = this.data.videoId
    if (!videoId || !this.data.canCompare) return
    const seq = ++this._compareSeq
    this.setData({ compareLoading: true, compareError: '' })
    request({
      url: `/videos/${videoId}/retest-compare`,
      auth: true,
      data: { frame },
    })
      .then((body) => {
        if (seq !== this._compareSeq) return
        const base = body.baseline || {}
        const cur = body.current || {}
        const maxB = Math.max(0, (base.frame_count || 1) - 1)
        const maxC = Math.max(0, (cur.frame_count || 1) - 1)
        const delta = body.score_delta
        const baseSc = body.baseline_score
        const curSc = body.current_score
        const patch = {
          compareLoading: false,
          compareMax: Math.min(maxB, maxC),
          compareFrame: frame,
        }
        if (delta != null && baseSc && curSc) {
          const sign = delta > 0 ? '+' : ''
          patch.scoreDelta = delta
          patch.scoreDeltaText = `${sign}${delta}`
          patch.baselineOverall = baseSc.overall_score
          patch.currentOverall = curSc.overall_score
          if (
            baseSc.benchmark_kind === 'synthetic_demo' ||
            curSc.benchmark_kind === 'synthetic_demo' ||
            baseSc.benchmark_kind === 'literature_cited' ||
            curSc.benchmark_kind === 'literature_cited'
          ) {
            patch.isSyntheticDemo = true
            patch.scoringBanner = SYNTHETIC_BANNER
          }
        }
        this.setData(patch)
        this.drawSkeleton(
          this._baseCtx,
          this._baseCssW || 160,
          this._baseCssH || 240,
          base,
          '基准'
        )
        this.drawSkeleton(
          this._curCtx,
          this._curCssW || 160,
          this._curCssH || 240,
          cur,
          '复测'
        )
      })
      .catch((e) => {
        if (seq !== this._compareSeq) return
        this.setData({
          compareLoading: false,
          compareError: (e && (e.message || e.detail)) || '对比加载失败',
        })
      })
  },

  initOverlayCanvasAndLoad(frame) {
    const query = wx.createSelectorQuery()
    query
      .select('#overlayCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res || !res[0] || !res[0].node) {
          this.setData({ overlayError: '叠加画布不可用' })
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
        this._overlayCanvas = canvas
        this._overlayCtx = ctx
        this._overlayCssW = cssW
        this._overlayCssH = cssH
        this.setData({ overlayCssW: cssW, overlayCssH: cssH })
        this.loadOverlayFrame(frame)
      })
  },
  onOverlayScrub(e) {
    const frame = Number(e.detail.value) || 0
    this.setData({ overlayFrame: frame })
    this.loadOverlayFrame(frame)
  },
  loadOverlayFrame(frame) {
    const videoId = this.data.videoId
    if (!videoId || !this.data.overlayAvailable) return
    const seq = ++this._overlaySeq
    this.setData({ overlayLoading: true, overlayError: '' })
    request({
      url: `/videos/${videoId}/pose/overlay`,
      auth: true,
      data: { frame },
    })
      .then((body) => {
        if (seq !== this._overlaySeq) return
        const stage = body.current_stage || null
        const patch = {
          overlayLoading: false,
          overlayMax: Math.max(0, (body.frame_count || 1) - 1),
          overlayFrame: body.frame != null ? body.frame : frame,
          overlayStageName: stage ? stage.name || stage.code : '',
          overlaySynthetic:
            body.benchmark_kind === 'synthetic_demo' ||
            !!(body.standard && body.standard.synthetic_demo),
        }
        if (body.banner) {
          patch.scoringBanner = body.banner
          patch.isSyntheticDemo = body.benchmark_kind === 'synthetic_demo'
          patch.isLiteratureCited = body.benchmark_kind === 'literature_cited'
        }
        if (body.stage_timeline && body.stage_timeline.segments && !this.data.stageSegments.length) {
          patch.stageSegments = body.stage_timeline.segments.map((s, i) =>
            humanizeStageSegment(s, i)
          )
          patch.stageNotice = body.stage_timeline.notice || ''
        }
        this.setData(patch)
        this.drawOverlay(this._overlayCtx, this._overlayCssW || 360, this._overlayCssH || 480, body)
      })
      .catch((e) => {
        if (seq !== this._overlaySeq) return
        this.setData({
          overlayLoading: false,
          overlayError: (e && (e.message || e.detail)) || '叠加加载失败',
        })
      })
  },
  drawOverlay(ctx, w, h, body) {
    if (!ctx) return
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = '#181820'
    ctx.fillRect(0, 0, w, h)

    const drawSide = (side, fallbackColor) => {
      if (!side) return
      const landmarks = side.landmarks || []
      const bones = side.bones || []
      const color = side.color || fallbackColor
      const pts = landmarks.map((lm) => {
        if (!lm || lm.x == null || lm.y == null) return null
        if (lm.visibility != null && lm.visibility < 0.1) return null
        return { x: lm.x * w, y: lm.y * h }
      })
      ctx.strokeStyle = color
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
      ctx.fillStyle = color
      pts.forEach((p) => {
        if (!p) return
        ctx.beginPath()
        ctx.arc(p.x, p.y, 3, 0, Math.PI * 2)
        ctx.fill()
      })
    }

    // green standard under, blue user on top
    drawSide(body.standard, '#50c878')
    drawSide(body.user, '#4da3ff')

    ctx.fillStyle = '#b4b4c8'
    ctx.font = '12px sans-serif'
    ctx.fillText(body.label || body.notice || '非评分叠加', 8, 18)
    ctx.fillStyle = '#50c878'
    ctx.fillText('标准', 8, 36)
    ctx.fillStyle = '#4da3ff'
    ctx.fillText('用户', 48, 36)
  },
  drawSkeleton(ctx, w, h, body, label) {
    if (!ctx) return
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = '#181820'
    ctx.fillRect(0, 0, w, h)

    const landmarks = (body && body.landmarks) || []
    const bones = (body && body.bones) || []
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
    ctx.fillText(label || '仅关键点可视化，非评分', 8, 18)
  },
  setPlayerRate(e) {
    const rate = Number(e.currentTarget.dataset.rate)
    this.setData({ playbackRate: rate })
    try {
      const ctx = wx.createVideoContext('detailPlayer', this)
      if (ctx.playbackRate) ctx.playbackRate(rate)
    } catch (err) {}
  },
  seekPlayer(e) {
    const delta = Number(e.currentTarget.dataset.delta) || 0
    const t = Math.max(0, (this.data.playerTime || 0) + delta)
    try {
      wx.createVideoContext('detailPlayer', this).seek(t)
    } catch (err) {}
  },
  onPlayerTime(e) {
    this.setData({ playerTime: e.detail.currentTime || 0 })
  },
  toggleSkeletonMode() {
    const next = !this.data.showSkeleton
    this.setData({ showSkeleton: next })
    if (next && this.data.poseExtracted) {
      wx.nextTick(() => this.initCanvasAndLoad(this.data.previewFrame || 0))
    }
  },
  toggleOverlayMode() {
    const next = !this.data.showOverlayPanel
    this.setData({ showOverlayPanel: next })
    if (next && this.data.overlayAvailable) {
      wx.nextTick(() => this.initOverlayCanvasAndLoad(this.data.overlayFrame || 0))
    }
  },
})
