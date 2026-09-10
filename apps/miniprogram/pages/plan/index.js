const { request, ensureLogin } = require('../../utils/request')

Page({
  data: {
    plan: null,
    showDays: false,
    todayFocus: '',
    todayHint: '',
    skillId: '',
    ctaDrillCode: '',
  },
  onShow() {
    ensureLogin()
      .then(() =>
        Promise.all([
          request({ url: '/plans/current', auth: true }).catch(() => null),
          request({ url: '/me/next-focus', auth: true }).catch(() => null),
        ]),
      )
      .then(([plan, focus]) => {
        let todayFocus = ''
        let todayHint = ''
        let skillId = ''
        let ctaDrillCode = ''
        if (focus && !focus.empty && focus.primary_issue) {
          todayFocus = focus.primary_issue.title
          todayHint = focus.skill && focus.skill.name
            ? `技能：${focus.skill.name}`
            : ''
          skillId = (focus.skill && focus.skill.id) || ''
          ctaDrillCode = (focus.cta_drill && focus.cta_drill.code) || ''
        } else if (plan && plan.days && plan.days.length) {
          const d0 = plan.days[0]
          todayFocus = d0.focus || plan.title
          todayHint = d0.notes || '按计划练一小段即可'
        } else if (focus && focus.message) {
          todayFocus = focus.message
          skillId = (focus.skill && focus.skill.id) || ''
        }
        this.setData({ plan, todayFocus, todayHint, skillId, ctaDrillCode })
      })
      .catch(() => this.setData({ plan: null }))
  },
  toggleDays() {
    this.setData({ showDays: !this.data.showDays })
  },
  goTest() { wx.navigateTo({ url: '/pages/plan/test' }) },
  goFilm() {
    const id = this.data.skillId
    if (id) {
      wx.navigateTo({ url: `/pages/filming/guide?skill_id=${id}` })
      return
    }
    wx.switchTab({ url: '/pages/skills/tree' })
  },
  goDrill() {
    const code = this.data.ctaDrillCode
    if (code) {
      wx.navigateTo({ url: `/pages/drills/detail?code=${code}` })
      return
    }
    wx.showToast({ title: '暂无推荐练习', icon: 'none' })
  },
  checkIn(e) {
    const dayId = e.currentTarget.dataset.day
    const planId = this.data.plan.id
    request({
      url: '/sessions/check-in',
      method: 'POST',
      auth: true,
      data: { plan_id: planId, plan_day_id: dayId, rating: 4 },
    })
      .then(() => wx.showToast({ title: '已记录' }))
      .catch((err) => wx.showToast({ title: err.message || '失败', icon: 'none' }))
  },
})
