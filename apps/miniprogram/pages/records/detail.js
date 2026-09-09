const { request, ensureLogin } = require('../../utils/request')

const STATUS_LABEL = {
  pending: '等待中',
  rejected_precheck: '预检未通过',
  queued: '排队中',
  not_implemented: '分析未开放',
  failed: '失败',
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
    checks: [],
    jobs: [],
    precheckPassed: false,
    durationText: '',
    createdText: '',
  },
  onLoad(q) {
    const id = q.id
    if (!id) {
      this.setData({ loading: false, error: '缺少视频 id' })
      return
    }
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
        this.setData({
          loading: false,
          video,
          checks,
          jobs,
          precheckPassed: !!(video.precheck && video.precheck.passed),
          durationText: formatDuration(video.duration_ms),
          createdText: formatTime(video.created_at),
        })
      })
      .catch((e) => {
        this.setData({
          loading: false,
          error: (e && (e.message || e.detail)) || '加载失败',
        })
      })
  },
})
