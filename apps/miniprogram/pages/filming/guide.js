const { request } = require('../../utils/request')
const { primaryStatusLabel } = require('../../utils/honesty')
const handednessUtil = require('../../utils/handedness')
const { PRIVACY_BADGE } = require('../../utils/privacy')

const DEFAULT_KEYS = ['全身入画', '球拍可见', '竖屏且光线充足']

function pickKeyChecks(guide) {
  const list = guide.checklist || []
  if (list.length >= 3) return list.slice(0, 3)
  const keys = []
  if (guide.full_body_required) keys.push('全身入画')
  if (guide.racket_visible) keys.push('球拍可见')
  keys.push(guide.orientation === 'portrait' ? '竖屏拍摄' : '按引导方向拍摄')
  while (keys.length < 3 && list.length) {
    const n = list[keys.length]
    if (n && keys.indexOf(n) === -1) keys.push(n)
    else break
  }
  return (keys.length ? keys : DEFAULT_KEYS).slice(0, 3)
}

Page({
  data: { guides: [], error: '', skillId: '', handedness: 'right', privacyBadge: PRIVACY_BADGE },
  onLoad(q) {
    const skillId = q.skill_id
    if (!skillId) {
      this.setData({ error: '缺少 skill_id' })
      return
    }
    this.setData({ skillId, handedness: handednessUtil.getLocal() })
    handednessUtil.syncFromServer().then((h) => {
      if (h) this.setData({ handedness: h })
    })
    request({ url: `/filming-guides/${skillId}` })
      .then((guides) => {
        const mapped = (guides || []).map((g) => ({
          ...g,
          keyChecks: pickKeyChecks(g),
          checklistOpen: false,
          statusLabel: primaryStatusLabel(g.verification_status),
        }))
        this.setData({ guides: mapped, error: '' })
      })
      .catch((e) => this.setData({ error: e.message || '加载失败' }))
  },
  setHandedness(e) {
    const hand = e.currentTarget.dataset.hand
    handednessUtil.save(hand).then((h) => this.setData({ handedness: h }))
  },
  toggleChecklist(e) {
    const id = e.currentTarget.dataset.id
    const guides = this.data.guides.map((g) =>
      g.id === id ? { ...g, checklistOpen: !g.checklistOpen } : g
    )
    this.setData({ guides })
  },
  startRecord() {
    wx.navigateTo({
      url: `/pages/filming/record?skill_id=${this.data.skillId}`,
    })
  },
})
