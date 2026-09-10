const { request, ensureLogin, getToken, baseUrl } = require('../../utils/request')
const handednessUtil = require('../../utils/handedness')
const subscribeUtil = require('../../utils/subscribe')
const { PRIVACY_BADGE, fetchPrivacyBadge } = require('../../utils/privacy')

/** WeChat chooseMedia camera maxDuration: prefer 60 when supported. */
const LIVE_MAX_SEC = 60

const FRIENDLY_FAIL = {
  duration: '时长不合适：请重拍 5–60 秒的完整击球短视频。',
  resolution: '画面不够清晰：请提高拍摄分辨率（短边建议 ≥ 720）。',
  brightness: '球馆光线偏暗：建议到更亮处重拍；若现场无法改善，可仍要上传（可能影响分析精度）。',
  orientation: '请竖屏拍摄：把手机竖过来再录一段。',
  probe: '视频打不开：请换一个常见格式（如 mp4）再试。',
}

const SOFT_TIPS = [
  '全身入镜（对照剪影）',
  '距离约 3–5 米，不太近/不太远',
  '球拍可见',
  '竖屏拍摄',
  '光线充足、背景干净',
]

function friendlyFailMessage(check) {
  const id = (check && check.id) || ''
  if (FRIENDLY_FAIL[id]) return FRIENDLY_FAIL[id]
  return (check && check.message) || '预检未通过，请按提示重拍'
}

function isBrightnessOnlyFails(fails) {
  return (
    Array.isArray(fails) &&
    fails.length > 0 &&
    fails.every((c) => c && c.id === 'brightness')
  )
}

