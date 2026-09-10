const { request } = require('../../utils/request')
const { primaryStatusLabel } = require('../../utils/honesty')
Page({
  data: { tips: [] },
  onShow() {
    request({ url: '/tips' })
      .then((tips) =>
        this.setData({
          tips: (tips || []).map((t) => ({
            ...t,
            statusLabel: primaryStatusLabel(t.verification_status),
          })),
        })
      )
      .catch(() => this.setData({ tips: [] }))
  },
})
