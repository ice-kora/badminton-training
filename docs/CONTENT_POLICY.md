# 内容与分析政策（短版）

## 内容溯源字段

所有教学内容（技能、阶段、内容块、错误、Drill、Tips、拍摄引导、Benchmark 壳）必须带：

| 字段 | 含义 |
|------|------|
| `source` | 来源标识，如 `editorial_draft` / `product_ux_guideline` / `placeholder_shell` |
| `verification_status` | `draft_unverified` \| `expert_pending` \| `verified` |

未经验证内容不得伪装成「官方标准动作数据」。

## 禁止事项

- **禁止**编造关节角、时序窗口等数值标准并当作事实展示
- **禁止** MediaPipe / 姿态评分 / 随机分数 / 伪 AI 分析报告
- **禁止**实时相机纠错 / 实时语音教练（本阶段）
- Motion Benchmark 的 `metric_table_json` / `metrics_json` **保持 null**，直至专家标注

## 允许事项

- 拍摄引导作为**产品 UX 指引**（机位、距离、光线、检查清单）
- 规则引擎生成的 7 日计划与「现在练什么」推荐（须文案标明非姿态 AI）
- 分析接口返回诚实错误：`{"code":"ANALYSIS_NOT_IMPLEMENTED","message":"..."}`

## 用户可见文案原则

中文 UI 中，凡涉及「分析 / 诊断」能力，需说明当前未上线；推荐页注明规则来源。
