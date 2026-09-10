const { request } = require('../../utils/request')
const { primaryStatusLabel } = require('../../utils/honesty')
Page({
  data: { errors: [] },
  onShow() {
    request({ url: '/errors' })
      .then((errors) =>
        this.setData({
          errors: (errors || []).map((e) => ({
            ...e,
            statusLabel: primaryStatusLabel(e.verification_status),
          })),
        })
      )
      .catch(() => this.setData({ errors: [] }))
  },
})
