const { baseUrl } = require('./config')

function getToken() {
  return wx.getStorageSync('access_token') || ''
}

function clearToken() {
  try {
    wx.removeStorageSync('access_token')
    wx.removeStorageSync('user_id')
    wx.removeStorageSync('nickname')
  } catch (e) {
    /* ignore */
  }
}

/**
 * Dev login uses shared openid `mp-dev-user` (see docs/RUN.md).
 * All local mini-program sessions share that account when ALLOW_DEV_LOGIN=true.
 */
function ensureLogin() {
  if (getToken()) return Promise.resolve(getToken())
  return request({
    url: '/auth/dev-login',
    method: 'POST',
    data: { openid: 'mp-dev-user', nickname: '小程序体验用户' },
    _retried401: true, // avoid recursive 401 loop on login itself
  }).then((data) => {
    wx.setStorageSync('access_token', data.access_token)
    wx.setStorageSync('user_id', data.user_id)
    wx.setStorageSync('nickname', data.nickname)
    return data.access_token
  })
}

function request(opts) {
  const {
    url,
    method = 'GET',
    data,
    auth = false,
    _retried401 = false,
  } = opts
  const header = { 'Content-Type': 'application/json' }
  if (auth) {
    const token = getToken()
    if (token) header.Authorization = `Bearer ${token}`
  }
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${baseUrl}${url}`,
      method,
      data,
      header,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
          return
        }
        if (res.statusCode === 401 && auth && !_retried401) {
          clearToken()
          ensureLogin()
            .then(() =>
              request({
                url,
                method,
                data,
                auth,
                _retried401: true,
              })
            )
            .then(resolve)
            .catch(reject)
          return
        }
        if (res.statusCode === 501 && res.data && res.data.code) {
          // Honest ANALYSIS_NOT_IMPLEMENTED etc.
          reject(res.data)
          return
        }
        const msg =
          (res.data && (res.data.detail || res.data.message)) ||
          `HTTP ${res.statusCode}`
        reject(typeof msg === 'string' ? { message: msg } : msg)
      },
      fail(err) {
        reject({ message: err.errMsg || '网络错误' })
      },
    })
  })
}

/** Mint short-lived video file token (not the 7d session JWT). */
function fetchVideoFileUrl(videoId) {
  return request({ url: `/videos/${videoId}/file-token`, auth: true }).then(
    (data) => {
      const token = data && data.token
      if (!token) {
        return Promise.reject({ message: '无法获取视频播放令牌' })
      }
      return `${baseUrl}/videos/${videoId}/file?token=${encodeURIComponent(token)}`
    }
  )
}

module.exports = {
  request,
  ensureLogin,
  getToken,
  clearToken,
  fetchVideoFileUrl,
  baseUrl,
}
