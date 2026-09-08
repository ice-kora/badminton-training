const { request } = require('../../utils/request')
Page({
  data: { tips: [] },
  onShow() {
    request({ url: '/tips' })
      .then((tips) => this.setData({ tips }))
      .catch(() => this.setData({ tips: [] }))
  },
})
