const { request, ensureLogin } = require('../../utils/request')
Page({
  data: { rec: null },
  onShow() { this.refresh() },
  refresh() {
    ensureLogin()
      .then(() => request({ url: '/recommendations/what-to-practice-now', auth: true }))
      .then((rec) => this.setData({ rec }))
      .catch((e) => {
        this.setData({
          rec: {
            title: '暂无法获取推荐',
            reason: e.message || '请先登录并生成计划',
            method: 'rule_based_from_plan_and_checkins',
            disclaimer: '基于计划与打卡的规则推荐，不是姿态/AI 动作评分。',
          },
        })
      })
  },
  goPlan() { wx.switchTab({ url: '/pages/plan/index' }) },
})
