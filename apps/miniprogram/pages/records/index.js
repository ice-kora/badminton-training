const { request, ensureLogin } = require('../../utils/request')

const STATUS_LABEL = {
  pending: '等待中',
  rejected_precheck: '预检未通过',
  queued: '排队中',
  extracting: '提取中',
  pose_extracted: '已提取',
  pose_failed: '提取失败',
  failed: '提取失败',
  not_implemented: '分析未开放',
}

function formatTime(iso) {
  if (!iso) return ''
  const s = String(iso).replace('T', ' ')
  return s.length > 19 ? s.slice(0, 19) : s
}

function formatDuration(ms) {
  if (ms == null) return '-'
  const sec = Math.round(ms / 1000)
  return `${sec} 秒`
}

Page({
  data: {
    videos: [],
    sessions: [],
    nickname: '',
    loading: true,
    error: '',
  },
  onShow() {
    this.setData({ nickname: wx.getStorageSync('nickname') || '' })
    this.reload()
  },
  reload() {
    this.setData({ loading: true, error: '' })
    ensureLogin()
      .then(() =>
        Promise.all([
          request({ url: '/videos', auth: true }),
          request({ url: '/sessions', auth: true }).catch(() => []),
        ])
      )
      .then(([videos, sessions]) => {
        const mapped = (videos || []).map((v) => {
          const job = v.latest_job || null
          return {
            ...v,
            durationText: formatDuration(v.duration_ms),
            createdText: formatTime(v.created_at),
            jobStatus: job ? job.status : '',
            jobStatusLabel: job
              ? STATUS_LABEL[job.status] || job.status
              : '无任务',
            jobErrorCode: job ? job.error_code || '' : '',
          }
        })
        this.setData({ videos: mapped, sessions: sessions || [], loading: false })
      })
      .catch((e) => {
        this.setData({
          loading: false,
          error: (e && (e.message || e.detail)) || '加载失败',
          videos: [],
        })
      })
  },
  goVideoDetail(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: `/pages/records/detail?id=${id}` })
  },
  goRecommend() { wx.navigateTo({ url: '/pages/recommend/index' }) },
  goTips() { wx.navigateTo({ url: '/pages/tips/index' }) },
  goErrors() { wx.navigateTo({ url: '/pages/errors/index' }) },
})
