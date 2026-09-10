# 冷启动 / 病毒传播修复（O1–O4）

> 诚实原则：样例≠用户分；隐私承诺绑定 `VIDEO_TTL_DAYS`；分享只读 +「我也要测」；摄影师辅助不做自动 3s 高光。

## O1 样例报告

- 首页 CTA：「没在球场？点此体验高远球标准诊断样例」→ `pages/samples/report?code=forehand_clear`
- API：`GET /samples/forehand_clear`（静态 JSON + `/static/samples/`）
- 小程序离线嵌入：`assets/samples/forehand_clear.js`
- 展示：【样例】横幅、大分、主问题、≤3 问题、示意媒体、粘性「我也要测 → 去拍摄」

## O2 隐私气囊

- 拍摄引导 / 录制页持久徽章，文案含原片约 N 天删除（`videoTtlDays` ↔ `VIDEO_TTL_DAYS`，默认 7）
- 不做公开分享；不以人脸识别为目的；仅私有骨架提取

## O3 原生分享深链

- 结果页 / 样例页：`onShareAppMessage` + `onShareTimeline`
- 路径：`pages/filming/result?job_id=...&share=1` 或 `pages/samples/report?code=forehand_clear&share=1`
- `share=1`：只读 + 浮动「我也要测」

## O4 摄影师辅助

- 录制页模式：「自己拍 / 帮别人拍」
- 帮别人拍：3-2-1 倒计时遮罩 + 全身剪影框 +「对准全身，挥拍时按录」
- **不**宣称自动截取 3 秒挥拍

## 明确不做

真实支付、端侧 MediaPipe、自动高光 clip、假分。
