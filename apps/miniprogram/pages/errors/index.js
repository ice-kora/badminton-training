const { request } = require('../../utils/request')
Page({
  data: { errors: [] },
  onShow() {
    request({ url: '/errors' })
      .then((errors) => this.setData({ errors }))
      .catch(() => this.setData({ errors: [] }))
  },
})
