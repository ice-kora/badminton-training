const { baseUrl } = require('./config')

function getToken() {
  return wx.getStorageSync('access_token') || ''
}

function request({ url, method = 'GET', data, auth = false }) {
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
        } else if (res.statusCode === 501 && res.data && res.data.code) {
          // Honest ANALYSIS_NOT_IMPLEMENTED etc.
          reject(res.data)
        } else {
          const msg =
            (res.data && (res.data.detail || res.data.message)) ||
            `HTTP ${res.statusCode}`
          reject(typeof msg === 'string' ? { message: msg } : msg)
        }
      },
      fail(err) {
        reject({ message: err.errMsg || '网络错误' })
      },
    })
  })
}

function ensureLogin() {
  if (getToken()) return Promise.resolve(getToken())
  return request({
    url: '/auth/dev-login',
    method: 'POST',
    data: { openid: 'mp-dev-user', nickname: '小程序体验用户' },
  }).then((data) => {
    wx.setStorageSync('access_token', data.access_token)
    wx.setStorageSync('user_id', data.user_id)
    wx.setStorageSync('nickname', data.nickname)
    return data.access_token
  })
}

module.exports = { request, ensureLogin, getToken, baseUrl }
