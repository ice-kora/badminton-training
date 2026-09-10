/**
 * Privacy airbag copy — tied to VIDEO_TTL_DAYS (server default 7).
 */
const { videoTtlDays } = require('./config')

const TTL = Number(videoTtlDays) || 7

const PRIVACY_BADGE =
  `🔒 隐私承诺：仅私有处理提取骨架，原片约 ${TTL} 天删除；不做公开分享；不以人脸识别为目的。`

function privacyBadge(ttlDays) {
  const d = Number(ttlDays) || TTL
  return `🔒 隐私承诺：仅私有处理提取骨架，原片约 ${d} 天删除；不做公开分享；不以人脸识别为目的。`
}

module.exports = { PRIVACY_BADGE, privacyBadge, VIDEO_TTL_DAYS: TTL }
