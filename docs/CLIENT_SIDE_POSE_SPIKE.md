# 端侧姿态 Spike（诚实笔记）

> 目标：评估「手机端抽关键点 → 只上传 JSON」以降低服务端算力与原片存储，**逼近** Zero-Ops。  
> **本轮不实现**完整端上 MediaPipe；不把任何微信能力等同于 MediaPipe PoseLandmarker。

## 结论摘要

| 路径 | 可行性（2026 微信环境） | 说明 |
|------|-------------------------|------|
| 微信 `VKSession` / VisionKit 人体 | 有限 | 偏 AR/人体检测与简易骨架，**≠** MediaPipe Pose Landmarker 33 点拓扑与置信度语义；坐标空间、遮挡、运动模糊表现需单独标定。 |
| WASM MediaPipe / TF.js Pose | 实验级 | 包体与冷启动大；低端安卓易掉帧；小程序 worker / 内存上限易踩坑；审核与第三方模型分发需自担。 |
| 原生插件 / App 容器 | 中长期 | 能力更接近桌面 MediaPipe，但跳出「纯小程序」分发，与当前微信主路径冲突。 |

**禁止对外话术**：不要写「已用 VisionKit = PoseLandmarker」或「已实现端侧专业评分」。

## 与当前服务端契约

今日服务端：

1. 上传原片 → 预检 → `analysis_job` 排队  
2. worker 抽 33 点 → `pose_analyses` + keypoint JSON  
3. 有 published benchmark 才评分  

端侧迁移的**目标契约**（未落地）：

1. 端上产出与现网兼容的关键点 JSON（时间戳、landmark 名、归一化坐标）  
2. `POST` 仅 JSON（+ 可选缩略图），**不传**或短 TTL 原片  
3. 服务端跳过 extract，直接 `pose_extracted` → 评分  

## 迁移步骤（若开下一轮）

1. **Schema 冻结**：导出一份 `pose_analyses.keypoint_path` 样例，写 `docs/pose_json_schema.md`（landmark 数、坐标系、缺帧策略）。  
2. **对拍**：同一短片服务端 MediaPipe vs 端侧候选，算 MPJPE / 关键帧命中率；不过线不下线。  
3. **双模上传**：`POST /videos/pose-json`（需登录）；保留原片上传作 fallback。  
4. **预检下沉**：时长/朝向仍可在端上拦；亮度可提示但服务端可抽检。  
5. **TTL 对齐**：JSON-only 路径下原片可不落盘或 TTL=0；关键点与分数仍长留。  
6. **诚实 UI**：结果页标明「端侧关键点（实验）」；失败自动回退服务端队列。

## 风险

- 拓扑不一致会导致几何评分（肩髋角等）系统性偏差。  
- 低端机耗电与热节流 → 用户中途杀进程 → 任务悬挂。  
- 审核：大型 WASM / 原生插件增加拒审概率。  

## 本轮范围

只保留本笔记 + 商业路线图引用。无 VKSession 接入代码、无 WASM 包、无「已 Zero-Ops」声明。
