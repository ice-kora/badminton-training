# Motion Benchmark 标注与发布（短版）

> 目标：把「标准动作库」做成可版本化的**数据资产流水线**。  
> 硬规则：**禁止编造关节角 / 时序数值并当作已验证标准**。未核验数值须保持 `null`，或显式标记 `draft_unverified` / `expert_pending`（且校验器会拒绝「有数值却仍标 draft」的默认路径）。

## 1. 采集（capture）

1. 按该技能的 **FilmingGuide**（产品 UX，非关节标准）拍摄参考视频：竖屏、时长 **5–60s**、全身/拍面可见。
2. 记录元数据占位：`handedness`（left|right|either）、`camera_view`（如 side_rear_45）。
3. 原始视频与标注包分目录存放；包内只存引用路径，不把大文件塞进 Git。

## 2. 标注（annotate）

| 层 | 内容 | 谁填 | 数值？ |
|----|------|------|--------|
| stages | 阶段名 / 顺序（可与教学内容对齐） | 编辑可草稿 | 无数值 |
| keyframes | 关键帧标签与时间戳占位 | 编辑可草稿 | 时间戳可空 |
| metrics | 指标 id / 名称 / 单位 | 编辑列壳 | **range_* 默认 null** |
| common_error_refs | 错误 id 引用 | 编辑可空 | — |
| linked_drill_codes | 已有 Drill code | 编辑 | — |

**专家稍后必须填写**：各 metric 的合理区间、关键帧判定说明、与错误的映射、`verification_status=verified` 与 `source`（专家署名 / 文献）。

## 3. 存储与版本

- 包文件：`docs/benchmark/templates/{skill_code}.v{N}.json`（或导入后的 DB 行）。
- Schema：`docs/benchmark/schema.json`。
- DB：`motion_benchmarks`（按技能一条壳）+ `benchmark_versions`（每次导入一版）+ `benchmark_stages` / `benchmark_metrics`（从包展开）。
- `status`：`draft` →（核验后）`published`；分析只应消费 **published**。

## 4. 校验 / 导入 / 发布

```bash
# 仓库根目录
python scripts/benchmark_validate.py docs/benchmark/templates/forehand_clear.v0.json
python scripts/benchmark_import.py docs/benchmark/templates/forehand_clear.v0.json
# 默认拒绝 draft_unverified 发布
python scripts/benchmark_publish.py forehand_clear --version 0.1.0
```

- **validate**：对照 schema；若存在非 null 数值区间且 `verification_status=draft_unverified` → **失败**（除非 `--allow-unverified-numbers`）。
- **import**：写入 DB 为 **draft** 版本，不自动 published。
- **publish**：仅 `verified`（或策略允许的状态）可发布；`draft_unverified` 默认拦截（`--force-draft-forbidden` 为默认策略说明；覆盖需显式危险开关）。

## 5. API（只读）

- `GET /benchmarks` — 列表（含是否有已发布版本）
- `GET /benchmarks/{skill_code}` — 当前可见包摘要
- `GET /benchmarks/{skill_code}/versions` — 版本历史

无公开写接口。

## 6. 与分析的关系

分析仍返回 `ANALYSIS_NOT_IMPLEMENTED`，**不返回分数**。若该技能尚无 published 版本，任务 `message` 可附带 `awaiting_published_benchmark` 说明。
