const { request, ensureLogin } = require('../../utils/request')

const STATUS_LABEL = {
  pending: '等待中',
  rejected_precheck: '预检未通过',
  queued: '排队中',
  extracting: '提取中',
  pose_extracted: '已提取',
  scored: '已评分',
  pose_failed: '提取失败',
  failed: '提取失败',
  not_implemented: '分析未开放',
}

function formatTime(iso) {
  if (!iso) return ''
  const s = String(iso).replace('T', ' ')
  return s.length > 19 ? s.slice(0, 19) : s
}

Page({
  data: {
    history: [],
    historyAsc: [],
    videos: [],
    nickname: '',
    loading: true,
    error: '',
    historyBanner: '',
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
          request({ url: '/me/score-history?limit=20', auth: true }),
          request({ url: '/videos', auth: true }).catch(() => []),
        ])
      )
      .then(([history, videos]) => {
        const mapped = (history || []).map((h) => ({
          ...h,
          createdText: formatTime(h.created_at),
        }))
        const maxScore = Math.max(1, ...mapped.map((h) => Number(h.overall_score) || 0))
        const historyAsc = mapped
          .slice()
          .reverse()
          .map((h) => ({
            ...h,
            barHeight: Math.max(8, Math.round(((Number(h.overall_score) || 0) / maxScore) * 120)),
          }))
        const banner = mapped.find((h) => h.banner)?.banner || ''
        const vmapped = (videos || []).map((v) => {
          const job = v.latest_job || null
          return {
            ...v,
            createdText: formatTime(v.created_at),
            jobStatusLabel: job ? STATUS_LABEL[job.status] || job.status : '无任务',
          }
        })
        this.setData({
          history: mapped,
          historyAsc,
          historyBanner: banner,
          videos: vmapped,
          loading: false,
        })
      })
      .catch((e) => {
        this.setData({
          loading: false,
          error: (e && (e.message || e.detail)) || '加载失败',
          history: [],
        })
      })
  },
  goVideoDetail(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: `/pages/records/detail?id=${id}` })
  },
})
