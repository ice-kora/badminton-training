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
    demoUrl: '',
    waitTips: FALLBACK_TIPS.slice(),
    waitTipIndex: 0,
    waitTip: FALLBACK_TIPS[0],
    subscribeSoftHint: '',
    skillName: '',
    shareCanvasW: 600,
    shareCanvasH: 900,
    sharingCard: false,
    fromShare: false,
    readOnly: false,
  },
  _pollTimer: null,
  _tipTimer: null,
  _subscribeRequested: false,
  onLoad(q) {
    const fromShare = !!(q && (q.share === '1' || q.share === 1))
    this.setData({
      jobId: q.job_id || '',
      videoId: q.video_id || '',
      skillId: q.skill_id || '',
      fromShare,
      readOnly: fromShare,
    })
    try {
      wx.showShareMenu({
        withShareTicket: true,
        menus: ['shareAppMessage', 'shareTimeline'],
      })
    } catch (e) { /* older base lib */ }
    if (q.skill_id) this.loadSkillName(q.skill_id)
    if (q.video_id) {
      const token = getToken()
      this.setData({
        videoUrl: `${baseUrl}/videos/${q.video_id}/file?token=${encodeURIComponent(token || '')}`,
      })
    }
    this.loadWaitTips()
    this.startTipRotation()
    if (!fromShare) this.maybeRequestSubscribe()
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
          demoUrl: this._resolveDemoUrl(cta),
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
    // Opt-in only: do not force overlay on detail; user opens 并排对比 when ready
  },
  goDetail() {
    if (!this.data.videoId) return
    wx.navigateTo({ url: `/pages/records/detail?id=${this.data.videoId}` })
  },
  goDrill() {
    const cta = this.data.ctaDrill
    if (cta && cta.code) {
      wx.navigateTo({ url: `/pages/drills/detail?code=${cta.code}` })
      return
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
  _resolveDemoUrl(cta) {
    if (!cta) return ''
    return cta.demo_gif_url || cta.demo_media_url || ''
  },
  loadSkillName(skillId) {
    request({ url: `/skills/${skillId}` })
      .then((sk) => {
        if (sk && sk.name) this.setData({ skillName: sk.name })
      })
      .catch(() => {})
  },
  onRemoveWatermarkHook() {
    wx.showToast({
      title: '去水印高清导出 · 即将开放',
      icon: 'none',
      duration: 2500,
    })
  },
  onShareCard() {
    if (!this.data.scored || !this.data.score) {
      wx.showToast({ title: '评分完成后可分享', icon: 'none' })
      return
    }
    if (this.data.sharingCard) return
    this.setData({ sharingCard: true })
    wx.showLoading({ title: '生成中', mask: true })
    this._drawShareCard()
      .then((filePath) => this._exportShareImage(filePath))
      .catch((err) => {
        const msg = (err && err.message) || '生成失败'
        wx.showToast({ title: msg, icon: 'none' })
      })
      .finally(() => {
        wx.hideLoading()
        this.setData({ sharingCard: false })
      })
  },
  _drawShareCard() {
    const W = this.data.shareCanvasW
    const H = this.data.shareCanvasH
    const score = this.data.score || {}
    const overall = score.overall_score != null ? String(score.overall_score) : '—'
    const skill = this.data.skillName || '羽毛球技术'
    const primary =
      this.data.primarySentence ||
      (score.primary_issue && score.primary_issue.title
        ? `优先改：${score.primary_issue.title}`
        : '本次未检出显著问题')
    const watermark = '羽毛球AI教练 · 体验版'
    const ctx = wx.createCanvasContext('shareCard', this)

    // background
    ctx.setFillStyle('#0f172a')
    ctx.fillRect(0, 0, W, H)
    // accent panel
    ctx.setFillStyle('#1e293b')
    roundRect(ctx, 36, 80, W - 72, H - 200, 24)
    ctx.fill()

    // kicker
    ctx.setFillStyle('#94a3b8')
    ctx.setFontSize(22)
    ctx.setTextAlign('left')
    ctx.fillText('训练成绩卡', 64, 130)

    // skill name
    ctx.setFillStyle('#f8fafc')
    ctx.setFontSize(28)
    ctx.fillText(truncate(skill, 16), 64, 175)

    // score badge circle
    const cx = W / 2
    const cy = 340
    ctx.beginPath()
    ctx.arc(cx, cy, 110, 0, Math.PI * 2)
    ctx.setFillStyle('#22c55e')
    ctx.fill()
    ctx.beginPath()
    ctx.arc(cx, cy, 96, 0, Math.PI * 2)
    ctx.setFillStyle('#0f172a')
    ctx.fill()
    ctx.setFillStyle('#4ade80')
    ctx.setTextAlign('center')
    ctx.setFontSize(64)
    ctx.fillText(overall, cx, cy + 22)
    ctx.setFillStyle('#94a3b8')
    ctx.setFontSize(18)
    ctx.fillText('综合分', cx, cy + 52)

    // tiny skeleton stick figure (decorative, not pose data)
    drawTinySkeleton(ctx, W - 120, 300)

    // primary issue
    ctx.setTextAlign('left')
    ctx.setFillStyle('#e2e8f0')
    ctx.setFontSize(22)
    wrapText(ctx, primary, 64, 520, W - 128, 32, 3)

    // watermark
    ctx.setFillStyle('rgba(148,163,184,0.85)')
    ctx.setFontSize(18)
    ctx.setTextAlign('center')
    ctx.fillText(watermark, W / 2, H - 48)

    return new Promise((resolve, reject) => {
      ctx.draw(false, () => {
        setTimeout(() => {
          wx.canvasToTempFilePath(
            {
              canvasId: 'shareCard',
              width: W,
              height: H,
              destWidth: W,
              destHeight: H,
              fileType: 'png',
              success: (res) => resolve(res.tempFilePath),
              fail: (e) => reject(new Error((e && e.errMsg) || 'canvasToTempFilePath failed')),
            },
            this
          )
        }, 80)
      })
    })
  },
  _exportShareImage(filePath) {
    // Prefer Moments share menu when available; else save to album
    return new Promise((resolve, reject) => {
      if (typeof wx.showShareImageMenu === 'function') {
        wx.showShareImageMenu({
          path: filePath,
          success: () => resolve(filePath),
          fail: () => {
            this._saveShareToAlbum(filePath).then(resolve).catch(reject)
          },
        })
      } else {
        this._saveShareToAlbum(filePath).then(resolve).catch(reject)
      }
    })
  },
  _saveShareToAlbum(filePath) {
    return new Promise((resolve, reject) => {
      const save = () => {
        wx.saveImageToPhotosAlbum({
          filePath,
          success: () => {
            wx.showToast({ title: '已保存到相册', icon: 'success' })
            resolve(filePath)
          },
          fail: (e) => reject(new Error((e && e.errMsg) || '保存失败')),
        })
      }
      wx.getSetting({
        success: (st) => {
          if (st.authSetting && st.authSetting['scope.writePhotosAlbum'] === false) {
            wx.showModal({
              title: '需要相册权限',
              content: '请允许保存图片到相册以便分享装逼卡',
              success: (r) => {
                if (r.confirm) wx.openSetting({})
                reject(new Error('无相册权限'))
              },
            })
            return
          }
          save()
        },
        fail: () => save(),
      })
    })
  },
  goTryMyself() {
    const skillId = this.data.skillId
    if (skillId) {
      wx.navigateTo({ url: `/pages/filming/guide?skill_id=${skillId}` })
      return
    }
    wx.switchTab({ url: '/pages/skills/tree' })
  },
  onShareAppMessage() {
    const jobId = this.data.jobId || ''
    const videoId = this.data.videoId || ''
    const skillId = this.data.skillId || ''
    const skill = this.data.skillName || '动作'
    const primary = this.data.primarySentence || ''
    let title = `来看看我的${skill}动作诊断`
    if (primary.indexOf('手臂') !== -1 || primary.indexOf('转体') !== -1) {
      title = '来看看我的杀球动作诊断：发力靠手臂还是转体？'
    } else if (skill.indexOf('杀') !== -1) {
      title = '来看看我的杀球动作诊断：发力靠手臂还是转体？'
    } else if (skill.indexOf('高远') !== -1) {
      title = '来看看我的高远球动作诊断：发力靠手臂还是转体？'
    } else if (primary) {
      title = `来看看我的${skill}诊断：${primary.replace(/^优先改：/, '')}`
    }
    let path = `/pages/filming/result?job_id=${jobId}&share=1`
    if (videoId) path += `&video_id=${videoId}`
    if (skillId) path += `&skill_id=${skillId}`
    return { title, path }
  },
  onShareTimeline() {
    const jobId = this.data.jobId || ''
    const videoId = this.data.videoId || ''
    const skillId = this.data.skillId || ''
    const skill = this.data.skillName || '动作'
    const title =
      skill.indexOf('杀') !== -1
        ? '来看看我的杀球动作诊断：发力靠手臂还是转体？'
        : skill.indexOf('高远') !== -1
          ? '来看看我的高远球动作诊断：发力靠手臂还是转体？'
          : `来看看我的${skill}动作诊断`
    let query = `job_id=${jobId}&share=1`
    if (videoId) query += `&video_id=${videoId}`
    if (skillId) query += `&skill_id=${skillId}`
    return { title, query }
  },

})

