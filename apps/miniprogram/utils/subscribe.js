/**
 * wx.requestSubscribeMessage scaffold.
 *
 * touristappid / 体验版无正式模板时无法真实推送。需要正式 AppID +
 * 已审核订阅消息模板。模板 id 为空时跳过 API 调用，仅本地软提示。
 *
 * Persistence: wx.storage key subscribe_opt_in; optional PATCH /me/profile.
 */
const STORAGE_KEY = 'subscribe_opt_in'
const { request, ensureLogin } = require('./request')

function getTemplateId() {
  try {
    const app = getApp()
    const fromGlobal =
      app &&
      app.globalData &&
      (app.globalData.subscribeTemplateId || app.globalData.SUBSCRIBE_TEMPLATE_ID)
    if (fromGlobal && String(fromGlobal).trim()) return String(fromGlobal).trim()
  } catch (e) { /* ignore */ }
  try {
    const cfg = require('./config')
    if (cfg && cfg.subscribeTemplateId && String(cfg.subscribeTemplateId).trim()) {
      return String(cfg.subscribeTemplateId).trim()
    }
  } catch (e2) { /* ignore */ }
  return ''
}

function isOptedInLocal() {
  try {
    return !!wx.getStorageSync(STORAGE_KEY)
  } catch (e) {
    return false
  }
}

function setOptedInLocal(v) {
  try {
    if (v) wx.setStorageSync(STORAGE_KEY, true)
    else wx.removeStorageSync(STORAGE_KEY)
  } catch (e) { /* ignore */ }
}

function syncPreferenceToServer(optedIn) {
  return ensureLogin()
    .then(() =>
      request({
        url: '/me/profile',
        method: 'PATCH',
        auth: true,
        data: { subscribe_opt_in: !!optedIn },
      })
    )
    .catch(() => null)
}

/**
 * After upload / while waiting. Returns { skipped, reason, accepted }.
 * Does NOT claim push delivery works without a real template.
 */
function requestAnalysisSubscribe() {
  const tmplId = getTemplateId()
  if (!tmplId) {
    return Promise.resolve({
      skipped: true,
      reason: 'empty_template',
      accepted: false,
      softHint: '分析完成后可在成长页查看',
    })
  }
  if (typeof wx.requestSubscribeMessage !== 'function') {
    return Promise.resolve({
      skipped: true,
      reason: 'api_unavailable',
      accepted: false,
      softHint: '分析完成后可在成长页查看',
    })
  }
  return new Promise((resolve) => {
    wx.requestSubscribeMessage({
      tmplIds: [tmplId],
      success: (res) => {
        const st = res && res[tmplId]
        const accepted = st === 'accept'
        if (accepted) {
          setOptedInLocal(true)
          syncPreferenceToServer(true)
        }
        resolve({
          skipped: false,
          reason: st || 'unknown',
          accepted,
          softHint: accepted ? '' : '分析完成后可在成长页查看',
        })
      },
      fail: () => {
        resolve({
          skipped: false,
          reason: 'fail',
          accepted: false,
          softHint: '分析完成后可在成长页查看',
        })
      },
    })
  })
}

module.exports = {
  getTemplateId,
  isOptedInLocal,
  setOptedInLocal,
  requestAnalysisSubscribe,
  STORAGE_KEY,
}
