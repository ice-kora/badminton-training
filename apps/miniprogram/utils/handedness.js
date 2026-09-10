/** Dominant-hand preference: localStorage + optional API sync. Default right. */

const STORAGE_KEY = 'handedness'
const { request, ensureLogin } = require('./request')

function normalize(v) {
  return v === 'left' ? 'left' : 'right'
}

function getLocal() {
  try {
    return normalize(wx.getStorageSync(STORAGE_KEY) || 'right')
  } catch (e) {
    return 'right'
  }
}

function setLocal(v) {
  const h = normalize(v)
  try {
    wx.setStorageSync(STORAGE_KEY, h)
  } catch (e) { /* ignore */ }
  return h
}

function syncFromServer() {
  return ensureLogin()
    .then(() => request({ url: '/me/profile', auth: true }))
    .then((p) => {
      if (p && (p.handedness === 'left' || p.handedness === 'right')) {
        return setLocal(p.handedness)
      }
      return getLocal()
    })
    .catch(() => getLocal())
}

function save(handedness) {
  const h = setLocal(handedness)
  return ensureLogin()
    .then(() =>
      request({
        url: '/me/profile',
        method: 'PATCH',
        auth: true,
        data: { handedness: h },
      })
    )
    .then(() => h)
    .catch(() => h)
}

module.exports = {
  getLocal,
  setLocal,
  syncFromServer,
  save,
  normalize,
}
