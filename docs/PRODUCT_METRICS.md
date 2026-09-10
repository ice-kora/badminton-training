# Product Metrics（草案）

## North Star

**双周复测率（biweekly retest rate）**：过去 14 天内，对同一 `skill_id` 再次上传并完成分析（有 `baseline_video_id` 或同技能第二次+视频）的用户占比。

- 为什么：诚实评分闭环的核心是「改一点 → 再拍对比」，而非日活刷屏。
- 本期：仅文档定义；看板 / 埋点实现 out of scope（Phase-2 P1）。
- 辅助：单次结果页「再录对比」点击率、成长页回访、订阅消息授权率（授权 ≠ 送达；touristappid 无真实推送）。

## 不做的虚荣指标

- 未评分前的「预估分 / 模拟分」
- 实时摄像头纠错次数
