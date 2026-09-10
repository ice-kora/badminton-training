const { request } = require('../../utils/request')
const { primaryStatusLabel, AWAITING_SCORE_MSG } = require('../../utils/honesty')

Page({
  data: {
    skill: null,
    skillStatusLabel: null,
    contentBlocks: [],
    awaitingHint: AWAITING_SCORE_MSG,
  },
  onLoad(q) {
    const id = q.id
    request({ url: `/skills/${id}` })
      .then((skill) => {
        const contentBlocks = (skill.content_blocks || []).map((b) => ({
          ...b,
          statusLabel: primaryStatusLabel(b.verification_status),
        }))
        this.setData({
          skill,
          skillStatusLabel: primaryStatusLabel(skill.verification_status),
          contentBlocks,
        })
        wx.setNavigationBarTitle({ title: skill.name })
      })
      .catch((e) => wx.showToast({ title: e.message || '加载失败', icon: 'none' }))
  },
  goViewer3d() {
    const s = this.data.skill
    wx.navigateTo({
      url: `/pages/viewer3d/index?skill_code=${s.code}&skill_id=${s.id}`,
    })
  },
  goFilming() {
    wx.navigateTo({ url: `/pages/filming/guide?skill_id=${this.data.skill.id}` })
  },
})
