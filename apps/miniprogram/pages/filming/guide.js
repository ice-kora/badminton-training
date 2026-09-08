const { request } = require('../../utils/request')

Page({
  data: { guides: [], error: '', skillId: '' },
  onLoad(q) {
    const skillId = q.skill_id
    if (!skillId) {
      this.setData({ error: '缺少 skill_id' })
      return
    }
    this.setData({ skillId })
    request({ url: `/filming-guides/${skillId}` })
      .then((guides) => this.setData({ guides, error: '' }))
      .catch((e) => this.setData({ error: e.message || '加载失败' }))
  },
  startRecord() {
    wx.navigateTo({
      url: `/pages/filming/record?skill_id=${this.data.skillId}`,
    })
  },
})
