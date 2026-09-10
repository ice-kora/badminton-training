const { request, baseUrl } = require('../../utils/request')

/** Offline-friendly embed — same shape as GET /samples/forehand_clear */
const EMBEDDED = require('../../assets/samples/forehand_clear')

function absMedia(url) {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  if (url.indexOf('/') === 0) return `${baseUrl}${url}`
  return url
}

Page({
  data: {
    code: 'forehand_clear',
    fromShare: false,
    sampleBanner: '文献/演示数据，非你的真实视频评分',
    honesty: '',
    banner: '',
    score: null,
    problems: [],
    primaryTitle: '',
    mediaUrl: '',
    mediaCaption: '',
    skillId: '',
    shareTitle: '来看看高远球标准诊断样例：发力靠手臂还是转体？',
    error: '',
  },
  onLoad(q) {
    const code = (q && q.code) || 'forehand_clear'
    const fromShare = !!(q && (q.share === '1' || q.share === 1))
    this.setData({ code, fromShare })
    try {
      wx.showShareMenu({
        withShareTicket: true,
        menus: ['shareAppMessage', 'shareTimeline'],
      })
    } catch (e) { /* older base lib */ }
    this.loadSample(code)
  },
  loadSample(code) {
    const apply = (data) => {
      const score = data.score || null
      const problems = ((score && score.problems) || []).slice(0, 3)
      const primary =
        (score && score.primary_issue) || problems[0] || null
      const media = data.media || {}
      let mediaUrl = absMedia(media.url || '')
      if (!mediaUrl && score && score.cta_drill) {
        mediaUrl = absMedia(
          score.cta_drill.demo_gif_url || score.cta_drill.demo_media_url || ''
        )
      }
      const share = data.share || {}
      this.setData({
        sampleBanner:
          (data.sample_banner || '').replace(/^【样例】/, '') ||
          '文献/演示数据，非你的真实视频评分',
        honesty:
          data.honesty ||
          '本页为冷启动样例报告，使用文献/演示数据，不代表任何用户上传视频。',
        banner: data.banner || '',
        score,
        problems,
        primaryTitle: (primary && primary.title) || '示意主问题',
        mediaUrl,
        mediaCaption: media.caption || '示意动图（非用户原片）',
        shareTitle:
          share.title ||
          '来看看高远球标准诊断样例：发力靠手臂还是转体？',
        error: '',
      })
      // Resolve skill_id for filming CTA when API is up
      request({ url: '/skills/tree' })
        .then((tree) => {
          const skills = []
          ;(tree.categories || []).forEach((c) => {
            ;(c.skills || []).forEach((s) => skills.push(s))
          })
          const hit = skills.find((s) => s.code === code)
          if (hit) this.setData({ skillId: String(hit.id) })
        })
        .catch(() => {})
    }

    request({ url: `/samples/${code}` })
      .then(apply)
      .catch(() => {
        // Offline / API down: embed
        if (code === 'forehand_clear' || !code) {
          apply(EMBEDDED)
        } else {
          this.setData({ error: '样例加载失败', score: null })
        }
      })
  },
  goFilm() {
    const skillId = this.data.skillId
    if (skillId) {
      wx.navigateTo({ url: `/pages/filming/guide?skill_id=${skillId}` })
      return
    }
    wx.switchTab({ url: '/pages/skills/tree' })
  },
  onShareAppMessage() {
    const code = this.data.code || 'forehand_clear'
    return {
      title: this.data.shareTitle,
      path: `/pages/samples/report?code=${code}&share=1`,
    }
  },
  onShareTimeline() {
    const code = this.data.code || 'forehand_clear'
    return {
      title: this.data.shareTitle,
      query: `code=${code}&share=1`,
    }
  },
})
