const { request, ensureLogin, getToken, baseUrl } = require('../../utils/request')
const {
  SYNTHETIC_BANNER,
  LITERATURE_BANNER,
  bannerForKind,
  humanizeJobMessage,
  AWAITING_SCORE_MSG,
} = require('../../utils/honesty')
const { FALLBACK_TIPS, normalizeTips } = require('../../utils/waitTips')
const subscribeUtil = require('../../utils/subscribe')

const TERMINAL = { scored: 1, failed: 1, pose_failed: 1, not_implemented: 1, rejected_precheck: 1 }

function stepState(status) {
  const s = status || ''
  const order = ['uploaded', 'queued', 'extracting', 'pose_extracted', 'scored']
  const map = {
    pending: 'queued',
    rejected_precheck: 'queued',
    queued: 'queued',
    extracting: 'extracting',
    pose_extracted: 'pose_extracted',
    scored: 'scored',
    failed: 'failed',
    pose_failed: 'failed',
    not_implemented: 'pose_extracted',
  }
  const cur = map[s] || 'uploaded'
  const idx = order.indexOf(cur === 'failed' ? 'extracting' : cur)
  const cls = {
    uploaded: 'done',
    queued: '',
    extracting: '',
    pose: '',
    final: '',
  }
  if (s === 'failed' || s === 'pose_failed' || s === 'rejected_precheck') {
    cls.uploaded = 'done'
    cls.queued = s === 'rejected_precheck' ? 'fail' : 'done'
    cls.extracting = s === 'rejected_precheck' ? '' : 'fail'
    cls.pose = ''
    cls.final = 'fail'
    return { cls, finalLabel: '失败' }
  }
  const mark = (key, at) => {
    if (idx > at) return 'done'
    if (idx === at) return 'current'
    return ''
  }
  cls.uploaded = 'done'
  cls.queued = mark('queued', 1)
  cls.extracting = mark('extracting', 2)
  cls.pose = mark('pose_extracted', 3)
  if (s === 'scored') cls.final = 'done'
  else if (s === 'not_implemented' || s === 'pose_extracted') cls.final = 'current'
  else cls.final = ''
  let finalLabel = '评分'
  if (s === 'not_implemented') finalLabel = '待标准库'
  else if (s === 'pose_extracted') finalLabel = '待评分'
  else if (s === 'scored') finalLabel = '已评分'
  return { cls, finalLabel }
}

function isWaitingStatus(status, scored) {
  // Show tips while not yet scored (incl. pose_extracted / not_implemented).
  if (scored) return false
  if (status === 'failed' || status === 'pose_failed' || status === 'rejected_precheck') return false
  return true
}

