/**
 * Wait-state micro-tips while analysis is polling (not scores).
 * Prefer API GET /tips/wait; fall back to this static list.
 */
const FALLBACK_TIPS = [
  '击球瞬间尽量全身入画，肩髋转体才便于图像平面测量。',
  '高远球引拍时肘领先于拍头，避免「甩臂」代偿。',
  '杀球落地后尽快回中，复测时对比脚步是否更稳。',
  '竖屏、腰高、后斜约 45°——机位比「贴地仰拍」更利于肩胸识别。',
  '灯光均匀比分辨率更重要：暗球馆易漏关键点。',
  '一次只练一个纠错点，两周后再拍对比，进步更清晰。',
  '持拍手侧同向后斜放置手机，左手用户请镜像机位。',
  '短视频 5–15 秒含一次完整击球即可，不必录整场。',
]

function normalizeTips(raw) {
  if (!Array.isArray(raw) || !raw.length) return FALLBACK_TIPS.slice()
  const out = []
  for (const item of raw) {
    if (typeof item === 'string' && item.trim()) out.push(item.trim())
    else if (item && typeof item.text === 'string' && item.text.trim()) out.push(item.text.trim())
    else if (item && typeof item.body === 'string' && item.body.trim()) out.push(item.body.trim())
  }
  return out.length ? out : FALLBACK_TIPS.slice()
}

module.exports = {
  FALLBACK_TIPS,
  normalizeTips,
}
