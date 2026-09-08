const { request, ensureLogin } = require('../../utils/request')

Page({
  data: { sessions: [], nickname: '' },
  onShow() {
    this.setData({ nickname: wx.getStorageSync('nickname') || '' })
    ensureLogin()
      .then(() => request({ url: '/sessions', auth: true }))
      .then((sessions) => this.setData({ sessions }))
      .catch(() => this.setData({ sessions: [] }))
  },
  goRecommend() { wx.navigateTo({ url: '/pages/recommend/index' }) },
  goTips() { wx.navigateTo({ url: '/pages/tips/index' }) },
  goErrors() { wx.navigateTo({ url: '/pages/errors/index' }) },
})