Page({
  data: {
    jobId: '',
    videoId: '',
    skillId: '',
    jobStatus: '',
    jobMessage: '',
    errorCode: '',
    error: '',
    scored: false,
    waiting: true,
    score: null,
    issues: [],
    primarySentence: '',
    drillLabel: '去练推荐练习',
    ctaDrill: null,
    banner: '',
    isSyntheticDemo: false,
    isLiteratureCited: false,
    stepClass: { uploaded: 'done', queued: '', extracting: '', pose: '', final: '' },
    finalStepLabel: '评分',
    videoUrl: '',
    playbackRate: 1,
    currentTime: 0,
    poseExtracted: false,
    overlayAvailable: false,
    showOverlay: false,
    waitTips: FALLBACK_TIPS.slice(),
    waitTipIndex: 0,
    waitTip: FALLBACK_TIPS[0],
    subscribeSoftHint: '',
  },
  _pollTimer: null,
  _tipTimer: null,
  _subscribeRequested: false,
  onLoad(q) {
    this.setData({
      jobId: q.job_id || '',
      videoId: q.video_id || '',
      skillId: q.skill_id || '',
    })
    if (q.video_id) {
      const token = getToken()
      this.setData({
        videoUrl: `${baseUrl}/videos/${q.video_id}/file?token=${encodeURIComponent(token || '')}`,
      })
    }
    this.loadWaitTips()
    this.startTipRotation()
    this.maybeRequestSubscribe()
    if (!q.job_id) return
    ensureLogin()
      .then(() => {
        if (q.video_id) {
          const token = getToken()
          this.setData({
            videoUrl: `${baseUrl}/videos/${q.video_id}/file?token=${encodeURIComponent(token || '')}`,
          })
        }
        this.pollOnce()
        this._pollTimer = setInterval(() => this.pollOnce(), 2000)
      })
      .catch((e) => this.setData({ error: e.message || '加载失败' }))
  },
  onUnload() {
    if (this._pollTimer) clearInterval(this._pollTimer)
    if (this._tipTimer) clearInterval(this._tipTimer)
  },
  loadWaitTips() {
    request({ url: '/tips/wait' })
      .then((raw) => {
        const tips = normalizeTips(raw && (raw.tips || raw))
        this.setData({
          waitTips: tips,
          waitTipIndex: 0,
          waitTip: tips[0] || FALLBACK_TIPS[0],
        })
      })
      .catch(() => {
        /* keep FALLBACK_TIPS */
      })
  },
  startTipRotation() {
    if (this._tipTimer) clearInterval(this._tipTimer)
    this._tipTimer = setInterval(() => {
      if (!this.data.waiting) return
      const tips = this.data.waitTips || FALLBACK_TIPS
      if (!tips.length) return
      const next = (this.data.waitTipIndex + 1) % tips.length
      this.setData({ waitTipIndex: next, waitTip: tips[next] })
    }, 4500)
  },
  maybeRequestSubscribe() {
    if (this._subscribeRequested) return
    this._subscribeRequested = true
    subscribeUtil
      .requestAnalysisSubscribe()
      .then((res) => {
        const hint =
          (res && res.softHint) ||
          (res && res.skipped && res.reason === 'empty_template'
            ? '分析完成后可在成长页查看'
            : '')
        if (hint) this.setData({ subscribeSoftHint: hint })
      })
      .catch(() => {
        this.setData({ subscribeSoftHint: '分析完成后可在成长页查看' })
      })
  },
  pollOnce() {
    const jobId = this.data.jobId
    if (!jobId) return
    request({ url: `/analysis/jobs/${jobId}`, auth: true })
      .then((job) => {
        const score = job.score || null
        const issues = ((score && score.problems) || []).slice(0, 3)
        const primary = (score && score.primary_issue) || issues[0] || null
        const cta = (score && score.cta_drill) || null
        const kind = job.benchmark_kind || (score && score.benchmark_kind) || ''
        const banner =
          bannerForKind(kind, (score && score.banner) || '') ||
          (score && score.banner) ||
          ''
        const steps = stepState(job.status)
        const scored = job.status === 'scored' && !!score
        const waiting = isWaitingStatus(job.status, scored)
        const friendlyMsg = humanizeJobMessage(job.status, job.error_code, job.message)
        const primarySentence = primary
          ? `优先改：${primary.title}`
          : scored
            ? '本次未检出显著问题'
            : job.status === 'not_implemented' || job.error_code === 'ANALYSIS_NOT_IMPLEMENTED'
              ? AWAITING_SCORE_MSG
              : '分析完成后会展示优先改进点'
        const drillLabel = cta && cta.name ? `去练：${cta.name}` : '去练推荐练习'
        this.setData({
          jobStatus: job.status,
          jobMessage: friendlyMsg,
          errorCode: '',
          score,
          scored,
          waiting,
          issues,
          primarySentence,
          ctaDrill: cta,
          drillLabel,
          banner,
          isSyntheticDemo: kind === 'synthetic_demo',
          isLiteratureCited: kind === 'literature_cited',
          stepClass: steps.cls,
          finalStepLabel: steps.finalLabel,
          poseExtracted: job.status === 'pose_extracted' || job.status === 'scored',
          overlayAvailable: job.status === 'pose_extracted' || job.status === 'scored',
        })
        if (!waiting && this._tipTimer) {
          clearInterval(this._tipTimer)
          this._tipTimer = null
        }
        if (TERMINAL[job.status] && this._pollTimer) {
          clearInterval(this._pollTimer)
          this._pollTimer = null
        }
      })
      .catch((e) => this.setData({ error: (e && e.message) || '轮询失败' }))
  },
  setRate(e) {
    const rate = Number(e.currentTarget.dataset.rate)
    this.setData({ playbackRate: rate })
    try {
      const ctx = wx.createVideoContext('resultPlayer', this)
      if (ctx.playbackRate) ctx.playbackRate(rate)
    } catch (err) { /* ignore */ }
  },
  seekBy(e) {
    const delta = Number(e.currentTarget.dataset.delta) || 0
    const t = Math.max(0, (this.data.currentTime || 0) + delta)
    try {
      const ctx = wx.createVideoContext('resultPlayer', this)
      ctx.seek(t)
    } catch (err) { /* ignore */ }
  },
  onTimeUpdate(e) {
    this.setData({ currentTime: e.detail.currentTime || 0 })
  },
  toggleOverlay() {
    const turningOn = !this.data.showOverlay
    this.setData({ showOverlay: turningOn })
    if (turningOn && this.data.videoId) {
      wx.navigateTo({ url: `/pages/records/detail?id=${this.data.videoId}` })
    }
  },
  goDetail() {
    if (!this.data.videoId) return
    wx.navigateTo({ url: `/pages/records/detail?id=${this.data.videoId}` })
  },
  goDrill() {
    const cta = this.data.ctaDrill
    if (cta && cta.code) {
      wx.showToast({ title: `练习 ${cta.name || cta.code}`, icon: 'none' })
    }
    wx.switchTab({ url: '/pages/plan/index' })
  },
  goRetest() {
    const skillId = this.data.skillId
    const videoId = this.data.videoId
    if (!skillId) {
      wx.switchTab({ url: '/pages/skills/tree' })
      return
    }
    let url = `/pages/filming/record?skill_id=${skillId}`
    if (videoId) url += `&baseline_video_id=${videoId}`
    wx.navigateTo({ url })
  },
})
