/** User-facing honesty labels — no raw developer codes on primary UI. */

const STATUS_LABEL = {
  literature_cited: '文献科研参考标准（非教练现场标定）',
  synthetic_demo: '工程演示基准（非教练标定）',
  draft_unverified: '内容校对中',
  placeholder_shell: '内容校对中',
  expert_pending: '专家审校中',
  verified: '已标定',
}

const SYNTHETIC_BANNER = '工程演示基准（非教练标定）'
const LITERATURE_BANNER = '文献科研参考标准（非教练现场标定）'

const AWAITING_SCORE_MSG = '该动作标准标定中，暂时无法评分'

function statusLabel(raw) {
  if (!raw) return ''
  const key = String(raw)
  if (STATUS_LABEL[key]) return STATUS_LABEL[key]
  if (key === 'draft_unverified' || key === 'placeholder_shell') return '内容校对中'
  return key
}

/** Hide draft/placeholder tags from primary surfaces; return null to hide. */
function primaryStatusLabel(raw) {
  const key = String(raw || '')
  if (!key || key === 'draft_unverified' || key === 'placeholder_shell') return null
  return statusLabel(key)
}

function bannerForKind(kind, fallback) {
  if (kind === 'literature_cited') return LITERATURE_BANNER
  if (kind === 'synthetic_demo') return SYNTHETIC_BANNER
  return fallback || ''
}

function humanizeJobMessage(status, errorCode, message) {
  const code = String(errorCode || '')
  const msg = String(message || '')
  if (
    code === 'ANALYSIS_NOT_IMPLEMENTED' ||
    status === 'not_implemented' ||
    msg.indexOf('awaiting_published_benchmark') !== -1 ||
    msg.indexOf('ANALYSIS_NOT_IMPLEMENTED') !== -1
  ) {
    return AWAITING_SCORE_MSG
  }
  // Strip raw codes from primary message when possible
  if (msg.indexOf('ANALYSIS_NOT_IMPLEMENTED') !== -1) {
    return AWAITING_SCORE_MSG
  }
  return msg
}

module.exports = {
  STATUS_LABEL,
  SYNTHETIC_BANNER,
  LITERATURE_BANNER,
  AWAITING_SCORE_MSG,
  statusLabel,
  primaryStatusLabel,
  bannerForKind,
  humanizeJobMessage,
}
