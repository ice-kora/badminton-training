const { request, ensureLogin } = require('../../utils/request')

const LEVELS = [
  { value: 'beginner', label: '入门', desc: '刚接触或能简单对拉，技术不系统。' },
  { value: 'intermediate', label: '进阶', desc: '有固定动作，想提高落点与连贯。' },
  { value: 'advanced', label: '提高', desc: '俱乐部对抗较多，追求细节与组合。' },
]

Page({
  data: { levels: LEVELS, level: '', levelLabel: '' },
  select(e) {
    const level = e.currentTarget.dataset.level
    const found = LEVELS.find((x) => x.value === level)
    this.setData({ level, levelLabel: found ? found.label : level })
  },
  submit() {
    const { level } = this.data
    if (!level) return
    ensureLogin()
      .then(() =>
        request({
          url: '/plans/level-test',
          method: 'POST',
          auth: true,
          data: { level },
        })
      )
      .then(() => {
        wx.showToast({ title: '计划已生成' })
        setTimeout(() => wx.switchTab({ url: '/pages/plan/index' }), 500)
      })
      .catch((e) => wx.showToast({ title: e.message || '失败', icon: 'none' }))
  },
})
