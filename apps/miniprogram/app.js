const { ensureLogin } = require('./utils/request')

App({
  globalData: {
    user: null,
  },
  onLaunch() {
    ensureLogin().catch((err) => {
      console.warn('dev-login failed', err)
    })
  },
})
