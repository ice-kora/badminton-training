const { request } = require('../../utils/request')

Page({
  data: { skill: null, analyzeMsg: '' },
  onLoad(q) {
    const id = q.id
    request({ url: `/skills/${id}` })
      .then((skill) => {
        this.setData({ skill })
        wx.setNavigationBarTitle({ title: skill.name })
      })
      .catch((e) => wx.showToast({ title: e.message || '加载失败', icon: 'none' }))
  },
  goFilming() {
    wx.navigateTo({ url: `/pages/filming/guide?skill_id=${this.data.skill.id}` })
  },
  tryAnalyze() {
    request({
      url: '/analysis/jobs',
      method: 'POST',
      data: { skill_id: this.data.skill.id },
    })
      .then(() => this.setData({ analyzeMsg: '意外成功' }))
      .catch((e) => {
        const msg = e.code
          ? `${e.code}: ${e.message}`
          : (e.message || '分析未实现')
        this.setData({ analyzeMsg: msg })
      })
  },
})