function truncate(s, n) {
  const t = String(s || '')
  return t.length > n ? t.slice(0, n - 1) + '…' : t
}

function roundRect(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + rr, y)
  ctx.arcTo(x + w, y, x + w, y + h, rr)
  ctx.arcTo(x + w, y + h, x, y + h, rr)
  ctx.arcTo(x, y + h, x, y, rr)
  ctx.arcTo(x, y, x + w, y, rr)
  ctx.closePath()
}

function wrapText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
  const chars = String(text || '').split('')
  let line = ''
  let lineCount = 0
  for (let i = 0; i < chars.length; i++) {
    const test = line + chars[i]
    const m = ctx.measureText(test)
    if (m.width > maxWidth && line) {
      ctx.fillText(line, x, y + lineCount * lineHeight)
      lineCount += 1
      line = chars[i]
      if (lineCount >= maxLines) return
    } else {
      line = test
    }
  }
  if (line && lineCount < maxLines) ctx.fillText(line, x, y + lineCount * lineHeight)
}

function drawTinySkeleton(ctx, x, y) {
  ctx.setStrokeStyle('#64748b')
  ctx.setLineWidth(3)
  ctx.beginPath()
  ctx.arc(x, y - 40, 10, 0, Math.PI * 2) // head
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(x, y - 28)
  ctx.lineTo(x, y + 10) // torso
  ctx.moveTo(x, y - 10)
  ctx.lineTo(x - 22, y + 5) // L arm
  ctx.moveTo(x, y - 10)
  ctx.lineTo(x + 28, y - 25) // R arm raised (racket side hint)
  ctx.moveTo(x, y + 10)
  ctx.lineTo(x - 16, y + 40)
  ctx.moveTo(x, y + 10)
  ctx.lineTo(x + 16, y + 40)
  ctx.stroke()
}
