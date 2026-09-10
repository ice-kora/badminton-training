const { ensureLogin } = require('./utils/request')
const config = require('./utils/config')

App({
  globalData: {
    user: null,
    /**
     * 订阅消息模板 ID（可覆盖 config.subscribeTemplateId）。
     * 空字符串 = 不调用 requestSubscribeMessage。
     * 注意：touristappid / 未配置正式模板时无法真实推送。
     */
    subscribeTemplateId: (config && config.subscribeTemplateId) || '',
  },
  onLaunch() {
    ensureLogin().catch((err) => {
      console.warn('dev-login failed', err)
    })
  },
})
