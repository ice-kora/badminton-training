const { request, ensureLogin } = require('../../utils/request')

Page({
  data: { rec: null },
  onShow() {
    ensureLogin()
      .then(() => request({ url: '/recommendations/what-to-practice-now', auth: true }))
      .then((rec) => this.setData({ rec }))
      .catch(() => this.setData({ rec: null }))
  },
  goPlan() { wx.switchTab({ url: '/pages/plan/index' }) },
  goRecommend() { wx.navigateTo({ url: '/pages/recommend/index' }) },
  goSkills() { wx.switchTab({ url: '/pages/skills/tree' }) },
  goTest() { wx.navigateTo({ url: '/pages/plan/test' }) },
  goTips() { wx.navigateTo({ url: '/pages/tips/index' }) },
  goErrors() { wx.navigateTo({ url: '/pages/errors/index' }) },
})
