const { request, ensureLogin } = require('../../utils/request')

Page({
  data: { plan: null },
  onShow() {
    ensureLogin()
      .then(() => request({ url: '/plans/current', auth: true }))
      .then((plan) => this.setData({ plan }))
      .catch(() => this.setData({ plan: null }))
  },
  goTest() { wx.navigateTo({ url: '/pages/plan/test' }) },
  checkIn(e) {
    const dayId = e.currentTarget.dataset.day
    const planId = this.data.plan.id
    request({
      url: '/sessions/check-in',
      method: 'POST',
      auth: true,
      data: { plan_id: planId, plan_day_id: dayId, rating: 4 },
    })
      .then(() => wx.showToast({ title: '已打卡' }))
      .catch((err) => wx.showToast({ title: err.message || '失败', icon: 'none' }))
  },
})
