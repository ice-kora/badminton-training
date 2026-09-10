const { request, ensureLogin, baseUrl } = require('../../utils/request')

const LOCAL_FALLBACK = {
  clear_stance_hold: '/assets/drills/clear_stance_hold.gif',
  clear_rhythm_breakdown: '/assets/drills/clear_rhythm_breakdown.gif',
  tumble_touch: '/assets/drills/tumble_touch.gif',
}

function resolveDemoUrl(drill) {
  if (!drill) return ''
  const media = drill.demo_media_url || drill.demo_gif_url || ''
  if (media) {
    if (media.indexOf('http') === 0) return media
    return `${baseUrl}${media}`
  }
  const local = LOCAL_FALLBACK[drill.code]
  return local || ''
}

Page({
  data: {
    loading: true,
    error: '',
    drill: null,
    demoUrl: '',
    skillId: '',
  },
  onLoad(q) {
    const code = q.code || q.id
    if (!code) {
      this.setData({ loading: false, error: '缺少练习 code' })
      return
    }
    ensureLogin()
      .then(() => request({ url: `/drills/${code}` }))
      .then((drill) => {
        this.setData({
          loading: false,
          drill,
          demoUrl: resolveDemoUrl(drill),
          skillId: drill.skill_id || '',
        })
        wx.setNavigationBarTitle({ title: drill.name || '练习示范' })
      })
      .catch((e) => {
        this.setData({
          loading: false,
          error: (e && e.message) || '加载失败',
        })
      })
  },
  goFilm() {
    const id = this.data.skillId
    if (id) {
      wx.navigateTo({ url: `/pages/filming/guide?skill_id=${id}` })
      return
    }
    wx.switchTab({ url: '/pages/skills/tree' })
  },
  goPlan() {
    wx.switchTab({ url: '/pages/plan/index' })
  },
})
