const { request } = require('../../utils/request')

Page({
  data: { categories: [], error: '' },
  onShow() {
    request({ url: '/skills/tree' })
      .then((data) => this.setData({ categories: data.categories || [], error: '' }))
      .catch((e) => this.setData({ error: e.message || '加载失败' }))
  },
  goDetail(e) {
    wx.navigateTo({ url: `/pages/skills/detail?id=${e.currentTarget.dataset.id}` })
  },
})
