# UX Comfort 计划（U0–U6）

## 信息架构（4 Tab）

| Tab 文案 | 页面 | 职责 |
|----------|------|------|
| 今日 | `pages/index/index` | 下一优先改进点 + 拍摄 CTA |
| 学动作 | `pages/skills/tree` | 技能树 / 标准动作 |
| 训练 | `pages/plan/index` | 计划与打卡 |
| 成长 | `pages/records/index` | 评分历史与趋势 |

**禁止实时摄像头纠错。** 评分仅来自已发布 benchmark 的真实 `TrainingScore` / `PoseProblem` / `drills_json`；禁止 mock / 随机分。

## 验收要点

| ID | 验收 |
|----|------|
| U0 | tabBar 文案为 今日/学动作/训练/成长；本文件存在 |
| U1 | `GET /me/next-focus` 有评分→真实 primary_issue≤3 + cta_drill；无评分→新手拍摄 CTA 无假分；首页 hero「今天优先改 1 件事」 |
| U2 | 结果页大分 + 主问题句 + ≤3 问题卡 + 粘性 Drill/再录；score 序列化含 `primary_issue`/`cta_drill` |
| U3 | 引导页参考框 + 3 条关键检查，长清单可折叠；录制页预检失败友好文案 |
| U4 | 结果页轮询任务，步进 uploaded→precheck/queued→extracting→pose_extracted→scored\|failed |
| U5 | 结果/详情播放器：倍速 1/0.5/0.25、seek、骨架/叠加切换（可用时）、链到复测对比 |
| U6 | `GET /me/score-history`；成长页近期真实分数列表 |

## 诚实横幅

`synthetic_demo` / `literature_cited` 必须展示既有 LITERATURE/SYNTHETIC banner，不得伪装为教练标定。


## P0 体验修复（peer review）

| ID | 要点 |
|----|------|
| P0.1 | 取消强制 5 勾选；剪影/参考框 + 软提示；服务端 OpenCV 预检仍为硬门 |
| P0.2 | 用户文案：`literature_cited`→文献科研参考标准；`synthetic_demo`→工程演示基准；`ANALYSIS_NOT_IMPLEMENTED`→「该动作标准标定中，暂时无法评分」 |
| P0.3 | 现场拍摄最长 60s（微信上限，不支持则回退 15）；相册/服务端 5–60s |
| P0.4 | 持拍手 left\|right（本地 + `/me/profile`）；评分几何用优势侧关键点 |
