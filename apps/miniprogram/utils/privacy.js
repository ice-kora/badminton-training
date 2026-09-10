/**
 * Privacy airbag copy — TTL single-source-of-truth is GET /health
 * (video_ttl_days); local config value is only the offline fallback.
 */
const { request } = require('./request')
const { videoTtlDays } = require('./config')

const TTL = Number(videoTtlDays) || 7

const PRIVACY_BADGE =
  `🔒 隐私承诺：仅私有处理提取骨架，原片约 ${TTL} 天删除；不做公开分享；不以人脸识别为目的。`

function privacyBadge(ttlDays) {
  const d = Number(ttlDays) || TTL
  return `🔒 隐私承诺：仅私有处理提取骨架，原片约 ${d} 天删除；不做公开分享；不以人脸识别为目的。`
}

/**
 * Badge backed by server TTL, so copy always matches the actual purge policy.
 * Falls back to the static default when API is down (dev / cold start).
 */
function fetchPrivacyBadge() {
  return request({ url: '/health' })
    .then((data) => privacyBadge(data && data.video_ttl_days))
    .catch(() => PRIVACY_BADGE)
}

module.exports = {
  PRIVACY_BADGE,
  privacyBadge,
  fetchPrivacyBadge,
  VIDEO_TTL_DAYS: TTL,
}