Page({
  data: {
    skillId: '',
    baselineVideoId: '',
    isRetest: false,
    guide: null,
    softTips: SOFT_TIPS,
    handedness: 'right',
    liveMaxSec: LIVE_MAX_SEC,
    showCamera: false,
    videoPath: '',
    videoInfo: '',
    uploading: false,
    failChecks: [],
    brightnessOnlyFail: false,
    error: '',
    privacyBadge: PRIVACY_BADGE,
    filmMode: 'self',
    countdownActive: false,
    countdownNum: 3,
  },
  _countdownTimer: null,
  onLoad(q) {
    // Badge TTL follows server policy (GET /health); static copy is the fallback.
    fetchPrivacyBadge().then((badge) => this.setData({ privacyBadge: badge }))
    const skillId = q.skill_id
    if (!skillId) {
      this.setData({ error: '缺少 skill_id' })
      return
    }
    const baselineVideoId = q.baseline_video_id || ''
    this.setData({
      skillId,
      baselineVideoId,
      isRetest: !!baselineVideoId,
      handedness: handednessUtil.getLocal(),
    })
    handednessUtil.syncFromServer().then((h) => {
      if (h) this.setData({ handedness: h })
    })
    request({ url: `/filming-guides/${skillId}` })
      .then((guides) => {
        if (guides && guides[0]) this.setData({ guide: guides[0] })
      })
      .catch(() => {})
  },
  setHandedness(e) {
    const hand = e.currentTarget.dataset.hand
    handednessUtil.save(hand).then((h) => this.setData({ handedness: h }))
  },
  toggleCamera() {
    this.setData({ showCamera: !this.data.showCamera })
  },

  setFilmMode(e) {
    const mode = e.currentTarget.dataset.mode
    if (mode !== 'self' && mode !== 'cameraman') return
    this.setData({ filmMode: mode })
  },
  onStartCapture() {
    if (this.data.filmMode === 'cameraman') {
      this.startCameramanCountdown()
      return
    }
    this.chooseMedia()
  },
  startCameramanCountdown() {
    if (this.data.countdownActive) return
    if (this._countdownTimer) {
      clearInterval(this._countdownTimer)
      this._countdownTimer = null
    }
    this.setData({ countdownActive: true, countdownNum: 3 })
    this._countdownTimer = setInterval(() => {
      const n = this.data.countdownNum - 1
      if (n <= 0) {
        clearInterval(this._countdownTimer)
        this._countdownTimer = null
        this.setData({ countdownActive: false, countdownNum: 3 })
        this.chooseMedia()
        return
      }
      this.setData({ countdownNum: n })
    }, 1000)
  },
  chooseMedia() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['video'],
      sourceType: ['album', 'camera'],
      maxDuration: LIVE_MAX_SEC,
      camera: 'back',
      success: (res) => {
        const f = res.tempFiles[0]
        const dur = Number(f.duration || 0)
        const videoInfo = `约 ${dur.toFixed ? dur.toFixed(1) : dur}s · ${f.width || '?'}x${f.height || '?'}`
        if (dur > 60) {
          this.setData({
            videoPath: f.tempFilePath,
            videoInfo,
            failChecks: [],
            brightnessOnlyFail: false,
            error: `视频约 ${dur.toFixed(1)} 秒，超过 60 秒上限，请换 5–60 秒短视频`,
          })
          wx.showToast({ title: '视频过长，请重选', icon: 'none' })
          return
        }
        this.setData({
          videoPath: f.tempFilePath,
          videoInfo,
          failChecks: [],
          brightnessOnlyFail: false,
          error: '',
        })
      },
      fail: (err) => {
        const msg = (err && err.errMsg) || ''
        // Some bases reject maxDuration>15 — retry with 15 and keep copy honest.
        if (LIVE_MAX_SEC > 15 && /maxDuration|duration/i.test(msg)) {
          wx.chooseMedia({
            count: 1,
            mediaType: ['video'],
            sourceType: ['album', 'camera'],
            maxDuration: 15,
            camera: 'back',
            success: (res) => {
              this.setData({ liveMaxSec: 15 })
              const f = res.tempFiles[0]
              const dur = Number(f.duration || 0)
              this.setData({
                videoPath: f.tempFilePath,
                videoInfo: `约 ${dur}s · ${f.width || '?'}x${f.height || '?'}`,
                failChecks: [],
                brightnessOnlyFail: false,
                error: '',
              })
            },
            fail: (e2) => this.setData({ error: e2.errMsg || '选择视频失败' }),
          })
          return
        }
        this.setData({ error: msg || '选择视频失败' })
      },
    })
  },
  retake() {
    this.setData({
      videoPath: '',
      videoInfo: '',
      failChecks: [],
      brightnessOnlyFail: false,
      error: '',
    })
    this.onStartCapture()
  },
  onUnload() {
    if (this._countdownTimer) {
      clearInterval(this._countdownTimer)
      this._countdownTimer = null
    }
  },
  doUploadForce() {
    this.doUpload({ forceBrightness: true })
  },
  doUpload(opts) {
    const forceBrightness = !!(opts && opts.forceBrightness)
    if (!this.data.videoPath) {
      wx.showToast({ title: '请先选择视频', icon: 'none' })
      return
    }
    this.setData({ uploading: true, failChecks: [], brightnessOnlyFail: false, error: '' })
    const tipsAck = {}
    SOFT_TIPS.forEach((_, i) => {
      tipsAck[`tip_${i}`] = true
    })
    ensureLogin()
      .then(() => {
        return new Promise((resolve, reject) => {
          wx.uploadFile({
            url: `${baseUrl}/videos/upload`,
            filePath: this.data.videoPath,
            name: 'file',
            formData: (() => {
              const fd = {
                skill_id: String(this.data.skillId),
                client_checklist_json: JSON.stringify({
                  soft_tips_only: true,
                  silhouette_guide: true,
                  ...tipsAck,
                }),
                frame_coverage_hints_json: JSON.stringify({
                  silhouette_guide: true,
                  note: 'client silhouette + soft tips only; not pose; not mandatory checklist',
                }),
                handedness: this.data.handedness || 'right',
              }
              if (this.data.baselineVideoId) {
                fd.baseline_video_id = String(this.data.baselineVideoId)
              }
              if (forceBrightness) {
                fd.force_upload = 'true'
                fd.precheck_override = 'brightness'
                fd.accept_quality_risk = 'true'
              }
              return fd
            })(),
            header: {
              Authorization: `Bearer ${getToken()}`,
            },
            success: (res) => {
              let body = res.data
              try {
                body = JSON.parse(res.data)
              } catch (e) {
                /* keep raw */
              }
              if (res.statusCode >= 200 && res.statusCode < 300) {
                resolve(body)
              } else {
                reject({ statusCode: res.statusCode, body })
              }
            },
            fail: (err) => reject({ message: err.errMsg || '上传失败' }),
          })
        })
      })
      .then((body) => {
        this.setData({ uploading: false })
        const jobId = body.analysis_job && body.analysis_job.id
        const videoId = body.video && body.video.id
        const goResult = () => {
          wx.redirectTo({
            url: `/pages/filming/result?job_id=${jobId}&video_id=${videoId}&skill_id=${this.data.skillId}`,
          })
        }
        // P2.3: request subscribe while still in upload flow; empty tmpl → soft skip.
        subscribeUtil
          .requestAnalysisSubscribe()
          .catch(() => null)
          .then(goResult)
      })
      .catch((err) => {
        this.setData({ uploading: false })
        const detail = (err.body && err.body.detail) || err.body || err
        if (detail && detail.precheck && detail.precheck.checks) {
          const fails = detail.precheck.checks
            .filter((c) => c.status === 'fail')
            .map((c) => ({ ...c, friendly: friendlyFailMessage(c) }))
          const brightnessOnlyFail = isBrightnessOnlyFails(fails)
          this.setData({
            failChecks: fails,
            brightnessOnlyFail,
            error:
              brightnessOnlyFail
                ? '球馆偏暗：可重拍，或确认风险后仍要上传'
                : detail.message || '预检未通过，请按下方提示重拍',
          })
        } else {
          const msg =
            (detail && (detail.message || detail.detail)) ||
            err.message ||
            '上传失败'
          this.setData({ error: typeof msg === 'string' ? msg : JSON.stringify(msg) })
        }
      })
  },
})
