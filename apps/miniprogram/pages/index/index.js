const { request, ensureLogin } = require('../../utils/request')

Page({
  data: {
    focus: null,
    banner: '',
    ctaLabel: '去拍摄',
    skillId: '',
    error: '',
  },
  onShow() {
    this.reload()
  },
  reload() {
    ensureLogin()
      .then(() => request({ url: '/me/next-focus', auth: true }))
      .then((focus) => {
        const banner = focus.banner || ''
        const ctaLabel = focus.cta_label || (focus.empty ? '先拍一段' : '去改进')
        this.setData({
          focus,
          banner,
          ctaLabel,
          skillId: (focus.skill && focus.skill.id) || '',
          error: '',
        })
      })
      .catch((e) => {
        this.setData({
          focus: null,
          error: (e && (e.message || e.detail)) || '加载失败',
        })
      })
  },
  goCta() {
    const focus = this.data.focus
    if (focus && focus.cta_path) {
      const path = focus.cta_path
      if (path.indexOf('/pages/plan') === 0 || path.indexOf('/pages/skills/tree') === 0 || path.indexOf('/pages/records') === 0 || path.indexOf('/pages/index') === 0) {
        wx.switchTab({ url: path.split('?')[0] })
      } else {
        wx.navigateTo({ url: path })
      }
      return
    }
    this.goGuide()
  },
  goGuide() {
    const id = this.data.skillId
    if (!id) {
      wx.switchTab({ url: '/pages/skills/tree' })
      return
    }
    wx.navigateTo({ url: `/pages/filming/guide?skill_id=${id}` })
  },
  goSkills() { wx.switchTab({ url: '/pages/skills/tree' }) },
  goPlan() { wx.switchTab({ url: '/pages/plan/index' }) },
  goGrowth() { wx.switchTab({ url: '/pages/records/index' }) },
  goTips() { wx.navigateTo({ url: '/pages/tips/index' }) },
  goSample() {
    wx.navigateTo({ url: '/pages/samples/report?code=forehand_clear' })
  },
})
