const { request } = require('../../utils/request')
const { primaryStatusLabel } = require('../../utils/honesty')

Page({
  data: { categories: [], error: '' },
  onShow() {
    request({ url: '/skills/tree' })
      .then((data) => {
        const categories = (data.categories || []).map((cat) => ({
          ...cat,
          skills: (cat.skills || []).map((s) => ({
            ...s,
            statusLabel: primaryStatusLabel(s.verification_status),
          })),
        }))
        this.setData({ categories, error: '' })
      })
      .catch((e) => this.setData({ error: e.message || '加载失败' }))
  },
  goDetail(e) {
    wx.navigateTo({ url: `/pages/skills/detail?id=${e.currentTarget.dataset.id}` })
  },
})
